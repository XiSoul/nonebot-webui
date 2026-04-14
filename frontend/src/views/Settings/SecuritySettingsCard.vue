<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import router from '@/router'
import { clearAuthToken } from '@/client/auth'
import { useToastStore } from '@/stores'
import {
  getSecuritySettings,
  updateSecuritySettings,
  type SecuritySettings
} from './security-client'

type TokenMode = 'permanent' | 'random'

const toast = useToastStore()

const loading = ref(false)
const saving = ref(false)
const warningModal = ref<HTMLDialogElement | null>(null)

const settings = ref<SecuritySettings | null>(null)
const servicePort = ref<string | number>('18080')
const tokenMode = ref<TokenMode>('permanent')
const randomTokenExpireHours = ref<string | number>('24')
const currentToken = ref('')
const newToken = ref('')
const confirmToken = ref('')

const showCurrentToken = ref(false)
const showNewToken = ref(false)
const showConfirmToken = ref(false)

const tokenRules = [
  {
    id: 'length',
    label: '至少 10 位',
    check: (value: string) => value.length >= 10
  },
  {
    id: 'digit',
    label: '包含至少 1 个数字',
    check: (value: string) => /\d/.test(value)
  },
  {
    id: 'lowercase',
    label: '包含至少 1 个小写字母',
    check: (value: string) => /[a-z]/.test(value)
  },
  {
    id: 'uppercase',
    label: '包含至少 1 个大写字母',
    check: (value: string) => /[A-Z]/.test(value)
  },
  {
    id: 'special',
    label: '包含至少 1 个特殊字符',
    check: (value: string) => /[ !@#$%^&*()_+\-=\[\]{};':"\\|,.<>/?]/.test(value)
  }
] as const

const isDocker = computed(() => settings.value?.is_docker ?? false)
const isRandomMode = computed(() => tokenMode.value === 'random')
const currentPort = computed(() => settings.value?.service_port ?? 18080)
const currentHost = computed(() => settings.value?.service_host || '0.0.0.0')
const currentTokenMode = computed<TokenMode>(() => settings.value?.token_mode || 'permanent')
const currentRandomTokenExpireHours = computed(() => settings.value?.random_token_expire_hours ?? 24)
const currentTokenExpiresAt = computed(() => settings.value?.token_expires_at ?? 0)

const normalizedPort = computed(() => String(servicePort.value ?? '').trim())
const normalizedRandomTokenExpireHours = computed(() =>
  String(randomTokenExpireHours.value ?? '').trim()
)
const normalizedCurrentToken = computed(() => currentToken.value.trim())
const normalizedNewToken = computed(() => newToken.value.trim())
const normalizedConfirmToken = computed(() => confirmToken.value.trim())
const hasPortChange = computed(() => normalizedPort.value !== String(currentPort.value))

const randomTokenHoursChanged = computed(() => {
  if (!isRandomMode.value) return false
  return normalizedRandomTokenExpireHours.value !== String(currentRandomTokenExpireHours.value)
})

const requiresManualTokenInput = computed(() => tokenMode.value === 'permanent')
const canEditNewToken = computed(
  () => requiresManualTokenInput.value && normalizedCurrentToken.value.length > 0
)
const isConfirmFilled = computed(() => normalizedConfirmToken.value.length > 0)
const isConfirmMatched = computed(
  () =>
    normalizedNewToken.value.length > 0 &&
    normalizedConfirmToken.value.length > 0 &&
    normalizedNewToken.value === normalizedConfirmToken.value
)

const hasTokenChange = computed(() => {
  if (tokenMode.value !== currentTokenMode.value) {
    return true
  }

  if (tokenMode.value === 'random') {
    return randomTokenHoursChanged.value
  }

  return normalizedNewToken.value.length > 0
})

const evaluatedRules = computed(() =>
  tokenRules.map((rule) => ({
    ...rule,
    active: normalizedNewToken.value.length > 0,
    passed: rule.check(normalizedNewToken.value)
  }))
)

const currentRandomTokenExpiryText = computed(() => {
  if (!currentTokenExpiresAt.value || currentTokenMode.value !== 'random') {
    return '未启用随机 token'
  }
  return new Date(currentTokenExpiresAt.value * 1000).toLocaleString()
})

const createTargetUrl = (port: number, path: string) => {
  const target = new URL(window.location.href)
  target.port = String(port)
  target.pathname = path
  target.search = ''
  target.hash = ''
  return target.toString()
}

const getRuleClass = (active: boolean, passed: boolean) => {
  if (!active) return 'border-base-content/10 bg-base-100 text-base-content/70'
  return passed
    ? 'border-success/30 bg-success/10 text-success'
    : 'border-error/30 bg-error/10 text-error'
}

const getEyeIcon = (visible: boolean) => (visible ? 'visibility_off' : 'visibility')

const resetTokenInputs = () => {
  currentToken.value = ''
  newToken.value = ''
  confirmToken.value = ''
  showCurrentToken.value = false
  showNewToken.value = false
  showConfirmToken.value = false
}

const loadSettings = async () => {
  loading.value = true
  const { data, error } = await getSecuritySettings()
  loading.value = false

  if (error) {
    toast.add('error', `加载安全设置失败：${error}`, '', 5000)
    return
  }

  if (!data) return

  settings.value = data
  servicePort.value = String(data.service_port || 18080)
  tokenMode.value = data.token_mode || 'permanent'
  randomTokenExpireHours.value = String(data.random_token_expire_hours || 24)
}

const validateForm = () => {
  const trimmedPort = normalizedPort.value

  if (!hasTokenChange.value && !hasPortChange.value) {
    toast.add('warning', '当前没有可保存的变更', '', 3000)
    return false
  }

  if (hasTokenChange.value && !normalizedCurrentToken.value) {
    toast.add('warning', '请先输入当前登录凭证', '', 4000)
    return false
  }

  if (tokenMode.value === 'permanent') {
    if (hasTokenChange.value) {
      if (!normalizedNewToken.value) {
        toast.add('warning', '请输入新的永久登录凭证', '', 4000)
        return false
      }
      if (!normalizedConfirmToken.value) {
        toast.add('warning', '请再次输入新的永久登录凭证进行确认', '', 4000)
        return false
      }
      if (evaluatedRules.value.some((rule) => !rule.passed)) {
        toast.add('warning', '新的永久登录凭证不符合复杂度要求', '', 4000)
        return false
      }
      if (!isConfirmMatched.value) {
        toast.add('warning', '两次输入的新登录凭证不一致', '', 4000)
        return false
      }
    }
  } else {
    const parsedHours = Number(normalizedRandomTokenExpireHours.value)
    if (!Number.isInteger(parsedHours) || parsedHours < 1 || parsedHours > 720) {
      toast.add('warning', '随机 token 有效期必须是 1 到 720 小时之间的整数', '', 4000)
      return false
    }
  }

  const parsedPort = Number(trimmedPort)
  if (!Number.isInteger(parsedPort) || parsedPort < 1024 || parsedPort > 49151) {
    toast.add('warning', '服务端口必须是 1024 到 49151 之间的整数', '', 4000)
    return false
  }

  return true
}

const applySettings = async () => {
  if (!validateForm()) return

  saving.value = true
  const { data, error } = await updateSecuritySettings({
    current_token: normalizedCurrentToken.value,
    new_token: tokenMode.value === 'permanent' ? normalizedNewToken.value : '',
    service_port: Number(normalizedPort.value),
    token_mode: tokenMode.value,
    random_token_expire_hours: Number(normalizedRandomTokenExpireHours.value || 24)
  })
  saving.value = false

  if (error) {
    toast.add('error', `保存安全设置失败：${error}`, '', 5000)
    return
  }

  if (!data) return

  warningModal.value?.close()
  toast.add('success', data.message || '安全设置已保存', '', 5000)

  const nextPort = data.service_port || Number(normalizedPort.value)
  const tokenChanged = data.token_changed
  const portChanged = data.port_changed

  settings.value = {
    ...(settings.value ?? {
      is_docker: false,
      service_host: '0.0.0.0',
      service_port: nextPort,
      token_hint: '',
      token_mode: tokenMode.value,
      random_token_expire_hours: Number(normalizedRandomTokenExpireHours.value || 24),
      token_expires_at: 0
    }),
    service_port: nextPort,
    token_mode: data.token_mode,
    random_token_expire_hours: data.random_token_expire_hours,
    token_expires_at: data.token_expires_at
  }
  servicePort.value = String(nextPort)
  tokenMode.value = data.token_mode
  randomTokenExpireHours.value = String(data.random_token_expire_hours || 24)
  resetTokenInputs()

  if (tokenChanged) {
    clearAuthToken()
  }

  if (portChanged && data.restart_scheduled) {
    const target = createTargetUrl(nextPort, tokenChanged ? '/login' : '/')
    toast.add('warning', `服务即将切换到 ${nextPort} 端口，页面将自动跳转`, '', 5000)
    window.setTimeout(() => {
      window.location.href = target
    }, 2500)
    return
  }

  if (tokenChanged) {
    if (data.token_mode === 'random') {
      toast.add('warning', '请到 Docker 日志中查看新的随机登录凭证，然后重新登录', '', 6000)
    } else {
      toast.add('info', '请使用新的永久登录凭证重新登录', '', 5000)
    }
    router.push('/login')
    return
  }

  await loadSettings()
}

const submitSettings = () => {
  if (!validateForm()) return

  if (isDocker.value && hasPortChange.value) {
    warningModal.value?.showModal()
    return
  }

  void applySettings()
}

watch(tokenMode, (nextMode) => {
  if (nextMode === 'random') {
    newToken.value = ''
    confirmToken.value = ''
    showNewToken.value = false
    showConfirmToken.value = false
  }
})

onMounted(() => {
  void loadSettings()
})
</script>

<template>
  <div class="w-full p-6 bg-base-200 rounded-box flex flex-col gap-4">
    <div class="flex flex-col gap-2">
      <h2 class="text-xl font-semibold">安全设置</h2>
      <div class="text-sm opacity-70">
        这里可以修改 WebUI 的登录凭证模式与服务端口。服务端口默认使用 18080。
      </div>
      <div class="text-xs opacity-60">
        当前运行环境：{{ isDocker ? 'Docker' : '非 Docker' }}，当前监听：{{ currentHost }}:{{ currentPort }}
      </div>
      <div class="bg-base-content/10 h-[1px]"></div>
    </div>

    <div v-if="loading" class="text-sm opacity-70">加载中...</div>

    <div v-else class="flex flex-col gap-4">
      <div class="alert bg-base-100 border border-base-content/10">
        <span class="material-symbols-outlined text-primary">shield_lock</span>
        <div class="text-sm leading-6">
          <div>默认推荐使用永久 token，永久 token 不自动过期，需要你手动修改。</div>
          <div>随机 token 不会在页面明文展示，只会写入 Docker 日志；过期后系统会自动生成新的随机 token 并再次写入日志。</div>
          <div>{{ settings?.token_hint || '修改登录凭证前，请先输入当前登录凭证。' }}</div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <button
          type="button"
          class="text-left rounded-xl border p-4 transition-colors"
          :class="tokenMode === 'permanent' ? 'border-primary bg-primary/10' : 'border-base-content/10 bg-base-100'"
          @click="tokenMode = 'permanent'"
        >
          <div class="flex items-center justify-between gap-3">
            <div class="font-semibold">永久 token</div>
            <span class="badge" :class="tokenMode === 'permanent' ? 'badge-primary' : 'badge-ghost'">
              默认
            </span>
          </div>
          <div class="mt-2 text-sm opacity-75">
            不设置有效期，适合长期固定凭证的场景。修改时需要输入当前登录凭证和新的永久 token。
          </div>
        </button>

        <button
          type="button"
          class="text-left rounded-xl border p-4 transition-colors"
          :class="tokenMode === 'random' ? 'border-warning bg-warning/10' : 'border-base-content/10 bg-base-100'"
          @click="tokenMode = 'random'"
        >
          <div class="flex items-center justify-between gap-3">
            <div class="font-semibold">随机 token</div>
            <span class="badge" :class="tokenMode === 'random' ? 'badge-warning' : 'badge-ghost'">
              日志输出
            </span>
          </div>
          <div class="mt-2 text-sm opacity-75">
            保存后自动生成随机 token，并写入 Docker 日志。适合临时登录或定期轮换凭证的场景。
          </div>
        </button>
      </div>

      <div class="grid grid-cols-1 gap-4">
        <label class="form-control w-full">
          <div class="label py-1">
            <span class="label-text">当前登录凭证</span>
          </div>
          <div class="join w-full">
            <input
              v-model="currentToken"
              :type="showCurrentToken ? 'text' : 'password'"
              class="input input-sm input-bordered font-mono join-item flex-1"
              placeholder="输入当前正在使用的登录凭证"
            />
            <button
              type="button"
              class="btn btn-sm btn-outline join-item"
              @click="showCurrentToken = !showCurrentToken"
            >
              <span class="material-symbols-outlined">{{ getEyeIcon(showCurrentToken) }}</span>
            </button>
          </div>
          <div class="label py-1">
            <span class="label-text-alt opacity-70">
              只要登录凭证设置有变化，保存时都会先校验当前登录凭证。
            </span>
          </div>
        </label>

        <template v-if="requiresManualTokenInput">
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <label class="form-control w-full">
              <div class="label py-1">
                <span class="label-text">新的永久登录凭证</span>
              </div>
              <div class="join w-full">
                <input
                  v-model="newToken"
                  :type="showNewToken ? 'text' : 'password'"
                  :disabled="!canEditNewToken"
                  class="input input-sm input-bordered font-mono join-item flex-1"
                  :placeholder="canEditNewToken ? '输入新的永久登录凭证' : '请先输入当前登录凭证'"
                />
                <button
                  type="button"
                  class="btn btn-sm btn-outline join-item"
                  :disabled="!canEditNewToken"
                  @click="showNewToken = !showNewToken"
                >
                  <span class="material-symbols-outlined">{{ getEyeIcon(showNewToken) }}</span>
                </button>
              </div>
            </label>

            <label class="form-control w-full">
              <div class="label py-1">
                <span class="label-text">确认新的永久登录凭证</span>
              </div>
              <div class="join w-full">
                <input
                  v-model="confirmToken"
                  :type="showConfirmToken ? 'text' : 'password'"
                  :disabled="!canEditNewToken"
                  class="input input-sm input-bordered font-mono join-item flex-1"
                  :placeholder="canEditNewToken ? '再次输入新的永久登录凭证' : '请先输入当前登录凭证'"
                />
                <button
                  type="button"
                  class="btn btn-sm btn-outline join-item"
                  :disabled="!canEditNewToken"
                  @click="showConfirmToken = !showConfirmToken"
                >
                  <span class="material-symbols-outlined">{{ getEyeIcon(showConfirmToken) }}</span>
                </button>
              </div>
              <div class="label py-1">
                <span
                  class="label-text-alt"
                  :class="
                    !isConfirmFilled
                      ? 'opacity-70'
                      : isConfirmMatched
                        ? 'text-success'
                        : 'text-error'
                  "
                >
                  {{
                    !isConfirmFilled
                      ? '确认输入后会在这里实时提示是否一致。'
                      : isConfirmMatched
                        ? '两次输入一致'
                        : '两次输入不一致'
                  }}
                </span>
              </div>
            </label>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div
              v-for="rule in evaluatedRules"
              :key="rule.id"
              class="rounded-lg px-3 py-2 border transition-colors"
              :class="getRuleClass(rule.active, rule.passed)"
            >
              {{ rule.label }}
            </div>
          </div>
        </template>

        <template v-else>
          <div class="grid grid-cols-1 lg:grid-cols-[minmax(0,260px),1fr] gap-4 items-start">
            <label class="form-control w-full">
              <div class="label py-1">
                <span class="label-text">随机 token 有效期</span>
              </div>
              <input
                v-model="randomTokenExpireHours"
                type="text"
                inputmode="numeric"
                class="input input-sm input-bordered font-mono"
                placeholder="24"
              />
              <div class="label py-1">
                <span class="label-text-alt opacity-70">单位：小时，范围 1 到 720</span>
              </div>
            </label>

            <div class="alert bg-warning/10 border border-warning/30 text-sm leading-6">
              <span class="material-symbols-outlined text-warning">warning</span>
              <div>
                <div>保存后会立即生成新的随机 token，并且当前页面会退出登录。</div>
                <div>请先确认你能查看 Docker 日志，否则拿不到新的随机 token。</div>
                <div>当前随机 token 到期时间：{{ currentRandomTokenExpiryText }}</div>
              </div>
            </div>
          </div>
        </template>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-[minmax(0,320px),1fr] gap-4 items-start">
        <label class="form-control w-full">
          <div class="label py-1">
            <span class="label-text">服务端口</span>
          </div>
          <input
            v-model="servicePort"
            type="text"
            inputmode="numeric"
            class="input input-sm input-bordered font-mono"
            placeholder="18080"
          />
          <div class="label py-1">
            <span class="label-text-alt opacity-70">默认端口：18080，仅支持输入数字</span>
          </div>
        </label>

        <div class="alert bg-warning/10 border border-warning/30 text-sm leading-6">
          <span class="material-symbols-outlined text-warning">warning</span>
          <div>
            <div>修改端口前，请先在 Docker 中提前映射目标端口。</div>
            <div>如果没有映射就直接修改，页面会因为无法访问新端口而打不开。</div>
          </div>
        </div>
      </div>

      <div class="flex flex-wrap gap-3">
        <button class="btn btn-primary" :disabled="saving" @click="submitSettings">
          {{ saving ? '保存中...' : '保存安全设置' }}
        </button>
        <button class="btn btn-ghost" :disabled="loading || saving" @click="void loadSettings()">
          重新加载
        </button>
      </div>
    </div>
  </div>

  <dialog ref="warningModal" class="modal">
    <div class="modal-box rounded-xl flex flex-col gap-4">
      <h3 class="text-lg font-semibold">确认修改服务端口</h3>
      <div class="text-sm leading-6 opacity-80">
        修改前请确认 Docker 已提前映射 {{ normalizedPort || '新端口' }}。
      </div>
      <div class="text-sm leading-6 opacity-80">
        保存后服务会自动重启并切换到新端口。如果没有完成端口映射，当前页面可能会无法打开。
      </div>
      <div class="flex justify-end gap-3">
        <button class="btn btn-sm btn-ghost" @click="warningModal?.close()">取消</button>
        <button class="btn btn-sm btn-warning" :disabled="saving" @click="applySettings">
          {{ saving ? '提交中...' : '我已确认，继续修改' }}
        </button>
      </div>
    </div>
    <form method="dialog" class="modal-backdrop">
      <button>close</button>
    </form>
  </dialog>
</template>
