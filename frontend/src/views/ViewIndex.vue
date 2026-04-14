<script setup lang="ts">
import HeaderIndex from '@/components/header/HeaderIndex.vue'
import SidebarIndex from '@/components/sidebar/SidebarIndex.vue'
import { RouterView, useRoute } from 'vue-router'

const route = useRoute()
</script>

<template>
  <div class="relative h-screen flex">
    <SidebarIndex class="shrink-0" />
    <div class="h-full w-full flex flex-col">
      <HeaderIndex />
      <div class="h-full w-full overflow-y-auto p-4 2xl:px-20">
        <RouterView :key="route.fullPath" />
      </div>
    </div>
  </div>
</template>