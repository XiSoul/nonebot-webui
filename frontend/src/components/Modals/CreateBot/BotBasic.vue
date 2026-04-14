<script setup lang="ts">
import { ref } from 'vue'
import { limitContentShow } from '@/client/utils'
import FolderSelect from '@/components/Modals/Global/FolderSelect.vue'
import { useCreateBotStore } from '.'

const store = useCreateBotStore()

const folderSelectModal = ref<InstanceType<typeof FolderSelect> | null>()

const acceptModalData = (data: string) => {
  store.projectPath = data
}
</script>

<template>
  <div class="flex flex-col gap-8">
    <FolderSelect ref="folderSelectModal" @select-folder="acceptModalData" />

    <div class="flex flex-col items-center justify-center w-full">
      <div class="form-control w-full max-w-xs">
        <div class="label">
          <span class="label-text">实例名称</span>
        </div>
        <input
          type="text"
          placeholder="请输入"
          class="input input-bordered w-full max-w-xs"
          v-model="store.projectName"
        />
      </div>

      <div class="form-control w-full max-w-xs">
        <div class="label">
          <span class="label-text">实例绝对路径</span>
        </div>
        <input
          type="text"
          placeholder="例如: /data/nonebot 或 /home/xisoul/bots"
          class="input input-bordered w-full max-w-xs"
          v-model="store.projectPath"
        />
        <div class="label py-1">
          <span class="label-text-alt opacity-70"
            >支持手动输入目录（可用容器挂载目录，避免重建容器后丢失数据）</span
          >
        </div>
        <button class="btn btn-outline btn-primary" @click="folderSelectModal?.openModal">
          从 Base Dir 选择
        </button>
        <div class="label">
          <span v-if="store.projectPath" class="label-text bg-base-300 p-1 rounded w-full">
            当前路径: {{ limitContentShow(store.projectPath, 60) }}
          </span>
        </div>
      </div>
    </div>

    <div class="w-full flex items-center">
      <button class="btn btn-sm btn-primary text-base-100" @click="store.step--">上一步</button>

      <div class="w-full"></div>

        <button
          :class="{
          'btn btn-sm btn-primary text-base-100': true,
          'btn-disabled': !store.projectName.trim().length || !store.projectPath.trim().length
        }"
        @click="store.step++"
      >
        下一步
      </button>
    </div>
  </div>
</template>
