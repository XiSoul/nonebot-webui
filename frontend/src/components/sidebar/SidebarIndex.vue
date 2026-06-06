<script setup lang="ts">
import SideMenu from '@/components/sidebar/SideMenu.vue'
import router from '@/router'
import { useCustomStore } from '@/stores'

const store = useCustomStore()
const logoUrl = 'https://x.none.bot/favicon.png'
</script>

<template>
  <div class="fixed left-0 top-0 z-20 flex h-full overflow-hidden lg:relative">
    <Transition>
      <div
        v-show="store.menuShow"
        role="button"
        aria-label="关闭侧边栏遮罩"
        class="hidden h-screen w-screen bg-slate-900/45 backdrop-blur-sm md:block lg:hidden"
        @click="store.toggleMenuShow()"
      ></div>
    </Transition>

    <aside
      :class="{
        'fixed left-0 top-0 flex h-full flex-col px-4 py-4 transition-all duration-200 lg:relative': true,
        '-translate-x-full lg:translate-x-0 nb-sidebar-surface shadow-xl': true,
        '!-translate-x-0': store.menuShow,
        'lg:!w-20 lg:px-3': store.menuMinify
      }"
      class="w-full md:w-1/2 lg:w-72"
    >
      <div class="flex items-center justify-between gap-3">
        <button
          class="nb-focusable flex min-w-0 items-center gap-3 rounded-2xl p-1.5 text-left transition hover:bg-base-content/5"
          @click="router.push('/'), store.toggleMenuShow()"
        >
          <div class="indicator shrink-0">
            <span
              v-if="store.isDebug"
              class="indicator-item indicator-middle indicator-center material-symbols-outlined text-warning"
            >
              build
            </span>
            <span
              class="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-primary/20 to-secondary/10 shadow-sm ring-1 ring-base-content/10"
            >
              <img :src="logoUrl" alt="NoneBot" class="h-9 w-9 object-contain" />
            </span>
          </div>

          <div class="min-w-0 shrink-0" :class="{ 'visible lg:invisible': store.menuMinify }">
            <div class="text-xl font-bold leading-6 tracking-tight">NoneBot</div>
            <div class="text-xs opacity-60">WebUI 控制台</div>
          </div>
        </button>

        <button
          class="btn btn-sm btn-square btn-ghost flex items-center justify-center lg:hidden"
          aria-label="收起侧边栏"
          @click="store.toggleMenuShow()"
        >
          <span class="material-symbols-outlined text-2xl"> arrow_back_ios_new </span>
        </button>
      </div>

      <SideMenu />
    </aside>
  </div>
</template>

<style scoped>
.material-symbols-outlined {
  font-variation-settings:
    'FILL' 0,
    'wght' 300,
    'GRAD' -25,
    'opsz' 48;
}

.v-enter-active,
.v-leave-active {
  transition: opacity 150ms ease;
}

.v-enter-from,
.v-leave-to {
  opacity: 0;
}
</style>
