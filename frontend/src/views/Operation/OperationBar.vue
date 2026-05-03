<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ProcessService, ProjectService } from '@/client/api'
import { getErrorMessage, sleep } from '@/client/utils'
import { useNoneBotStore, useToastStore } from '@/stores'
import { getRuntimeState, type RuntimeState } from '@/utils/runtimeState'

const store = useNoneBotStore()
const toast = useToastStore()

const deleteConfirmModal = ref<HTMLDialogElement>()
const operating = ref(false)
const deleting = ref(false)
const deleteCountdown = ref(0)
let deleteCountdownTimer: ReturnType<typeof setInterval> | null = null
const pendingRuntimeState = ref<RuntimeState | ''>('')

const runtimeState = computed<RuntimeState>(() => pendingRuntimeState.value || getRuntimeState(selectedBot.value))
const isStopped = computed(() => runtimeState.value === 'stopped')
const isStarting = computed(() => runtimeState.value === 'starting')
const isRunning = computed(() => runtimeState.value === 'running')

const hasBot = computed(() => Boolean(store.selectedBot))
const selectedBot = computed(() => store.selectedBot)
const canDelete = computed(
  () =>
    hasBot.value &&
    isStopped.value &&
    !operating.value &&
    !deleting.value
)
const canConfirmDelete = computed(() => deleteCountdown.value <= 0 && !deleting.value && !operating.value)
const statusLabel = computed(() => {
  if (isRunning.value) return '运行中'
  if (isStarting.value) return '启动中'
  return '未运行'
})
const statusClass = computed(() =>
  isRunning.value
    ? 'badge-success text-base-100'
    : isStarting.value
      ? 'badge-warning'
      : 'badge-error text-base-100'
)
const startupDurationLabel = computed(() => {
  const seconds = Number(selectedBot.value?.startup_duration_seconds ?? 0)
  if (!isRunning.value || !Number.isFinite(seconds) || seconds <= 0) return ''
  return `本次启动 ${seconds >= 10 ? seconds.toFixed(0) : seconds.toFixed(1)}s`
})
const actionSummary = computed(() => {
  if (!selectedBot.value) return '请选择一个实例后再执行启动、停止、重启或删除操作。'
  if (deleting.value) return '正在删除实例记录，请不要关闭当前页面。'
  if (isStarting.value) return '实例正在启动或初始化依赖，此时可以点击停止，避免卡死在启动流程。'
  if (operating.value) return '正在与后端同步实例状态，请稍候。'
  if (isRunning.value) return '实例正在运行，可在右侧 Shell 中继续执行维护命令。'
  return '实例当前未运行，可先在这里启动，也可以直接进入下方常驻 Shell 做依赖排查。'
})
const actionButtons = computed(() => [
  {
    key: 'run',
    label: '启动',
    desc: '按当前环境变量启动实例',
    variant: 'btn-primary text-base-100',
    disabled: !isStopped.value || operating.value || deleting.value,
    action: runBot
  },
  {
    key: 'stop',
    label: '停止',
    desc: '终止当前实例进程',
    variant: 'btn-ghost',
    disabled: (isStopped.value && !isStarting.value) || deleting.value,
    action: stopBot
  },
  {
    key: 'restart',
    label: '重启',
    desc: isStopped.value ? '当前未运行时执行重新启动' : '终止当前实例后重新启动',
    variant: 'btn-ghost',
    disabled: !hasBot.value || deleting.value || isStarting.value,
    action: restartBot
  },
  {
    key: 'delete',
    label: '删除',
    desc: '移除记录或彻底删除目录',
    variant: 'btn-outline btn-primary',
    disabled: !canDelete.value,
    action: openDeleteConfirm
  }
])

const clearDeleteCountdown = () => {
  if (deleteCountdownTimer) {
    clearInterval(deleteCountdownTimer)
    deleteCountdownTimer = null
  }
}

const waitForRuntimeState = async (
  expectedStates: RuntimeState[],
  {
    projectId,
    attempts = 60,
    interval = 1000
  }: {
    projectId: string
    attempts?: number
    interval?: number
  }
) => {
  for (let index = 0; index < attempts; index += 1) {
    await store.loadBots()
    const nextBot = store.bots[projectId]
    const nextState = getRuntimeState(nextBot)
    if (expectedStates.includes(nextState)) {
      return nextState
    }
    await sleep(interval)
  }
  return getRuntimeState(store.bots[projectId])
}

const markStarting = (projectId: string) => {
  pendingRuntimeState.value = 'starting'
}

