<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useNoneBotStore, useToastStore } from '@/stores'
import {
  getGlobalLogCatalog,
  getGlobalLogEntries,
  getGlobalLogSettings,
  updateGlobalLogSettings,
  type GlobalLogEntry,
  type LogKind,
  type LogLevel
} from './log-center-client'

const nonebotStore = useNoneBotStore()
const toast = useToastStore()

const loadingSettings = ref(false)
const savingSettings = ref(false)
const loadingEntries = ref(false)
const dates = ref<string[]>([])
const entries = ref<GlobalLogEntry[]>([])

const settings = reactive({
  min_level: 'DEBUG' as LogLevel,
  retention_days: 7,
  available_levels: ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] as LogLevel[]
})

const filters = reactive({
  kind: 'webui' as LogKind,
  level: 'DEBUG' as LogLevel,
  date: '',
  search: '',
  project_id: '',
  project_name: ''
})

const projectOptions = computed(() => nonebotStore.getExtendedBotsList())

const levelClass = (level: LogLevel) => {
  if (level === 'DEBUG') return 'text-sky-300'
  if (level === 'INFO') return 'text-emerald-300'
  if (level === 'WARNING') return 'text-amber-300'
  return 'text-rose-300'
}

const syncProjectName = () => {
  const selected = projectOptions.value.find((item) => item.project_id === filters.project_id)
  filters.project_name = selected?.project_name || ''
}

const loadSettings = async () => {
  loadingSettings.value = true
  const { data, error } = await getGlobalLogSettings()
  loadingSettings.value = false

  if (error || !data) {
    toast.add('error', `加载日志设置失败：${error}`, '', 5000)
    return
  }

  settings.min_level = data.min_level
  settings.retention_days = data.retention_days
  settings.available_levels = data.available_levels
  filters.level = data.min_level
  toast.setMinLevel(data.min_level)
}

const loadCatalog = async () => {
  syncProjectName()
  const { data, error } = await getGlobalLogCatalog(
    filters.kind,
    filters.project_id,
    filters.project_name
  )

  if (error || !data) {
    toast.add('error', `加载日志目录失败：${error}`, '', 5000)
    dates.value = []
    filters.date = ''
    return
  }

  dates.value = data.dates
  if (!dates.value.includes(filters.date)) {
    filters.date = dates.value[0] || ''
  }
}

const loadEntries = async () => {
  syncProjectName()
  if (!filters.date) {
    entries.value = []
    return
  }

  loadingEntries.value = true
  const { data, error } = await getGlobalLogEntries({
    kind: filters.kind,
    date: filters.date,
    level: filters.level,
    search: filters.search,
    project_id: filters.project_id,
    project_name: filters.project_name
  })
  loadingEntries.value = false

  if (error || !data) {
    toast.add('error', `加载日志内容失败：${error}`, '', 5000)
    return
  }

  entries.value = data.items
}

const refreshLogs = async () => {
  await loadCatalog()
  await loadEntries()
}

const saveSettings = async () => {
  savingSettings.value = true
  const { error } = await updateGlobalLogSettings({
    min_level: settings.min_level,
    retention_days: settings.retention_days
  })
  savingSettings.value = false

  if (error) {
    toast.add('error', `保存日志设置失败：${error}`, '', 5000)
    return
  }

  toast.setMinLevel(settings.min_level)
  toast.add('success', '日志设置已保存', '', 4000)
  filters.level = settings.min_level
  await refreshLogs()
}

watch(
  () => [filters.kind, filters.project_id],
  async () => {
    await loadCatalog()
    await loadEntries()
  }
)

watch(
  () => [filters.date, filters.level, filters.search],
  async () => {
    await loadEntries()
  }
)

void nonebotStore.loadBots()
void loadSettings().then(refreshLogs)
</script>

