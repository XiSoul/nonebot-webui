<script setup lang="ts">
import { ProcessService, type ProcessLog } from '@/client/api'
import { getAuthToken } from '@/client/auth'
import {
  getProjectRuntimeLogKey,
  getProjectTerminalLogKey,
  openProjectTerminal
} from '@/client/process'
import { generateURLForWebUI, getErrorMessage } from '@/client/utils'
import { getRuntimeState, isRuntimeActive, type RuntimeState } from '@/utils/runtimeState'
import { useCustomStore, useNoneBotStore, useToastStore } from '@/stores'
import { useWebSocket } from '@vueuse/core'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    mode?: 'runtime' | 'shell'
  }>(),
  {
    mode: 'shell'
  }
)

type DownloadProgressSnapshot = {
  label: string
  percent: number
  totalBytes: number | null
  timestampMs: number
}

type QuickCommand = {
  id: string
  label: string
  command: string
}

type RecentCommand = {
  id: string
  command: string
}

const store = useNoneBotStore()
const customStore = useCustomStore()
const toast = useToastStore()
const runtimeState = computed<RuntimeState>(() => getRuntimeState(store.selectedBot))
const runtimeActive = computed(() => isRuntimeActive(store.selectedBot))

const logData = ref<ProcessLog[]>([])
const logShowTable = ref<HTMLElement>()
const quickCommandModal = ref<HTMLDialogElement>()
const currentBot = ref('')
const commandInput = ref('')
const commandSending = ref(false)
const currentTimeMs = ref(Date.now())
const terminalCacheKey = computed(() =>
  store.selectedBot?.project_id ? `terminalCache:${props.mode}:${store.selectedBot.project_id}` : ''
)
const MISSING_LOG_STORAGE_ERROR = 'Log storage not found.'
const PROCESS_FINISHED_MESSAGE = 'Process finished.'
const PROCESS_NOT_RUNNING_ERROR = 'Process is not running.'
const PROCESS_NOT_FOUND_ERROR = 'Process not found.'
const QUICK_COMMANDS_STORAGE_KEY = 'terminalQuickCommands:v1'
const RECENT_COMMANDS_STORAGE_KEY = 'terminalRecentCommands:v1'
const customQuickCommands = ref<QuickCommand[]>([])
const recentCommands = ref<RecentCommand[]>([])
const newQuickCommandLabel = ref('')
const newQuickCommandCommand = ref('')
let currentTimeTimer: ReturnType<typeof setInterval> | null = null
const currentLogKey = ref('')
const selectedProjectName = computed(() => store.selectedBot?.project_name || '未选择实例')
const selectedProjectDir = computed(() => store.selectedBot?.project_dir || '未连接项目目录')
const selectedProjectDirShort = computed(() => {
  const dir = selectedProjectDir.value
  if (dir.length <= 52) return dir
  return `...${dir.slice(-49)}`
})

const resolveLogKey = async (projectId?: string) => {
  const id = projectId ?? store.selectedBot?.project_id
  if (!id) {
    currentLogKey.value = ''
    return ''
  }

  if (props.mode === 'runtime') {
    const { data, error } = await getProjectRuntimeLogKey(id)
    if (error || !data?.detail) {
      currentLogKey.value = id
      return currentLogKey.value
    }
    currentLogKey.value = data.detail
    return data.detail
  }

  const { data, error } = await getProjectTerminalLogKey(id)
  if (error || !data?.detail) {
    currentLogKey.value = `${id}:shell`
    return currentLogKey.value
  }
  currentLogKey.value = data.detail
  return data.detail
}

const parseSizeToBytes = (size: number, unit: string) => {
  const normalizedUnit = unit.trim().toUpperCase()
  const unitMap: Record<string, number> = {
    B: 1,
    KB: 1000,
    MB: 1000 ** 2,
    GB: 1000 ** 3,
    TB: 1000 ** 4,
    KIB: 1024,
    MIB: 1024 ** 2,
    GIB: 1024 ** 3,
    TIB: 1024 ** 4
  }

  return size * (unitMap[normalizedUnit] ?? 1)
}

