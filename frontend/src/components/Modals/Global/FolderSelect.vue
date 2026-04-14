<script setup lang="ts">
import { FileService, type FileInfo } from '@/client/api'
import { covertTimestampToDateString, limitContentShow } from '@/client/utils'
import { ref } from 'vue'
import { useToastStore } from '@/stores'

const emit = defineEmits<{
  selectFolder: [value: string]
}>()

const folderSelectModal = ref<HTMLDialogElement>()
const toast = useToastStore()

defineExpose({
  openModal: async () => {
    folderSelectModal.value?.showModal()

    await getFileList('.')
  },
  closeModal: () => {
    folderSelectModal.value?.close()
  }
})

const newFolderModal = ref<HTMLDialogElement>()

const fileList = ref<FileInfo[]>([]),
  newFolderName = ref(''),
  currentPath = ref(''),
  selectedFolder = ref(''),
  isCreatingFolder = ref(false)

const getErrorMessage = (error: any): string => {
  if (!error) return '未知错误'
  const detail = error.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || JSON.stringify(item)).join('; ')
  }
  if (detail && typeof detail === 'object') return JSON.stringify(detail)
  return String(error)
}

const getFileList = async (path: string) => {
  const { data, error } = await FileService.getFileListV1FileListGet({
    query: {
      path: path
    }
  })

  if (error) {
    toast.add('error', `读取目录失败：${getErrorMessage(error)}`, '', 5000)
    fileList.value = []
    return
  }

  if (data) {
    fileList.value = data.detail
  }
}

const createFolder = async (folderName: string, path: string) => {
  isCreatingFolder.value = true
  const name = folderName.trim()
  if (!name) {
    isCreatingFolder.value = false
    return
  }

  const { data, error } = await FileService.createFileV1FileCreatePost({
    body: {
      name,
      path: path,
      is_dir: true
    }
  })

  if (error) {
    toast.add('error', `新建文件夹失败：${getErrorMessage(error)}`, '', 5000)
    isCreatingFolder.value = false
    return
  }

  if (data) {
    fileList.value = data.detail
    if (currentPath.value) {
      selectedFolder.value = `${currentPath.value}/${name}`
    } else {
      selectedFolder.value = name
    }
    newFolderName.value = ''
    newFolderModal.value?.close()
  }
  isCreatingFolder.value = false
}

const deleteFolder = async (path: string) => {
  if (!path) return

  const confirmed = window.confirm(`确定彻底删除目录 "${path}" 吗？`)
  if (!confirmed) return

  const { data, error } = await FileService.deleteFileV1FileDeleteDelete({
    query: {
      path: path
    }
  })

  if (error) {
    toast.add('error', `删除文件夹失败：${getErrorMessage(error)}`, '', 5000)
    return
  }

  if (selectedFolder.value === path) {
    selectedFolder.value = ''
  }

  if (data) {
    fileList.value = data.detail
  }
}

const updateFileList = async (path: string, isFolder: boolean) => {
  if (!isFolder) return

  currentPath.value = path
  await getFileList(path)
}

const selectFolder = (path: string, isFolder: boolean) => {
  if (!isFolder) return
  selectedFolder.value = path
}
</script>

<template>
  <dialog ref="folderSelectModal" class="modal">
    <div class="modal-box w-11/12 max-w-5xl rounded-xl flex flex-col gap-4">
      <h3 class="font-semibold text-lg">文件夹选择</h3>

      <div class="overflow-hidden max-h-96 h-full bg-base-200 rounded-lg p-4">
        <div class="text-sm breadcrumbs pb-2">
          <ul>
            <li @click="updateFileList('', true)">
              <a>(Base Dir) /</a>
            </li>
            <li v-for="(item, index) in currentPath.split('/')" :key="item">
              <a
                @click="
                  updateFileList(
                    currentPath
                      .split('/')
                      .slice(0, index + 1)
                      .join('/'),
                    true
                  )
                "
              >
                {{ item }}
              </a>
            </li>
          </ul>
        </div>

        <div class="overflow-auto max-h-80">
          <table class="table table-pin-rows w-full">
            <thead class="z-10">
              <tr class="border-b-0">
                <th class="rounded-s-lg">名称</th>
                <th>修改时间</th>
                <th>类型</th>
                <th class="rounded-e-lg">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="file in fileList"
                :key="file.name"
                role="button"
                class="transition hover:bg-base-300"
                @click="selectFolder(file.path, file.is_dir)"
              >
                <td class="flex items-center gap-1 shrink-0 whitespace-nowrap">
                  <span class="material-symbols-outlined">
                    {{ file.is_dir ? 'folder' : 'draft' }}
                  </span>
                  <a class="hover:link" @click="updateFileList(file.path, file.is_dir)">
                    {{ limitContentShow(file.name, 10) }}
                  </a>
                </td>
                <td class="whitespace-nowrap">
                  {{ covertTimestampToDateString(file.modified_time) }}
                </td>
                <td class="whitespace-nowrap">{{ file.is_dir ? '文件夹' : '文件' }}</td>
                <td class="flex items-center whitespace-nowrap">
                  <button
                    class="btn btn-ghost btn-xs text-error"
                    @click.stop="deleteFolder(file.path)"
                  >
                    <span class="fill-current material-symbols-outlined">delete</span>
                  </button>
                </td>
              </tr>
              <tr v-if="!fileList.length">
                <td colspan="4" class="text-center">暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="bg-base-200 rounded-lg p-4 text-sm">
        当前选择:
        <span v-if="selectedFolder" class="bg-base-300 p-1 rounded">
          (Base Dir)/{{ selectedFolder }}
        </span>
      </div>

      <div class="flex justify-between flex-col md:flex-row gap-4 md:gap-0">
        <div class="flex gap-4 justify-between md:justify-start">
          <button class="btn btn-sm" @click="updateFileList(currentPath, true)">刷新</button>
          <button class="btn btn-sm" @click="newFolderModal?.showModal()">新建文件夹</button>
          <button class="btn btn-sm" @click="selectFolder(currentPath, true)">选中当前目录</button>
        </div>

        <div class="flex gap-4 justify-end">
          <button class="btn btn-sm" @click="folderSelectModal?.close()">取消</button>
          <button
            :class="{
              'btn btn-sm btn-primary text-base-100': true,
              'btn-disabled': !selectedFolder
            }"
            @click="folderSelectModal?.close(), emit('selectFolder', selectedFolder)"
          >
            确认
          </button>
        </div>
      </div>
    </div>
  </dialog>

  <dialog ref="newFolderModal" class="modal">
    <div class="modal-box rounded-xl flex flex-col gap-4">
      <h3 class="font-semibold text-lg">新建文件夹</h3>
      <div class="flex justify-center">
        <input
          type="text"
          placeholder="请输入"
          class="input input-bordered w-full max-w-xs"
          v-model="newFolderName"
        />
      </div>
      <div class="flex justify-end gap-4">
        <button class="btn btn-sm" @click="newFolderModal?.close(), (newFolderName = '')">
          取消
        </button>
        <button
          :class="{
            'btn btn-sm btn-primary text-base-100': true,
            'btn-disabled': !newFolderName.trim() || isCreatingFolder
          }"
          @click="createFolder(newFolderName, currentPath)"
        >
          {{ isCreatingFolder ? '创建中...' : '确认' }}
        </button>
      </div>
    </div>
  </dialog>
</template>

<style scoped>
.material-symbols-outlined {
  font-variation-settings:
    'FILL' 0,
    'wght' 300,
    'GRAD' 0,
    'opsz' 24;
}
</style>
