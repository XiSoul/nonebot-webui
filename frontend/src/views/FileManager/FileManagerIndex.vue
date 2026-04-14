<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { editor as monacoEditor } from 'monaco-editor/esm/vs/editor/editor.api.js'
import EditorItem from '@/components/EditorItem.vue'
import { useCustomStore, useNoneBotStore, useToastStore } from '@/stores'
import { covertTimestampToDateString } from '@/client/utils'
import {
  type FileManagerEntry,
  type FileManagerRoot,
  type FileManagerScope,
  createFileManagerEntry,
  deleteFileManagerEntry,
  getFileManagerContent,
  getFileManagerList,
  getFileManagerRoots,
  saveFileManagerContent
} from './file-manager-client'

const customStore = useCustomStore()
const nonebotStore = useNoneBotStore()
const toast = useToastStore()

const loadingRoots = ref(false)
const loadingList = ref(false)
const loadingContent = ref(false)
const savingContent = ref(false)
const roots = ref<FileManagerRoot[]>([])
const entries = ref<FileManagerEntry[]>([])
const currentPath = ref('')
const selectedEntryPath = ref('')
const openedFilePath = ref('')
const editorValue = ref('')
const savedValue = ref('')
const openedEncoding = ref('utf-8')
const editor = ref<monacoEditor.IStandaloneCodeEditor>()

const selectedProject = computed(() => nonebotStore.selectedBot)
const selectedProjectId = computed(() => selectedProject.value?.project_id || '')
const selectedProjectName = computed(() => selectedProject.value?.project_name || '')
const currentRoot = computed(() => roots.value[0])
const currentScope = computed<FileManagerScope>(() => currentRoot.value?.scope || 'mapped')
const isRootAvailable = computed(() => Boolean(currentRoot.value?.available))
const isDirty = computed(() => openedFilePath.value && editorValue.value !== savedValue.value)
const breadcrumbParts = computed(() =>
  currentPath.value ? currentPath.value.split('/').filter(Boolean) : []
)

