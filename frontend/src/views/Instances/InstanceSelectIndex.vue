<script setup lang="ts">
import { onMounted, ref } from 'vue'
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

const getCurrentEnv = (bot: NoneBotProjectMeta) => {
  return bot.use_env === '.env.prod' ? '.env.prod' : '.env'
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
    <div class="modal-box">
      <h3 class="font-bold text-lg">修改实例路径</h3>
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

  <div class="flex flex-col gap-4">
    <div class="p-6 rounded-box bg-base-200 flex flex-col md:flex-row md:items-center gap-4">
      <div class="text-lg font-semibold">实例选择</div>
      <div class="md:ml-auto flex gap-2">
        <button class="btn btn-sm btn-primary text-base-100" @click="createBotModal?.openModal()">
          创建实例
        </button>
        <button class="btn btn-sm btn-outline btn-primary" @click="addBotModal?.openModal()">
          添加实例
        </button>
      </div>
    </div>

    <div class="p-6 rounded-box bg-base-200">
      <div v-if="nonebotStore.getExtendedBotsList().length" class="grid gap-3">
        <div
          v-for="bot in nonebotStore.getExtendedBotsList()"
          :key="bot.project_id"
          role="button"
          class="flex items-center justify-between gap-4 transition bg-base-100 hover:bg-base-300 rounded-lg p-4"
          @click="nonebotStore.selectBot(bot)"
        >
          <div class="flex items-center gap-3 min-w-0 flex-1">
            <span class="material-symbols-outlined text-3xl shrink-0"> deployed_code </span>
            <div class="min-w-0 flex-1">
              <div class="flex flex-col gap-2 min-w-0 md:flex-row md:items-center md:gap-3">
                <div class="font-medium truncate">{{ bot.project_name }}</div>
                <div
                  class="join join-horizontal w-fit"
                  @click.stop
                >
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
              </div>
              <div class="flex items-center gap-2">
                <div class="text-xs opacity-60 truncate flex-1">{{ bot.project_dir }}</div>
                <button
                  class="btn btn-ghost btn-xs opacity-50 hover:opacity-100 transition"
                  @click.stop="openEditPathModal(bot)"
                >
                  修改路径
                </button>
              </div>
            </div>
          </div>
          <div class="shrink-0 flex flex-wrap justify-end gap-2">
            <span
              v-if="nonebotStore.selectedBot?.project_id === bot.project_id"
              class="badge bg-blue-500 text-base-100"
            >
              当前选择
            </span>
            <span
              class="badge"
              :class="
                getRuntimeState(bot) === 'missing'
                  ? 'badge-error text-base-100'
                  : getRuntimeState(bot) === 'running'
                    ? 'badge-success text-base-100'
                    : getRuntimeState(bot) === 'starting'
                      ? 'badge-warning'
                      : 'badge-ghost'
              "
            >
              {{
                getRuntimeState(bot) === 'missing'
                  ? '目录缺失'
                  : getRuntimeState(bot) === 'running'
                    ? '运行中'
                    : getRuntimeState(bot) === 'starting'
                      ? '启动中'
                      : '未运行'
              }}
            </span>
          </div>
        </div>
      </div>
      <div v-else class="text-center opacity-70">暂无实例</div>
    </div>
  </div>
</template>
