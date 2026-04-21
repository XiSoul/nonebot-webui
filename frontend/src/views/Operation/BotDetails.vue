<script setup lang="ts">
import { computed, ref, watch, type ComputedRef } from 'vue'
import router from '@/router'
import { useNoneBotStore } from '@/stores'
import { getContainerRuntimeSettings } from '@/views/Settings/container-client'
import { useInstanceMessageCount } from '@/composables/useInstanceMessageCount'
import type { NoneBotProjectMeta } from '@/client/api'

type detailItem = {
  title: string
  details?: ComputedRef<string[]>
  key?: string
}

type SelectedBotWithProxy = NoneBotProjectMeta & {
  bot_use_global_proxy?: boolean
  bot_http_proxy?: string
  bot_https_proxy?: string
  bot_all_proxy?: string
  bot_proxy_protocol?: string
  bot_proxy_host?: string
  bot_proxy_port?: string
  bot_proxy_username?: string
  bot_proxy_password?: string
}

const store = useNoneBotStore()
const selectedBot = computed(() => store.selectedBot as SelectedBotWithProxy | undefined)
const { messageCount: selectedBotMessageCount } = useInstanceMessageCount(selectedBot)

const detailShowModal = ref<HTMLDialogElement>(),
  detailShowModalTitle = ref(''),
  detailShowModalContent = ref<string[]>([])
const globalBotProxyUrl = ref('')

const maskProxySecret = (value: string) => {
  const text = value.trim()
  if (!text.includes('://') || !text.includes('@')) return text

  const [protocol, remainder] = text.split('://', 2)
  const atIndex = remainder.indexOf('@')
  if (atIndex < 0) return text

  const auth = remainder.slice(0, atIndex)
  const host = remainder.slice(atIndex + 1)
  const colonIndex = auth.indexOf(':')
  if (colonIndex < 0) {
    return `${protocol}://${auth}@${host}`
  }

  return `${protocol}://${auth.slice(0, colonIndex)}:***@${host}`
}

const buildProjectProxyUrl = (bot: SelectedBotWithProxy | undefined) => {
  if (!bot) return ''

  const existing =
    bot.bot_all_proxy?.trim() || bot.bot_http_proxy?.trim() || bot.bot_https_proxy?.trim() || ''
  if (existing) return existing

  const host = bot.bot_proxy_host?.trim() || ''
  const port = bot.bot_proxy_port?.trim() || ''
  if (!host || !port) return ''

  const protocol = bot.bot_proxy_protocol?.trim() || 'http'
  const username = bot.bot_proxy_username?.trim() || ''
  const password = bot.bot_proxy_password?.trim() || ''
  let auth = ''
  if (username || password) {
    auth = `${encodeURIComponent(username)}:${password ? '***' : ''}@`
  }

  return `${protocol}://${auth}${host}:${port}`
}

const proxyDisplay = computed(() => {
  const bot = selectedBot.value
  if (!bot) return ''

  const projectProxy = maskProxySecret(buildProjectProxyUrl(bot))
  if (!bot.bot_use_global_proxy) {
    return projectProxy ? `已开启：${projectProxy}` : ''
  }

  const globalProxy = maskProxySecret(globalBotProxyUrl.value)
  return globalProxy ? `已开启（跟随全局）：${globalProxy}` : ''
})

const basicItems: detailItem[] = [
  {
    title: '实例ID',
    details: computed(() => [selectedBot.value?.project_id ?? 'unknown'])
  },
  {
    title: '实例名称',
    details: computed(() => [selectedBot.value?.project_name ?? 'unknown'])
  },
  {
    title: '实例路径',
    details: computed(() => [selectedBot.value?.project_dir ?? 'unknown'])
  },
  {
    title: '实例 Python 镜像',
    details: computed(() => [selectedBot.value?.mirror_url ?? 'unknown'])
  },
  {
    title: '实例消息条数',
    details: computed(() => [`${selectedBotMessageCount.value}`])
  },
  {
    title: '实例代理',
    details: computed(() => (proxyDisplay.value ? [proxyDisplay.value] : []))
  }
]

