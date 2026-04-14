<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useToastStore } from '@/stores'
import {
  applyContainerRuntimeProfile,
  deleteContainerRuntimeProfile,
  getContainerRuntimeProfiles,
  getContainerRuntimeSettings,
  saveContainerRuntimeProfile,
  testContainerRuntimeSettings,
  updateContainerRuntimeSettings,
  type ContainerRuntimeConnectivityItem,
  type ContainerRuntimeProfile,
  type ContainerRuntimeSettings
} from './container-client'

const toast = useToastStore()

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const profileSaving = ref(false)
const profileApplying = ref(false)
const profileDeleting = ref(false)
const isDocker = ref(false)
const currentPreset = ref('custom')
const newProfileName = ref('')
const selectedProfileName = ref('')
const testResults = ref<ContainerRuntimeConnectivityItem[]>([])
const testAllPassed = ref<boolean | null>(null)
const profiles = ref<ContainerRuntimeProfile[]>([])

type RuntimeForm = Omit<ContainerRuntimeSettings, 'is_docker'>

const createEmptyForm = (): RuntimeForm => ({
  proxy_url: '',
  http_proxy: '',
  https_proxy: '',
  all_proxy: '',
  no_proxy: '',
  debian_mirror: '',
  pip_index_url: '',
  pip_extra_index_url: '',
  pip_trusted_host: '',
  github_proxy_base_url: '',
  bot_http_proxy: '',
  bot_https_proxy: '',
  bot_all_proxy: '',
  bot_no_proxy: '',
  bot_proxy_protocol: 'http',
  bot_proxy_host: '',
  bot_proxy_port: '',
  bot_proxy_username: '',
  bot_proxy_password: '',
  bot_proxy_apply_target: 'http_https',
  bot_proxy_instances: ''
})

const form = ref<RuntimeForm>(createEmptyForm())

const buildSubmitPayload = (): RuntimeForm => ({
  ...form.value,
  http_proxy: '',
  https_proxy: '',
  all_proxy: ''
})

type SourcePreset = {
  id: string
  name: string
  debian_mirror: string
  pip_index_url: string
  pip_trusted_host: string
}

const presets: SourcePreset[] = [
  {
    id: 'official',
    name: '官方源',
    debian_mirror: '',
    pip_index_url: 'https://pypi.org/simple',
    pip_trusted_host: 'pypi.org files.pythonhosted.org'
  },
  {
    id: 'tuna',
    name: '清华 TUNA',
    debian_mirror: 'https://mirrors.tuna.tsinghua.edu.cn',
    pip_index_url: 'https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple',
    pip_trusted_host: 'mirrors.tuna.tsinghua.edu.cn'
  },
  {
    id: 'ustc',
    name: '中科大',
    debian_mirror: 'https://mirrors.ustc.edu.cn',
    pip_index_url: 'https://mirrors.ustc.edu.cn/pypi/web/simple',
    pip_trusted_host: 'mirrors.ustc.edu.cn'
  },
  {
    id: 'aliyun',
    name: '阿里云',
    debian_mirror: 'https://mirrors.aliyun.com',
    pip_index_url: 'https://mirrors.aliyun.com/pypi/simple',
    pip_trusted_host: 'mirrors.aliyun.com'
  },
  {
    id: 'huawei',
    name: '华为云',
    debian_mirror: 'https://repo.huaweicloud.com',
    pip_index_url: 'https://repo.huaweicloud.com/repository/pypi/simple',
    pip_trusted_host: 'repo.huaweicloud.com'
  }
]

const resetTestResults = () => {
  testResults.value = []
  testAllPassed.value = null
}

const applyPresetById = (presetId: string) => {
  const preset = presets.find((item) => item.id === presetId)
  if (!preset) return

  form.value.debian_mirror = preset.debian_mirror
  form.value.pip_index_url = preset.pip_index_url
  form.value.pip_extra_index_url = ''
  form.value.pip_trusted_host = preset.pip_trusted_host
  currentPreset.value = presetId
  resetTestResults()
}

const applyPreset = () => {
  if (currentPreset.value === 'custom') return
  applyPresetById(currentPreset.value)
  const preset = presets.find((item) => item.id === currentPreset.value)
  toast.add('success', `已应用预设：${preset?.name ?? currentPreset.value}`, '', 3000)
}