const parseLogTimeToMs = (value?: string) => {
  if (!value) return null

  const match = value.match(/^(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?$/)
  if (!match) return null

  const now = new Date()
  now.setHours(
    Number(match[1]),
    Number(match[2]),
    Number(match[3]),
    Number((match[4] ?? '0').padEnd(3, '0'))
  )

  return now.getTime()
}

const formatBytesPerSecond = (bytesPerSecond: number) => {
  if (!Number.isFinite(bytesPerSecond) || bytesPerSecond <= 0) return null

  const units = ['B/s', 'KiB/s', 'MiB/s', 'GiB/s']
  let value = bytesPerSecond
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }

  const digits = value >= 100 ? 0 : value >= 10 ? 1 : 2
  return `${value.toFixed(digits)} ${units[unitIndex]}`
}

const formatAge = (ageMs: number) => {
  const totalSeconds = Math.max(0, Math.floor(ageMs / 1000))
  if (totalSeconds < 60) return `${totalSeconds}s 前`

  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return seconds ? `${minutes}m ${seconds}s 前` : `${minutes}m 前`
}

const extractDownloadSnapshots = (logs: ProcessLog[]) => {
  const snapshots: DownloadProgressSnapshot[] = []
  let currentLabel = '下载任务'

  for (const item of logs) {
    const message = String(item.message ?? '')
    const downloadMatch = message.match(/Downloading\s+(.+?)\s+from\s+/i)
    if (downloadMatch?.[1]) {
      currentLabel = downloadMatch[1].trim()
    }

    const progressMatch = message.match(
      /Progress:\s*\|.*?(\d+(?:\.\d+)?)%\s+of\s+(\d+(?:\.\d+)?)\s*([KMGT]?i?B)/i
    )
    if (!progressMatch) continue

    const timestampMs = parseLogTimeToMs(item.time) ?? currentTimeMs.value
    const percent = Number(progressMatch[1])
    const totalBytes = parseSizeToBytes(Number(progressMatch[2]), progressMatch[3])

    snapshots.push({
      label: currentLabel,
      percent,
      totalBytes: Number.isFinite(totalBytes) ? totalBytes : null,
      timestampMs
    })
  }

  return snapshots
}

const isDownloadStartMessage = (message: string) => /Downloading\s+.+\s+from\s+/i.test(message)
const isDownloadProgressMessage = (message: string) => /Progress:\s*\|.*?\d+(?:\.\d+)?%\s+of\s+\d+(?:\.\d+)?\s*[KMGT]?i?B/i.test(message)
const isDownloadRetryMessage = (message: string) => /retrying with official mirror/i.test(message)
const isDownloadFailureMessage = (message: string) => /Failed to install browsers|Download failed|Download failure/i.test(message)
const isDependencyInstallMessage = (message: string) => /Installing dependencies\.\.\./i.test(message)
const isLocalCommandEcho = (message?: string) => String(message ?? '').trimStart().startsWith('>')

const getDownloadRowKind = (message?: string) => {
  if (isLocalCommandEcho(message)) return ''

  const text = String(message ?? '')
  if (isDownloadProgressMessage(text)) return 'progress'
  if (isDownloadStartMessage(text)) return 'start'
  if (isDownloadRetryMessage(text)) return 'retry'
  if (isDependencyInstallMessage(text)) return 'deps'
  if (isDownloadFailureMessage(text)) return 'failure'
  return ''
}

const scrollToBottom = async () => {
  await nextTick()
  if (logShowTable.value) {
    logShowTable.value.scrollTop = logShowTable.value.scrollHeight
  }
}

const appendLocalLog = async (message: string) => {
  logData.value.push({ message })
  await scrollToBottom()
}

const restoreCachedLogs = () => {
  const cacheKey = terminalCacheKey.value
  if (!cacheKey) return
  try {
    const raw = sessionStorage.getItem(cacheKey)
    if (!raw) return
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return
    logData.value = parsed.slice(-400)
  } catch {
    // ignore cache errors
  }
}

const persistCachedLogs = () => {
  const cacheKey = terminalCacheKey.value
  if (!cacheKey) return
  try {
    sessionStorage.setItem(cacheKey, JSON.stringify(logData.value.slice(-400)))
  } catch {
    // ignore cache errors
  }
}

const fillCommand = (value: string) => {
  commandInput.value = value
}

const saveCustomQuickCommands = () => {
  try {
    localStorage.setItem(QUICK_COMMANDS_STORAGE_KEY, JSON.stringify(customQuickCommands.value))
  } catch {
    // ignore cache errors
  }
}

