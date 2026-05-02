import { computed, onMounted, onUnmounted, ref, watch, type Ref } from 'vue'
import { getAuthToken } from '@/client/auth'
import { generateURLForWebUI } from '@/client/utils'
import type { NoneBotProjectMeta, ProcessLog } from '@/client/api'
import { getRuntimeState } from '@/utils/runtimeState'

const INSTANCE_MESSAGE_PATTERNS = [
  /"post_type"\s*:\s*"message"/i,
  /"message_type"\s*:/i,
  /\bmessage_id\b/i,
  /收到消息/i,
  /received message/i,
  /\bmessage from\b/i,
  /\buser message\b/i,
  /onebot.+message/i
]

const isInstanceMessageLog = (log: ProcessLog) => {
  const content = `${log.message ?? ''}`.trim()
  if (!content) return false
  return INSTANCE_MESSAGE_PATTERNS.some((pattern) => pattern.test(content))
}

const fetchProcessLogs = async (projectId: string) => {
  const token = getAuthToken()
  if (!token) return [] as ProcessLog[]

  const response = await fetch(
    generateURLForWebUI(
      `/v1/process/log/history?log_count=200&log_id=${encodeURIComponent(projectId)}`
    ),
    {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`
      }
    }
  )

  if (!response.ok) {
    return [] as ProcessLog[]
  }

  const payload = (await response.json()) as { detail?: ProcessLog[] }
  return payload.detail ?? []
}

export const useInstanceMessageCount = (
  selectedBot: Ref<NoneBotProjectMeta | undefined>,
  interval = 8000
) => {
  const messageCount = ref(0)
  let messagePollTimer: ReturnType<typeof setInterval> | null = null

  const syncMessageCount = async () => {
    const projectId = selectedBot.value?.project_id || ''
    if (!projectId || getRuntimeState(selectedBot.value) !== 'running') {
      messageCount.value = 0
      return
    }

    const logs = await fetchProcessLogs(projectId)

    if (selectedBot.value?.project_id !== projectId) {
      return
    }

    messageCount.value = logs.filter(isInstanceMessageLog).length
  }

  const clearMessagePollTimer = () => {
    if (!messagePollTimer) return
    clearInterval(messagePollTimer)
    messagePollTimer = null
  }

  const restartMessagePolling = () => {
    clearMessagePollTimer()
    void syncMessageCount()

    if (!selectedBot.value?.project_id || getRuntimeState(selectedBot.value) !== 'running') {
      return
    }

    messagePollTimer = setInterval(() => {
      void syncMessageCount()
    }, interval)
  }

  onMounted(() => {
    restartMessagePolling()
  })

  onUnmounted(() => {
    clearMessagePollTimer()
  })

  watch(
    computed(() => `${selectedBot.value?.project_id ?? ''}:${getRuntimeState(selectedBot.value)}`),
    () => {
      restartMessagePolling()
    }
  )

  return {
    messageCount,
    refreshMessageCount: syncMessageCount
  }
}
