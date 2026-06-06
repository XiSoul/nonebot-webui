<script setup lang="ts">
import { computed, ref } from 'vue'
import { useNoneBotStore } from '@/stores'
import { getRuntimeState } from '@/utils/runtimeState'
import CreateBotIndex from '@/components/Modals/CreateBot/CreateBotIndex.vue'
import MachineStat from '@/views/Dashboard/MachineStat.vue'
import AddBotIndex from '@/components/Modals/AddBot/AddBotIndex.vue'
import { useInstanceMessageCount } from '@/composables/useInstanceMessageCount'

const store = useNoneBotStore()

const createBotModal = ref<InstanceType<typeof CreateBotIndex> | null>()
const addBotModal = ref<InstanceType<typeof AddBotIndex> | null>()

const bots = computed(() => store.getExtendedBotsList())
const runningCount = computed(() => bots.value.filter((bot) => getRuntimeState(bot) === 'running').length)
const startingCount = computed(() => bots.value.filter((bot) => getRuntimeState(bot) === 'starting').length)
const missingCount = computed(() => bots.value.filter((bot) => getRuntimeState(bot) === 'missing').length)
const selectedBot = computed(() => store.selectedBot)
const selectedRuntimeState = computed(() => getRuntimeState(selectedBot.value))
const selectedStateLabel = computed(() => {
  if (selectedRuntimeState.value === 'running') return '运行中'
  if (selectedRuntimeState.value === 'starting') return '启动中'
  if (selectedRuntimeState.value === 'missing') return '目录缺失'
  return '未运行'
})
const selectedStateBadge = computed(() => {
  if (selectedRuntimeState.value === 'running') return 'badge-success text-base-100'
  if (selectedRuntimeState.value === 'starting') return 'badge-warning'
  if (selectedRuntimeState.value === 'missing') return 'badge-error text-base-100'
  return 'badge-ghost'
})
const { messageCount: selectedBotMessageCount } = useInstanceMessageCount(selectedBot)
</script>

<template>
  <CreateBotIndex ref="createBotModal" />
  <AddBotIndex ref="addBotModal" />

  <div class="grid gap-5">
    <section class="nb-page-heading overflow-hidden">
      <div class="max-w-3xl">
        <div class="mb-3 inline-flex items-center gap-2 rounded-full bg-base-100/50 px-3 py-1 text-xs font-medium ring-1 ring-base-content/10">
          <span class="material-symbols-outlined text-base text-primary">rocket_launch</span>
          NoneBot WebUI 控制台
        </div>
        <h1 class="text-2xl font-bold tracking-tight md:text-3xl">更清晰地管理你的机器人实例</h1>
        <p class="mt-2 text-sm leading-6 opacity-70">
          创建、接入、运行、插件、配置、文件和日志集中在一个响应式工作台中，适合 NAS 与服务器长期维护。
        </p>
      </div>
      <div class="flex flex-wrap gap-2 md:justify-end">
        <button class="btn btn-primary text-base-100 shadow-lg shadow-primary/20" @click="createBotModal?.openModal()">
          <span class="material-symbols-outlined">add_circle</span>
          创建实例
        </button>
        <button class="btn btn-outline" @click="addBotModal?.openModal()">
          <span class="material-symbols-outlined">drive_folder_upload</span>
          添加实例
        </button>
      </div>
    </section>

    <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <div class="nb-action-card">
        <div class="flex items-center justify-between gap-3">
          <div>
            <div class="text-sm opacity-60">已有实例</div>
            <div class="mt-2 text-4xl font-bold">{{ bots.length }}</div>
          </div>
          <span class="material-symbols-outlined rounded-2xl bg-primary/10 p-3 text-3xl text-primary">deployed_code</span>
        </div>
      </div>
      <div class="nb-action-card">
        <div class="flex items-center justify-between gap-3">
          <div>
            <div class="text-sm opacity-60">正在运行</div>
            <div class="mt-2 text-4xl font-bold text-success">{{ runningCount }}</div>
          </div>
          <span class="material-symbols-outlined rounded-2xl bg-success/10 p-3 text-3xl text-success">play_circle</span>
        </div>
      </div>
      <div class="nb-action-card">
        <div class="flex items-center justify-between gap-3">
          <div>
            <div class="text-sm opacity-60">启动中</div>
            <div class="mt-2 text-4xl font-bold text-warning">{{ startingCount }}</div>
          </div>
          <span class="material-symbols-outlined rounded-2xl bg-warning/10 p-3 text-3xl text-warning">progress_activity</span>
        </div>
      </div>
      <div class="nb-action-card">
        <div class="flex items-center justify-between gap-3">
          <div>
            <div class="text-sm opacity-60">目录异常</div>
            <div class="mt-2 text-4xl font-bold text-error">{{ missingCount }}</div>
          </div>
          <span class="material-symbols-outlined rounded-2xl bg-error/10 p-3 text-3xl text-error">folder_off</span>
        </div>
      </div>
    </section>

    <section class="grid gap-4 xl:grid-cols-3">
      <div class="nb-panel-surface rounded-[1.75rem] p-5 xl:col-span-2">
        <div class="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 class="text-lg font-semibold">当前实例概况</h2>
            <p class="mt-1 text-xs opacity-60">消息数按实例日志中的消息事件识别，不统计页面通知和普通运行日志。</p>
          </div>
          <span class="badge badge-lg whitespace-nowrap px-4" :class="selectedStateBadge">
            {{ selectedStateLabel }}
          </span>
        </div>

        <div class="grid gap-3 md:grid-cols-3">
          <div class="rounded-2xl bg-base-100/65 p-4 ring-1 ring-base-content/5 md:col-span-2">
            <div class="text-xs opacity-60">当前实例</div>
            <div class="mt-2 break-all text-xl font-semibold">
              {{ selectedBot?.project_name || '未选择实例' }}
            </div>
            <div class="mt-2 truncate text-xs opacity-55">
              {{ selectedBot?.project_dir || '请先创建或添加一个 NoneBot 项目' }}
            </div>
          </div>
          <div class="rounded-2xl bg-base-100/65 p-4 ring-1 ring-base-content/5">
            <div class="text-xs opacity-60">当前实例消息</div>
            <div class="mt-2 text-4xl font-bold">{{ selectedBotMessageCount }}</div>
            <div class="mt-2 text-xs opacity-55">来自实例日志识别</div>
          </div>
        </div>
      </div>

      <div class="nb-panel-surface rounded-[1.75rem] p-5">
        <h2 class="text-lg font-semibold">推荐操作流</h2>
        <div class="mt-4 space-y-3">
          <div class="flex gap-3 rounded-2xl bg-base-100/55 p-3">
            <span class="material-symbols-outlined text-primary">looks_one</span>
            <div><div class="font-medium">选择实例</div><div class="text-xs opacity-60">确认当前操作目标</div></div>
          </div>
          <div class="flex gap-3 rounded-2xl bg-base-100/55 p-3">
            <span class="material-symbols-outlined text-primary">looks_two</span>
            <div><div class="font-medium">检查配置</div><div class="text-xs opacity-60">切换 .env / .env.prod 并校验路径</div></div>
          </div>
          <div class="flex gap-3 rounded-2xl bg-base-100/55 p-3">
            <span class="material-symbols-outlined text-primary">looks_3</span>
            <div><div class="font-medium">启动并查看日志</div><div class="text-xs opacity-60">通过实例操作与日志定位状态</div></div>
          </div>
        </div>
      </div>
    </section>

    <MachineStat />
  </div>
</template>
