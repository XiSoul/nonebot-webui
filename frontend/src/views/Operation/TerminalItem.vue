<script setup lang="ts">
import { ProcessService, type ProcessLog } from '@/client/api'
import { getAuthToken } from '@/client/auth'
import { openProjectTerminal } from '@/client/process'
import { generateURLForWebUI, getErrorMessage } from '@/client/utils'
import { useCustomStore, useNoneBotStore, useToastStore } from '@/stores'
import { useWebSocket } from '@vueuse/core'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

const store = useNoneBotStore()
const customStore = useCustomStore()
const toast = useToastStore()

const logData = ref<ProcessLog[]>([])
const logShowTable = ref<HTMLElement>()
const currentBot = ref('')
const commandInput = ref('')
const commandSending = ref(false)
const MISSING_LOG_STORAGE_ERROR = 'Log storage not found.'
const PROCESS_FINISHED_MESSAGE = 'Process finished.'
const PROCESS_NOT_RUNNING_ERROR = 'Process is not running.'
const PROCESS_NOT_FOUND_ERROR = 'Process not found.'

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

const fillCommand = (value: string) => {
  commandInput.value = value
}

const subscribeLog = (projectId?: string) => {
  const logKey = projectId ?? store.selectedBot?.project_id
  if (!logKey) return
  send(JSON.stringify({ type: 'log', log_key: logKey }))
  currentBot.value = logKey
}

const getHistoryLogs = async (projectId?: string) => {
  const logId = projectId ?? store.selectedBot?.project_id
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
      if (store.selectedBot?.project_id === logId) {
        logData.value = []
      }
      return
    }
    toast.add("warning", `Get history logs failed: ${errorDetail}`, "", 5000)
    return
  }

  if (data) {
    if (store.selectedBot?.project_id !== logId) return
    logData.value = data.detail
    await scrollToBottom()
  }
}

const syncSelectedBotStatus = async () => {
  if (!store.selectedBot?.project_id) return
  await store.loadBots()
}

const ensureStoppedProjectTerminal = async (projectId?: string) => {
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
  if (!store.selectedBot) return
  if (!store.selectedBot.is_running) {
    const ready = await ensureStoppedProjectTerminal(store.selectedBot.project_id)
    if (!ready) return false
  }

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
      if (!store.selectedBot?.is_running) {
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
          toast.add('error', `Send command failed: ${getErrorMessage(retry.error)}`, '', 5000)
          return false
        }
        if (displayEcho) await appendLocalLog(displayEcho)
        return true
      }
      return false
    }
    toast.add('error', `Send command failed: ${getErrorMessage(error)}`, '', 5000)
    return false
  }

  if (displayEcho) await appendLocalLog(displayEcho)
  return true
}

const sendCommand = async () => {
  const command = commandInput.value.trim()
  if (!command) return

  if (store.selectedBot?.is_running && status.value !== 'OPEN') {
    await syncSelectedBotStatus()
    if (store.selectedBot?.is_running) {
      toast.add('warning', '实例运行中，但终端连接已断开，请先重连。', '', 3000)
      return
    }
  }

  const sent = await writeToProcess(`${command}\n`, `> ${command}`)
  if (sent) {
    commandInput.value = ''
  }
}

const sendInterrupt = async () => {
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
  () => Boolean(store.selectedBot) && (!store.selectedBot?.is_running || status.value === 'OPEN') && !commandSending.value
)
const canInterrupt = computed(
  () => Boolean(store.selectedBot) && (!store.selectedBot?.is_running || status.value === 'OPEN') && !commandSending.value
)
const terminalModeLabel = computed(() => {
  if (!store.selectedBot) return '未选择实例'
  if (store.selectedBot.is_running) {
    return status.value === 'OPEN' ? '实例输入' : '等待重连'
  }
  return 'Shell 会话'
})
const commandPlaceholder = computed(() => {
  if (!store.selectedBot) return '请先选择实例'
  if (store.selectedBot.is_running) {
    if (status.value === 'OPEN') return 'Type command, press Enter to send'
    return '实例运行中，但终端连接已断开，请先重连或等待状态同步'
  }
  return '实例已停止，当前为常驻 Shell，可直接执行 pip install、playwright install、nb run 等命令'
})

