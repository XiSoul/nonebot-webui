import { ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { v4 as uuidv4 } from 'uuid'
import { ProjectService } from '@/client/api'
import type { NoneBotProjectMeta } from '@/client/api'
import { getErrorMessage } from '@/client/utils'
import { useToastStore } from './ToastStore'
import { useStatusStore } from './StatusStore'

const ID_OF_ENV_STATUS = uuidv4()
const ID_OF_BOT_STATUS = uuidv4()
const SELECTED_BOT_KEY = 'selectedBot'

export const useNoneBotStore = defineStore('nonebotStore', () => {
  const bots = ref<{ [key: string]: NoneBotProjectMeta }>({})
  const selectedBot = ref<NoneBotProjectMeta>()
  const isLoadingBots = ref(false)
  let reloadQueued = false
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null

  const toast = useToastStore()
  const statusStore = useStatusStore()

  const loadSelectedFromStorage = () => {
    const raw = localStorage.getItem(SELECTED_BOT_KEY)
    if (!raw) return
    try {
      selectedBot.value = JSON.parse(raw) as NoneBotProjectMeta
    } catch {
      localStorage.removeItem(SELECTED_BOT_KEY)
    }
  }

  loadSelectedFromStorage()

  const getExtendedBotsList = (): NoneBotProjectMeta[] => {
    return Object.keys(bots.value).map((projectID) => ({
      projectID,
      ...bots.value[projectID]
    }))
  }

  const syncBotEnvState = (projectId: string, env: string) => {
    const target = bots.value[projectId]
    if (target) {
      target.use_env = env
    }

    if (selectedBot.value?.project_id === projectId && selectedBot.value) {
      selectedBot.value.use_env = env
      localStorage.setItem(SELECTED_BOT_KEY, JSON.stringify(selectedBot.value))
    }
  }

  const selectBot = (bot: NoneBotProjectMeta, silent = false) => {
    selectedBot.value = bot
    localStorage.setItem(SELECTED_BOT_KEY, JSON.stringify(bot))
    if (!silent) {
      toast.add('success', `已选择实例: ${bot.project_name}`, '', 3000)
    }
  }

  const loadBots = async () => {
    if (isLoadingBots.value) {
      reloadQueued = true
      return
    }

    isLoadingBots.value = true
    try {
      const { data } = await ProjectService.listProjectV1ProjectListGet()
      if (!data) return

      bots.value = data.detail
      const botList = Object.values(bots.value)
      if (!botList.length) {
        selectedBot.value = undefined
        localStorage.removeItem(SELECTED_BOT_KEY)
        return
      }

      if (selectedBot.value) {
        const synced = bots.value[selectedBot.value.project_id]
        if (synced) {
          selectedBot.value = synced
          localStorage.setItem(SELECTED_BOT_KEY, JSON.stringify(synced))
          return
        }
      }

      // Auto-fallback to first instance when current one is deleted.
      selectBot(botList[0], true)
    } finally {
      isLoadingBots.value = false
      if (reloadQueued) {
        reloadQueued = false
        void loadBots()
      }
    }
  }

  const startHeartbeat = (interval = 3000) => {
    if (heartbeatTimer) return
    heartbeatTimer = setInterval(() => {
      void loadBots()
    }, interval)
  }

  const stopHeartbeat = () => {
    if (!heartbeatTimer) return
    clearInterval(heartbeatTimer)
    heartbeatTimer = null
  }

  const updateBotEnv = async (projectId: string, env: string) => {
    const normalizedEnv = env.trim()
    if (!projectId || !normalizedEnv) return false

    const { data, error } = await ProjectService.useProjectEnvV1ProjectConfigEnvUsePost({
      query: {
        env: normalizedEnv,
        project_id: projectId
      }
    })

    if (error) {
      toast.add('error', `更新环境失败, 原因: ${getErrorMessage(error)}`, '', 5000)
      return false
    }

    if (data) {
      syncBotEnvState(projectId, normalizedEnv)
      toast.add('success', `环境已切换到 ${normalizedEnv}`, '', 3000)
      return true
    }

    return false
  }

  const updateEnv = async (env: string) => {
    if (!selectedBot.value) return false
    return updateBotEnv(selectedBot.value.project_id, env)
  }

  watch(
    () => selectedBot.value,
    (bot) => {
      if (!bot) return
      statusStore.update(ID_OF_BOT_STATUS, 'badge-ghost', `当前实例: ${bot.project_name}`)
      statusStore.update(ID_OF_ENV_STATUS, 'badge-ghost', `当前环境: ${bot.use_env}`)
    }
  )

  watch(
    () => selectedBot.value?.use_env,
    (env) => {
      statusStore.update(ID_OF_ENV_STATUS, 'badge-ghost', `当前环境: ${env}`)
    }
  )

  return {
    bots,
    selectedBot,
    getExtendedBotsList,
    selectBot,
    loadBots,
    startHeartbeat,
    stopHeartbeat,
    updateBotEnv,
    updateEnv
  }
})
