<script setup lang="ts">
import ExtensionCard from './ExtensionCard.vue'
import { useSearchStore } from './client'

const store = useSearchStore()
</script>

<template>
  <div
    v-if="store.storeData.length > 0"
    class="relative grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 grid-rows-auto gap-5"
  >
    <div
      v-if="store.isRequesting"
      class="absolute z-20 top-1/4 right-1/2 flex items-center gap-4 translate-x-1/2 translate-y-1/2 rounded-2xl border border-base-content/10 bg-base-100/85 px-5 py-3 shadow-2xl backdrop-blur"
    >
      搜索中...
      <span class="loading loading-spinner loading-md text-primary"></span>
    </div>
    <div
      v-for="data in store.storeData"
      :key="data.name"
      :class="{ 'blur-sm pointer-events-none': store.isRequesting }"
    >
      <ExtensionCard :data="data" />
    </div>
  </div>
  <div v-else class="nb-empty-state">
    <div>
      <span class="material-symbols-outlined text-5xl opacity-35">search_off</span>
      <h2 class="mt-3 text-lg font-semibold">没有结果</h2>
      <p class="mt-1 text-sm opacity-60">尝试清空关键字，或切换插件 / 适配器 / 驱动分类重新搜索。</p>
    </div>
  </div>
</template>
