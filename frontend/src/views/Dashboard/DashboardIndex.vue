<script setup lang="ts">
import { computed, ref } from 'vue'
import { useNoneBotStore } from '@/stores'
import CreateBotIndex from '@/components/Modals/CreateBot/CreateBotIndex.vue'
import MachineStat from '@/views/Dashboard/MachineStat.vue'
import AddBotIndex from '@/components/Modals/AddBot/AddBotIndex.vue'
import { useInstanceMessageCount } from '@/composables/useInstanceMessageCount'

const store = useNoneBotStore()

const createBotModal = ref<InstanceType<typeof CreateBotIndex> | null>()
const addBotModal = ref<InstanceType<typeof AddBotIndex> | null>()

const getBotIsRunning = computed(() => {
  return store.getExtendedBotsList().filter((bot) => bot.is_running).length
})

const selectedBot = computed(() => store.selectedBot)
const { messageCount: selectedBotMessageCount } = useInstanceMessageCount(selectedBot)
</script>

<template>
  <CreateBotIndex ref="createBotModal" />
  <AddBotIndex ref="addBotModal" />

  <div class="grid gap-4">
    <div class="grid gap-4 grid-cols-1 xl:grid-cols-3">
      <div class="col-span-1 xl:col-span-2 card bg-primary/[.2] card-body justify-center gap-4">
        <h2 class="card-title">欢迎使用 NoneBot WebUI</h2>
        <div class="text-sm space-y-1">
          <p>这里是面向 NoneBot 实例的图形化管理面板，适合创建、接入、运行和维护多个机器人实例。</p>
          <p>你可以在这里完成实例选择、实例操作、插件安装、配置修改、文件管理、备份恢复和日志排查。</p>
          <p>如果在部署、更新或使用过程中遇到问题，欢迎加入 QQ 群交流：1074735930。</p>
        </div>
        <div class="card-actions justify-start gap-3">
          <button
            class="btn btn-primary btn-sm font-normal text-base-100"
            @click="createBotModal?.openModal()"
          >
            创建实例
          </button>
          <button
            class="btn btn-sm btn-outline font-normal"
            @click="addBotModal?.openModal()"
          >
            添加实例
          </button>
        </div>
      </div>

      <div class="grid gap-4 grid-cols-2 xl:grid-cols-none">
        <div class="stats stats-vertical lg:stats-horizontal">
          <div class="stat">
            <div class="stat-title">已有实例</div>
            <div class="stat-value">{{ store.getExtendedBotsList().length }}</div>
          </div>

          <div class="stat">
            <div class="stat-title">正在运行</div>
            <div class="stat-value">{{ getBotIsRunning }}</div>
          </div>
        </div>

        <div class="card bg-base-200">
          <div class="card-body gap-4">
            <div class="flex items-start justify-between gap-3">
              <div>
                <p class="text-base font-semibold">当前实例概况</p>
                <div class="text-xs opacity-60 mt-1">
                  消息数按实例日志中的消息事件识别，不统计页面通知和普通运行日志
                </div>
              </div>
              <span
                class="badge badge-lg min-h-10 min-w-[5.5rem] px-4 text-sm font-semibold whitespace-nowrap inline-flex items-center justify-center"
                :class="selectedBot?.is_running ? 'badge-success text-base-100' : 'badge-ghost'"
              >
                {{ selectedBot?.is_running ? '运行中' : '未运行' }}
              </span>
            </div>

            <div class="rounded-xl bg-base-100 px-4 py-3">
              <div class="text-xs opacity-60">当前实例</div>
              <div class="mt-1 text-lg font-semibold break-all">
                {{ selectedBot?.project_name || '未选择实例' }}
              </div>
            </div>

            <div class="stats bg-base-100 shadow-sm">
              <div class="stat px-4 py-3">
                <div class="stat-title">当前实例消息</div>
                <div class="stat-value text-3xl">{{ selectedBotMessageCount }}</div>
                <div class="stat-desc">来自实例日志识别</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <MachineStat />
  </div>
</template>
