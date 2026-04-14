<script setup lang="ts">
import { ref } from 'vue'
import { client, AuthService } from '@/client/api'
import { setAuthToken } from '@/client/auth'
import { createDebugApiBaseUrl, getDefaultApiBaseUrl } from '@/client/base'
import { getErrorMessage } from '@/client/utils'
import router from '@/router'
import { useNoneBotStore, useToastStore } from '@/stores'

const toast = useToastStore()
const nonebotStore = useNoneBotStore()

const token = ref('')
const isDebug = ref(false)
const host = ref('')
const port = ref('')

const login = async () => {
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
    return
  }

  if (data?.detail) {
    setAuthToken(data.detail)
    client.interceptors.request.use((request) => {
      request.headers.set('Authorization', `Bearer ${data.detail}`)
      return request
    })
    router.push('/')
    await nonebotStore.loadBots()
    toast.add('success', '登录成功', '', 5000)
  }
}
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
            <span class="label-text">开发模式</span>
            <input
              type="checkbox"
              class="checkbox checkbox-xs"
              :checked="isDebug"
              @click="isDebug = !isDebug"
            />
          </div>
        </label>

        <div class="form-control">
          <button class="btn btn-primary text-base-100">
            开始使用<span class="material-symbols-outlined"> chevron_right </span>
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
    </form>
  </div>
</template>
