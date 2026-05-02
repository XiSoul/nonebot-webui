<script setup lang="ts">
import {
  ProjectService,
  StoreService,
  type Adapter as BaseAdapter,
  type Driver as BaseDriver,
  type nb_cli_plugin_webui__app__models__base__Plugin
} from '@/client/api'
import { updateProjectPlugin } from '@/client/store'
import { compareSemanticVersion, getErrorMessage } from '@/client/utils'
import router from '@/router'
import { useNoneBotStore, useToastStore } from '@/stores'
import { isRuntimeActive } from '@/utils/runtimeState'
import { useFetch } from '@vueuse/core'
import { computed, onMounted, ref } from 'vue'

const store = useNoneBotStore()
const toast = useToastStore()

interface Plugin extends nb_cli_plugin_webui__app__models__base__Plugin {
  valid?: boolean
  time?: string
  skip_test?: boolean
  latestVersion?: string
  releases?: string[]
  selectedVersion?: string
}

interface Adapter extends BaseAdapter {
  latestVersion?: string
}

interface Driver extends BaseDriver {
  latestVersion?: string
}

const pluginsRef = ref<Plugin[]>()
const adaptersRef = ref<Adapter[]>()
const driversRef = ref<Driver[]>()
const updatingPluginNames = ref<string[]>([])
const isModuleActionLocked = computed(() => isRuntimeActive(store.selectedBot))

const normalizePackageName = (value?: string) => {
  return `${value ?? ''}`.trim().replace(/[-_.]+/g, '-').replace(/^-+|-+$/g, '')
}

const resolvePluginPackageName = (plugin: Plugin) => {
  const rawSpec = `${plugin.project_link ?? ''}`.trim()
  let candidate = rawSpec

  if (candidate.startsWith('-e ')) {
    candidate = candidate.slice(3).trim()
  }

  if (candidate.includes(' @ ')) {
    candidate = candidate.split(' @ ', 1)[0]?.trim() ?? ''
  } else if (candidate.includes('@') && candidate.includes('://')) {
    candidate = candidate.split('@', 1)[0]?.trim() ?? ''
  }

  const matched = candidate.match(/[A-Za-z0-9][A-Za-z0-9_.-]*/)
  const packageName = normalizePackageName(matched?.[0])
  if (packageName && packageName !== 'unknown') {
    return packageName
  }

  for (const fallback of [plugin.module_name, plugin.name]) {
    const normalized = normalizePackageName(fallback)
    if (normalized && normalized !== 'unknown') {
      return normalized
    }
  }

  return ''
}

const ensureBotStopped = () => {
  if (!store.selectedBot) {
    toast.add('warning', '请先选择实例', '', 5000)
    return false
  }

  if (isRuntimeActive(store.selectedBot)) {
    toast.add('warning', '实例运行中，请先停止实例后再进行插件、适配器或驱动操作', '', 5000)
    return false
  }

  return true
}

const getPlugins = async () => {
  const { data } = await ProjectService.getPluginsV1ProjectPluginsGet({
    query: { project_id: store.selectedBot!.project_id }
  })

  if (data) pluginsRef.value = data.detail
}

const getAdapters = async () => {
  const { data } = await ProjectService.getAdaptersV1ProjectAdaptersGet({
    query: { project_id: store.selectedBot!.project_id }
  })

  if (data) adaptersRef.value = data.detail
}

const getDrivers = async () => {
  const { data } = await ProjectService.getDriversV1ProjectDriversGet({
    query: { project_id: store.selectedBot!.project_id }
  })

  if (data) driversRef.value = data.detail
}

const getData = async () => {
  if (!store.selectedBot) {
    toast.add('warning', '请先选择实例', '', 5000)
    return
  }

  await getPlugins()
  await getAdapters()
  await getDrivers()
  toast.add('info', '模块列表已刷新', '', 3000)
}

