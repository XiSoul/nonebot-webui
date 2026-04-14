<script setup lang="ts">
import { ProcessService, type ProcessLog } from '@/client/api'
import { getAuthToken } from '@/client/auth'
import { generateURLForWebUI } from '@/client/utils'
import { useCustomStore, useNoneBotStore, useToastStore } from '@/stores'
import { useWebSocket } from '@vueuse/core'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

const store = useNoneBotStore()
const customStore = useCustomStore()
const toast = useToastStore()

const logData = ref<ProcessLog[]>([])
const logShowTable = ref<HTMLElement>()
const currentBot = ref("")
const commandInput = ref("")
const commandSending = ref(false)
let historyPollTimer: ReturnType<typeof setInterval> | null = null

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

const subscribeLog = (projectId?: string) => {
  const logKey = projectId ?? store.selectedBot?.project_id
  if (!logKey) return
  send(JSON.stringify({ type: "log", log_key: logKey }))
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
    toast.add("warning", `Get history logs failed: ${error.detail}`, "", 5000)
    return
  }

  if (data) {
    if (store.selectedBot?.project_id !== logId) return
    logData.value = data.detail
    await scrollToBottom()
  }
}

const writeToProcess = async (content: string, displayEcho?: string) => {
  if (!store.selectedBot) return
  if (!store.selectedBot.is_running) {
    toast.add("warning", "Bot is not running.", "", 3000)
    return
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
    toast.add("error", `Send command failed: ${error.detail}`, "", 5000)
    return
  }

  if (displayEcho) await appendLocalLog(displayEcho)
}

const sendCommand = async () => {
  const command = commandInput.value.trim()
  if (!command) return

  await writeToProcess(`${command}\n`, `> ${command}`)
  commandInput.value = ""
}

const sendInterrupt = async () => {
  if (!store.selectedBot) return
  if (!store.selectedBot.is_running) {
    toast.add("warning", "Bot is not running.", "", 3000)
    return
  }

  commandSending.value = true
  const { error } = await ProcessService.interruptProcessV1ProcessInterruptPost({
    query: {
      project_id: store.selectedBot.project_id
    }
  })
  commandSending.value = false

  if (error) {
    toast.add("error", `Send interrupt failed: ${error.detail}`, "", 5000)
    return
  }

  await appendLocalLog("^C")
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
        toast.add("success", "Debug: terminal websocket connected.", "TerminalItem.vue", 5000)
      }
    },
    onDisconnected() {
      if (!customStore.isDebug) return
      toast.add("warning", "Debug: terminal websocket disconnected.", "TerminalItem.vue", 5000)
    }
  }
)

const canWriteCommand = computed(
  () => Boolean(store.selectedBot?.is_running) && status.value === "OPEN"
)

onMounted(async () => {
  if (!store.selectedBot) return
  await getHistoryLogs(store.selectedBot.project_id)
  if (store.selectedBot.is_running) open()

  historyPollTimer = setInterval(() => {
    if (!store.selectedBot?.project_id) return
    void getHistoryLogs(store.selectedBot.project_id)
  }, 8000)
})

onUnmounted(() => {
  if (historyPollTimer) {
    clearInterval(historyPollTimer)
    historyPollTimer = null
  }
  close()
})

watch(
  () => data.value,
  async (rawData) => {
    if (!rawData) return

    const parsedData: ProcessLog = JSON.parse(rawData.toString())
    logData.value.push(parsedData)
    await scrollToBottom()
  }
)

watch(
  () => status.value,
  async (newStatus) => {
    if (newStatus !== "OPEN") return
    subscribeLog()
    await getHistoryLogs()
  }
)

watch(
  () => store.selectedBot?.project_id,
  async (projectId, previousProjectId) => {
    if (!projectId) {
      currentBot.value = ""
      logData.value = []
      close()
      return
    }

    if (projectId !== previousProjectId) {
      currentBot.value = projectId
      logData.value = []
      await getHistoryLogs(projectId)
    }

    if (store.selectedBot?.is_running) {
      if (status.value !== "OPEN") {
        open()
      } else {
        subscribeLog(projectId)
        await getHistoryLogs(projectId)
      }
    } else if (status.value === "OPEN") {
      close()
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
      if (status.value !== "OPEN") {
        open()
      } else {
        subscribeLog(projectId)
      }
      return
    }

    if (status.value === "OPEN") {
      close()
    }
  }
)

const retry = () => {
  if (store.selectedBot?.project_id !== currentBot.value) logData.value = []
  logData.value.push({
    message: "Retrying websocket connection..."
  })
  open()
}
</script>

<template>
  <div class="w-full p-6 rounded-box bg-base-200 flex flex-col gap-3">
    <div class="flex justify-between gap-4">
      <div class="flex items-center gap-3">
        <span class="font-semibold">Terminal Output</span>
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
      <input
        v-model="commandInput"
        class="input input-sm input-bordered flex-1 font-mono"
        placeholder="Type command, press Enter to send"
        :disabled="!canWriteCommand || commandSending"
      />
      <button
        class="btn btn-sm btn-primary text-base-100"
        type="submit"
        :disabled="!canWriteCommand || commandSending"
      >
        Send
      </button>
      <button
        class="btn btn-sm btn-warning"
        type="button"
        :disabled="!canWriteCommand || commandSending"
        @click="sendInterrupt"
      >
        Ctrl+C
      </button>
    </form>
  </div>
</template>
