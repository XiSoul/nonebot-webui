<script setup lang="ts">
import { ProcessService, type ProcessLog } from '@/client/api'
import { getAuthToken } from '@/client/auth'
import {
  createProjectTerminalSession,
  getProjectRuntimeLogKey,
  listProjectTerminalSessions,
  type TerminalSessionInfo
} from '@/client/process'
import { resizeProjectTerminal } from '@/client/terminal'
import { generateURLForWebUI, getErrorMessage } from '@/client/utils'
import { useNoneBotStore, useToastStore } from '@/stores'
import { getRuntimeState, isRuntimeActive } from '@/utils/runtimeState'
import { FitAddon } from '@xterm/addon-fit'
import { Terminal, type ITerminalOptions } from '@xterm/xterm'
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import '@xterm/xterm/css/xterm.css'

const props = withDefaults(
  defineProps<{
    mode?: 'runtime' | 'shell'
  }>(),
  {
    mode: 'shell'
  }
)

type TerminalThemeId = 'midnight' | 'graphite' | 'nord' | 'paper'

const TERMINAL_THEME_KEY = 'nonebot_terminal_theme'
const TERMINAL_THEMES: Record<
  TerminalThemeId,
  { label: string; accent: string; theme: ITerminalOptions['theme'] }
> = {
  midnight: {
    label: 'Midnight',
    accent: 'from-primary/18 via-secondary/10 to-transparent',
    theme: {
      background: '#09111f',
      foreground: '#e5edf7',
      cursor: '#f8fafc',
      selectionBackground: 'rgba(96, 165, 250, 0.24)',
      black: '#0f172a',
      red: '#f87171',
      green: '#4ade80',
      yellow: '#facc15',
      blue: '#60a5fa',
      magenta: '#f472b6',
      cyan: '#22d3ee',
      white: '#e2e8f0',
      brightBlack: '#475569',
      brightRed: '#fb7185',
      brightGreen: '#86efac',
      brightYellow: '#fde047',
      brightBlue: '#93c5fd',
      brightMagenta: '#f9a8d4',
      brightCyan: '#67e8f9',
      brightWhite: '#f8fafc'
    }
  },
  graphite: {
    label: 'Graphite',
    accent: 'from-slate-300/20 via-slate-500/10 to-transparent',
    theme: {
      background: '#111315',
      foreground: '#e7e5e4',
      cursor: '#fafaf9',
      selectionBackground: 'rgba(214, 211, 209, 0.22)',
      black: '#1c1917',
      red: '#f87171',
      green: '#86efac',
      yellow: '#fde68a',
      blue: '#93c5fd',
      magenta: '#f0abfc',
      cyan: '#67e8f9',
      white: '#e7e5e4',
      brightBlack: '#57534e',
      brightRed: '#fca5a5',
      brightGreen: '#bbf7d0',
      brightYellow: '#fef3c7',
      brightBlue: '#bfdbfe',
      brightMagenta: '#f5d0fe',
      brightCyan: '#a5f3fc',
      brightWhite: '#fafaf9'
    }
  },
  nord: {
    label: 'Nord',
    accent: 'from-sky-300/25 via-blue-400/10 to-transparent',
    theme: {
      background: '#2e3440',
      foreground: '#d8dee9',
      cursor: '#eceff4',
      selectionBackground: 'rgba(129, 161, 193, 0.24)',
      black: '#3b4252',
      red: '#bf616a',
      green: '#a3be8c',
      yellow: '#ebcb8b',
      blue: '#81a1c1',
      magenta: '#b48ead',
      cyan: '#88c0d0',
      white: '#e5e9f0',
      brightBlack: '#4c566a',
      brightRed: '#bf616a',
      brightGreen: '#a3be8c',
      brightYellow: '#ebcb8b',
      brightBlue: '#81a1c1',
      brightMagenta: '#b48ead',
      brightCyan: '#8fbcbb',
      brightWhite: '#eceff4'
    }
  },
  paper: {
    label: 'Paper',
    accent: 'from-amber-300/20 via-orange-300/10 to-transparent',
    theme: {
      background: '#f7f4ec',
      foreground: '#3f3f46',
      cursor: '#0f172a',
      cursorAccent: '#f7f4ec',
      selectionBackground: 'rgba(217, 119, 6, 0.16)',
      black: '#3f3f46',
      red: '#dc2626',
      green: '#15803d',
      yellow: '#a16207',
      blue: '#1d4ed8',
      magenta: '#9333ea',
      cyan: '#0f766e',
      white: '#71717a',
      brightBlack: '#71717a',
      brightRed: '#ef4444',
      brightGreen: '#22c55e',
      brightYellow: '#ca8a04',
      brightBlue: '#3b82f6',
      brightMagenta: '#a855f7',
      brightCyan: '#14b8a6',
      brightWhite: '#18181b'
    }
  }
}