const clearVisibleFields = () => {
  form.value.proxy_url = ''
  form.value.http_proxy = ''
  form.value.https_proxy = ''
  form.value.all_proxy = ''
  form.value.no_proxy = ''
  form.value.debian_mirror = ''
  form.value.pip_index_url = ''
  form.value.pip_extra_index_url = ''
  form.value.pip_trusted_host = ''
  form.value.github_proxy_base_url = ''
  currentPreset.value = 'custom'
  resetTestResults()
}

const githubProxyPreview = computed(() => {
  const base = form.value.github_proxy_base_url.trim().replace(/\/+$/, '')
  if (!base) return ''
  return `${base}/https://github.com/nonebot/nonebot2`
})

const testSummaryClass = computed(() => {
  if (testAllPassed.value === null) return 'badge-ghost'
  return testAllPassed.value ? 'badge-success' : 'badge-warning'
})

const hasProfileSelection = computed(() => selectedProfileName.value.trim().length > 0)

const loadProfiles = async () => {
  const { data, error } = await getContainerRuntimeProfiles()
  if (error) {
    toast.add('error', `加载全局代理档案失败：${error}`, '', 5000)
    return
  }

  profiles.value = data ?? []
  if (!profiles.value.find((item) => item.name === selectedProfileName.value)) {
    selectedProfileName.value = ''
  }
}

const loadSettings = async () => {
  loading.value = true
  const { data, error } = await getContainerRuntimeSettings()
  loading.value = false

  if (error) {
    toast.add('error', `加载全局代理失败：${error}`, '', 5000)
    return
  }

  if (!data) return
  isDocker.value = data.is_docker
  form.value = {
    proxy_url: data.proxy_url,
    http_proxy: data.http_proxy,
    https_proxy: data.https_proxy,
    all_proxy: data.all_proxy,
    no_proxy: data.no_proxy,
    debian_mirror: data.debian_mirror,
    pip_index_url: data.pip_index_url,
    pip_extra_index_url: data.pip_extra_index_url,
    pip_trusted_host: data.pip_trusted_host,
    github_proxy_base_url: data.github_proxy_base_url,
    bot_http_proxy: data.bot_http_proxy,
    bot_https_proxy: data.bot_https_proxy,
    bot_all_proxy: data.bot_all_proxy,
    bot_no_proxy: data.bot_no_proxy,
    bot_proxy_protocol: data.bot_proxy_protocol,
    bot_proxy_host: data.bot_proxy_host,
    bot_proxy_port: data.bot_proxy_port,
    bot_proxy_username: data.bot_proxy_username,
    bot_proxy_password: data.bot_proxy_password,
    bot_proxy_apply_target: data.bot_proxy_apply_target,
    bot_proxy_instances: data.bot_proxy_instances ?? ''
  }
  resetTestResults()
}

const saveSettings = async () => {
  saving.value = true
  const { error } = await updateContainerRuntimeSettings(buildSubmitPayload())
  saving.value = false

  if (error) {
    toast.add('error', `保存全局代理失败：${error}`, '', 5000)
    return
  }

  toast.add('success', '全局代理已保存并生效', '', 4000)
}

const runConnectivityTest = async () => {
  testing.value = true
  const { data, error } = await testContainerRuntimeSettings(buildSubmitPayload(), 'quick')
  testing.value = false

  if (error) {
    toast.add('error', `连通性测试失败：${error}`, '', 5000)
    return
  }

  if (!data) return
  testResults.value = data.results
  testAllPassed.value = data.ok
  toast.add(
    data.ok ? 'success' : 'warning',
    data.ok ? '连通性测试通过' : '连通性测试存在失败项',
    '',
    4000
  )
}

const saveCurrentAsProfile = async () => {
  const name = newProfileName.value.trim()
  if (!name) {
    toast.add('warning', '请先填写档案名称', '', 3000)
    return
  }

  profileSaving.value = true
  const { error } = await saveContainerRuntimeProfile(name, buildSubmitPayload())
  profileSaving.value = false

  if (error) {
    toast.add('error', `保存档案失败：${error}`, '', 5000)
    return
  }

  newProfileName.value = ''
  selectedProfileName.value = name
  await loadProfiles()
  toast.add('success', `已保存档案：${name}`, '', 3000)
}

const loadSelectedProfileToForm = () => {
  const profile = profiles.value.find((item) => item.name === selectedProfileName.value)
  if (!profile) {
    toast.add('warning', '请先选择档案', '', 3000)
    return
  }

  form.value = { ...profile }
  currentPreset.value = 'custom'
  resetTestResults()
  toast.add('success', `已加载档案：${profile.name}`, '', 3000)
}