const updateLatestVersion = async () => {
  if (!store.selectedBot) {
    toast.add('warning', '请先选择实例', '', 5000)
    return
  }

  const fetchLatestVersion = async (packageName: string) => {
    if (!packageName) return null
    const url = `https://pypi.org/pypi/${packageName}/json`
    const { data } = await useFetch(url).json<{
      info: {
        version: string
      }
      releases: Record<string, any[]>
    }>()
    return data.value
  }

  if (pluginsRef.value) {
    pluginsRef.value = await Promise.all(
      pluginsRef.value.map(async (plugin: Plugin) => {
        plugin.latestVersion = 'ignore'
        const packageName = resolvePluginPackageName(plugin)
        const data = await fetchLatestVersion(packageName)
        if (data) {
          plugin.latestVersion = data.info.version
          plugin.releases = Object.keys(data.releases)
          plugin.selectedVersion = plugin.version
        }
        return plugin
      })
    )
  }

  toast.add('info', '版本检查完成', '', 3000)
}

onMounted(async () => {
  await getData()
  await updateLatestVersion()
})

const uninstall = async (module: Plugin | Adapter | Driver) => {
  if (!ensureBotStopped()) return

  const moduleType = 'valid' in module ? 'plugin' : 'module'
  const { data, error } = await StoreService.uninstallNonebotModuleV1StoreNonebotUninstallPost({
    query: {
      env: store.selectedBot!.use_env!,
      project_id: store.selectedBot!.project_id
    },
    // @ts-ignore
    body: {
      ...module,
      module_type: moduleType
    }
  })

  if (error) {
    toast.add('error', `卸载失败，原因：${getErrorMessage(error)}`, '', 5000)
    return
  }

  if (data) {
    await getData()
    toast.add('success', '卸载成功', '', 4000)
  }
}

const updatePlugin = async (plugin: Plugin) => {
  if (!ensureBotStopped()) return

  const projectId = store.selectedBot!.project_id
  const env = store.selectedBot!.use_env!
  const moduleName = plugin.module_name || ''
  const targetVersion =
    plugin.selectedVersion && plugin.selectedVersion !== plugin.version
      ? plugin.selectedVersion
      : plugin.latestVersion && compareSemanticVersion(plugin.version!, plugin.latestVersion) < 0
        ? plugin.latestVersion
        : ''

  updatingPluginNames.value.push(moduleName)
  toast.add('info', `开始更新插件 ${plugin.name}，可在实例终端查看详细日志`, '', 5000)

  const { data, error } = await updateProjectPlugin(projectId, env, {
    ...plugin,
    version: plugin.version ?? '0.0.0',
    valid: plugin.valid ?? true,
    time: plugin.time ?? '',
    skip_test: plugin.skip_test ?? false,
    module_type: 'plugin'
  }, targetVersion)

  updatingPluginNames.value = updatingPluginNames.value.filter((name) => name !== moduleName)

  if (error) {
    toast.add('error', `更新失败，原因：${getErrorMessage(error)}`, '', 5000)
    return
  }

  if (data) {
    await getData()
    await updateLatestVersion()
    toast.add('success', `${plugin.name} 更新完成`, '', 4000)
  }
}
</script>