const syncRuntimeState = async () => {
  await store.loadBots()
  if (pendingRuntimeState.value && store.selectedBot) {
    const nextState = getRuntimeState(store.selectedBot)
    if (nextState !== pendingRuntimeState.value || nextState === 'stopped') {
      pendingRuntimeState.value = ''
    }
  }
}

const openDeleteConfirm = () => {
  if (!canDelete.value) return
  clearDeleteCountdown()
  deleteCountdown.value = 3
  deleteCountdownTimer = setInterval(() => {
    deleteCountdown.value -= 1
    if (deleteCountdown.value <= 0) {
      deleteCountdown.value = 0
      clearDeleteCountdown()
    }
  }, 1000)
  deleteConfirmModal.value?.showModal()
}

const runBot = async () => {
  if (!store.selectedBot || operating.value || deleting.value) return
  operating.value = true

  const projectId = store.selectedBot.project_id
  const projectName = store.selectedBot.project_name
  markStarting(projectId)
  const { data, error } = await ProcessService.runProcessV1ProcessRunPost({
    query: { project_id: projectId }
  })

  if (error) {
    pendingRuntimeState.value = ''
    toast.add('error', `启动失败，原因：${getErrorMessage(error)}`, '', 5000)
  }
  if (data) {
    const nextState = await waitForRuntimeState(['running', 'stopped'], {
      projectId,
      attempts: 90,
      interval: 1000
    })
    pendingRuntimeState.value = ''
    if (nextState === 'running') {
      toast.add('success', `${projectName} 已启动`, '', 3000)
    } else {
      await syncRuntimeState()
      toast.add('warning', `${projectName} 启动流程已结束，但实例未进入运行中，请查看右侧日志`, '', 5000)
    }
  }

  operating.value = false
}

const stopBot = async () => {
  if (!store.selectedBot || operating.value || deleting.value) return
  operating.value = true

  const projectId = store.selectedBot.project_id
  const projectName = store.selectedBot.project_name
  pendingRuntimeState.value = 'stopped'
  const { data, error } = await ProcessService.stopProcessV1ProcessStopPost({
    query: { project_id: projectId }
  })

  if (error) {
    pendingRuntimeState.value = ''
    toast.add('error', `停止失败，原因：${getErrorMessage(error)}`, '', 5000)
  }
  if (data) {
    await syncRuntimeState()
    toast.add('success', `${projectName} 已停止`, '', 3000)
  }

  operating.value = false
}

const restartBot = async () => {
  if (!store.selectedBot || operating.value || deleting.value) return
  if (isStopped.value) {
    await runBot()
    return
  }
  await stopBot()

  const pollingInterval = 600
  const maxAttempts = 20
  let attempts = 0
  while (attempts < maxAttempts) {
    attempts++
    await store.loadBots()
    if (getRuntimeState(store.selectedBot) === 'stopped') break
    await sleep(pollingInterval)
  }

  if (attempts >= maxAttempts) {
    toast.add('error', '重启失败：等待停止超时', '', 5000)
    return
  }
  await runBot()
}

const deleteBot = async (isFully: boolean) => {
  if (!store.selectedBot || !canDelete.value) return
  deleting.value = true

  const projectId = store.selectedBot.project_id
  const projectName = store.selectedBot.project_name
  deleteConfirmModal.value?.close()

  const { data, error } = await ProjectService.deleteProjectV1ProjectDeleteDelete({
    query: {
      project_id: projectId,
      delete_fully: isFully
    }
  })

  if (error) {
    toast.add('error', `删除失败，原因：${getErrorMessage(error)}`, '', 5000)
    deleting.value = false
    return
  }

  if (data) {
    await syncRuntimeState()
    toast.add('success', `${projectName} 已删除`, '', 3000)
  }

  deleting.value = false
}

onUnmounted(() => {
  clearDeleteCountdown()
})

watch(
  () => store.selectedBot,
  (bot) => {
    if (!pendingRuntimeState.value || !bot) return
    const nextState = getRuntimeState(bot)
    if (nextState !== pendingRuntimeState.value || nextState === 'stopped') {
      pendingRuntimeState.value = ''
    }
  },
  { deep: true }
)
</script>

