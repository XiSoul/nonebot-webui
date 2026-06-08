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

    <ul class="flex flex-col gap-1">
      <li v-for="route in mainRoutes" :key="route.name" @click="recordView(route)">
        <RouterLink
          :to="route.routeData.path"
          class="nb-sidebar-link group"
          :class="{
            'is-active': route.routeData.path === getCurrentRoute(),
            'lg:justify-center lg:px-0': customStore.menuMinify
          }"
          @click="customStore.toggleMenuShow()"
        >
          <span v-if="route.googleIcon" class="material-symbols-outlined shrink-0 text-[1.45rem]">
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
      <ul class="flex flex-col gap-1">
        <li v-for="route in footerRoutes" :key="route.name" @click="recordView(route)">
          <RouterLink
            :to="route.routeData.path"
            class="nb-sidebar-link group"
            :class="{
              'is-active': route.routeData.path === getCurrentRoute(),
              'lg:justify-center lg:px-0': customStore.menuMinify
            }"
            @click="customStore.toggleMenuShow()"
          >
            <span v-if="route.googleIcon" class="material-symbols-outlined shrink-0 text-[1.45rem]">
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

.nb-sidebar-link {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  min-height: 2.5rem;
  padding: 0.5rem 0.75rem;
  border-left: 3px solid transparent;
  border-radius: 0.25rem 0.75rem 0.75rem 0.25rem;
  color: var(--fallback-bc, oklch(var(--bc) / 0.86));
  line-height: 1.25rem;
  text-decoration: none;
  background-clip: border-box;
  transition:
    background-color 150ms ease,
    border-color 150ms ease,
    color 150ms ease;
}

.nb-sidebar-link:hover {
  background: oklch(var(--p) / 0.1);
}

.nb-sidebar-link:active,
.nb-sidebar-link.is-active,
.nb-sidebar-link.router-link-active,
.nb-sidebar-link.router-link-exact-active {
  border-left-color: rgb(234 83 83 / 0.9);
  border-radius: 0.25rem 0.75rem 0.75rem 0.25rem;
  color: var(--fallback-bc, oklch(var(--bc) / 0.94));
  background:
    linear-gradient(90deg, rgb(234 83 83 / 0.2) 0%, rgb(234 83 83 / 0.14) 45%, rgb(99 102 241 / 0.07) 100%),
    oklch(var(--p) / 0.12);
  box-shadow: none;
}

.nb-sidebar-link.is-active:hover,
.nb-sidebar-link.router-link-active:hover,
.nb-sidebar-link.router-link-exact-active:hover {
  background:
    linear-gradient(90deg, rgb(234 83 83 / 0.2) 0%, rgb(234 83 83 / 0.14) 45%, rgb(99 102 241 / 0.07) 100%),
    oklch(var(--p) / 0.12);
}
</style>
