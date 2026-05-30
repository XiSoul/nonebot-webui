<script setup lang="ts">
import AddBotIndex from '@/components/Modals/AddBot/AddBotIndex.vue'
import CreateBotIndex from '@/components/Modals/CreateBot/CreateBotIndex.vue'
import { useNoneBotStore } from '@/stores'
import { ref } from 'vue'

const nonebotStore = useNoneBotStore()

const createBotModal = ref<InstanceType<typeof CreateBotIndex> | null>()
const addBotModal = ref<InstanceType<typeof AddBotIndex> | null>()
</script>

<template>
  <CreateBotIndex ref="createBotModal" />
  <AddBotIndex ref="addBotModal" />

  <div class="flex flex-col gap-4">
    <div class="p-8 rounded-box bg-base-200 flex flex-col gap-8">
      <h1 class="text-4xl flex gap-4">欢迎<span>🎉</span></h1>

      <div class="text-base-content/75">
        <div>您的 NoneBot CLI WebUI 已准备就绪。</div>
        <div>请选择或创建一个 NoneBot 实例以开始。</div>
        <div>接下来......</div>
      </div>

      <div class="grid gap-4 grid-cols-1 md:grid-cols-3">
        <a
          href="https://nonebot.dev"
          target="_blank"
          class="p-4 border border-base-content/25 rounded-box flex flex-col gap-2 md:gap-4 transition hover:shadow-lg"
        >
          <div class="text-lg font-semibold">阅读文档</div>
          <div class="text-base-content/75">查看文档以解决有关 NoneBot 的大部分疑问。</div>
        </a>

        <a
          href="https://nonebot.dev/docs/community/contact"
          target="_blank"
          class="p-4 border border-base-content/25 rounded-box flex flex-col gap-2 md:gap-4 transition hover:shadow-lg"
        >
          <div class="text-lg font-semibold">参与讨论</div>
          <div class="text-base-content/75">
            如在安装、开发或使用过程中遇到了任何问题，或有新奇的点子，欢迎参与我们的社区讨论。
          </div>
        </a>

        <a
          class="p-4 border border-base-content/25 rounded-box flex flex-col gap-2 md:gap-4 transition hover:shadow-lg"
        >
          <div class="text-lg font-semibold">开始使用</div>
          <div class="flex items-center justify-center gap-2">
            <button
              class="btn btn-md lg:btn-sm btn-primary font-normal text-base-100"
              @click="createBotModal?.openModal()"
            >
              创建实例
            </button>
            <button
              class="btn btn-md lg:btn-sm btn-primary font-normal btn-outline"
              @click="addBotModal?.openModal()"
            >
              添加实例
            </button>
          </div>
        </a>
      </div>
    </div>

    <div class="p-8 rounded-box bg-base-200">
      <div class="overflow-x-auto">
        <table class="table">
          <thead>
            <tr>
              <th>实例名称</th>
              <th>适配器</th>
            </tr>
          </thead>

          <tbody>
            <tr
              role="button"
              v-for="(bot, id) in nonebotStore.bots"
              :key="id"
              class="hover:bg-base-300 transition-colors"
              @click="nonebotStore.selectBot(bot)"
            >
              <td>
                {{ bot.project_name }}
                <span
                  v-if="nonebotStore.selectedBot?.project_id === bot.project_id"
                  class="ml-2 badge badge-outline text-base-content"
                >
                  选择中
                </span>
              </td>
              <td class="flex flex-wrap gap-2">
                <span v-for="(adapter, index) in bot.adapters" :key="index" class="badge">
                  {{ adapter.name }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
