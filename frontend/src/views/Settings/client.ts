import {
  type ConfigType,
  type ModuleType,
  type ModuleConfigFather,
  ProjectService,
  ConfigTypeSchema,
  ModuleTypeSchema
} from '@/client/api'
import { getErrorMessage } from '@/client/utils'
import { useNoneBotStore, useToastStore } from '@/stores'
import { defineStore } from 'pinia'
import { ref } from 'vue'

const store = useNoneBotStore()
const toast = useToastStore()

export type ModuleConfigType = ModuleType | ConfigType | 'all'

export const updateConfig = async (
  moduleType: ModuleType | ConfigType,
  confType: string,
  k: string,
  v: any
) => {
  if (!store.selectedBot) {
    toast.add('warning', '未选择实例', '', 5000)
    return
  }

  const wasRunning = Boolean(store.selectedBot.is_running)

  const { data, error } = await ProjectService.updateProjectConfigV1ProjectConfigUpdatePost({
    query: {
      module_type: moduleType,
      project_id: store.selectedBot.project_id
    },
    body: {
      env: store.selectedBot.use_env!,
      conf_type: confType,
      k,
      v
    }
  })

  if (error) {
    toast.add('error', `更新失败，原因：${getErrorMessage(error)}`, '', 5000)
  }

  if (data) {
    await store.loadBots()
    toast.add('success', wasRunning ? '更新成功，实例已自动重启' : '更新成功', '', 5000)
  }

  return { data, error }
}

export const useSettingsStore = defineStore('settingsStore', () => {
  const viewModule = ref<ModuleConfigType>('all')
  const settingsData = ref<ModuleConfigFather[]>([])
  const viewData = ref<ModuleConfigFather[]>([])
  const isRequesting = ref(false)
  const searchInput = ref<string>('')
  const hiddenProjectMetaKeys = new Set([
    'proxy_url',
    'container_proxy_url',
    'mirror_url',
    'http_proxy',
    'https_proxy',
    'all_proxy',
    'no_proxy',
    'debian_mirror',
    'pip_index_url',
    'pip_extra_index_url',
    'pip_trusted_host',
    'bot_use_global_proxy',
    'bot_http_proxy',
    'bot_https_proxy',
    'bot_all_proxy',
    'bot_no_proxy',
    'bot_proxy_protocol',
    'bot_proxy_host',
    'bot_proxy_port',
    'bot_proxy_username',
    'bot_proxy_password',
    'bot_proxy_apply_target',
    'bot_proxy_instances'
  ])

  const shouldHideProxyProperty = (name: string) => {
    const normalizedName = name.trim().toLowerCase()
    return (
      hiddenProjectMetaKeys.has(normalizedName) ||
      normalizedName.includes('proxy') ||
      normalizedName.includes('mirror') ||
      normalizedName.startsWith('pip_')
    )
  }

  const sanitizeModules = (modules: ModuleConfigFather[]) =>
    modules
      .map((item) => ({
        ...item,
        properties: item.properties.filter((prop) => !shouldHideProxyProperty(prop.name))
      }))
      .filter((item) => item.properties.length > 0)

  const getTomlConf = async (projectID: string) => {
    isRequesting.value = true
    const { data, error } = await ProjectService.getProjectMetaConfigV1ProjectConfigMetaDetailGet({
      query: {
        project_id: projectID
      }
    })

    if (error) {
      toast.add('error', `获取实例 toml 配置失败，原因：${getErrorMessage(error)}`, '', 5000)
    }

    if (data) {
      settingsData.value = settingsData.value.concat(sanitizeModules(data.detail))
    }

    isRequesting.value = false
  }

  const getNoneBotConf = async (projectID: string) => {
    isRequesting.value = true
    const { data, error } =
      await ProjectService.getProjectNonebotConfigV1ProjectConfigNonebotDetailGet({
        query: {
          project_id: projectID
        }
      })

    if (error) {
      toast.add('error', `获取实例 NoneBot 配置失败，原因：${getErrorMessage(error)}`, '', 5000)
    }

    if (data) {
      settingsData.value = settingsData.value.concat(sanitizeModules(data.detail))
    }

    isRequesting.value = false
  }

  const getNoneBotPluginConf = async (projectID: string) => {
    isRequesting.value = true
    const { data, error } =
      await ProjectService.getProjectNonebotPluginConfigV1ProjectConfigNonebotPluginDetailGet({
        query: {
          project_id: projectID
        }
      })

    if (error) {
      toast.add('error', `获取实例插件配置失败，原因：${getErrorMessage(error)}`, '', 5000)
    }

    if (data) {
      settingsData.value = settingsData.value.concat(sanitizeModules(data.detail))
    }

    isRequesting.value = false
  }

  const updateViewData = (searchText?: string) => {
    viewData.value = settingsData.value.filter((item) => {
      if (!searchText) return true
      return (
        item.title.includes(searchText) ||
        item.name.includes(searchText) ||
        (item.description ?? '').includes(searchText)
      )
    })

    const filter = [...ConfigTypeSchema.enum, ...ModuleTypeSchema.enum]
    if (viewModule.value !== 'all' && Object.values(filter).includes(viewModule.value)) {
      viewData.value = viewData.value.filter((item) => item.module_type === viewModule.value)
    }
  }

  const init = async () => {
    if (!store.selectedBot) {
      toast.add('warning', '未选择实例', '', 5000)
      settingsData.value = []
      viewData.value = []
      return
    }

    settingsData.value = []
    viewData.value = []

    const projectID = store.selectedBot.project_id

    await getTomlConf(projectID)
    await getNoneBotConf(projectID)
    await getNoneBotPluginConf(projectID)

    updateViewData(searchInput.value)
  }

  const setViewModule = (module: ModuleConfigType) => {
    viewModule.value = module
    searchInput.value = ''
    updateViewData()
  }

  return {
    viewModule,
    settingsData,
    viewData,
    isRequesting,
    searchInput,
    init,
    updateViewData,
    setViewModule
  }
})
