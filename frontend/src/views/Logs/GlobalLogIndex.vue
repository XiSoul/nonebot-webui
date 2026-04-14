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
  <div class="flex flex-col gap-4">
    <div class="rounded-box bg-base-200 p-6 flex flex-col gap-2">
      <h2 class="text-xl font-semibold">全局日志</h2>
      <div class="text-sm opacity-70">
        这里可以查看 WebUI 操作日志和实例运行日志。日志按天分文件存储，支持按等级、日期、实例和关键字过滤。
      </div>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-[1.2fr_1.4fr] gap-4 items-start">
      <section class="rounded-box bg-base-200 p-5 flex flex-col gap-4">
        <div class="flex items-center justify-between gap-2">
          <h3 class="text-lg font-semibold">日志设置</h3>
          <button class="btn btn-primary text-base-100" :disabled="savingSettings || loadingSettings" @click="saveSettings">
            {{ savingSettings ? '保存中...' : '保存设置' }}
          </button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label class="form-control">
            <div class="label py-1"><span class="label-text">默认过滤等级</span></div>
            <select v-model="settings.min_level" class="select select-bordered">
              <option v-for="level in settings.available_levels" :key="level" :value="level">
                {{ level }}
              </option>
            </select>
          </label>

          <label class="form-control">
            <div class="label py-1"><span class="label-text">日志保留天数</span></div>
            <input
              v-model.number="settings.retention_days"
              type="number"
              min="1"
              max="180"
              class="input input-bordered font-mono"
            />
          </label>
        </div>

        <div class="text-sm opacity-70">
          前端通知、备份测试结果、页面报错和实例运行输出都会写入日志。系统会按设置的保留天数定时清理旧日志。
        </div>
      </section>

      <section class="rounded-box bg-base-200 p-5 flex flex-col gap-4">
        <div class="flex items-center justify-between gap-2">
          <h3 class="text-lg font-semibold">查看筛选</h3>
          <button class="btn btn-outline btn-error" :disabled="loadingEntries" @click="refreshLogs">
            {{ loadingEntries ? '刷新中...' : '刷新日志' }}
          </button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          <label class="form-control">
            <div class="label py-1"><span class="label-text">日志来源</span></div>
            <select v-model="filters.kind" class="select select-bordered">
              <option value="webui">WebUI 日志</option>
              <option value="instance">实例日志</option>
            </select>
          </label>

          <label v-if="filters.kind === 'instance'" class="form-control">
            <div class="label py-1"><span class="label-text">实例</span></div>
            <select v-model="filters.project_id" class="select select-bordered">
              <option value="">请选择实例</option>
              <option v-for="project in projectOptions" :key="project.project_id" :value="project.project_id">
                {{ project.project_name }}
              </option>
            </select>
          </label>

          <label class="form-control">
            <div class="label py-1"><span class="label-text">等级</span></div>
            <select v-model="filters.level" class="select select-bordered">
              <option v-for="level in settings.available_levels" :key="level" :value="level">
                {{ level }}
              </option>
            </select>
          </label>

          <label class="form-control">
            <div class="label py-1"><span class="label-text">日期</span></div>
            <select v-model="filters.date" class="select select-bordered">
              <option value="">请选择日期</option>
              <option v-for="date in dates" :key="date" :value="date">
                {{ date }}
              </option>
            </select>
          </label>

          <label class="form-control md:col-span-2 xl:col-span-1">
            <div class="label py-1"><span class="label-text">关键字</span></div>
            <input v-model="filters.search" class="input input-bordered" placeholder="搜索消息、详情或来源" />
          </label>
        </div>
      </section>
    </div>

    <section class="rounded-box bg-base-200 p-5 flex flex-col gap-4">
      <div class="flex items-center justify-between gap-2">
        <h3 class="text-lg font-semibold">日志内容</h3>
        <span class="badge badge-outline">{{ entries.length }} 条</span>
      </div>

      <div v-if="!filters.date" class="text-sm opacity-60">请先选择一个日志日期。</div>
      <div v-else-if="!entries.length" class="text-sm opacity-60">当前筛选条件下暂无日志。</div>

      <div v-else class="overflow-x-auto">
        <table class="table table-sm">
          <thead>
            <tr>
              <th>时间</th>
              <th>等级</th>
              <th>来源</th>
              <th>消息</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in entries" :key="`${item.timestamp}-${item.source}-${item.message}`">
              <td class="font-mono text-xs align-top whitespace-nowrap">{{ item.timestamp }}</td>
              <td class="align-top">
                <span
                  :class="{
                    'badge badge-outline': true,
                    'badge-info': item.level === 'DEBUG' || item.level === 'INFO',
                    'badge-warning': item.level === 'WARNING',
                    'badge-error text-base-100': item.level === 'ERROR' || item.level === 'CRITICAL'
                  }"
                >
                  {{ item.level }}
                </span>
              </td>
              <td class="font-mono text-xs align-top">{{ item.source }}</td>
              <td class="align-top">
                <div class="break-all">{{ item.message }}</div>
                <div v-if="item.detail" class="text-xs opacity-70 break-all mt-1">
                  {{ item.detail }}
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