const formatSize = (size: number) => {
  if (!size) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let value = size
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`
}

const guessLanguage = (path: string) => {
  const lower = path.toLowerCase()
  if (lower.endsWith('.py')) return 'python'
  if (lower.endsWith('.json')) return 'json'
  if (lower.endsWith('.yaml') || lower.endsWith('.yml')) return 'yaml'
  if (lower.endsWith('.toml')) return 'ini'
  if (lower.endsWith('.env') || lower.endsWith('.txt') || lower.endsWith('.log')) return 'shell'
  if (lower.endsWith('.md')) return 'markdown'
  if (lower.endsWith('.js')) return 'javascript'
  if (lower.endsWith('.ts')) return 'typescript'
  if (lower.endsWith('.vue')) return 'html'
  if (lower.endsWith('.xml')) return 'xml'
  if (lower.endsWith('.html') || lower.endsWith('.htm')) return 'html'
  if (lower.endsWith('.css')) return 'css'
  if (lower.endsWith('.sh')) return 'shell'
  return 'plaintext'
}

const editorLanguage = computed(() => guessLanguage(openedFilePath.value))

watch(
  () => customStore.currentTheme,
  (theme) => {
    editor.value?.updateOptions({
      theme: theme === 'dark' ? 'vs-dark' : 'vs'
    })
  }
)

const ensureProjectSelected = async () => {
  if (selectedProjectId.value) return true
  await nonebotStore.loadBots()
  if (selectedProjectId.value) return true
  toast.add('warning', '请先选择一个实例', '', 4000)
  return false
}

const confirmDiscardChanges = (message = '当前文件有未保存内容，确定继续吗？') => {
  if (!isDirty.value) return true
  return window.confirm(message)
}

const resetEditor = () => {
  openedFilePath.value = ''
  editorValue.value = ''
  savedValue.value = ''
  openedEncoding.value = 'utf-8'
}

const loadRoots = async () => {
  if (!(await ensureProjectSelected())) return

  loadingRoots.value = true
  const { data, error } = await getFileManagerRoots(selectedProjectId.value)
  loadingRoots.value = false

  if (error || !data) {
    toast.add('error', `加载文件管理根目录失败：${error}`, '', 5000)
    roots.value = []
    return
  }

  roots.value = data.roots
}

const loadList = async (path = currentPath.value) => {
  if (!(await ensureProjectSelected())) return

  loadingList.value = true
  const { data, error } = await getFileManagerList(selectedProjectId.value, currentScope.value, path)
  loadingList.value = false

  if (error || !data) {
    toast.add('error', `加载目录失败：${error}`, '', 5000)
    entries.value = []
    return
  }

  currentPath.value = data.current_path
  entries.value = data.items
  if (!entries.value.some((item) => item.path === selectedEntryPath.value)) {
    selectedEntryPath.value = ''
  }
}

const goToParent = async () => {
  if (!currentPath.value) return
  const parts = currentPath.value.split('/').filter(Boolean)
  parts.pop()
  await loadList(parts.join('/'))
}

const openDirectory = async (path: string) => {
  await loadList(path)
}

const openFile = async (path: string) => {
  if (!confirmDiscardChanges()) return
  if (!(await ensureProjectSelected())) return

  loadingContent.value = true
  const { data, error } = await getFileManagerContent(selectedProjectId.value, currentScope.value, path)
  loadingContent.value = false

  if (error || !data) {
    toast.add('error', `打开文件失败：${error}`, '', 5000)
    return
  }

  openedFilePath.value = data.path
  editorValue.value = data.content
  savedValue.value = data.content
  openedEncoding.value = data.encoding || 'utf-8'
  selectedEntryPath.value = path
}

const handleEntryClick = (entry: FileManagerEntry) => {
  selectedEntryPath.value = entry.path
}

const handleEntryOpen = async (entry: FileManagerEntry) => {
  if (entry.is_dir) {
    await openDirectory(entry.path)
    return
  }
  await openFile(entry.path)
}

const saveCurrentFile = async () => {
  if (!(await ensureProjectSelected())) return
  if (!openedFilePath.value) {
    toast.add('warning', '请先打开一个文件', '', 4000)
    return
  }

  savingContent.value = true
  const { data, error } = await saveFileManagerContent({
    project_id: selectedProjectId.value,
    scope: currentScope.value,
    path: openedFilePath.value,
    content: editorValue.value,
    encoding: openedEncoding.value
  })
  savingContent.value = false

  if (error || !data) {
    toast.add('error', `保存文件失败：${error}`, '', 5000)
    return
  }

  savedValue.value = data.content
  toast.add('success', '文件已保存', openedFilePath.value, 4000)
  await loadList(currentPath.value)
}

const createEntry = async (isDir: boolean) => {
  if (!(await ensureProjectSelected())) return
  const name = window.prompt(isDir ? '请输入新文件夹名称' : '请输入新文件名称')
  if (!name?.trim()) return

  const { data, error } = await createFileManagerEntry({
    project_id: selectedProjectId.value,
    scope: currentScope.value,
    path: currentPath.value,
    name: name.trim(),
    is_dir: isDir
  })

  if (error || !data) {
    toast.add('error', `${isDir ? '创建文件夹' : '创建文件'}失败：${error}`, '', 5000)
    return
  }

  entries.value = data.items
  toast.add('success', isDir ? '文件夹已创建' : '文件已创建', name.trim(), 3000)
}

const deleteEntry = async () => {
  if (!(await ensureProjectSelected())) return
  if (!selectedEntryPath.value) {
    toast.add('warning', '请先选择一个文件或文件夹', '', 4000)
    return
  }

  if (openedFilePath.value === selectedEntryPath.value && isDirty.value) {
    if (!window.confirm('当前打开文件有未保存内容，删除后无法恢复，确定继续吗？')) return
  } else if (!window.confirm(`确定删除 "${selectedEntryPath.value}" 吗？`)) {
    return
  }

  const deletingPath = selectedEntryPath.value
  const { data, error } = await deleteFileManagerEntry({
    project_id: selectedProjectId.value,
    scope: currentScope.value,
    path: deletingPath
  })

  if (error || !data) {
    toast.add('error', `删除失败：${error}`, '', 5000)
    return
  }

  if (openedFilePath.value === deletingPath) {
    resetEditor()
  }
  selectedEntryPath.value = ''
  currentPath.value = data.current_path
  entries.value = data.items
  toast.add('success', '删除成功', deletingPath, 3000)
}

watch(
  () => selectedProjectId.value,
  async () => {
    currentPath.value = ''
    selectedEntryPath.value = ''
    resetEditor()
    if (!selectedProjectId.value) {
      roots.value = []
      entries.value = []
      return
    }
    await loadRoots()
    await loadList('')
  },
  { immediate: true }
)
</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="rounded-box bg-base-200 p-6 flex flex-col gap-3">
      <div class="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div class="space-y-1">
          <h2 class="text-xl font-semibold">文件管理</h2>
          <div class="text-sm opacity-70">
            根据实例实际安装方式自动识别目录来源。映射实例显示映射目录，安装在容器内的实例显示容器内实例目录。
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <span v-if="selectedProjectName" class="badge badge-primary text-base-100">
            当前实例：{{ selectedProjectName }}
          </span>
          <span v-else class="badge badge-outline">请先选择实例</span>
        </div>
      </div>

      <div class="rounded-xl border border-base-content/10 bg-base-100 px-4 py-4">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="badge badge-outline">{{ currentRoot?.label || '实例目录' }}</span>
          <span v-if="currentRoot?.scope === 'installed'" class="badge badge-warning">Docker 内</span>
          <span v-else-if="currentRoot?.scope === 'mapped'" class="badge badge-primary text-base-100">映射目录</span>
        </div>
        <div class="text-sm opacity-70 mt-3">
          {{ currentRoot?.description || '等待加载实例目录信息...' }}
        </div>
        <div class="text-xs opacity-60 mt-3 break-all">
          {{ currentRoot?.root_path || '等待加载...' }}
        </div>
      </div>
    </div>

    <div
      v-if="currentRoot && !currentRoot.available"
      class="alert alert-warning text-sm"
    >
      <span class="material-symbols-outlined">warning</span>
      <div>
        当前目录不可用：{{ currentRoot.detail || '未知原因' }}
      </div>
    </div>

    <div class="flex flex-col gap-4">
      <section class="rounded-box bg-base-200 p-4 flex min-h-0 flex-col gap-4 overflow-hidden">
        <div class="flex items-center justify-between gap-2">
          <div>
            <h3 class="text-lg font-semibold">目录浏览</h3>
            <div class="text-xs opacity-60 mt-1 break-all">
              {{ currentRoot?.root_path || '未选择目录' }}
            </div>
          </div>
          <span class="badge badge-outline">{{ entries.length }} 项</span>
        </div>

        <div class="breadcrumbs text-sm overflow-x-auto whitespace-nowrap">
          <ul class="flex-nowrap">
            <li><a @click="void loadList('')">根目录</a></li>
            <li v-for="(part, index) in breadcrumbParts" :key="`${part}-${index}`">
              <a
                @click="
                  void loadList(
                    breadcrumbParts.slice(0, index + 1).join('/')
                  )
                "
              >
                {{ part }}
              </a>
            </li>
          </ul>
        </div>

        <div class="flex flex-wrap gap-2 md:justify-end">
          <button class="btn btn-sm" :disabled="loadingList || !isRootAvailable" @click="void loadList(currentPath)">
            刷新
          </button>
          <button class="btn btn-sm" :disabled="!currentPath || loadingList" @click="void goToParent()">
            返回上级
          </button>
          <button class="btn btn-sm btn-outline btn-primary" :disabled="!isRootAvailable" @click="void createEntry(false)">
            新建文件
          </button>
          <button class="btn btn-sm btn-outline btn-primary" :disabled="!isRootAvailable" @click="void createEntry(true)">
            新建文件夹
          </button>
          <button class="btn btn-sm btn-outline btn-error" :disabled="!selectedEntryPath" @click="void deleteEntry()">
            删除
          </button>
        </div>

        <div class="h-[420px] overflow-auto rounded-box border border-base-300 bg-base-100">
          <table class="table table-sm min-w-[980px]">
            <thead>
              <tr>
                <th class="w-[60%]">名称</th>
                <th class="w-[16%] whitespace-nowrap">大小</th>
                <th class="w-[24%] whitespace-nowrap">修改时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loadingList">
                <td colspan="3" class="text-center opacity-60">加载中...</td>
              </tr>
              <tr v-else-if="!entries.length">
                <td colspan="3" class="text-center opacity-60">当前目录为空</td>
              </tr>
              <tr
                v-for="entry in entries"
                :key="entry.path"
                class="cursor-pointer"
                :class="selectedEntryPath === entry.path ? 'active' : ''"
                @click="handleEntryClick(entry)"
                @dblclick="void handleEntryOpen(entry)"
              >
                <td>
                  <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-base shrink-0">
                      {{ entry.is_dir ? 'folder' : 'description' }}
                    </span>
                    <span class="break-all">{{ entry.name }}</span>
                  </div>
                </td>
                <td class="whitespace-nowrap text-xs">
                  {{ entry.is_dir ? '-' : formatSize(entry.size) }}
                </td>
                <td class="whitespace-nowrap text-xs">
                  {{ covertTimestampToDateString(entry.modified_time) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="rounded-box bg-base-200 p-4 flex h-[720px] min-h-0 flex-col gap-4 overflow-hidden">
        <div class="flex items-center justify-between gap-2 flex-wrap">
          <div>
            <h3 class="text-lg font-semibold">文件编辑</h3>
            <div class="text-xs opacity-60 mt-1 break-all">
              {{ openedFilePath || '请选择并双击一个文件开始编辑' }}
            </div>
          </div>

          <div class="flex gap-2">
            <span v-if="openedFilePath" class="badge badge-outline">
              {{ editorLanguage }}
            </span>
            <button
              class="btn btn-sm btn-primary text-base-100"
              :disabled="!openedFilePath || savingContent || !isDirty"
              @click="void saveCurrentFile()"
            >
              {{ savingContent ? '保存中...' : '保存文件' }}
            </button>
          </div>
        </div>

        <div
          v-if="!openedFilePath"
          class="flex-1 rounded-box border border-dashed border-base-300 bg-base-100 flex items-center justify-center text-sm opacity-60 min-h-0"
        >
          双击左侧文件列表中的文件即可打开编辑。
        </div>

        <div v-else class="flex min-h-0 flex-1 flex-col gap-3">
          <div class="text-xs opacity-60 flex flex-wrap items-center gap-3">
            <span>编码：{{ openedEncoding }}</span>
            <span>状态：{{ isDirty ? '未保存' : '已保存' }}</span>
            <span v-if="loadingContent">文件加载中...</span>
          </div>

          <div class="min-h-0 flex-1 rounded-lg bg-base-100 p-2 shadow-inner">
            <EditorItem
              v-model="editorValue"
              class="h-full"
              :editor-optional="{
                language: editorLanguage,
                theme: customStore.currentTheme === 'dark' ? 'vs-dark' : 'vs',
                minimap: { enabled: false },
                accessibilitySupport: 'off',
                automaticLayout: true
              }"
              v-on:editor="
                (event) => {
                  editor = event
                }
              "
              v-on:update-value="
                (value) => {
                  editorValue = value
                }
              "
            />
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
