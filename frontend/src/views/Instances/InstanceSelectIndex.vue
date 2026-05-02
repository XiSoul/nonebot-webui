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

const getCurrentEnv = (bot: NoneBotProjectMeta) => {
  return bot.use_env === '.env.prod' ? '.env.prod' : '.env'
}

const switchEnv = async (bot: NoneBotProjectMeta, env: (typeof ENV_OPTIONS)[number]) => {
  if (envSwitchingProjectId.value === bot.project_id || getCurrentEnv(bot) === env) return
  envSwitchingProjectId.value = bot.project_id
  await nonebotStore.updateBotEnv(bot.project_id, env)
  envSwitchingProjectId.value = ''
}

onMounted(async () => {
  await nonebotStore.loadBots()
})
</script>

<template>
  <CreateBotIndex ref="createBotModal" />
  <AddBotIndex ref="addBotModal" />

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
              <div class="text-xs opacity-60 truncate">{{ bot.project_dir }}</div>
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
                getRuntimeState(bot) === 'running'
                  ? 'badge-success text-base-100'
                  : getRuntimeState(bot) === 'starting'
                    ? 'badge-warning'
                    : 'badge-ghost'
              "
            >
              {{
                getRuntimeState(bot) === 'running'
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