<template>
  <div class="nb-page">
    <section class="nb-panel-surface rounded-[1.5rem] p-3">
      <div class="flex flex-wrap items-center gap-3">
        <div class="mr-auto min-w-[9rem]">
          <div class="text-lg font-bold leading-tight">全局日志</div>
          <div class="text-xs opacity-60">{{ entries.length }} 条</div>
        </div>

        <label class="form-control w-36">
          <select v-model="filters.kind" class="select select-bordered select-sm">
            <option value="webui">WebUI 日志</option>
            <option value="instance">实例日志</option>
          </select>
        </label>

        <label v-if="filters.kind === 'instance'" class="form-control w-40">
          <select v-model="filters.project_id" class="select select-bordered select-sm">
            <option value="">请选择实例</option>
            <option v-for="project in projectOptions" :key="project.project_id" :value="project.project_id">
              {{ project.project_name }}
            </option>
          </select>
        </label>

        <label class="form-control w-28">
          <select v-model="filters.level" class="select select-bordered select-sm">
            <option v-for="level in settings.available_levels" :key="level" :value="level">
              {{ level }}
            </option>
          </select>
        </label>

        <label class="form-control w-36">
          <select v-model="filters.date" class="select select-bordered select-sm">
            <option value="">请选择日期</option>
            <option v-for="date in dates" :key="date" :value="date">
              {{ date }}
            </option>
          </select>
        </label>

        <label class="form-control min-w-[14rem] flex-1">
          <input v-model="filters.search" class="input input-bordered input-sm" placeholder="搜索消息、详情或来源" />
        </label>

        <details class="dropdown dropdown-end">
          <summary class="btn btn-outline btn-primary btn-sm">设置</summary>
          <div class="dropdown-content z-30 mt-2 w-80 rounded-box border border-base-300 bg-base-100 p-4 shadow-xl">
            <div class="mb-3 text-sm font-semibold">日志设置</div>
            <div class="grid grid-cols-2 gap-3">
              <label class="form-control">
                <div class="label py-1"><span class="label-text text-xs">默认等级</span></div>
                <select v-model="settings.min_level" class="select select-bordered select-sm">
                  <option v-for="level in settings.available_levels" :key="level" :value="level">
                    {{ level }}
                  </option>
                </select>
              </label>

              <label class="form-control">
                <div class="label py-1"><span class="label-text text-xs">保留天数</span></div>
                <input
                  v-model.number="settings.retention_days"
                  type="number"
                  min="1"
                  max="180"
                  class="input input-bordered input-sm font-mono"
                />
              </label>
            </div>
            <button class="btn btn-primary btn-sm mt-4 w-full text-base-100" :disabled="savingSettings || loadingSettings" @click="saveSettings">
              {{ savingSettings ? '保存中...' : '保存设置' }}
            </button>
          </div>
        </details>

        <button class="btn btn-outline btn-primary btn-sm" :disabled="loadingEntries" @click="refreshLogs">
          {{ loadingEntries ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </section>

    <section class="nb-panel-surface rounded-[1.5rem] p-3 flex flex-col gap-2">

      <div v-if="!filters.date" class="nb-empty-state text-sm opacity-70">请先选择一个日志日期。</div>
      <div v-else-if="!entries.length" class="nb-empty-state text-sm opacity-70">当前筛选条件下暂无日志。</div>

      <div
        v-else
        class="global-log-console h-[calc(100vh-15rem)] min-h-[32rem] overflow-auto rounded-[22px] border border-slate-900/75 bg-slate-950 px-4 py-3 font-mono text-[13px] leading-6 text-slate-100 shadow-inner"
      >
        <div
          v-for="item in entries"
          :key="`${item.timestamp}-${item.source}-${item.message}`"
          class="grid grid-cols-1 gap-x-3 border-b border-white/5 py-1.5 last:border-b-0 xl:grid-cols-[13.5rem_4.5rem_14rem_minmax(0,1fr)]"
        >
          <span class="text-slate-400">{{ item.timestamp }}</span>
          <span class="font-semibold leading-6" :class="levelClass(item.level)">{{ item.level }}</span>
          <span class="min-w-0 break-all text-slate-300">
            {{ item.project_name ? `${item.source}/${item.project_name}` : item.source }}
          </span>
          <span class="min-w-0 break-all text-slate-100">
            <span :class="levelClass(item.level)">{{ item.message }}</span>
            <span v-if="item.detail" class="text-slate-300"> | {{ item.detail }}</span>
          </span>
        </div>
      </div>
    </section>
  </div>
</template>