<template>
  <dialog ref="deleteConfirmModal" class="modal">
    <div class="modal-box rounded-[24px] border border-base-content/10 bg-base-100 shadow-2xl flex flex-col gap-5">
      <div class="flex flex-col gap-2">
        <h3 class="font-semibold text-lg">确定删除实例吗？</h3>
        <p class="text-sm opacity-70">
          你可以只删除 WebUI 记录，也可以连实例目录一起删除。为避免误触，按钮会短暂倒计时后再解锁。
        </p>
      </div>
      <div class="grid gap-3 md:grid-cols-3">
        <button
          class="btn btn-sm btn-error text-base-100 shadow-none"
          :disabled="!canConfirmDelete"
          @click="deleteBot(true)"
        >
          {{ deleteCountdown > 0 ? `彻底删除 (${deleteCountdown}s)` : '彻底删除' }}
        </button>
        <button
          class="btn btn-sm btn-warning shadow-none"
          :disabled="!canConfirmDelete"
          @click="deleteBot(false)"
        >
          {{ deleteCountdown > 0 ? `仅删除记录 (${deleteCountdown}s)` : '仅删除记录' }}
        </button>
        <button class="btn btn-sm btn-ghost shadow-none" :disabled="deleting" @click="deleteConfirmModal?.close()">
          取消
        </button>
      </div>
    </div>
  </dialog>

  <section class="relative overflow-hidden rounded-[28px] border border-base-content/10 bg-base-200 px-5 py-6 shadow-sm lg:px-7 lg:py-7">
    <div class="pointer-events-none absolute inset-0 opacity-60">
      <div class="absolute -right-16 top-0 h-40 w-40 rounded-full bg-primary/10 blur-3xl"></div>
      <div class="absolute bottom-0 left-0 h-32 w-32 rounded-full bg-info/10 blur-3xl"></div>
    </div>

    <div class="relative flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
      <div class="flex min-w-0 flex-1 flex-col gap-4">
        <div class="flex flex-wrap items-center gap-3 text-xs uppercase tracking-[0.24em] text-base-content/45">
          <span>实例控制台</span>
          <span class="h-px w-10 bg-base-content/10"></span>
          <span>{{ selectedBot?.use_env || '.env' }}</span>
        </div>

        <div class="flex flex-col gap-3">
          <div class="flex flex-wrap items-center gap-3">
            <h1 class="max-w-full truncate text-2xl font-semibold lg:text-3xl">
              {{ selectedBot?.project_name || '未选择实例' }}
            </h1>
            <div class="badge badge-lg badge-ghost font-mono text-base-content/70">
              {{ selectedBot?.project_id || 'unknown' }}
            </div>
            <div class="badge badge-lg" :class="statusClass">
              {{ statusLabel }}
            </div>
            <div
              v-if="startupDurationLabel"
              class="badge badge-lg badge-outline font-mono text-base-content/70"
            >
              {{ startupDurationLabel }}
            </div>
          </div>

          <p class="max-w-3xl text-sm leading-6 text-base-content/70">
            {{ actionSummary }}
          </p>
        </div>

        <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <div class="rounded-2xl border border-base-content/10 bg-base-100/70 px-4 py-3 backdrop-blur">
            <div class="text-xs uppercase tracking-[0.18em] text-base-content/45">实例路径</div>
            <div class="mt-2 break-all font-mono text-sm text-base-content/80">
              {{ selectedBot?.project_dir || '-' }}
            </div>
          </div>

          <div class="rounded-2xl border border-base-content/10 bg-base-100/70 px-4 py-3 backdrop-blur">
            <div class="text-xs uppercase tracking-[0.18em] text-base-content/45">操作保护</div>
            <div class="mt-2 text-sm text-base-content/80">
              {{ canDelete ? '实例已停止，可安全删除' : '启动中或运行中实例会禁用删除按钮' }}
            </div>
          </div>

          <div class="rounded-2xl border border-base-content/10 bg-base-100/70 px-4 py-3 backdrop-blur">
            <div class="text-xs uppercase tracking-[0.18em] text-base-content/45">当前节奏</div>
            <div class="mt-2 text-sm text-base-content/80">
              {{ operating ? '正在同步状态…' : deleting ? '正在删除…' : isStarting ? '适合停止卡住的启动流程或直接重启' : isRunning ? '适合观察日志与发送维护命令' : '适合启动实例或先在 Shell 排障' }}
            </div>
          </div>
        </div>
      </div>

      <div class="grid gap-3 sm:grid-cols-2 xl:w-[26rem]">
        <button
          v-for="item in actionButtons"
          :key="item.key"
          class="btn h-auto min-h-0 justify-start gap-3 rounded-2xl border border-base-content/10 px-4 py-4 normal-case shadow-none"
          :class="item.variant"
          :disabled="item.disabled"
          @click="item.action()"
        >
          <div class="flex flex-col items-start gap-1">
            <span class="text-sm font-semibold">{{ item.label }}</span>
            <span class="text-left text-xs opacity-80">{{ item.desc }}</span>
          </div>
        </button>
      </div>
    </div>
  </section>
</template>
