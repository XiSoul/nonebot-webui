<script setup lang="ts">
import HeaderIndex from '@/components/header/HeaderIndex.vue'
import SidebarIndex from '@/components/sidebar/SidebarIndex.vue'
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="relative h-screen overflow-hidden p-2 sm:p-3 lg:p-4">
    <div class="nb-shell flex h-full rounded-[24px] lg:rounded-[28px]">
      <SidebarIndex class="shrink-0" />
      <div class="relative z-10 h-full w-full flex min-w-0 flex-col">
        <HeaderIndex />
        <main class="h-full w-full overflow-y-auto p-3 sm:p-4 xl:p-6 2xl:px-20">
          <RouterView />
        </main>
      </div>
    </div>
  </div>
</template>