const applySelectedProfile = async () => {
  const name = selectedProfileName.value.trim()
  if (!name) {
    toast.add('warning', '请先选择档案', '', 3000)
    return
  }

  profileApplying.value = true
  const { error } = await applyContainerRuntimeProfile(name)
  profileApplying.value = false

  if (error) {
    toast.add('error', `应用档案失败：${error}`, '', 5000)
    return
  }

  await loadSettings()
  await loadProfiles()
  toast.add('success', `已应用档案：${name}`, '', 3000)
}

const deleteSelectedProfile = async () => {
  const name = selectedProfileName.value.trim()
  if (!name) {
    toast.add('warning', '请先选择档案', '', 3000)
    return
  }

  if (!window.confirm(`确认删除档案「${name}」吗？`)) return

  profileDeleting.value = true
  const { error } = await deleteContainerRuntimeProfile(name)
  profileDeleting.value = false

  if (error) {
    toast.add('error', `删除档案失败：${error}`, '', 5000)
    return
  }

  selectedProfileName.value = ''
  await loadProfiles()
  toast.add('success', `已删除档案：${name}`, '', 3000)
}

onMounted(async () => {
  await Promise.all([loadSettings(), loadProfiles()])
})
</script>

<template>
  <div class="w-full p-6 bg-base-200 rounded-box flex flex-col gap-4">
    <div class="flex flex-col gap-2">
      <h2 class="text-xl font-semibold">全局代理与镜像源</h2>
      <div class="text-sm opacity-70">
        这里用于配置 Docker 运行环境代理、Linux 镜像源、pip 源，以及 GitHub 链接拼接式加速地址。
      </div>
      <div class="text-xs opacity-60">当前运行环境：{{ isDocker ? 'Docker' : '非 Docker' }}</div>
      <div class="bg-base-content/10 h-[1px]"></div>
    </div>

    <div v-if="loading" class="text-sm opacity-70">加载中...</div>

    <div v-else class="flex flex-col gap-4">
      <div class="p-3 rounded-lg bg-base-100 flex flex-col md:flex-row gap-2 md:items-center">
        <span class="text-sm opacity-70 min-w-fit">一键预设</span>
        <select v-model="currentPreset" class="select select-sm select-bordered flex-1">
          <option value="custom">自定义</option>
          <option v-for="preset in presets" :key="preset.id" :value="preset.id">
            {{ preset.name }}
          </option>
        </select>
        <button class="btn btn-sm" :disabled="currentPreset === 'custom'" @click="applyPreset">
          应用预设
        </button>
        <button class="btn btn-sm btn-ghost" @click="clearVisibleFields">清空</button>
      </div>

      <div class="p-3 rounded-lg bg-base-100 flex flex-col gap-2">
        <div class="flex flex-col md:flex-row gap-2 md:items-center">
          <span class="text-sm opacity-70 min-w-fit">配置档案</span>
          <input
            v-model="newProfileName"
            class="input input-sm input-bordered md:w-64"
            placeholder="例如：home-proxy"
          />
          <button
            class="btn btn-sm"
            :disabled="profileSaving || profileApplying || profileDeleting"
            @click="saveCurrentAsProfile"
          >
            {{ profileSaving ? '保存中...' : '保存当前配置' }}
          </button>
        </div>

        <div class="flex flex-col md:flex-row gap-2 md:items-center">
          <select v-model="selectedProfileName" class="select select-sm select-bordered flex-1">
            <option value="">选择档案</option>
            <option v-for="profile in profiles" :key="profile.name" :value="profile.name">
              {{ profile.name }}
            </option>
          </select>
          <button class="btn btn-sm btn-ghost" :disabled="!hasProfileSelection" @click="loadSelectedProfileToForm">
            加载到表单
          </button>
          <button
            class="btn btn-sm"
            :disabled="!hasProfileSelection || profileSaving || profileApplying || profileDeleting"
            @click="applySelectedProfile"
          >
            {{ profileApplying ? '应用中...' : '应用档案' }}
          </button>
          <button
            class="btn btn-sm btn-outline btn-error"
            :disabled="!hasProfileSelection || profileSaving || profileApplying || profileDeleting"
            @click="deleteSelectedProfile"
          >
            {{ profileDeleting ? '删除中...' : '删除档案' }}
          </button>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label class="form-control w-full md:col-span-2">
          <div class="label py-1"><span class="label-text">全局代理地址</span></div>
          <input
            v-model="form.proxy_url"
            class="input input-sm input-bordered font-mono"
            placeholder="例如：http://127.0.0.1:7890 或 socks5://127.0.0.1:1080"
          />
          <div class="label pt-1 pb-0">
            <span class="label-text-alt opacity-70">
              一个输入框同时作用于 HTTP/HTTPS；当填写 socks4、socks5、socks5h 时会同时写入 ALL_PROXY。
            </span>
          </div>
        </label>
        <label class="form-control w-full md:col-span-2">
          <div class="label py-1"><span class="label-text">NO_PROXY</span></div>
          <input
            v-model="form.no_proxy"
            class="input input-sm input-bordered font-mono"
            placeholder="127.0.0.1,localhost,.internal"
          />
        </label>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label class="form-control w-full md:col-span-2">
          <div class="label py-1"><span class="label-text">GitHub 加速代理地址</span></div>
          <input
            v-model="form.github_proxy_base_url"
            class="input input-sm input-bordered font-mono"
            placeholder="https://github.xisoul.cn"
          />
        </label>
        <div class="w-full md:col-span-2 p-3 rounded-lg bg-base-100 flex flex-col gap-1">
          <div class="text-sm opacity-80">拼接示例</div>
          <code class="text-xs break-all">
            {{ githubProxyPreview || '填写后将按 “代理地址/原始 GitHub 链接” 方式拼接，例如 https://github.xisoul.cn/https://github.com/nonebot/nonebot2' }}
          </code>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label class="form-control w-full md:col-span-2">
          <div class="label py-1"><span class="label-text">Debian/APT 镜像源</span></div>
          <input v-model="form.debian_mirror" class="input input-sm input-bordered font-mono" />
        </label>
        <label class="form-control w-full md:col-span-2">
          <div class="label py-1"><span class="label-text">PIP_INDEX_URL</span></div>
          <input v-model="form.pip_index_url" class="input input-sm input-bordered font-mono" />
        </label>
        <label class="form-control w-full md:col-span-2">
          <div class="label py-1"><span class="label-text">PIP_EXTRA_INDEX_URL</span></div>
          <input
            v-model="form.pip_extra_index_url"
            class="input input-sm input-bordered font-mono"
          />
        </label>
        <label class="form-control w-full md:col-span-2">
          <div class="label py-1"><span class="label-text">PIP_TRUSTED_HOST</span></div>
          <input
            v-model="form.pip_trusted_host"
            class="input input-sm input-bordered font-mono"
          />
        </label>
      </div>

      <div class="flex flex-wrap items-center justify-end gap-2">
        <button class="btn btn-sm" :disabled="testing || saving" @click="runConnectivityTest">
          {{ testing ? '测试中...' : '连通性测试' }}
        </button>
        <button class="btn btn-sm btn-primary text-base-100" :disabled="saving" @click="saveSettings">
          {{ saving ? '保存中...' : '保存并应用' }}
        </button>
      </div>

      <div v-if="testAllPassed !== null" class="flex items-center gap-2">
        <span class="badge" :class="testSummaryClass">
          {{ testAllPassed ? 'PASS' : 'PARTIAL FAIL' }}
        </span>
        <span class="text-xs opacity-70">{{ testResults.length }} 项检测</span>
      </div>

      <div v-if="testResults.length" class="overflow-x-auto rounded-box border border-base-content/10">
        <table class="table table-xs">
          <thead>
            <tr>
              <th>项目</th>
              <th>状态</th>
              <th>HTTP</th>
              <th>延迟</th>
              <th>目标</th>
              <th>错误</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in testResults" :key="`${item.name}-${item.target}`">
              <td class="font-mono">{{ item.name }}</td>
              <td>
                <span
                  class="badge badge-xs"
                  :class="item.skipped ? 'badge-ghost' : item.ok ? 'badge-success' : 'badge-warning'"
                >
                  {{ item.skipped ? 'SKIP' : item.ok ? 'OK' : 'FAIL' }}
                </span>
              </td>
              <td>{{ item.status_code || '-' }}</td>
              <td>{{ item.elapsed_ms }}ms</td>
              <td class="font-mono break-all">{{ item.target }}</td>
              <td class="font-mono break-all text-xs">{{ item.error || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
