<script setup lang="ts">
import HeaderIndex from '@/components/header/HeaderIndex.vue'
import SidebarIndex from '@/components/sidebar/SidebarIndex.vue'
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="relative h-screen overflow-hidden p-3 lg:p-4">
    <div class="nb-shell flex h-full rounded-[28px]">
    <SidebarIndex class="shrink-0" />
    <div class="h-full w-full flex flex-col min-w-0">
      <HeaderIndex />
      <div class="h-full w-full overflow-y-auto p-4 2xl:px-20">
        <RouterView />
      </div>
    </div>
    </div>
  </div>
</template>