const visibleBasicItems = computed(() =>
  basicItems.filter((item) => (item.details?.value.length ?? 0) > 0)
)

const installedItems: detailItem[] = [
  {
    key: 'plugin',
    title: '已配置插件',
    details: computed(() => selectedBot.value?.plugins.map((plugin) => plugin.name!) ?? [])
  },
  {
    key: 'plugin-dir',
    title: '本地插件目录',
    details: computed(() => selectedBot.value?.plugin_dirs ?? [])
  },
  {
    key: 'discovered-plugin-dir',
    title: '扫描到的候选插件目录',
    details: computed(() => selectedBot.value?.discovered_plugin_dirs ?? [])
  }
]

const loadGlobalBotProxy = async () => {
  if (!selectedBot.value?.bot_use_global_proxy) {
    globalBotProxyUrl.value = ''
    return
  }

  const { data, error } = await getContainerRuntimeSettings()
  if (error || !data) {
    globalBotProxyUrl.value = ''
    return
  }

  globalBotProxyUrl.value =
    data.bot_all_proxy?.trim() || data.bot_http_proxy?.trim() || data.bot_https_proxy?.trim() || ''
}

const openModal = (key: string) => {
  const target = installedItems.find((item) => item.key === key)
  detailShowModalTitle.value = target?.title ?? ''
  detailShowModalContent.value = target?.details?.value ?? []
  detailShowModal.value?.showModal()
}

watch(
  () => selectedBot.value?.project_id,
  () => {
    void loadGlobalBotProxy()
  },
  { immediate: true }
)
</script>

<template>
  <dialog ref="detailShowModal" class="modal">
    <div class="modal-box rounded-lg flex flex-col gap-4">
      <h3 class="font-semibold text-lg">{{ detailShowModalTitle }}详细</h3>

      <div class="flex flex-wrap gap-2">
        <div v-for="d in detailShowModalContent" :key="d" class="badge badge-ghost">
          {{ d }}
        </div>
        <div v-if="!detailShowModalContent.length">暂无数据</div>
      </div>

      <div class="flex justify-between">
        <div class="flex items-center gap-2">
          <button
            class="btn btn-sm btn-primary font-normal text-base-100"
            @click="router.push('/store'), detailShowModal?.close()"
          >
            管理
          </button>
        </div>

        <div class="flex items-center gap-2">
          <button class="btn btn-sm btn-ghost" @click="detailShowModal?.close()">关闭</button>
        </div>
      </div>
    </div>
  </dialog>

  <div class="grid gap-4 grid-cols-1 xl:grid-cols-2">
    <div class="w-full p-6 bg-base-200 rounded-box">
      <div class="overflow-x-auto">
        <table class="table table-sm">
          <tbody>
            <tr v-for="item in visibleBasicItems" :key="item.title">
              <td class="pl-0 text-base font-semibold">{{ item.title }}</td>
              <td>{{ item.details?.value[0] }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="w-full p-6 bg-base-200 rounded-box">
      <table class="table">
        <tbody>
          <tr v-for="item in installedItems" :key="item.title">
            <td class="pl-0 text-base font-semibold">{{ item.title }}</td>
            <td>
              <div class="badge">{{ item.details?.value.length }} 个</div>
            </td>
            <td class="flex justify-end pr-0">
              <button class="btn btn-sm btn-ghost" @click="openModal(item.key!)">详细</button>
            </td>
          </tr>
        </tbody>
      </table>

      <div class="mt-4 text-xs leading-6 opacity-70">
        这里只保留插件相关信息。
        <span class="font-mono">plugin_dirs</span> 是项目声明的本地插件目录，候选目录来自扫描结果，不会自动改写配置。
      </div>
    </div>
  </div>
</template>
