<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { ProcessService, ProjectService } from '@/client/api'
import { getErrorMessage, sleep } from '@/client/utils'
import { useNoneBotStore, useToastStore } from '@/stores'

const store = useNoneBotStore()
const toast = useToastStore()

const deleteConfirmModal = ref<HTMLDialogElement>()
const operating = ref(false)
const deleting = ref(false)
const deleteCountdown = ref(0)
let deleteCountdownTimer: ReturnType<typeof setInterval> | null = null

const hasBot = computed(() => Boolean(store.selectedBot))
const selectedBot = computed(() => store.selectedBot)
const canDelete = computed(
  () =>
    hasBot.value &&
    !store.selectedBot?.is_running &&
    !operating.value &&
    !deleting.value
)
const canConfirmDelete = computed(() => deleteCountdown.value <= 0 && !deleting.value && !operating.value)
const statusLabel = computed(() => (selectedBot.value?.is_running ? '运行中' : '未运行'))
const statusClass = computed(() =>
  selectedBot.value?.is_running
    ? 'badge-success text-base-100'
    : 'badge-error text-base-100'
)
const actionSummary = computed(() => {
  if (!selectedBot.value) return '请选择一个实例后再执行启动、停止、重启或删除操作。'
  if (operating.value) return '正在与后端同步实例状态，请稍候。'
  if (deleting.value) return '正在删除实例记录，请不要关闭当前页面。'
  if (selectedBot.value.is_running) return '实例正在运行，可在右侧 Shell 中继续执行维护命令。'
  return '实例当前未运行，可先在这里启动，也可以直接进入下方常驻 Shell 做依赖排查。'
})
const actionButtons = computed(() => [
  {
    key: 'run',
    label: '启动',
    desc: '按当前环境变量启动实例',
    variant: 'btn-primary text-base-100',
    disabled: Boolean(selectedBot.value?.is_running) || operating.value || deleting.value,
    action: runBot
  },
  {
    key: 'stop',
    label: '停止',
    desc: '终止当前实例进程',
    variant: 'btn-ghost',
    disabled: !selectedBot.value?.is_running || operating.value || deleting.value,
    action: stopBot
  },
  {
    key: 'restart',
    label: '重启',
    desc: '停止后重新启动实例',
    variant: 'btn-ghost',
    disabled: !selectedBot.value?.is_running || operating.value || deleting.value,
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

const reloadAndSyncSelection = async () => {
  await store.loadBots()
  if (!store.selectedBot && Object.values(store.bots).length) {
    store.selectBot(Object.values(store.bots)[0])
  }
}

const runBot = async () => {
  if (!store.selectedBot || operating.value || deleting.value) return
  operating.value = true

  const projectId = store.selectedBot.project_id
  const projectName = store.selectedBot.project_name
  const { data, error } = await ProcessService.runProcessV1ProcessRunPost({
    query: { project_id: projectId }
  })

  if (error) {
    toast.add('error', `启动失败，原因：${getErrorMessage(error)}`, '', 5000)
  }
  if (data) {
    await reloadAndSyncSelection()
    toast.add('success', `${projectName} 已启动`, '', 3000)
  }

  operating.value = false
}

const stopBot = async () => {
  if (!store.selectedBot || operating.value || deleting.value) return
  operating.value = true

  const projectId = store.selectedBot.project_id
  const projectName = store.selectedBot.project_name
  const { data, error } = await ProcessService.stopProcessV1ProcessStopPost({
    query: { project_id: projectId }
  })

  if (error) {
    toast.add('error', `停止失败，原因：${getErrorMessage(error)}`, '', 5000)
  }
  if (data) {
    await reloadAndSyncSelection()
    toast.add('success', `${projectName} 已停止`, '', 3000)
  }

  operating.value = false
}

const restartBot = async () => {
  if (!store.selectedBot || operating.value || deleting.value) return
  await stopBot()

  const pollingInterval = 600
  const maxAttempts = 20
  let attempts = 0
  while (attempts < maxAttempts) {
    attempts++
    await store.loadBots()
    if (!store.selectedBot?.is_running) break
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
    await reloadAndSyncSelection()
    toast.add('success', `${projectName} 已删除`, '', 3000)
  }

  deleting.value = false
}

onUnmounted(() => {
  clearDeleteCountdown()
})
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
              {{ canDelete ? '实例已停止，可安全删除' : '运行中实例会禁用删除按钮' }}
            </div>
          </div>

          <div class="rounded-2xl border border-base-content/10 bg-base-100/70 px-4 py-3 backdrop-blur">
            <div class="text-xs uppercase tracking-[0.18em] text-base-content/45">当前节奏</div>
            <div class="mt-2 text-sm text-base-content/80">
              {{ operating ? '正在同步状态…' : deleting ? '正在删除…' : selectedBot?.is_running ? '适合观察日志与发送维护命令' : '适合启动实例或先在 Shell 排障' }}
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
