<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ProjectService } from '@/client/api'
import { useNoneBotStore, useToastStore } from '@/stores'

type ProxyProtocol = 'http' | 'https' | 'socks4' | 'socks5' | 'socks5h'
type ProxyApplyTarget = 'http_https' | 'all_proxy' | 'http_only' | 'https_only'

type ProjectBotProxyForm = {
  bot_use_global_proxy: boolean
  bot_no_proxy: string
  bot_proxy_protocol: ProxyProtocol
  bot_proxy_host: string
  bot_proxy_port: string
  bot_proxy_username: string
  bot_proxy_password: string
  bot_proxy_apply_target: ProxyApplyTarget
}

const labels = {
  title: '实例代理',
  desc: '这里是当前实例的独立代理设置。默认继承“全局代理”里的配置；关闭继承后，只有当前实例走这里的代理。',
  loading: '加载中...',
  useGlobal: '使用全局代理',
  inheritDesc: '当前实例将继承左侧“全局代理”中的机器人网络代理配置。',
  protocol: '代理协议',
  applyTarget: '应用目标',
  host: '代理主机',
  port: '代理端口',
  username: '用户名（可选）',
  password: '密码（可选）',
  noProxy: 'NO_PROXY（可选）',
  preview: '代理预览',
  save: '保存实例代理',
  saving: '保存中...',
  hostPlaceholder: '192.168.1.10',
  portPlaceholder: '7890',
  noProxyPlaceholder: '127.0.0.1,localhost,.internal',
  loadError: '加载实例代理失败',
  selectBot: '未选择实例',
  noChanges: '没有需要保存的改动',
  invalidHostPort: '请填写正确的代理主机和端口',
  saveError: '保存实例代理失败',
  saveSuccess: '实例代理已保存'
}

const defaultForm = (): ProjectBotProxyForm => ({
  bot_use_global_proxy: true,
  bot_no_proxy: '',
  bot_proxy_protocol: 'http',
  bot_proxy_host: '',
  bot_proxy_port: '',
  bot_proxy_username: '',
  bot_proxy_password: '',
  bot_proxy_apply_target: 'http_https'
})

const protocolOptions: Array<{ label: string; value: ProxyProtocol }> = [
  { label: 'HTTP', value: 'http' },
  { label: 'HTTPS', value: 'https' },
  { label: 'SOCKS4', value: 'socks4' },
  { label: 'SOCKS5', value: 'socks5' },
  { label: 'SOCKS5H', value: 'socks5h' }
]

const applyTargetOptions: Array<{ label: string; value: ProxyApplyTarget }> = [
  { label: 'HTTP + HTTPS', value: 'http_https' },
  { label: 'ALL_PROXY', value: 'all_proxy' },
  { label: '仅 HTTP', value: 'http_only' },
  { label: '仅 HTTPS', value: 'https_only' }
]

const store = useNoneBotStore()
const toast = useToastStore()

const loading = ref(false)
const saving = ref(false)
const form = ref<ProjectBotProxyForm>(defaultForm())
const snapshot = ref<ProjectBotProxyForm>(defaultForm())

const buildProxyUrl = (maskPassword = false) => {
  const host = form.value.bot_proxy_host.trim()
  const port = form.value.bot_proxy_port.trim()
  if (!host || !port) return ''

  const username = form.value.bot_proxy_username.trim()
  const password = form.value.bot_proxy_password.trim()
  let auth = ''
  if (username || password) {
    const encodedUser = encodeURIComponent(username)
    const encodedPassword = encodeURIComponent(password)
    auth = `${encodedUser}:${maskPassword ? '***' : encodedPassword}@`
  }

  return `${form.value.bot_proxy_protocol}://${auth}${host}:${port}`
}

