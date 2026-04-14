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
const canDelete = computed(
  () =>
    hasBot.value &&
    !store.selectedBot?.is_running &&
    Object.values(store.bots).length > 1 &&
    !operating.value &&
    !deleting.value
)
const canConfirmDelete = computed(() => deleteCountdown.value <= 0 && !deleting.value && !operating.value)

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
    <div class="modal-box rounded-lg flex flex-col gap-4">
      <h3 class="font-semibold text-lg">确定删除实例吗？</h3>
      <div class="grid grid-cols-3 gap-4">
        <button
          class="btn btn-sm hover:btn-primary shadow-none"
          :disabled="!canConfirmDelete"
          @click="deleteBot(true)"
        >
          {{ deleteCountdown > 0 ? `彻底删除 (${deleteCountdown}s)` : '彻底删除' }}
        </button>
        <button
          class="btn btn-sm hover:btn-warning shadow-none"
          :disabled="!canConfirmDelete"
          @click="deleteBot(false)"
        >
          {{ deleteCountdown > 0 ? `仅删除记录 (${deleteCountdown}s)` : '仅删除记录' }}
        </button>
        <button class="btn btn-sm shadow-none" :disabled="deleting" @click="deleteConfirmModal?.close()">
          取消
        </button>
      </div>
    </div>
  </dialog>

  <div
    class="w-full p-6 bg-base-200 rounded-box flex flex-col md:flex-row items-center justify-between gap-2 md:gap-0"
  >
    <div class="flex items-center gap-4">
      <div class="text-lg font-semibold">{{ store.selectedBot?.project_name }}</div>
      <div class="flex items-center gap-2">
        <div class="badge badge-sm text-gray-500">{{ store.selectedBot?.project_id }}</div>
        <div v-if="store.selectedBot?.is_running" class="badge badge-sm badge-success text-base-100">
          运行中
        </div>
        <div v-else class="badge badge-sm badge-error text-base-100">未运行</div>
      </div>
    </div>

    <div class="flex gap-2">
      <button
        :class="{ 'btn btn-sm btn-primary font-normal text-base-100': true, 'btn-disabled': store.selectedBot?.is_running || operating || deleting }"
        @click="runBot()"
      >
        启动
      </button>
      <button
        :class="{ 'btn btn-sm shadow-none font-normal': true, 'btn-disabled': !store.selectedBot?.is_running || operating || deleting }"
        @click="stopBot()"
      >
        停止
      </button>
      <button
        :class="{ 'btn btn-sm shadow-none font-normal border-red': true, 'btn-disabled': !store.selectedBot?.is_running || operating || deleting }"
        @click="restartBot()"
      >
        重启
      </button>
      <button
        :class="{ 'btn btn-sm btn-outline btn-primary shadow-none font-normal': true, 'btn-disabled': !canDelete }"
        :disabled="!canDelete"
        @click="openDeleteConfirm()"
      >
        删除
      </button>
    </div>
  </div>
</template>
