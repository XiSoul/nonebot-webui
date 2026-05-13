<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { client, AuthService } from '@/client/api'
import { getRememberLogin, setAuthToken } from '@/client/auth'
import { createDebugApiBaseUrl, getDefaultApiBaseUrl } from '@/client/base'
import { getErrorMessage } from '@/client/utils'
import router from '@/router'
import { useRoute } from 'vue-router'
import { useNoneBotStore, useToastStore } from '@/stores'

type ClientRequest = Parameters<typeof client.interceptors.request.use>[0] extends (
  request: infer T,
  ...args: any[]
) => any
  ? T
  : Request

const toast = useToastStore()
const nonebotStore = useNoneBotStore()
const route = useRoute()

const token = ref('')
const rememberLogin = ref(false)
const isDebug = ref(false)
const host = ref('')
const port = ref('')
const isSubmitting = ref(false)
const autoLoginAttempted = ref(false)
const autoLoginDebug = ref('')
const autoLoginState = ref('')
const detectedToken = ref('')
let autoLoginPollTimer: ReturnType<typeof setInterval> | null = null

const extractTokenFromUrl = () => {
  const routeToken = `${route.query.token ?? ''}`.trim()
  if (routeToken) return routeToken

  try {
    const currentUrl = new URL(window.location.href)
    const searchToken = currentUrl.searchParams.get('token')?.trim() ?? ''
    if (searchToken) return searchToken

    if (currentUrl.hash) {
      const hash = currentUrl.hash.replace(/^#/, '')
      const hashParams = new URLSearchParams(hash.replace(/^.*\?/, ''))
      const hashToken = hashParams.get('token')?.trim() ?? ''
      if (hashToken) return hashToken
    }
  } catch {
    // ignore parsing errors and fall back below
  }

  const href = window.location.href
  const tokenMatch = href.match(/(?:[?&#]|:token=|\/token\/)([^&#]+)/i)
  if (tokenMatch?.[1]) {
    return decodeURIComponent(tokenMatch[1]).trim()
  }

  const rawSearch = window.location.search.replace(/^\?/, '').trim()
  if (!rawSearch) return ''
  const params = new URLSearchParams(rawSearch)
  return params.get('token')?.trim() ?? ''
}

const readLooseTokenFromPath = () => {
  const path = `${window.location.pathname}${window.location.search}${window.location.hash}`
  const markerMatches = [
    path.match(/\/login:token=([^&#?/]+)/i),
    path.match(/\/login\/token\/([^&#?/]+)/i),
    path.match(/\/login\/([^/?#]+)$/i)
  ]

  for (const match of markerMatches) {
    const value = match?.[1] ? decodeURIComponent(match[1]).trim() : ''
    if (value) return value
  }

  return ''
}

const stripTokenFromAddressBar = () => {
  try {
    const currentUrl = new URL(window.location.href)
    currentUrl.searchParams.delete('token')
    if (currentUrl.hash.includes('token=')) {
      const [hashPath, hashQuery = ''] = currentUrl.hash.replace(/^#/, '').split('?', 2)
      const hashParams = new URLSearchParams(hashQuery)
      hashParams.delete('token')
      const nextHashQuery = hashParams.toString()
      currentUrl.hash = nextHashQuery ? `${hashPath}?${nextHashQuery}` : hashPath
    }
    window.history.replaceState({}, '', currentUrl.toString())
  } catch {
    void router.replace({
      path: route.path,
      query: Object.fromEntries(
        Object.entries(route.query).filter(([key]) => key !== 'token')
      )
    })
  }
}

const refreshDetectedTokenFromUrl = () => {
  const queryToken = extractTokenFromUrl()
  const looseToken = readLooseTokenFromPath()
  const finalToken = queryToken || looseToken
  autoLoginDebug.value = `href=${window.location.href} | path=${window.location.pathname} | search=${window.location.search} | routeToken=${`${route.query.token ?? ''}`} | parsed=${queryToken} | loose=${looseToken} | final=${finalToken}`
  detectedToken.value = finalToken
  if (finalToken) {
    token.value = finalToken
  }
  return finalToken
}

const tryAutoLoginFromUrl = async () => {
  if (autoLoginAttempted.value) return

  const finalToken = refreshDetectedTokenFromUrl()
  if (!finalToken) return

  autoLoginAttempted.value = true
  autoLoginState.value = `token-found:${finalToken}`

  // Wait one tick so the input/model and router state are stable before login.
  await Promise.resolve()
  setTimeout(() => {
    void login()
  }, 50)
}

const login = async () => {
  if (isSubmitting.value) return
  isSubmitting.value = true
  autoLoginState.value = 'submitting'

  let baseUrl = getDefaultApiBaseUrl()

  if (isDebug.value) {
    baseUrl = createDebugApiBaseUrl(host.value, port.value)
    localStorage.setItem('isDebug', '1')
    localStorage.setItem('debugUrl', baseUrl)
  } else {
    localStorage.setItem('isDebug', '0')
    localStorage.removeItem('debugUrl')
  }

  client.setConfig({
    baseUrl
  })

  const { data, error } = await AuthService.authTokenV1AuthLoginPost({
    body: {
      token: token.value,
      mark: new Date().toISOString()
    }
  })

  if (error) {
    toast.add('error', `错误: ${getErrorMessage(error, '登录失败')}`, '', 5000)
    autoLoginState.value = `failed:${getErrorMessage(error, '登录失败')}`
    isSubmitting.value = false
    return
  }

  if (data?.detail) {
    setAuthToken(data.detail, rememberLogin.value)
    client.interceptors.request.use((request: ClientRequest) => {
      request.headers.set('Authorization', `Bearer ${data.detail}`)
      return request
    })
    toast.add('success', '登录成功', '', 5000)
    autoLoginState.value = 'success'
    if (detectedToken.value) {
      stripTokenFromAddressBar()
    }
    // Use a hard navigation after persisting the JWT to avoid getting stuck on /login
    // when the SPA router or initial app bootstrap order is not yet stable.
    window.location.replace('/')
    return
  }

  isSubmitting.value = false
}

onMounted(() => {
  rememberLogin.value = getRememberLogin()
  refreshDetectedTokenFromUrl()
  void tryAutoLoginFromUrl()

  autoLoginPollTimer = setInterval(() => {
    const latestToken = refreshDetectedTokenFromUrl()
    if (latestToken && !autoLoginAttempted.value) {
      void tryAutoLoginFromUrl()
      return
    }

    if (autoLoginAttempted.value || !window.location.pathname.includes('/login')) {
      if (autoLoginPollTimer) {
        clearInterval(autoLoginPollTimer)
        autoLoginPollTimer = null
      }
    }
  }, 400)
})

watch(
  () => route.fullPath,
  () => {
    refreshDetectedTokenFromUrl()
    void tryAutoLoginFromUrl()
  }
)

onUnmounted(() => {
  if (autoLoginPollTimer) {
    clearInterval(autoLoginPollTimer)
    autoLoginPollTimer = null
  }
})
</script>

<template>
  <div class="shrink-0 w-full">
    <form class="flex justify-center flex-col gap-4 lg:gap-0" @submit.prevent="login">
      <div class="flex justify-center gap-0 lg:gap-4 flex-col lg:flex-row">
        <label class="form-control">
          <input
            v-model="token"
            type="password"
            placeholder="请输入登录凭证"
            class="input input-ghost bg-base-200"
            required
          />
          <div class="label">
            <div class="flex items-center gap-2">
              <span class="label-text">记住登录</span>
              <input v-model="rememberLogin" type="checkbox" class="checkbox checkbox-xs" />
            </div>
            <div class="flex items-center gap-2">
              <span class="label-text">开发模式</span>
              <input
                type="checkbox"
                class="checkbox checkbox-xs"
                :checked="isDebug"
                @click="isDebug = !isDebug"
              />
            </div>
          </div>
        </label>

        <div class="form-control">
          <button class="btn btn-primary text-base-100">
            {{ detectedToken ? '使用链接凭证登录' : '开始使用' }}<span class="material-symbols-outlined"> chevron_right </span>
          </button>
        </div>
      </div>

      <div v-if="isDebug" class="form-control flex gap-4 flex-col">
        <input
          v-model="host"
          type="text"
          placeholder="host"
          class="input input-ghost bg-base-200"
          required
        />

        <input
          v-model="port"
          type="text"
          placeholder="port"
          class="input input-ghost bg-base-200"
          required
        />
      </div>

      <div
        v-if="detectedToken"
        class="mt-3 flex max-w-[42rem] items-center justify-between gap-3 rounded-xl border border-primary/20 bg-primary/5 px-3 py-2 text-left"
      >
        <div class="min-w-0 text-xs leading-5 text-base-content/70">
          已识别到链接中的登录凭证，可直接使用它登录。
        </div>
        <button class="btn btn-xs btn-primary text-base-100 shrink-0" type="button" @click="login">
          使用链接凭证登录
        </button>
      </div>

      <div v-if="autoLoginDebug" class="mt-3 max-w-[42rem] break-all text-left text-[11px] leading-5 text-base-content/55">
        {{ autoLoginDebug }}
      </div>
      <div v-if="autoLoginState" class="mt-1 max-w-[42rem] break-all text-left text-[11px] leading-5 text-primary">
        auto-login-state: {{ autoLoginState }}
      </div>
    </form>
  </div>
</template>