const proxyPreview = computed(() => buildProxyUrl(true))
const canSave = computed(() => {
  if (form.value.bot_use_global_proxy) return true
  const host = form.value.bot_proxy_host.trim()
  const port = form.value.bot_proxy_port.trim()
  return !!host && /^\d+$/.test(port)
})
const hasChanges = computed(() => JSON.stringify(form.value) !== JSON.stringify(snapshot.value))

const loadProfile = async () => {
  const bot = store.selectedBot
  if (!bot) {
    form.value = defaultForm()
    snapshot.value = defaultForm()
    return
  }

  loading.value = true
  const { data, error } = await ProjectService.getProjectProfileV1ProjectProfileGet({
    query: { project_id: bot.project_id }
  })
  loading.value = false

  if (error || !data?.detail) {
    toast.add('error', `${labels.loadError}: ${error?.detail ?? ''}`, '', 5000)
    return
  }

  const detail = data.detail as any
  form.value = {
    bot_use_global_proxy: Boolean(detail.bot_use_global_proxy ?? true),
    bot_no_proxy: String(detail.bot_no_proxy ?? ''),
    bot_proxy_protocol: (detail.bot_proxy_protocol ?? 'http') as ProxyProtocol,
    bot_proxy_host: String(detail.bot_proxy_host ?? ''),
    bot_proxy_port: String(detail.bot_proxy_port ?? ''),
    bot_proxy_username: String(detail.bot_proxy_username ?? ''),
    bot_proxy_password: String(detail.bot_proxy_password ?? ''),
    bot_proxy_apply_target: (detail.bot_proxy_apply_target ?? 'http_https') as ProxyApplyTarget
  }
  snapshot.value = JSON.parse(JSON.stringify(form.value))
}

const saveProfile = async () => {
  const bot = store.selectedBot
  if (!bot) {
    toast.add('warning', labels.selectBot, '', 3000)
    return
  }
  if (!hasChanges.value) {
    toast.add('warning', labels.noChanges, '', 3000)
    return
  }
  if (!canSave.value) {
    toast.add('warning', labels.invalidHostPort, '', 3000)
    return
  }

  const proxyUrl = form.value.bot_use_global_proxy ? '' : buildProxyUrl(false)
  const updates: Record<string, string | boolean> = {
    bot_use_global_proxy: form.value.bot_use_global_proxy,
    bot_no_proxy: form.value.bot_use_global_proxy ? '' : form.value.bot_no_proxy.trim(),
    bot_proxy_protocol: form.value.bot_use_global_proxy ? 'http' : form.value.bot_proxy_protocol,
    bot_proxy_host: form.value.bot_use_global_proxy ? '' : form.value.bot_proxy_host.trim(),
    bot_proxy_port: form.value.bot_use_global_proxy ? '' : form.value.bot_proxy_port.trim(),
    bot_proxy_username: form.value.bot_use_global_proxy ? '' : form.value.bot_proxy_username.trim(),
    bot_proxy_password: form.value.bot_use_global_proxy ? '' : form.value.bot_proxy_password,
    bot_proxy_apply_target: form.value.bot_use_global_proxy ? 'http_https' : form.value.bot_proxy_apply_target,
    bot_http_proxy: '',
    bot_https_proxy: '',
    bot_all_proxy: ''
  }

  if (!form.value.bot_use_global_proxy) {
    switch (form.value.bot_proxy_apply_target) {
      case 'all_proxy':
        updates.bot_all_proxy = proxyUrl
        break
      case 'http_only':
        updates.bot_http_proxy = proxyUrl
        break
      case 'https_only':
        updates.bot_https_proxy = proxyUrl
        break
      default:
        updates.bot_http_proxy = proxyUrl
        updates.bot_https_proxy = proxyUrl
        break
    }
  }

  saving.value = true
  for (const [key, value] of Object.entries(updates)) {
    const confType = typeof value === 'boolean' ? 'boolean' : 'string'
    const { error } = await ProjectService.updateProjectConfigV1ProjectConfigUpdatePost({
      query: {
        module_type: 'toml',
        project_id: bot.project_id
      },
      body: {
        env: bot.use_env || '.env',
        conf_type: confType,
        k: key,
        v: value
      }
    })
    if (error) {
      saving.value = false
      toast.add('error', `${labels.saveError}: ${error.detail ?? ''}`, '', 5000)
      return
    }
  }

  saving.value = false
  snapshot.value = JSON.parse(JSON.stringify(form.value))
  toast.add('success', labels.saveSuccess, '', 4000)
}