const loadCustomQuickCommands = () => {
  try {
    const raw = localStorage.getItem(QUICK_COMMANDS_STORAGE_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return
    customQuickCommands.value = parsed
      .map((item) => ({
        id: String(item?.id ?? `${Date.now()}-${Math.random()}`),
        label: String(item?.label ?? '').trim(),
        command: String(item?.command ?? '').trim()
      }))
      .filter((item) => item.label && item.command)
      .slice(0, 12)
  } catch {
    // ignore cache errors
  }
}

const saveRecentCommands = () => {
  try {
    localStorage.setItem(RECENT_COMMANDS_STORAGE_KEY, JSON.stringify(recentCommands.value))
  } catch {
    // ignore cache errors
  }
}

const loadRecentCommands = () => {
  try {
    const raw = localStorage.getItem(RECENT_COMMANDS_STORAGE_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return
    recentCommands.value = parsed
      .map((item) => ({
        id: String(item?.id ?? `${Date.now()}-${Math.random()}`),
        command: String(item?.command ?? '').trim()
      }))
      .filter((item) => item.command)
      .slice(0, 8)
  } catch {
    // ignore cache errors
  }
}

const pushRecentCommand = (command: string) => {
  const normalized = command.trim()
  if (!normalized) return
  recentCommands.value = [
    { id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, command: normalized },
    ...recentCommands.value.filter((item) => item.command !== normalized)
  ].slice(0, 8)
  saveRecentCommands()
}

const closeQuickCommandModal = () => {
  quickCommandModal.value?.close()
  newQuickCommandLabel.value = ''
  newQuickCommandCommand.value = ''
}

const openQuickCommandModal = () => {
  newQuickCommandLabel.value = ''
  newQuickCommandCommand.value = ''
  quickCommandModal.value?.showModal()
}

const addQuickCommand = () => {
  const label = newQuickCommandLabel.value.trim()
  const command = newQuickCommandCommand.value.trim()
  if (!label || !command) {
    toast.add('warning', '请填写快捷命令名称和命令内容', '', 3000)
    return
  }

  customQuickCommands.value.push({
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    label: label.slice(0, 20),
    command
  })
  saveCustomQuickCommands()
  closeQuickCommandModal()
  toast.add('success', '快捷命令已保存到本地', '', 3000)
}

const removeQuickCommand = (id: string) => {
  customQuickCommands.value = customQuickCommands.value.filter((item) => item.id !== id)
  saveCustomQuickCommands()
}

const subscribeLog = (projectId?: string) => {
  const logKey = projectId ?? currentLogKey.value
  if (!logKey) return
  send(JSON.stringify({ type: 'log', log_key: logKey }))
  currentBot.value = logKey
}

const getHistoryLogs = async (projectId?: string) => {
  const logId = projectId ?? currentLogKey.value
  if (!logId) return

  const getLogCount = 200
  const { data, error } = await ProcessService.getLogHistoryV1ProcessLogHistoryGet({
    query: {
      log_count: getLogCount,
      log_id: logId
    }
  })

  if (error) {
    const errorDetail =
      typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail ?? '')

    if (errorDetail === MISSING_LOG_STORAGE_ERROR) {
      if (currentLogKey.value === logId) {
        logData.value = []
      }
      return
    }
    toast.add("warning", `Get history logs failed: ${errorDetail}`, "", 5000)
    return
  }

  if (data) {
    if (currentLogKey.value !== logId) return
    logData.value = data.detail
    await scrollToBottom()
  }
}

const syncSelectedBotStatus = async () => {
  if (!store.selectedBot?.project_id) return
  await store.loadBots()
}

const ensureStoppedProjectTerminal = async (projectId?: string) => {
  if (props.mode !== 'shell') return true
  const id = projectId ?? store.selectedBot?.project_id
  if (!id) return false

  const { error } = await openProjectTerminal(id)
  if (error) {
    toast.add('error', `连接项目终端失败: ${getErrorMessage(error)}`, '', 5000)
    return false
  }
  return true
}

const isProcessUnavailableError = (error: unknown) => {
  const message = getErrorMessage(error, '')
  return message.includes(PROCESS_NOT_RUNNING_ERROR) || message.includes(PROCESS_NOT_FOUND_ERROR)
}

const writeToProcess = async (content: string, displayEcho?: string) => {
  if (props.mode !== 'shell') return false
  if (!store.selectedBot) return
  if (!runtimeActive.value) {
    const ready = await ensureStoppedProjectTerminal(store.selectedBot.project_id)
    if (!ready) return false
  }

  if (displayEcho) await appendLocalLog(displayEcho)

  commandSending.value = true
  const { error } = await ProcessService.writeToProcessV1ProcessWritePost({
    query: {
      project_id: store.selectedBot.project_id,
      content
    }
  })
  commandSending.value = false

  if (error) {
    if (isProcessUnavailableError(error)) {
      await syncSelectedBotStatus()
      if (!isRuntimeActive(store.selectedBot)) {
        const ready = await ensureStoppedProjectTerminal(store.selectedBot.project_id)
        if (!ready) return false

        commandSending.value = true
        const retry = await ProcessService.writeToProcessV1ProcessWritePost({
          query: {
            project_id: store.selectedBot.project_id,
            content
          }
        })
        commandSending.value = false

        if (retry.error) {
          await appendLocalLog(`命令发送失败：${getErrorMessage(retry.error)}`)
          toast.add('error', `Send command failed: ${getErrorMessage(retry.error)}`, '', 5000)
          return false
        }
        return true
      }
      return false
    }
    await appendLocalLog(`命令发送失败：${getErrorMessage(error)}`)
    toast.add('error', `Send command failed: ${getErrorMessage(error)}`, '', 5000)
    return false
  }

  return true
}

const sendCommand = async () => {
  if (props.mode !== 'shell') return
  const command = commandInput.value.trim()
  if (!command) return

  if (runtimeActive.value && status.value !== 'OPEN') {
    await syncSelectedBotStatus()
    if (isRuntimeActive(store.selectedBot)) {
      toast.add('warning', '实例运行中，但终端连接已断开，请先重连。', '', 3000)
      return
    }
  }

  const sent = await writeToProcess(`${command}\n`, `> ${command}`)
  if (sent) {
    pushRecentCommand(command)
    commandInput.value = ''
  }
}

const sendInterrupt = async () => {
  if (props.mode !== 'shell') return
  if (!store.selectedBot) return

  commandSending.value = true
  const { error } = await ProcessService.interruptProcessV1ProcessInterruptPost({
    query: {
      project_id: store.selectedBot.project_id
    }
  })
  commandSending.value = false

  if (error) {
    toast.add('error', `Send interrupt failed: ${getErrorMessage(error)}`, '', 5000)
    return
  }

  await appendLocalLog('^C')
}

const { status, data, close, open, send } = useWebSocket<ProcessLog>(
  generateURLForWebUI("/v1/process/log/ws", true),
  {
    immediate: false,
    autoReconnect: {
      retries: 5,
      delay: 1000
    },
    onConnected(ws) {
      const token = getAuthToken()
      ws.send(token)
      subscribeLog()
      void getHistoryLogs()

      if (customStore.isDebug) {
        toast.add('success', 'Debug: terminal websocket connected.', 'TerminalItem.vue', 5000)
      }
    },
    onDisconnected() {
      void syncSelectedBotStatus()
      if (!customStore.isDebug) return
      toast.add('warning', 'Debug: terminal websocket disconnected.', 'TerminalItem.vue', 5000)
    }
  }
)

const canWriteCommand = computed(
  () =>
    props.mode === 'shell' &&
    Boolean(store.selectedBot) &&
    (!runtimeActive.value || status.value === 'OPEN') &&
    !commandSending.value
)
const canInterrupt = computed(
  () =>
    props.mode === 'shell' &&
    Boolean(store.selectedBot) &&
    (!runtimeActive.value || status.value === 'OPEN') &&
    !commandSending.value
)
const terminalStatusTone = computed(() => {
  if (!store.selectedBot) return 'badge-ghost'
  if (status.value === 'OPEN') return 'badge-success text-base-100'
  return runtimeActive.value ? 'badge-warning' : 'badge-error text-base-100'
})
const terminalStatusText = computed(() => {
  if (!store.selectedBot) return '未选择实例'
  if (status.value === 'OPEN') return '已连接'
  return runtimeActive.value ? '等待重连' : '未连接'
})
const terminalModeLabel = computed(() => {
  if (!store.selectedBot) return '未选择实例'
  if (props.mode === 'runtime') return '实例运行日志'
  if (runtimeActive.value) {
    return status.value === 'OPEN' ? '并行 Shell' : '等待重连'
  }
  return 'Shell 会话'
})
const terminalSessionLabel = computed(() => {
  if (!store.selectedBot) return 'Detached'
  if (props.mode === 'runtime') return 'Runtime Stream'
  return runtimeActive.value ? 'Parallel Shell' : 'Maintenance Shell'
})
const terminalSummary = computed(() => {
  if (!store.selectedBot) return '请先选择一个实例，再附着日志流或维护 Shell。'
  if (props.mode === 'runtime') {
    return '这里专注观察实例输出、启动过程和异常日志，不直接发送维护命令。'
  }
  if (runtimeActive.value) {
    return '实例运行中，当前 Shell 会并行附着，适合执行依赖修复、代理排查和浏览器安装。'
  }
  return '实例停止时会维持一个常驻维护 Shell，适合手动执行 pip、playwright install、nb run 等命令。'
})
const terminalMetrics = computed(() => [
  { label: '实例', value: selectedProjectName.value },
  { label: '模式', value: terminalSessionLabel.value },
  { label: '日志', value: `${logData.value.length} 行` }
])
const commandDeck = computed<QuickCommand[]>(() => [
  { id: 'builtin-pip', label: '安装依赖', command: 'python -m pip install -U ' },
  { id: 'builtin-playwright', label: '装 Chromium', command: 'python -m playwright install chromium' },
  { id: 'builtin-nb-run', label: 'nb run', command: 'nb run' },
  ...customQuickCommands.value
])
const commandPlaceholder = computed(() => {
  if (props.mode !== 'shell') return '当前页面仅展示实例运行日志'
  if (!store.selectedBot) return '请先选择实例'
  if (runtimeActive.value) {
    if (status.value === 'OPEN') return '输入命令，例如 pip install、playwright install、nb run'
    return '实例运行中，但 Shell 连接已断开，请先重连或等待状态同步'
  }
  return '输入命令，例如 pip install、playwright install、nb run'
})

const downloadProgressState = computed(() => {
  const snapshots = extractDownloadSnapshots(logData.value)
  const latest = snapshots.length ? snapshots[snapshots.length - 1] : null
  if (!latest) return null

  const ageMs = currentTimeMs.value - latest.timestampMs
  if (ageMs > 5 * 60 * 1000 || latest.percent >= 100) return null

  const previous = [...snapshots]
    .reverse()
    .find(
      (snapshot) =>
        snapshot !== latest &&
        snapshot.label === latest.label &&
        snapshot.totalBytes === latest.totalBytes &&
        snapshot.percent < latest.percent
    )

  let speedText: string | null = null
  if (previous && latest.totalBytes) {
    const timeDiffSeconds = (latest.timestampMs - previous.timestampMs) / 1000
    const byteDiff = latest.totalBytes * ((latest.percent - previous.percent) / 100)
    if (timeDiffSeconds > 0 && byteDiff > 0) {
      speedText = formatBytesPerSecond(byteDiff / timeDiffSeconds)
    }
  }

  return {
    label: latest.label,
    percentValue: latest.percent,
    percentText: `${latest.percent.toFixed(latest.percent >= 100 ? 0 : 1).replace(/\.0$/, '')}%`,
    speedText,
    ageText: formatAge(ageMs),
    stalled: ageMs > 15000
  }
})

onMounted(async () => {
  loadCustomQuickCommands()
  loadRecentCommands()
  restoreCachedLogs()
  currentTimeTimer = setInterval(() => {
    currentTimeMs.value = Date.now()
  }, 1000)

  if (!store.selectedBot) return
  const logKey = await resolveLogKey(store.selectedBot.project_id)
  await getHistoryLogs(logKey)
  if (props.mode === 'shell' && !runtimeActive.value) {
    await ensureStoppedProjectTerminal(store.selectedBot.project_id)
  }
  open()
})

onUnmounted(() => {
  if (currentTimeTimer) {
    clearInterval(currentTimeTimer)
    currentTimeTimer = null
  }
  close()
})

watch(
  () => data.value,
  async (rawData) => {
    if (!rawData) return

    const parsedData: ProcessLog = JSON.parse(rawData.toString())
    logData.value.push(parsedData)
    if (parsedData.message === PROCESS_FINISHED_MESSAGE) {
      await syncSelectedBotStatus()
    }
    persistCachedLogs()
    await scrollToBottom()
  }
)

watch(
  () => status.value,
  async (newStatus) => {
    if (newStatus !== 'OPEN') return
    subscribeLog()
    await getHistoryLogs()
  }
)

watch(
  () => store.selectedBot?.project_id,
  async (projectId) => {
    if (!projectId) {
      currentLogKey.value = ''
      currentBot.value = ''
      logData.value = []
      close()
      return
    }

    const nextLogKey = await resolveLogKey(projectId)
    if (nextLogKey !== currentBot.value) {
      currentBot.value = nextLogKey
      restoreCachedLogs()
      await getHistoryLogs(nextLogKey)
      if (props.mode === 'shell' && !isRuntimeActive(store.selectedBot)) {
        await ensureStoppedProjectTerminal(projectId)
      }
    }

    if (status.value !== 'OPEN') {
      open()
    } else {
      subscribeLog(nextLogKey)
      await getHistoryLogs(nextLogKey)
    }
  }
)

watch(
  () => runtimeState.value,
  async (state) => {
    const projectId = store.selectedBot?.project_id
    if (!projectId) return
    const logKey = await resolveLogKey(projectId)

    if (props.mode === 'runtime') {
      if (status.value === 'OPEN') {
        subscribeLog(logKey)
        await getHistoryLogs(logKey)
      }
      return
    }

    if (state === 'running' || state === 'starting') {
      await getHistoryLogs(logKey)
      if (status.value !== 'OPEN') {
        open()
      } else {
        subscribeLog(logKey)
      }
      return
    }

    await ensureStoppedProjectTerminal(projectId)
    if (status.value === 'OPEN') {
      subscribeLog(logKey)
      await getHistoryLogs(logKey)
    }
  }
)

watch(
  () => logData.value,
  () => {
    persistCachedLogs()
  },
  { deep: true }
)

const retry = () => {
  if (store.selectedBot?.project_id !== currentBot.value) {
    logData.value = []
  }
  logData.value.push({
    message: 'Retrying websocket connection...'
  })
  open()
}
</script>

<template>
  <section class="w-full self-start rounded-[28px] border border-base-content/10 bg-base-200 p-5 shadow-sm lg:p-6">
    <dialog ref="quickCommandModal" class="modal">
      <div class="modal-box rounded-[24px] border border-base-content/10 bg-base-100 shadow-2xl flex flex-col gap-4">
        <div class="flex flex-col gap-2">
          <h3 class="font-semibold text-lg">新增快捷命令</h3>
          <p class="text-sm opacity-70">
            快捷命令会保存到当前浏览器本地，下次打开终端页仍然可用。
          </p>
        </div>

        <label class="form-control">
          <div class="label py-1">
            <span class="label-text">命令名称</span>
          </div>
          <input
            v-model="newQuickCommandLabel"
            class="input input-bordered"
            placeholder="例如：安装依赖"
          />
        </label>

        <label class="form-control">
          <div class="label py-1">
            <span class="label-text">命令内容</span>
          </div>
          <textarea
            v-model="newQuickCommandCommand"
            class="textarea textarea-bordered min-h-28 font-mono text-sm"
            placeholder="请输入要发送到终端的命令"
          ></textarea>
        </label>

        <div class="flex justify-end gap-2">
          <button class="btn btn-sm btn-ghost" type="button" @click="closeQuickCommandModal()">
            取消
          </button>
          <button class="btn btn-sm btn-primary text-base-100" type="button" @click="addQuickCommand()">
            保存
          </button>
        </div>
      </div>
      <form method="dialog" class="modal-backdrop" @submit.prevent="closeQuickCommandModal()">
        <button>close</button>
      </form>
    </dialog>

    <div class="flex flex-col gap-5">
      <div class="rounded-[26px] border border-base-content/10 bg-base-100/70 p-4 shadow-sm backdrop-blur">
        <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div class="flex min-w-0 flex-1 flex-col gap-3">
            <div class="flex flex-wrap items-center gap-3">
              <span class="text-lg font-semibold">Terminal Workspace</span>
              <div class="badge badge-sm badge-ghost font-normal">
                {{ terminalModeLabel }}
              </div>
              <div class="badge badge-sm font-normal" :class="terminalStatusTone">
                {{ terminalStatusText }}
              </div>
              <div
                v-if="downloadProgressState"
                :class="[
                  'badge badge-sm font-normal',
                  downloadProgressState.stalled ? 'badge-warning' : 'badge-info text-base-100'
                ]"
              >
                {{ downloadProgressState.label }} · {{ downloadProgressState.percentText }}
                <template v-if="downloadProgressState.speedText">
                  · {{ downloadProgressState.speedText }}
                </template>
                · {{ downloadProgressState.ageText }}
              </div>
            </div>

            <div class="rounded-2xl border border-base-content/8 bg-base-200/70 px-4 py-3">
              <div class="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-base-content/45">
                <span>Session</span>
                <span class="rounded-full bg-base-content/10 px-2 py-1 font-medium tracking-[0.16em] text-base-content/70">
                  {{ terminalSessionLabel }}
                </span>
              </div>
              <div class="mt-3 flex flex-col gap-2">
                <div class="text-sm font-medium text-base-content/85">
                  {{ selectedProjectName }}
                </div>
                <div class="font-mono text-xs text-base-content/55">
                  {{ selectedProjectDirShort }}
                </div>
                <p class="text-sm leading-6 text-base-content/68">
                  {{ terminalSummary }}
                </p>
              </div>
            </div>

            <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div
                v-for="metric in terminalMetrics"
                :key="metric.label"
                class="rounded-2xl border border-base-content/8 bg-base-100 px-4 py-3"
              >
                <div class="text-[11px] uppercase tracking-[0.18em] text-base-content/45">
                  {{ metric.label }}
                </div>
                <div class="mt-2 text-sm font-medium text-base-content/82">
                  {{ metric.value }}
                </div>
              </div>
            </div>
          </div>

          <div class="flex items-center justify-end gap-2">
            <button
              :class="{ 'btn btn-sm btn-ghost': true, hidden: status === 'OPEN' }"
              @click="retry()"
            >
              Retry
            </button>
          </div>
        </div>
      </div>

      <div
        v-if="downloadProgressState"
        :class="[
          'rounded-2xl border px-4 py-3 transition-colors',
          downloadProgressState.stalled
            ? 'border-warning/50 bg-warning/10'
            : 'border-info/40 bg-info/10'
        ]"
      >
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="flex min-w-0 flex-col gap-1">
            <div class="flex items-center gap-2">
              <span class="text-sm font-semibold">
                {{ downloadProgressState.stalled ? '下载可能卡住' : '正在下载' }}
              </span>
              <span
                :class="[
                  'badge badge-sm font-normal',
                  downloadProgressState.stalled ? 'badge-warning' : 'badge-info text-base-100'
                ]"
              >
                {{ downloadProgressState.percentText }}
              </span>
            </div>
            <p class="truncate text-sm text-base-content/75">
              {{ downloadProgressState.label }}
            </p>
          </div>

          <div class="flex items-center gap-2 text-sm">
            <span v-if="downloadProgressState.speedText" class="badge badge-ghost badge-sm">
              {{ downloadProgressState.speedText }}
            </span>
            <span class="badge badge-ghost badge-sm">
              {{ downloadProgressState.ageText }}
            </span>
          </div>
        </div>

        <progress
          class="progress mt-3 w-full"
          :class="downloadProgressState.stalled ? 'progress-warning' : 'progress-info'"
          :value="downloadProgressState.percentValue"
          max="100"
        />
      </div>

      <div class="rounded-[24px] border border-base-content/10 bg-base-300/30 p-3">
        <div
          ref="logShowTable"
          class="h-[28rem] max-h-[28rem] overflow-y-auto overflow-x-hidden rounded-[18px]"
        >
          <table class="table table-xs table-fixed rounded-none">
          <tbody>
            <tr
              v-for="(item, index) in logData"
              :key="`${item.time ?? 'log'}-${index}`"
              :class="{
                'flex w-full items-start font-mono text-[13px] leading-6': true,
                'bg-error/50': item.level === 'ERROR',
                'bg-warning/50': item.level === 'WARNING',
                'bg-info/10 border-l-4 border-info': ['start', 'progress', 'deps'].includes(getDownloadRowKind(item.message)),
                'bg-warning/10 border-l-4 border-warning': getDownloadRowKind(item.message) === 'retry',
                'bg-error/10 border-l-4 border-error': getDownloadRowKind(item.message) === 'failure'
              }"
            >
              <th v-if="item.time" class="sticky left-0 shrink-0 whitespace-nowrap bg-base-300/90 pl-0 text-gray-500">
                {{ item.time }}
              </th>
              <td v-if="item.level" class="w-24 shrink-0 whitespace-nowrap">{{ item.level }}</td>
              <td
                class="flex min-w-0 flex-1 items-start gap-2 whitespace-pre-wrap break-all"
                :class="{ 'pl-0 text-success': !item.time }"
              >
                <span
                  v-if="getDownloadRowKind(item.message) === 'start'"
                  class="badge badge-info badge-sm shrink-0 text-base-100"
                >
                  开始下载
                </span>
                <span
                  v-else-if="getDownloadRowKind(item.message) === 'progress'"
                  class="badge badge-info badge-sm shrink-0 text-base-100"
                >
                  下载进度
                </span>
                <span
                  v-else-if="getDownloadRowKind(item.message) === 'deps'"
                  class="badge badge-ghost badge-sm shrink-0"
                >
                  安装依赖
                </span>
                <span
                  v-else-if="getDownloadRowKind(item.message) === 'retry'"
                  class="badge badge-warning badge-sm shrink-0"
                >
                  切换官方源
                </span>
                <span
                  v-else-if="getDownloadRowKind(item.message) === 'failure'"
                  class="badge badge-error badge-sm shrink-0 text-base-100"
                >
                  下载失败
                </span>
                <span class="min-w-0 whitespace-pre-wrap break-all">{{ item.message }}</span>
              </td>
            </tr>
          </tbody>
          </table>
        </div>
      </div>

      <form
        v-if="props.mode === 'shell'"
        class="flex flex-col gap-3 rounded-[24px] border border-base-content/10 bg-base-100/60 p-4 backdrop-blur"
        @submit.prevent="sendCommand"
      >
          <div class="flex flex-col gap-3 rounded-2xl border border-base-content/8 bg-base-200/70 p-3">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-xs uppercase tracking-[0.24em] text-base-content/45">Command Deck</span>
              <button class="btn btn-xs btn-outline btn-primary" type="button" @click="openQuickCommandModal()">
                + 新增
              </button>
            </div>
            <div class="flex flex-wrap gap-2">
              <template v-for="item in commandDeck" :key="item.id">
                <button class="btn btn-xs btn-ghost" type="button" @click="fillCommand(item.command)">
                  {{ item.label }}
                </button>
                <button
                  v-if="!item.id.startsWith('builtin-')"
                  class="btn btn-xs btn-ghost px-2"
                  type="button"
                  title="删除快捷命令"
                  @click="removeQuickCommand(item.id)"
                >
                  ×
                </button>
              </template>
            </div>
            <div v-if="recentCommands.length" class="flex flex-col gap-2">
              <span class="text-xs uppercase tracking-[0.24em] text-base-content/45">Recent</span>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="item in recentCommands"
                  :key="item.id"
                  class="btn btn-xs btn-outline"
                  type="button"
                  @click="fillCommand(item.command)"
                >
                  {{ item.command }}
                </button>
              </div>
            </div>
          </div>

        <div class="flex flex-col gap-3 lg:flex-row">
          <div class="flex flex-1 items-stretch rounded-2xl border border-base-content/10 bg-base-300/40">
            <div class="flex items-center border-r border-base-content/10 px-3 font-mono text-xs text-base-content/45">
              $
            </div>
            <input
              v-model="commandInput"
              class="input input-sm h-auto flex-1 border-0 bg-transparent font-mono focus:outline-none"
              :placeholder="commandPlaceholder"
              :disabled="!canWriteCommand"
            />
          </div>
          <div class="flex gap-2">
            <button
              class="btn btn-sm btn-primary text-base-100"
              type="submit"
              :disabled="!canWriteCommand"
            >
              Send
            </button>
            <button
              class="btn btn-sm btn-warning"
              type="button"
              :disabled="!canInterrupt"
              @click="sendInterrupt"
            >
              Ctrl+C
            </button>
          </div>
        </div>
      </form>

      <div
        v-else
        class="rounded-[24px] border border-base-content/10 bg-base-100/60 p-4 text-sm leading-6 text-base-content/70 backdrop-blur"
      >
        维护命令、手动安装依赖和
        <span class="font-mono">playwright install</span>
        等操作已移动到左侧菜单中的独立
        <span class="font-semibold">终端</span>
        页面，避免与实例运行日志混在一起。
      </div>
    </div>
  </section>
</template>
