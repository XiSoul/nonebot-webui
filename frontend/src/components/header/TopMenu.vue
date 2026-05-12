<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import router from '@/router'
import { clearAuthToken } from '@/client/auth'
import { useCustomStore, useToastStore } from '@/stores'
import NotificationItem from '@/components/header/NotificationItem.vue'
import StatusItem from '@/components/header/StatusItem.vue'
import WebUISettings from '@/components/header/WebUISettings.vue'

const store = useCustomStore()
const toast = useToastStore()

const logout = () => {
  clearAuthToken()
  router.push('/login')
  toast.add('success', '已退出登录', '', 5000)
}

const currentThemeIcon = computed(() =>
  store.currentTheme === 'dark' ? 'dark_mode' : 'light_mode'
)

const currentThemeLabel = computed(() =>
  store.currentTheme === 'dark' ? '切换到亮色' : '切换到暗色'
)

const handleThemeToggle = () => {
  store.toggleTheme(store.currentTheme === 'dark' ? 'light' : 'dark')
}

const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')

const handleSystemThemeChange = () => {
  store.syncThemeWithSystem()
}

onMounted(() => {
  if (typeof mediaQuery.addEventListener === 'function') {
    mediaQuery.addEventListener('change', handleSystemThemeChange)
    return
  }
  mediaQuery.addListener(handleSystemThemeChange)
})

onUnmounted(() => {
  if (typeof mediaQuery.removeEventListener === 'function') {
    mediaQuery.removeEventListener('change', handleSystemThemeChange)
    return
  }
  mediaQuery.removeListener(handleSystemThemeChange)
})
</script>

<template>
  <div class="nb-header-surface relative h-16 px-4 xl:px-8 py-2 flex justify-end items-center">
    <button
      :class="{
        'z-20 absolute -left-5 size-10 flex items-center justify-center invisible lg:visible': true,
        '-scale-100': store.menuMinify
      }"
      @click="store.toggleMenuMinify()"
    >
      <span class="material-symbols-outlined"> menu_open </span>
    </button>
    <button
      class="visible lg:invisible relative size-10 flex items-center justify-center"
      @click="store.toggleMenuShow()"
    >
      <span class="material-symbols-outlined"> menu </span>
    </button>

    <div class="w-full"></div>

    <div class="h-full flex justify-end items-center gap-4">
      <StatusItem />

      <button
        class="btn btn-sm btn-ghost btn-square"
        :title="currentThemeLabel"
        @click="handleThemeToggle"
      >
        <span class="fill-current material-symbols-outlined">
          {{ currentThemeIcon }}
        </span>
      </button>

      <NotificationItem />

      <WebUISettings />
      <button class="btn btn-sm btn-ghost btn-square">
        <span class="material-symbols-outlined text-primary" @click="logout()"> logout </span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.material-symbols-outlined {
  font-variation-settings:
    'FILL' 0,
    'wght' 400,
    'GRAD' -25,
    'opsz' 48;
}
</style>