onMounted(async () => {
  if (!store.selectedBot) return
  await getHistoryLogs(store.selectedBot.project_id)
  if (!store.selectedBot.is_running) {
    await ensureStoppedProjectTerminal(store.selectedBot.project_id)
  }
  open()
})

onUnmounted(() => {
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
  async (projectId, previousProjectId) => {
    if (!projectId) {
      currentBot.value = ''
      logData.value = []
      close()
      return
    }

    if (projectId !== previousProjectId) {
      currentBot.value = projectId
      logData.value = []
      await getHistoryLogs(projectId)
      if (!store.selectedBot?.is_running) {
        await ensureStoppedProjectTerminal(projectId)
      }
    }

    if (status.value !== 'OPEN') {
      open()
    } else {
      subscribeLog(projectId)
      await getHistoryLogs(projectId)
    }
  }
)

watch(
  () => store.selectedBot?.is_running,
  async (isRunning) => {
    const projectId = store.selectedBot?.project_id
    if (!projectId) return

    if (isRunning) {
      await getHistoryLogs(projectId)
      if (status.value !== 'OPEN') {
        open()
      } else {
        subscribeLog(projectId)
      }
      return
    }

    await ensureStoppedProjectTerminal(projectId)
    if (status.value === 'OPEN') {
      subscribeLog(projectId)
      await getHistoryLogs(projectId)
    }
  }
)

const retry = () => {
  if (store.selectedBot?.project_id !== currentBot.value) logData.value = []
    logData.value.push({
      message: 'Retrying websocket connection...'
    })
  open()
}
</script>

<template>
  <div class="w-full p-6 rounded-box bg-base-200 flex flex-col gap-3">
    <div class="flex justify-between gap-4">
      <div class="flex items-center gap-3">
        <span class="font-semibold">Terminal Output</span>
        <div class="badge badge-sm badge-ghost font-normal">
          {{ terminalModeLabel }}
        </div>
        <div
          v-if="status === 'OPEN'"
          class="badge badge-sm badge-success font-normal text-base-100"
        >
          Connected
        </div>
        <div v-else class="badge badge-sm badge-error font-normal text-base-100">Disconnected</div>
      </div>

      <button
        :class="{ 'btn btn-sm btn-ghost': true, hidden: status === 'OPEN' }"
        @click="retry()"
      >
        Retry
      </button>
    </div>

    <table ref="logShowTable" class="overflow-auto h-96 !flex table table-xs rounded-none">
      <tbody>
        <tr
          v-for="(item, index) in logData"
          :key="`${item.time ?? 'log'}-${index}`"
          :class="{
            'flex font-mono': true,
            'bg-error/50': item.level === 'ERROR',
            'bg-warning/50': item.level === 'WARNING'
          }"
        >
          <th v-if="item.time" class="sticky left-0 right-0 text-gray-500 pl-0 bg-base-200">
            {{ item.time }}
          </th>
          <td v-if="item.level" class="flex">{{ item.level }}</td>
          <td :class="{ flex: true, 'pl-0 text-success': !item.time }">{{ item.message }}</td>
        </tr>
      </tbody>
    </table>

    <form class="flex flex-col md:flex-row gap-2" @submit.prevent="sendCommand">
      <div class="flex flex-wrap items-center gap-2 md:max-w-xs">
        <span class="text-xs text-base-content/70">常用命令</span>
        <button class="btn btn-xs btn-ghost" type="button" @click="fillCommand('python -m pip install -U ')">
          pip 安装
        </button>
        <button class="btn btn-xs btn-ghost" type="button" @click="fillCommand('nb run')">nb run</button>
      </div>
      <input
        v-model="commandInput"
        class="input input-sm input-bordered flex-1 font-mono"
        :placeholder="commandPlaceholder"
        :disabled="!canWriteCommand"
      />
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
    </form>
  </div>
</template>
