<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useCustomStore, useViewHistoryRecorderStore } from '@/stores'
import { defaultRoutes, type NavItem } from '@/router/client'

const route = useRoute()
const store = useViewHistoryRecorderStore()
const customStore = useCustomStore()
const mainRoutes = computed(() => defaultRoutes.filter((item) => item.placement !== 'footer'))
const footerRoutes = computed(() => defaultRoutes.filter((item) => item.placement === 'footer'))

const getCurrentRoute = () => route.path

const recordView = (route: NavItem) => {
  if (store.viewHistory.some((i: any) => i.routeData.path === route.routeData.path)) return
  store.record(route)
}
</script>

<template>
  <nav class="flex h-full flex-col pt-6">
    <div
      class="mb-3 px-3 text-[0.68rem] font-semibold uppercase tracking-[0.22em] opacity-45"
      :class="{ 'lg:hidden': customStore.menuMinify }"
    >
      Workspace
    </div>

    <ul class="menu gap-1 rounded-box px-0">
      <li v-for="route in mainRoutes" :key="route.name" @click="recordView(route)">
        <RouterLink
          :to="route.routeData.path"
          class="group min-h-11 rounded-2xl transition duration-150 hover:bg-primary/10"
          :class="{
            active: route.routeData.path === getCurrentRoute(),
            'btn-block lg:btn-square flex items-center justify-start lg:justify-center':
              customStore.menuMinify
          }"
          @click="customStore.toggleMenuShow()"
        >
          <span v-if="route.googleIcon" class="material-symbols-outlined text-[1.45rem]">
            {{ route.googleIcon }}
          </span>
          <span class="font-medium" :class="{ 'block lg:hidden': customStore.menuMinify }">
            {{ route.name }}
          </span>
        </RouterLink>
      </li>
    </ul>

    <div class="mt-auto pt-4">
      <div class="mb-3 border-t border-base-content/10"></div>
      <ul class="menu gap-1 rounded-box px-0">
        <li v-for="route in footerRoutes" :key="route.name" @click="recordView(route)">
          <RouterLink
            :to="route.routeData.path"
            class="min-h-11 rounded-2xl transition duration-150 hover:bg-primary/10"
            :class="{
              active: route.routeData.path === getCurrentRoute(),
              'btn-block lg:btn-square flex items-center justify-start lg:justify-center':
                customStore.menuMinify
            }"
            @click="customStore.toggleMenuShow()"
          >
            <span v-if="route.googleIcon" class="material-symbols-outlined text-[1.45rem]">
              {{ route.googleIcon }}
            </span>
            <span class="font-medium" :class="{ 'block lg:hidden': customStore.menuMinify }">
              {{ route.name }}
            </span>
          </RouterLink>
        </li>
      </ul>
    </div>
  </nav>
</template>

<style scoped>
.material-symbols-outlined {
  font-variation-settings:
    'FILL' 0,
    'wght' 300,
    'GRAD' -25,
    'opsz' 48;
}

.menu li > *:not(ul, .menu-title, details, .btn):active,
.menu li > *:not(ul, .menu-title, details, .btn).active,
.menu li > details > summary:active {
  --tw-bg-opacity: 0.16;
  background:
    linear-gradient(135deg, rgb(234 83 83 / 0.18), rgb(99 102 241 / 0.1)),
    var(--fallback-n, oklch(var(--p) / var(--tw-bg-opacity)));
  color: var(--fallback-nc, oklch(var(--pc) / var(--tw-text-opacity)));
  box-shadow: inset 3px 0 0 rgb(234 83 83 / 0.9);
}
</style>