const store = useNoneBotStore()
const toast = useToastStore()

const runtimeActive = computed(() => isRuntimeActive(store.selectedBot))
const runtimeState = computed(() => getRuntimeState(store.selectedBot))
const selectedProjectName = computed(() => store.selectedBot?.project_name || '未选择实例')
const selectedProjectDir = computed(() => store.selectedBot?.project_dir || '未连接项目目录')
const selectedProjectDirShort = computed(() => {
  const dir = selectedProjectDir.value
  if (dir.length <= 54) return dir
  return `...${dir.slice(-51)}`
})
const projectInitial = computed(() => {
  const source = selectedProjectName.value.trim()
  return source ? source.slice(0, 1).toUpperCase() : 'N'
})

const currentLogKey = ref('')
const logData = ref<ProcessLog[]>([])
const runtimeLogWrap = ref<HTMLElement>()
const terminalRoot = ref<HTMLElement>()
const commandInputRef = ref<HTMLInputElement>()
const commandInput = ref('')
const statusText = ref('未连接')
const sessionBusy = ref(false)
const socketConnected = ref(false)
const commandSending = ref(false)
const shellSessions = ref<TerminalSessionInfo[]>([])
const activeSessionId = ref('')
const selectedTheme = ref<TerminalThemeId>(
  (localStorage.getItem(TERMINAL_THEME_KEY) as TerminalThemeId) || 'midnight'
)

let termSocket: WebSocket | null = null
let runtimeSocket: WebSocket | null = null
let terminal: Terminal | null = null
let fitAddon: FitAddon | null = null
let resizeObserver: ResizeObserver | null = null
let pendingAttachSessionId: string | null = null

const canUseShellTerminal = computed(() => props.mode === 'shell' && Boolean(store.selectedBot))
const canWriteCommand = computed(
  () =>
    canUseShellTerminal.value &&
    socketConnected.value &&
    !commandSending.value &&
    Boolean(activeSessionId.value)
)
const canInterrupt = computed(() => canUseShellTerminal.value && socketConnected.value)
const canManageSessions = computed(
  () => props.mode === 'shell' && Boolean(store.selectedBot) && !sessionBusy.value
)
const activeTheme = computed(
  () => TERMINAL_THEMES[selectedTheme.value] ?? TERMINAL_THEMES.midnight
)
const themeOptions = computed(() =>
  Object.entries(TERMINAL_THEMES).map(([id, item]) => ({
    id: id as TerminalThemeId,
    label: item.label
  }))
)
const runtimeStateLabel = computed(() => {
  if (!store.selectedBot) return 'Detached'
  if (runtimeState.value === 'running') return 'Running'
  if (runtimeState.value === 'starting') return 'Starting'
  return 'Stopped'
})
const terminalModeLabel = computed(() => {
  if (!store.selectedBot) return '未选择实例'
  if (props.mode === 'runtime') return '实例运行日志'
  return 'Maintenance PTY'
})
const terminalSessionLabel = computed(() => {
  if (!store.selectedBot) return 'Detached'
  if (props.mode === 'runtime') return 'Runtime Stream'
  const active = shellSessions.value.find((item) => item.session_id === activeSessionId.value)
  return active?.title || 'Interactive PTY'
})
const terminalStatusTone = computed(() => {
  if (!store.selectedBot) return 'badge-ghost'
  if (props.mode === 'runtime') {
    if (runtimeState.value === 'running') return 'badge-success text-base-100'
    if (runtimeState.value === 'starting') return 'badge-warning'
    return 'badge-ghost'
  }
  if (socketConnected.value) return 'badge-success text-base-100'
  return runtimeActive.value ? 'badge-warning' : 'badge-error text-base-100'
})
const workspaceSummary = computed(() => {
  if (!store.selectedBot) return '先选择一个实例，再连接维护终端或查看运行日志。'
  if (props.mode === 'runtime') {
    return '这里专注查看实例启动和运行过程，保留原始输出节奏，不接收交互输入。'
  }
  return '维护终端保持常驻 PTY，会把输入、回显、Ctrl+C 和窗口尺寸直接同步到当前项目。'
})
const connectionHint = computed(() => {
  if (!store.selectedBot) return 'Select a project to start'
  if (props.mode === 'runtime') return 'Attached to runtime log stream'
  if (!shellSessions.value.length) return 'Create a PTY session to begin'
  if (socketConnected.value) return 'Shell is ready for interactive commands'
  return 'Waiting for PTY session attachment'
})
const commandPlaceholder = computed(() => {
  if (props.mode !== 'shell') return '当前页面仅展示实例运行日志'
  if (!store.selectedBot) return '请先选择实例'
  if (!socketConnected.value) return '终端连接中断，请等待重新附着'
  return '输入命令后按 Enter，例如 python -m pip install -U xxx'
})
const sidebarStats = computed(() => [
  { label: 'Project', value: selectedProjectName.value },
  { label: 'Runtime', value: runtimeStateLabel.value },
  { label: 'Sessions', value: String(shellSessions.value.length || 0) },
  { label: 'Status', value: statusText.value }
])
const activeSession = computed(
  () => shellSessions.value.find((item) => item.session_id === activeSessionId.value) ?? null
)
const activeSessionCreatedAt = computed(() => {
  if (!activeSession.value?.created_at) return '未建立'
  return new Date(activeSession.value.created_at * 1000).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit'
  })
})
const quickCommands = computed(() => {
  if (props.mode !== 'shell') return []
  return [
    { label: 'nb run', command: 'nb run' },
    { label: 'pip upgrade', command: 'python -m pip install -U pip' },
    {
      label: 'playwright',
      command: 'python -m playwright install chromium'
    }
  ]
})
const workspaceHeightClass = computed(() =>
  props.mode === 'shell' ? 'lg:h-[44rem]' : 'lg:h-[36rem]'
)
const terminalPaneHeightClass = computed(() =>
  props.mode === 'shell' ? 'h-[32rem] lg:h-full' : 'h-[28rem] lg:h-full'
)

