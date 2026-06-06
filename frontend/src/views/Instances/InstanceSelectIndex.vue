<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { NoneBotProjectMeta } from '@/client/api'
import { useNoneBotStore } from '@/stores'
import { getRuntimeState } from '@/utils/runtimeState'
import AddBotIndex from '@/components/Modals/AddBot/AddBotIndex.vue'
import CreateBotIndex from '@/components/Modals/CreateBot/CreateBotIndex.vue'

const nonebotStore = useNoneBotStore()
const createBotModal = ref<InstanceType<typeof CreateBotIndex> | null>(null)
const addBotModal = ref<InstanceType<typeof AddBotIndex> | null>(null)
const envSwitchingProjectId = ref('')
const ENV_OPTIONS = ['.env', '.env.prod'] as const

// 修改路径弹窗状态
const editingBotId = ref('')
const editingPath = ref('')
const updatingPath = ref(false)

const botList = computed(() => nonebotStore.getExtendedBotsList())
const runningCount = computed(() => botList.value.filter((bot) => getRuntimeState(bot) === 'running').length)
const issueCount = computed(() => botList.value.filter((bot) => getRuntimeState(bot) === 'missing').length)

const getCurrentEnv = (bot: NoneBotProjectMeta) => {
  return bot.use_env === '.env.prod' ? '.env.prod' : '.env'
}

const getRuntimeLabel = (bot: NoneBotProjectMeta) => {
  const state = getRuntimeState(bot)
  if (state === 'missing') return '目录缺失'
  if (state === 'running') return '运行中'
  if (state === 'starting') return '启动中'
  return '未运行'
}

const getRuntimeBadgeClass = (bot: NoneBotProjectMeta) => {
  const state = getRuntimeState(bot)
  if (state === 'missing') return 'badge-error text-base-100'
  if (state === 'running') return 'badge-success text-base-100'
  if (state === 'starting') return 'badge-warning'
  return 'badge-ghost'
}

const switchEnv = async (bot: NoneBotProjectMeta, env: (typeof ENV_OPTIONS)[number]) => {
  if (envSwitchingProjectId.value === bot.project_id || getCurrentEnv(bot) === env) return
  envSwitchingProjectId.value = bot.project_id
  await nonebotStore.updateBotEnv(bot.project_id, env)
  envSwitchingProjectId.value = ''
}

const openEditPathModal = (bot: NoneBotProjectMeta) => {
  editingBotId.value = bot.project_id
  editingPath.value = bot.project_dir
  const modal = document.getElementById('edit-path-modal') as HTMLDialogElement
  modal?.showModal()
}

const confirmEditPath = async () => {
  if (!editingBotId.value || !editingPath.value.trim()) return
  updatingPath.value = true
  const success = await nonebotStore.updateBotDir(editingBotId.value, editingPath.value.trim())
  updatingPath.value = false
  if (success) {
    const modal = document.getElementById('edit-path-modal') as HTMLDialogElement
    modal?.close()
    editingBotId.value = ''
    editingPath.value = ''
  }
}

onMounted(async () => {
  await nonebotStore.loadBots()
})
</script>

