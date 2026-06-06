<script setup lang="ts">
import SearchBar from './SearchBar.vue'
import ExtensionContainer from './ExtensionContainer.vue'
import Pagination from './Pagination.vue'
import { useSearchStore } from './client'
import { onMounted } from 'vue'
import { useNoneBotStore } from '@/stores'

const store = useSearchStore(),
  nonebotStore = useNoneBotStore()

onMounted(async () => {
  await store.updateData(nonebotStore.selectedBot?.project_id ?? '', false)
})
</script>

<template>
  <div class="nb-page">
    <section class="nb-page-heading">
      <div>
        <div class="nb-kicker">
          <span class="material-symbols-outlined text-base text-primary">extension</span>
          Extension Store
        </div>
        <h1 class="mt-3 text-2xl font-bold tracking-tight md:text-3xl">扩展商店</h1>
        <p class="mt-2 max-w-3xl text-sm leading-6 opacity-65">
          搜索 NoneBot 插件、适配器和驱动，按官方认证、测试状态、作者与标签快速过滤并安装到当前实例。
        </p>
      </div>
      <div class="flex flex-wrap gap-2 md:justify-end">
        <span class="badge badge-outline">{{ nonebotStore.selectedBot?.project_name || '未选择实例' }}</span>
        <span class="badge badge-primary text-base-100">{{ store.viewModule }}</span>
      </div>
    </section>

    <SearchBar />

    <Pagination />

    <ExtensionContainer />

    <Pagination />
  </div>
</template>