const formatSessionTime = (value: number) =>
  new Date(value * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

const scrollRuntimeToBottom = async () => {
  await nextTick()
  if (runtimeLogWrap.value) {
    runtimeLogWrap.value.scrollTop = runtimeLogWrap.value.scrollHeight
  }
}

const resolveRuntimeLogKey = async (projectId?: string) => {
  const id = projectId ?? store.selectedBot?.project_id
  if (!id) {
    currentLogKey.value = ''
    return ''
  }

  const { data, error } = await getProjectRuntimeLogKey(id)
  if (error || !data?.detail) {
    currentLogKey.value = id
    return currentLogKey.value
  }
  currentLogKey.value = data.detail
  return currentLogKey.value
}

const loadRuntimeHistory = async (logId?: string) => {
  const target = logId ?? currentLogKey.value
  if (!target) return

  const { data, error } = await ProcessService.getLogHistoryV1ProcessLogHistoryGet({
    query: {
      log_count: 300,
      log_id: target
    }
  })

  if (error) {
    toast.add('warning', `读取运行日志失败: ${getErrorMessage(error)}`, '', 4000)
    return
  }

  logData.value = data?.detail ?? []
  await scrollRuntimeToBottom()
}

const subscribeRuntimeLog = (send: (value: string) => void, logKey: string) => {
  if (!logKey) return
  send(JSON.stringify({ type: 'log', log_key: logKey }))
}

const disconnectResizeObserver = () => {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
}

const teardownRuntimeSocket = () => {
  if (runtimeSocket) {
    runtimeSocket.close()
    runtimeSocket = null
  }
}

const syncSessions = (sessions: TerminalSessionInfo[] = [], nextActiveId?: string | null) => {
  shellSessions.value = sessions
  if (nextActiveId) {
    activeSessionId.value = nextActiveId
    return
  }
  const active = sessions.find((item) => item.is_active)
  activeSessionId.value = active?.session_id || sessions[0]?.session_id || ''
}

const teardownTermSocket = () => {
  if (termSocket) {
    termSocket.close()
    termSocket = null
  }
  socketConnected.value = false
  statusText.value = '未连接'
  activeSessionId.value = ''
  shellSessions.value = []
  pendingAttachSessionId = null
  disconnectResizeObserver()
}

const disposeTerminal = () => {
  disconnectResizeObserver()
  fitAddon = null
  if (terminal) {
    terminal.dispose()
    terminal = null
  }
}

const applyThemeToTerminal = () => {
  localStorage.setItem(TERMINAL_THEME_KEY, selectedTheme.value)
  if (terminal) {
    terminal.options.theme = { ...activeTheme.value.theme }
  }
}

const attachTerminalResize = (projectId: string) => {
  if (!terminalRoot.value || !terminal || !fitAddon) return
  disconnectResizeObserver()

  const sendResize = async () => {
    fitAddon?.fit()
    const cols = terminal?.cols ?? 0
    const rows = terminal?.rows ?? 0
    if (cols > 0 && rows > 0) {
      await resizeProjectTerminal(projectId, cols, rows, activeSessionId.value || undefined)
      termSocket?.send(
        JSON.stringify({
          type: 'resize',
          project_id: projectId,
          session_id: activeSessionId.value || undefined,
          cols,
          rows
        })
      )
    }
  }

  resizeObserver = new ResizeObserver(() => {
    void sendResize()
  })
  resizeObserver.observe(terminalRoot.value)
  void sendResize()
}

const ensureTerminal = () => {
  if (!terminalRoot.value || terminal) return

  terminal = new Terminal({
    cursorBlink: true,
    fontFamily: '"Cascadia Mono", "Fira Code", "Consolas", monospace',
    fontSize: 13,
    lineHeight: 1.35,
    convertEol: false,
    theme: { ...activeTheme.value.theme }
  })

  fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  terminal.open(terminalRoot.value)
  fitAddon.fit()

  terminal.onData((value) => {
    if (!termSocket || termSocket.readyState !== WebSocket.OPEN) return
    termSocket.send(JSON.stringify({ type: 'input', data: value }))
  })
}

const focusCommandInput = async () => {
  await nextTick()
  commandInputRef.value?.focus()
}

const sendTerminalControl = (payload: Record<string, unknown>) => {
  if (!termSocket || termSocket.readyState !== WebSocket.OPEN) return
  termSocket.send(JSON.stringify(payload))
}

const markActiveSession = (sessionId: string) => {
  activeSessionId.value = sessionId
  shellSessions.value = shellSessions.value.map((item) => ({
    ...item,
    is_active: item.session_id === sessionId
  }))
}

const refreshTerminalSessions = async (projectId?: string) => {
  const id = projectId ?? store.selectedBot?.project_id
  if (!id || props.mode !== 'shell') return

  const { data, error } = await listProjectTerminalSessions(id)
  if (!error && data?.detail) {
    syncSessions(data.detail)
  }
}

const ensureDefaultShellSession = async (projectId: string) => {
  await refreshTerminalSessions(projectId)
  if (shellSessions.value.length > 0) return shellSessions.value[0]?.session_id || ''

  const { data, error } = await createProjectTerminalSession(projectId)
  if (error || !data?.detail) {
    toast.add('error', `创建终端会话失败: ${getErrorMessage(error)}`, '', 5000)
    return ''
  }

  shellSessions.value = [data.detail]
  markActiveSession(data.detail.session_id)
  return data.detail.session_id
}

const connectShellTerminal = async (projectId?: string, preferredSessionId?: string) => {
  if (props.mode !== 'shell') return

  const id = projectId ?? store.selectedBot?.project_id
  if (!id) return

  const ensuredSessionId = await ensureDefaultShellSession(id)
  const targetSessionId =
    preferredSessionId || activeSessionId.value || ensuredSessionId || shellSessions.value[0]?.session_id || ''
  if (!targetSessionId) {
    statusText.value = '未创建会话'
    return
  }

  ensureTerminal()
  teardownTermSocket()
  await refreshTerminalSessions(id)
  pendingAttachSessionId = targetSessionId

  termSocket = new WebSocket(generateURLForWebUI('/v1/process/terminal/ws', true))
  statusText.value = '连接中'

  termSocket.addEventListener('open', () => {
    const token = getAuthToken()
    if (token) {
      termSocket?.send(token)
    }
    terminal?.reset()
    sendTerminalControl({
      type: 'attach',
      project_id: id,
      session_id: targetSessionId
    })
  })

  termSocket.addEventListener('message', (event) => {
    try {
      const payload = JSON.parse(String(event.data))
      if (payload.type === 'ready') {
        syncSessions(payload.sessions ?? [], payload.session_id)
        if (payload.session_id) {
          markActiveSession(payload.session_id)
        }
        pendingAttachSessionId = null
        socketConnected.value = true
        statusText.value = '已连接'
        attachTerminalResize(id)
        void focusCommandInput()
        return
      }
      if (payload.type === 'sessions') {
        syncSessions(payload.sessions ?? [], payload.session_id)
        return
      }
      if (payload.type === 'output' && typeof payload.data === 'string') {
        terminal?.write(payload.data)
      }
    } catch {
      terminal?.write(String(event.data))
    }
  })

  termSocket.addEventListener('close', () => {
    socketConnected.value = false
    statusText.value = '已断开'
    pendingAttachSessionId = null
    disconnectResizeObserver()
  })

  termSocket.addEventListener('error', () => {
    socketConnected.value = false
    statusText.value = '连接失败'
  })
}

const createShellSession = async () => {
  const projectId = store.selectedBot?.project_id
  if (!projectId || !canManageSessions.value) return

  sessionBusy.value = true
  try {
    const { data, error } = await createProjectTerminalSession(projectId)
    if (error || !data?.detail) {
      toast.add('error', `创建终端会话失败: ${getErrorMessage(error)}`, '', 5000)
      return
    }
    shellSessions.value = [...shellSessions.value, data.detail]
    markActiveSession(data.detail.session_id)
    if (termSocket?.readyState === WebSocket.OPEN) {
      pendingAttachSessionId = data.detail.session_id
      terminal?.reset()
      sendTerminalControl({
        type: 'switch',
        project_id: projectId,
        session_id: data.detail.session_id
      })
    } else {
      await connectShellTerminal(projectId, data.detail.session_id)
    }
  } finally {
    sessionBusy.value = false
  }
}

const switchShellSession = async (sessionId: string) => {
  const projectId = store.selectedBot?.project_id
  if (!projectId || !sessionId || sessionId === activeSessionId.value || sessionBusy.value) return

  sessionBusy.value = true
  try {
    markActiveSession(sessionId)
    pendingAttachSessionId = sessionId
    terminal?.reset()
    sendTerminalControl({
      type: 'switch',
      project_id: projectId,
      session_id: sessionId
    })
  } finally {
    sessionBusy.value = false
  }
}

const closeShellSession = async (sessionId: string) => {
  const projectId = store.selectedBot?.project_id
  if (!projectId || !sessionId || sessionBusy.value) return

  sessionBusy.value = true
  try {
    terminal?.reset()
    sendTerminalControl({
      type: 'close',
      project_id: projectId,
      session_id: sessionId
    })
  } finally {
    sessionBusy.value = false
  }
}

const connectRuntimeLog = async (projectId?: string) => {
  if (props.mode !== 'runtime') return

  const id = projectId ?? store.selectedBot?.project_id
  if (!id) return

  const logKey = await resolveRuntimeLogKey(id)
  await loadRuntimeHistory(logKey)
  teardownRuntimeSocket()

  runtimeSocket = new WebSocket(generateURLForWebUI('/v1/process/log/ws', true))

  runtimeSocket.addEventListener('open', () => {
    const token = getAuthToken()
    if (token) {
      runtimeSocket?.send(token)
    }
    subscribeRuntimeLog((value) => runtimeSocket?.send(value), logKey)
  })

  runtimeSocket.addEventListener('message', async (event) => {
    try {
      const payload = JSON.parse(String(event.data)) as ProcessLog
      logData.value.push(payload)
      await scrollRuntimeToBottom()
    } catch {
      // ignore malformed runtime log payload
    }
  })
}

const sendCommand = async () => {
  if (!canWriteCommand.value) return

  const command = commandInput.value.trim()
  if (!command) return

  commandSending.value = true
  termSocket?.send(JSON.stringify({ type: 'input', data: `${command}\n` }))
  commandInput.value = ''
  commandSending.value = false
  await focusCommandInput()
}

const primeCommand = async (command: string, runImmediately = false) => {
  commandInput.value = command
  await focusCommandInput()
  if (runImmediately && canWriteCommand.value) {
    await sendCommand()
  }
}

const sendInterrupt = () => {
  if (!canInterrupt.value) return
  termSocket?.send(JSON.stringify({ type: 'interrupt' }))
}

watch(selectedTheme, () => {
  applyThemeToTerminal()
})

watch(
  () => store.selectedBot?.project_id,
  async (projectId) => {
    teardownRuntimeSocket()
    teardownTermSocket()
    disposeTerminal()
    logData.value = []
    currentLogKey.value = ''
    commandInput.value = ''

    if (!projectId) return

    if (props.mode === 'shell') {
      await nextTick()
      await connectShellTerminal(projectId)
    } else {
      await connectRuntimeLog(projectId)
    }
  },
  { immediate: true }
)

watch(
  () => runtimeState.value,
  async () => {
    if (props.mode !== 'runtime' || !store.selectedBot?.project_id) return
    const logKey = await resolveRuntimeLogKey(store.selectedBot.project_id)
    await loadRuntimeHistory(logKey)
  }
)

onUnmounted(() => {
  teardownRuntimeSocket()
  teardownTermSocket()
  disposeTerminal()
})
</script>

<template>
  <section
    class="terminal-workspace nb-panel-surface w-full overflow-hidden rounded-[30px]"
  >
    <div class="flex flex-col lg:flex-row" :class="workspaceHeightClass">
      <aside
        class="relative overflow-hidden border-b border-base-content/10 bg-base-100/78 backdrop-blur-xl lg:w-[22rem] lg:border-b-0 lg:border-r"
      >
        <div
          class="pointer-events-none absolute inset-0 bg-gradient-to-br"
          :class="activeTheme.accent"
        />
        <div class="relative flex h-full flex-col gap-5 overflow-y-auto p-5 lg:p-6">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="text-[11px] uppercase tracking-[0.26em] text-base-content/45">
                Terminal Workspace
              </div>
              <div class="mt-2 flex items-center gap-3">
                <div
                  class="flex h-11 w-11 items-center justify-center rounded-2xl border border-base-content/10 bg-base-100 text-sm font-semibold shadow-sm"
                >
                  {{ projectInitial }}
                </div>
                <div class="min-w-0">
                  <div class="truncate text-base font-semibold text-base-content/85">
                    {{ selectedProjectName }}
                  </div>
                  <div class="text-xs text-base-content/55">
                    {{ terminalModeLabel }}
                  </div>
                </div>
              </div>
            </div>
            <div class="badge badge-sm font-normal" :class="terminalStatusTone">
              {{ statusText }}
            </div>
          </div>

          <div class="rounded-[24px] border border-primary/10 bg-base-100/82 p-4 shadow-sm shadow-primary/5">
            <div class="flex items-center justify-between gap-3">
              <div class="text-[11px] uppercase tracking-[0.22em] text-base-content/45">
                Session
              </div>
              <div class="flex items-center gap-2">
                <div class="badge badge-sm badge-ghost font-normal">
                  {{ terminalSessionLabel }}
                </div>
                <button
                  v-if="props.mode === 'shell'"
                  class="btn btn-xs btn-ghost rounded-xl"
                  type="button"
                  :disabled="!canManageSessions"
                  @click="createShellSession"
                >
                  New
                </button>
              </div>
            </div>
            <p class="mt-3 text-sm leading-6 text-base-content/70">
              {{ workspaceSummary }}
            </p>
            <div class="mt-4 rounded-2xl border border-primary/10 bg-primary/6 px-3 py-3">
              <div class="text-[11px] uppercase tracking-[0.2em] text-base-content/40">
                Path
              </div>
              <div
                class="mt-2 break-all font-mono text-xs leading-6 text-base-content/70"
                :title="selectedProjectDir"
              >
                {{ selectedProjectDirShort }}
              </div>
            </div>
            <div
              v-if="props.mode === 'shell'"
              class="mt-4 rounded-2xl border border-base-content/10 bg-base-100/70 p-2"
            >
              <div class="mb-2 flex items-center justify-between px-2">
                <div class="text-[11px] uppercase tracking-[0.2em] text-base-content/40">
                  Tabs
                </div>
                <div class="text-[11px] text-base-content/45">
                  {{ shellSessions.length }}
                </div>
              </div>
              <div v-if="shellSessions.length" class="flex flex-col gap-2">
                <div
                  v-for="item in shellSessions"
                  :key="item.session_id"
                  class="group flex items-center justify-between rounded-2xl border px-3 py-3 transition"
                  :class="
                    item.session_id === activeSessionId
                      ? 'border-base-content/15 bg-base-200/80'
                      : 'border-transparent bg-base-100/70 hover:border-base-content/10 hover:bg-base-100'
                  "
                >
                  <button
                    class="min-w-0 flex-1 text-left"
                    type="button"
                    @click="switchShellSession(item.session_id)"
                  >
                    <div class="truncate text-sm font-medium text-base-content/80">
                      {{ item.title }}
                    </div>
                    <div class="mt-1 flex items-center gap-2 text-[11px] text-base-content/50">
                      <span>{{ formatSessionTime(item.created_at) }}</span>
                      <span class="rounded-full bg-base-content/10 px-2 py-0.5">
                        {{ item.is_running ? 'live' : 'stopped' }}
                      </span>
                    </div>
                  </button>
                  <button
                    class="btn btn-ghost btn-xs rounded-xl opacity-60 transition group-hover:opacity-100"
                    type="button"
                    :disabled="sessionBusy"
                    @click.stop="closeShellSession(item.session_id)"
                  >
                    ×
                  </button>
                </div>
              </div>
              <div v-else class="px-2 py-4 text-xs leading-5 text-base-content/50">
                还没有维护终端会话，点击右上角 New 创建第一个标签。
              </div>
            </div>
          </div>

          <div class="grid grid-cols-1 gap-3 sm:grid-cols-3 lg:grid-cols-1">
            <div
              v-for="item in sidebarStats"
              :key="item.label"
              class="rounded-[22px] border border-primary/10 bg-base-100/78 px-4 py-3 shadow-sm shadow-primary/5"
            >
              <div class="text-[11px] uppercase tracking-[0.18em] text-base-content/45">
                {{ item.label }}
              </div>
              <div class="mt-2 text-sm font-medium text-base-content/82">
                {{ item.value }}
              </div>
            </div>
          </div>

          <div
            v-if="props.mode === 'shell'"
            class="rounded-[24px] border border-base-content/10 bg-base-100/75 p-4"
          >
            <div class="flex items-center justify-between gap-3">
              <div class="text-[11px] uppercase tracking-[0.22em] text-base-content/45">
                Quick Commands
              </div>
              <button
                class="btn btn-ghost btn-xs px-2 normal-case"
                type="button"
                :disabled="!socketConnected"
                @click="primeCommand('clear', true)"
              >
                clear
              </button>
            </div>
            <div class="mt-3 flex flex-wrap gap-2">
              <button
                v-for="item in quickCommands"
                :key="item.command"
                class="btn btn-sm btn-ghost rounded-2xl border border-base-content/10 bg-base-100/80 font-mono text-[11px] font-normal normal-case"
                type="button"
                @click="primeCommand(item.command)"
              >
                {{ item.label }}
              </button>
            </div>
            <p class="mt-3 text-xs leading-5 text-base-content/55">
              点击后会先填入输入框，确认再执行，避免误触直接改动实例环境。
            </p>
          </div>

          <div class="mt-auto hidden rounded-[24px] border border-base-content/10 bg-base-100/60 px-4 py-3 text-xs leading-5 text-base-content/55 lg:block">
            {{ connectionHint }}
          </div>
        </div>
      </aside>

      <div class="flex min-w-0 flex-1 flex-col">
        <header
          class="flex flex-col gap-4 border-b border-base-content/10 px-4 py-4 sm:px-5 lg:flex-row lg:items-center lg:justify-between lg:px-6"
        >
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-lg font-semibold text-base-content/85">
                {{ props.mode === 'shell' ? 'Maintenance Terminal' : 'Runtime Log Stream' }}
              </span>
              <div class="badge badge-sm badge-ghost font-normal">
                {{ runtimeStateLabel }}
              </div>
            </div>
            <div class="mt-1 text-sm text-base-content/55">
              {{ connectionHint }}
            </div>
            <div v-if="props.mode === 'shell' && activeSession" class="mt-2 flex flex-wrap items-center gap-2 text-xs text-base-content/50">
              <span class="rounded-full bg-base-content/8 px-2 py-1 font-mono">
                {{ activeSession.title }}
              </span>
              <span>created {{ activeSessionCreatedAt }}</span>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <label
              v-if="props.mode === 'shell'"
              class="flex items-center gap-2 rounded-2xl border border-base-content/10 bg-base-100 px-3 py-2 text-xs text-base-content/60"
            >
              <span class="uppercase tracking-[0.18em]">Theme</span>
              <select
                v-model="selectedTheme"
                class="select select-sm min-h-0 border-0 bg-transparent pr-8 font-medium focus:outline-none"
              >
                <option
                  v-for="item in themeOptions"
                  :key="item.id"
                  :value="item.id"
                >
                  {{ item.label }}
                </option>
              </select>
            </label>

            <button
              v-if="props.mode === 'shell'"
              class="btn btn-sm btn-ghost rounded-2xl"
              type="button"
              :disabled="!canInterrupt"
              @click="sendInterrupt"
            >
              Ctrl+C
            </button>
          </div>
        </header>

        <div class="flex min-h-0 flex-1 flex-col p-3 sm:p-4 lg:p-5">
          <div
            v-if="props.mode === 'shell'"
            class="terminal-shell-panel flex min-h-0 flex-1 flex-col overflow-hidden rounded-[26px] border border-slate-900/80 bg-slate-950 shadow-inner"
            :class="terminalPaneHeightClass"
            :data-theme="selectedTheme"
          >
            <div class="flex items-center justify-between border-b border-white/5 px-4 py-3 text-xs text-slate-400">
              <div class="flex items-center gap-2">
                <span class="h-2.5 w-2.5 rounded-full bg-rose-400/90"></span>
                <span class="h-2.5 w-2.5 rounded-full bg-amber-300/90"></span>
                <span class="h-2.5 w-2.5 rounded-full bg-emerald-400/90"></span>
              </div>
              <div class="font-mono">{{ terminalSessionLabel }}</div>
            </div>
            <div ref="terminalRoot" class="terminal-shell min-h-0 flex-1"></div>
          </div>

          <div
            v-else
            class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[26px] border border-base-content/10 bg-slate-950 shadow-inner"
            :class="terminalPaneHeightClass"
          >
            <div class="flex items-center justify-between border-b border-white/5 px-4 py-3 text-xs text-slate-400">
              <span>Runtime Output</span>
              <span class="font-mono">{{ logData.length }} lines</span>
            </div>
            <div
              ref="runtimeLogWrap"
              class="min-h-0 flex-1 overflow-y-auto px-4 py-4 font-mono text-[13px] leading-6 text-slate-100"
            >
              <div
                v-for="(item, index) in logData"
                :key="`${item.time ?? 'log'}-${index}`"
                class="whitespace-pre-wrap break-all"
              >
                <span v-if="item.time" class="text-slate-500">{{ item.time }} </span>
                <span v-if="item.level" class="text-cyan-300">{{ item.level }} </span>
                <span>{{ item.message }}</span>
              </div>
            </div>
          </div>

          <form
            v-if="props.mode === 'shell'"
            class="mt-4 flex flex-col gap-3 rounded-[24px] border border-base-content/10 bg-base-100/75 p-4 backdrop-blur"
            @submit.prevent="sendCommand"
          >
            <div class="flex flex-col gap-3 xl:flex-row xl:items-center">
              <div
                class="flex flex-1 items-center rounded-[20px] border border-base-content/10 bg-base-300/40 px-3"
              >
                <div class="mr-3 font-mono text-xs text-base-content/45">$</div>
                <input
                  ref="commandInputRef"
                  v-model="commandInput"
                  class="h-12 flex-1 bg-transparent font-mono text-sm text-base-content/80 outline-none"
                  :placeholder="commandPlaceholder"
                  :disabled="!canWriteCommand"
                />
              </div>
              <div class="flex gap-2">
                <button
                  class="btn btn-sm btn-primary rounded-2xl px-5 text-base-100"
                  type="submit"
                  :disabled="!canWriteCommand"
                >
                  Run
                </button>
                <button
                  class="btn btn-sm btn-ghost rounded-2xl"
                  type="button"
                  :disabled="!socketConnected"
                  @click="primeCommand('pwd')"
                >
                  pwd
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.terminal-shell :deep(.xterm) {
  height: 100%;
  padding: 12px 14px;
}

.terminal-shell :deep(.xterm-viewport) {
  overflow-y: auto !important;
  scrollbar-width: none;
}

.terminal-shell :deep(.xterm-viewport::-webkit-scrollbar) {
  display: none;
}

.terminal-shell-panel[data-theme='paper'] {
  border-color: rgba(161, 98, 7, 0.45);
  background: #f7f4ec;
}

.terminal-shell-panel[data-theme='paper'] :deep(.xterm) {
  color: #3f3f46;
}
</style>