<template>
  <CreateBotIndex ref="createBotModal" />
  <AddBotIndex ref="addBotModal" />

  <!-- 修改路径弹窗 -->
  <dialog id="edit-path-modal" class="modal">
    <div class="modal-box rounded-[1.5rem]">
      <h3 class="text-lg font-bold">修改实例路径</h3>
      <div class="py-4">
        <label class="form-control w-full">
          <div class="label">
            <span class="label-text">新路径</span>
          </div>
          <input
            v-model="editingPath"
            type="text"
            class="input input-bordered w-full"
            placeholder="请输入新的绝对路径"
            @keydown.enter.prevent="confirmEditPath"
          />
          <div class="label">
            <span class="label-text-alt opacity-70">路径下需要包含有效的 NoneBot 项目（有 pyproject.toml）</span>
          </div>
        </label>
      </div>
      <div class="modal-action">
        <form method="dialog">
          <button class="btn btn-ghost mr-2">取消</button>
        </form>
        <button
          class="btn btn-primary text-base-100"
          :disabled="updatingPath || !editingPath.trim()"
          @click="confirmEditPath"
        >
          {{ updatingPath ? '更新中...' : '确认' }}
        </button>
      </div>
    </div>
    <form method="dialog" class="modal-backdrop">
      <button>close</button>
    </form>
  </dialog>

  <div class="flex flex-col gap-5">
    <section class="nb-page-heading">
      <div>
        <div class="mb-2 inline-flex items-center gap-2 rounded-full bg-base-100/50 px-3 py-1 text-xs font-medium ring-1 ring-base-content/10">
          <span class="material-symbols-outlined text-base text-primary">deployed_code</span>
          Instance Workspace
        </div>
        <h1 class="text-2xl font-bold tracking-tight">实例选择</h1>
        <p class="mt-1 text-sm opacity-65">集中查看状态、切换环境、修正路径，并快速指定当前操作实例。</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <button class="btn btn-primary text-base-100" @click="createBotModal?.openModal()">
          <span class="material-symbols-outlined">add_circle</span>
          创建实例
        </button>
        <button class="btn btn-outline" @click="addBotModal?.openModal()">
          <span class="material-symbols-outlined">drive_folder_upload</span>
          添加实例
        </button>
      </div>
    </section>

    <section class="grid gap-3 md:grid-cols-3">
      <div class="nb-action-card">
        <div class="text-sm opacity-60">全部实例</div>
        <div class="mt-2 text-3xl font-bold">{{ botList.length }}</div>
      </div>
      <div class="nb-action-card">
        <div class="text-sm opacity-60">运行中</div>
        <div class="mt-2 text-3xl font-bold text-success">{{ runningCount }}</div>
      </div>
      <div class="nb-action-card">
        <div class="text-sm opacity-60">需要处理</div>
        <div class="mt-2 text-3xl font-bold text-error">{{ issueCount }}</div>
      </div>
    </section>

    <section class="nb-panel-surface rounded-[1.75rem] p-4 md:p-5">
      <div v-if="botList.length" class="grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
        <article
          v-for="bot in botList"
          :key="bot.project_id"
          role="button"
          tabindex="0"
          class="nb-focusable group rounded-[1.5rem] bg-base-100/60 p-4 ring-1 ring-base-content/5 transition hover:-translate-y-0.5 hover:bg-base-100/80 hover:shadow-xl"
          :class="{ 'ring-2 ring-primary/50': nonebotStore.selectedBot?.project_id === bot.project_id }"
          @click="nonebotStore.selectBot(bot)"
          @keydown.enter.prevent="nonebotStore.selectBot(bot)"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="flex min-w-0 items-center gap-3">
              <span class="material-symbols-outlined shrink-0 rounded-2xl bg-primary/10 p-3 text-3xl text-primary">deployed_code</span>
              <div class="min-w-0">
                <h2 class="truncate font-semibold">{{ bot.project_name }}</h2>
                <p class="mt-1 truncate text-xs opacity-60">{{ bot.project_dir }}</p>
              </div>
            </div>
            <span class="badge whitespace-nowrap" :class="getRuntimeBadgeClass(bot)">
              {{ getRuntimeLabel(bot) }}
            </span>
          </div>

          <div class="mt-4 flex flex-wrap items-center gap-2">
            <span
              v-if="nonebotStore.selectedBot?.project_id === bot.project_id"
              class="badge badge-primary text-base-100"
            >
              当前选择
            </span>
            <span class="badge badge-outline">{{ getCurrentEnv(bot) }}</span>
          </div>

          <div class="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between" @click.stop>
            <div class="join join-horizontal w-fit">
              <button
                v-for="env in ENV_OPTIONS"
                :key="`${bot.project_id}-${env}`"
                type="button"
                class="join-item btn btn-xs min-w-[5.5rem]"
                :class="getCurrentEnv(bot) === env ? 'btn-primary text-base-100' : 'btn-outline'"
                :disabled="envSwitchingProjectId === bot.project_id"
                @click.stop="switchEnv(bot, env)"
              >
                {{ env }}
              </button>
            </div>
            <button class="btn btn-ghost btn-xs" @click.stop="openEditPathModal(bot)">
              <span class="material-symbols-outlined text-base">edit_location_alt</span>
              修改路径
            </button>
          </div>
        </article>
      </div>

      <div v-else class="grid min-h-64 place-items-center rounded-[1.5rem] bg-base-100/45 p-8 text-center">
        <div>
          <span class="material-symbols-outlined text-5xl opacity-35">inventory_2</span>
          <h2 class="mt-3 text-lg font-semibold">暂无实例</h2>
          <p class="mt-1 text-sm opacity-60">创建一个新项目，或接入已有 NoneBot 项目开始管理。</p>
          <div class="mt-4 flex justify-center gap-2">
            <button class="btn btn-sm btn-primary text-base-100" @click="createBotModal?.openModal()">创建实例</button>
            <button class="btn btn-sm btn-outline" @click="addBotModal?.openModal()">添加实例</button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
