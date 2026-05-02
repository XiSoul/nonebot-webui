import { createApp, type App as VueAPP } from 'vue'
import { createPinia } from 'pinia'
import router from '@/router'
import { client, AuthService } from './api'
import { getDefaultApiBaseUrl, normalizeApiBaseUrl } from './base'
import { clearAuthToken, getAuthToken } from './auth'
import { getErrorMessage } from './utils'
import { useNoneBotStore, useToastStore } from '@/stores'
import App from '@/App.vue'

type ClientRequest = Parameters<typeof client.interceptors.request.use>[0] extends (
  request: infer T,
  ...args: any[]
) => any
  ? T
  : Request

const installVuePlugins = (app: VueAPP) => {
  app.use(createPinia())
  app.use(router)
}

export const initWebUI = async () => {
  const app = createApp(App)
  installVuePlugins(app)
  app.mount('#app')

  const isDebug = localStorage.getItem('isDebug') === '1'
  const debugBase = isDebug ? localStorage.getItem('debugUrl') || '' : ''
  const base = normalizeApiBaseUrl(debugBase || getDefaultApiBaseUrl())

  client.setConfig({
    baseUrl: base
  })

  const token = getAuthToken()

  if (!token) {
    router.push('/login')
    return
  }

  client.interceptors.request.use((request: ClientRequest) => {
    request.headers.set('Authorization', `Bearer ${getAuthToken()}`)
    return request
  })

  const toast = useToastStore()
  const { data, error, response } = await AuthService.verifyTokenV1AuthVerifyPost({
    body: {
      jwt_token: token
    }
  })

  if (error && response.status === 403) {
    clearAuthToken()
    router.push('/login')
    toast.add('warning', getErrorMessage(error, '登录已过期，请重新登录'), '', 5000)
    return
  }

  if (data) {
    const expire = Number(data.detail)
    const now = Date.now() / 1000
    const diff = expire - now
    toast.add(
      'info',
      `登录会话有效期剩余: ${Math.floor((diff % 86400) / 3600)}h${Math.floor((diff % 3600) / 60)}m${Math.floor(diff % 60)}s`,
      '',
      10000
    )
  }

  const store = useNoneBotStore()
  await store.loadBots()
  store.startHeartbeat()
}