<template>
  <div class="flex flex-col gap-4 w-full">
    <div class="w-full p-6 bg-base-200 rounded-box flex items-center">
      <div class="shrink-0 font-semibold text-lg">
        <h3>模块操作</h3>
      </div>

      <div class="w-full flex items-center justify-end gap-2">
        <span v-if="isModuleActionLocked" class="badge badge-warning">
          实例运行中，模块操作已锁定
        </span>
        <button class="btn btn-sm shadow-none btn-primary text-base-100" @click="updateLatestVersion()">
          检查更新
        </button>
        <button class="btn btn-sm shadow-none" @click="getData()">刷新</button>
      </div>
    </div>

    <div class="collapse bg-base-200">
      <input type="checkbox" />
      <div class="collapse-title p-6">
        <h3 class="font-semibold text-lg">插件管理</h3>
      </div>

      <div class="collapse-content px-4 overflow-x-auto relative pb-4">
        <table class="table table-sm">
          <thead>
            <tr>
              <th>名称</th>
              <th>本地版本</th>
              <th>远程版本</th>
              <th>版本列表</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="plugin in pluginsRef"
              :key="plugin.module_name"
              class="hover:bg-base-300 transition-colors"
            >
              <th class="flex item-center gap-2 whitespace-nowrap">
                <span>{{ plugin.name }}</span>
                <span
                  v-if="compareSemanticVersion(plugin.version!, plugin.latestVersion!) < 0"
                  class="badge badge-primary text-base-100 font-normal"
                >
                  可更新
                </span>
              </th>
              <td>{{ plugin.version }}</td>
              <td>{{ plugin.latestVersion }}</td>
              <td>
                <select
                  v-model="plugin.selectedVersion"
                  class="select select-sm"
                  :disabled="!plugin.releases || isModuleActionLocked"
                >
                  <option disabled>请选择</option>
                  <option v-for="version in plugin.releases" :key="version">
                    {{ version }}
                  </option>
                </select>
              </td>
              <td class="flex item-center gap-2">
                <button
                  class="btn btn-ghost btn-sm"
                  @click="router.push(`/settings?search=${plugin.module_name}`)"
                >
                  设置
                </button>
                <label class="swap btn btn-sm btn-ghost" :class="{ 'btn-disabled': isModuleActionLocked }">
                  <input type="checkbox" :disabled="isModuleActionLocked" />
                  <div class="swap-off" @click="uninstall(plugin)">卸载</div>
                  <div class="swap-on text-primary">确认</div>
                </label>
                <button
                  v-if="
                    compareSemanticVersion(plugin.version!, plugin.latestVersion!) < 0 ||
                    (plugin.version !== plugin.selectedVersion && plugin.selectedVersion)
                  "
                  class="btn btn-primary btn-sm text-base-100"
                  :disabled="isModuleActionLocked || updatingPluginNames.includes(plugin.module_name || '')"
                  @click="updatePlugin(plugin)"
                >
                  {{ updatingPluginNames.includes(plugin.module_name || '') ? '更新中' : '更新' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="collapse bg-base-200">
      <input type="checkbox" />
      <div class="collapse-title p-6">
        <h3 class="font-semibold text-lg">适配器管理</h3>
      </div>
      <div class="collapse-content px-4 pb-4">
        <div class="overflow-x-auto">
          <table class="table table-sm">
            <thead>
              <tr>
                <th>名称</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="adapter in adaptersRef"
                :key="adapter.module_name"
                class="hover:bg-base-300 transition-colors"
              >
                <th>{{ adapter.name }}</th>
                <td class="flex item-center gap-2">
                  <button
                    class="btn btn-ghost btn-sm"
                    @click="router.push(`/settings?search=${adapter.module_name}`)"
                  >
                    设置
                  </button>
                  <button class="btn btn-ghost btn-sm" :disabled="isModuleActionLocked">卸载</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="collapse bg-base-200">
      <input type="checkbox" />
      <div class="collapse-title p-6">
        <h3 class="font-semibold text-lg">驱动管理</h3>
      </div>
      <div class="collapse-content px-4 pb-4">
        <div class="overflow-x-auto">
          <table class="table table-sm">
            <thead>
              <tr>
                <th>名称</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="driver in driversRef"
                :key="driver.module_name"
                class="hover:bg-base-300 transition-colors"
              >
                <th>{{ driver.name }}</th>
                <td class="flex item-center gap-2">
                  <button
                    class="btn btn-ghost btn-sm"
                    @click="router.push(`/settings?search=${driver.module_name}`)"
                  >
                    设置
                  </button>
                  <button class="btn btn-ghost btn-sm" :disabled="isModuleActionLocked">卸载</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