watch(
  () => store.selectedBot?.project_id,
  () => {
    loadProfile()
  },
  { immediate: true }
)
</script>

<template>
  <div class="w-full p-6 bg-base-200 rounded-box flex flex-col gap-4">
    <div class="flex flex-col gap-2">
      <h2 class="text-xl font-semibold">{{ labels.title }}</h2>
      <div class="text-sm opacity-70">{{ labels.desc }}</div>
      <div class="bg-base-content/10 h-[1px]"></div>
    </div>

    <div v-if="loading" class="text-sm opacity-70">{{ labels.loading }}</div>

    <div v-else class="flex flex-col gap-4">
      <label class="cursor-pointer label justify-start gap-2 p-0">
        <input v-model="form.bot_use_global_proxy" type="checkbox" class="toggle toggle-sm" />
        <span class="label-text">{{ labels.useGlobal }}</span>
      </label>

      <div v-if="form.bot_use_global_proxy" class="text-xs opacity-70">{{ labels.inheritDesc }}</div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label class="form-control w-full">
          <div class="label py-1"><span class="label-text">{{ labels.protocol }}</span></div>
          <select v-model="form.bot_proxy_protocol" class="select select-sm select-bordered">
            <option v-for="item in protocolOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </option>
          </select>
        </label>

        <label class="form-control w-full">
          <div class="label py-1"><span class="label-text">{{ labels.applyTarget }}</span></div>
          <select v-model="form.bot_proxy_apply_target" class="select select-sm select-bordered">
            <option v-for="item in applyTargetOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </option>
          </select>
        </label>

        <label class="form-control w-full">
          <div class="label py-1"><span class="label-text">{{ labels.host }}</span></div>
          <input
            v-model="form.bot_proxy_host"
            class="input input-sm input-bordered font-mono"
            :placeholder="labels.hostPlaceholder"
          />
        </label>

        <label class="form-control w-full">
          <div class="label py-1"><span class="label-text">{{ labels.port }}</span></div>
          <input
            v-model="form.bot_proxy_port"
            class="input input-sm input-bordered font-mono"
            :placeholder="labels.portPlaceholder"
          />
        </label>

        <label class="form-control w-full">
          <div class="label py-1"><span class="label-text">{{ labels.username }}</span></div>
          <input v-model="form.bot_proxy_username" class="input input-sm input-bordered font-mono" />
        </label>

        <label class="form-control w-full">
          <div class="label py-1"><span class="label-text">{{ labels.password }}</span></div>
          <input
            v-model="form.bot_proxy_password"
            type="password"
            class="input input-sm input-bordered font-mono"
          />
        </label>

        <label class="form-control w-full md:col-span-2">
          <div class="label py-1"><span class="label-text">{{ labels.noProxy }}</span></div>
          <input
            v-model="form.bot_no_proxy"
            class="input input-sm input-bordered font-mono"
            :placeholder="labels.noProxyPlaceholder"
          />
        </label>

        <div class="w-full md:col-span-2 p-3 rounded-lg bg-base-100 flex flex-col gap-2">
          <div class="text-sm opacity-80">{{ labels.preview }}</div>
          <code class="text-xs break-all">{{ proxyPreview || '-' }}</code>
        </div>
      </div>

      <div class="flex justify-end">
        <button
          class="btn btn-sm btn-primary text-base-100"
          :disabled="saving || !canSave"
          @click="saveProfile"
        >
          {{ saving ? labels.saving : labels.save }}
        </button>
      </div>
    </div>
  </div>
</template>
