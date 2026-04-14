<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useNoneBotStore, useToastStore } from '@/stores'
import {
  type BackupConnectivityResult,
  type BackupRemoteItem,
  type BackupSettings,
  type BackupSource,
  downloadProjectBackup,
  getBackupSettings,
  listRemoteBackups,
  restoreLocalBackup,
  restoreRemoteBackup,
  testBackupConnection,
  updateBackupSettings,
  uploadProjectBackupToRemote
} from './backup-client'

const nonebotStore = useNoneBotStore()
const toast = useToastStore()

const loadingSettings = ref(false)
const savingSettings = ref(false)
const downloadingBackup = ref(false)
const uploadingSource = ref<BackupSource | ''>('')
const refreshingSource = ref<BackupSource | ''>('')
const testingSource = ref<BackupSource | ''>('')
const restoringKey = ref('')
const restoringLocal = ref(false)
const localBackupFile = ref<File | null>(null)
const lastTestResult = ref<BackupConnectivityResult | null>(null)
const showArchivePassword = ref(false)
const restorePasswordModalVisible = ref(false)
const restorePasswordValue = ref('')
const restorePasswordMode = ref<'local' | 'remote'>('local')
const restorePasswordSource = ref<BackupSource>('webdav')
const restorePasswordKey = ref('')
const restorePasswordBusy = ref(false)

const webdavItems = ref<BackupRemoteItem[]>([])
const s3Items = ref<BackupRemoteItem[]>([])

const settings = reactive<BackupSettings>({
  webdav_url: '',
  webdav_username: '',
  webdav_password: '',
  webdav_base_path: '/',
  webdav_configured: false,
  s3_endpoint: '',
  s3_region: 'us-east-1',
  s3_bucket: '',
  s3_access_key: '',
  s3_secret_key: '',
  s3_prefix: '',
  s3_force_path_style: true,
  s3_configured: false,
  archive_password: '',
  archive_password_configured: false,
  auto_backup_enabled: false,
  auto_backup_interval_hours: 24,
  keep_count: 10,
  include_logs: false,
  log_project_ids: []
})

const selectedProjectId = computed(() => nonebotStore.selectedBot?.project_id || '')
const selectedProjectName = computed(() => nonebotStore.selectedBot?.project_name || '')
const projectOptions = computed(() => nonebotStore.getExtendedBotsList())
const selectedLogProjectNames = computed(() =>
  projectOptions.value
    .filter((item) => settings.log_project_ids.includes(item.project_id))
    .map((item) => item.project_name)
)

const normalizeLogProjectIds = (value: unknown) => {
  if (!Array.isArray(value)) return []
  return [...new Set(value.map((item) => String(item || '').trim()).filter(Boolean))]
}

const ensureProjectSelected = () => {
  if (!selectedProjectId.value) {
    toast.add('warning', '请先选择实例', '', 5000)
    return false
  }
  return true
}

const needsRestorePassword = (error?: string) =>
  String(error || '').toLowerCase().includes('requires password')

const openRestorePasswordModal = (
  mode: 'local' | 'remote',
  source: BackupSource = 'webdav',
  key = ''
) => {
  restorePasswordMode.value = mode
  restorePasswordSource.value = source
  restorePasswordKey.value = key
  restorePasswordValue.value = ''
  restorePasswordModalVisible.value = true
}

const closeRestorePasswordModal = () => {
  if (restorePasswordBusy.value) return
  restorePasswordModalVisible.value = false
  restorePasswordValue.value = ''
}

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

const loadSettings = async () => {
  loadingSettings.value = true
  const { data, error } = await getBackupSettings()
  loadingSettings.value = false

  if (error || !data) {
    toast.add('error', `加载备份配置失败：${error}`, '', 5000)
    return
  }

  Object.assign(settings, data)
  settings.log_project_ids = normalizeLogProjectIds(data.log_project_ids)
}

const loadRemoteList = async (source: BackupSource) => {
  refreshingSource.value = source
  const { data, error } = await listRemoteBackups(source)
  refreshingSource.value = ''

  if (error || !data) {
    toast.add('error', `加载 ${source.toUpperCase()} 备份列表失败：${error}`, '', 5000)
    return
  }

  if (source === 'webdav') {
    webdavItems.value = data
  } else {
    s3Items.value = data
  }
}

const loadAllRemoteLists = async () => {
  await Promise.all([loadRemoteList('webdav'), loadRemoteList('s3')])
}

const handleTestConnection = async (source: BackupSource) => {
  testingSource.value = source
  lastTestResult.value = null
  const { data, error } = await testBackupConnection(source, { ...settings })
  testingSource.value = ''

  if (error || !data) {
    lastTestResult.value = {
      ok: false,
      source,
      message: `${source.toUpperCase()} 连接失败。`,
      detail: error || '未知错误'
    }
    toast.add('error', `${source.toUpperCase()} 测试失败：${error}`, '', 6000)
    return
  }

  lastTestResult.value = data
  toast.add('success', `${source.toUpperCase()} 测试成功`, data.detail || '', 6000)
}

const saveSettings = async () => {
  savingSettings.value = true
  const { error } = await updateBackupSettings({ ...settings })
  savingSettings.value = false

  if (error) {
    toast.add('error', `保存备份配置失败：${error}`, '', 5000)
    return
  }

  settings.webdav_configured = Boolean(
    settings.webdav_url && settings.webdav_username && settings.webdav_password
  )
  settings.s3_configured = Boolean(
    settings.s3_endpoint &&
      settings.s3_region &&
      settings.s3_bucket &&
      settings.s3_access_key &&
      settings.s3_secret_key
  )
  settings.archive_password_configured = Boolean(settings.archive_password)
  settings.log_project_ids = normalizeLogProjectIds(settings.log_project_ids)
  toast.add('success', '备份配置已保存', '', 4000)
  await loadAllRemoteLists()
}

const handleDownloadBackup = async () => {
  if (!ensureProjectSelected()) return

  downloadingBackup.value = true
  const { error } = await downloadProjectBackup(selectedProjectId.value)
  downloadingBackup.value = false

  if (error) {
    toast.add('error', `下载本地备份失败：${error}`, '', 5000)
    return
  }

  toast.add(
    'success',
    '本地备份已开始下载',
    settings.archive_password ? '当前备份已按设置密码加密。' : '',
    4000
  )
}

const handleUploadBackup = async (source: BackupSource) => {
  if (!ensureProjectSelected()) return

  uploadingSource.value = source
  const { error } = await uploadProjectBackupToRemote(selectedProjectId.value, source)
  uploadingSource.value = ''

  if (error) {
    toast.add('error', `备份到 ${source.toUpperCase()} 失败：${error}`, '', 5000)
    return
  }

  toast.add(
    'success',
    `备份已上传到 ${source.toUpperCase()}`,
    settings.archive_password ? '当前备份已按设置密码加密。' : '',
    4000
  )
  await loadRemoteList(source)
}

const finishRestore = async (message: string) => {
  await nonebotStore.loadBots()
  toast.add('success', message, '', 5000)
}

const handleRemoteRestore = async (
  source: BackupSource,
  key: string,
  password = ''
) => {
  if (!ensureProjectSelected()) return
  if (!password) {
    if (
      !window.confirm(
        '恢复会覆盖当前实例文件夹内容。运行中的实例会先停止，恢复完成后按原状态重启，确认继续吗？'
      )
    ) {
      return false
    }
  }

  restoringKey.value = `${source}:${key}`
  const { data, error } = await restoreRemoteBackup(
    selectedProjectId.value,
    source,
    key,
    password
  )
  restoringKey.value = ''

  if (error || !data) {
    if (needsRestorePassword(error) && !password) {
      openRestorePasswordModal('remote', source, key)
      return false
    }
    toast.add('error', `恢复远端备份失败：${error}`, '', 5000)
    return false
  }

  await finishRestore(data.message)
  return true
}

const handleLocalFileChange = (event: Event) => {
  const input = event.target as HTMLInputElement
  localBackupFile.value = input.files?.[0] ?? null
}

const handleLocalRestore = async (password = '') => {
  if (!ensureProjectSelected()) return
  if (!localBackupFile.value) {
    toast.add('warning', '请先选择一个本地备份压缩包', '', 5000)
    return false
  }
  if (!password) {
    if (
      !window.confirm(
        '恢复会覆盖当前实例文件夹内容。运行中的实例会先停止，恢复完成后按原状态重启，确认继续吗？'
      )
    ) {
      return false
    }
  }

  restoringLocal.value = true
  const { data, error } = await restoreLocalBackup(
    selectedProjectId.value,
    localBackupFile.value,
    password
  )
  restoringLocal.value = false

  if (error || !data) {
    if (needsRestorePassword(error) && !password) {
      openRestorePasswordModal('local')
      return false
    }
    toast.add('error', `恢复本地备份失败：${error}`, '', 5000)
    return false
  }

  await finishRestore(data.message)
  return true
}

const submitRestorePassword = async () => {
  if (!restorePasswordValue.value.trim()) {
    toast.add('warning', '请输入备份密码', '', 4000)
    return
  }

  restorePasswordBusy.value = true
  let ok = false
  if (restorePasswordMode.value === 'local') {
    ok = Boolean(await handleLocalRestore(restorePasswordValue.value))
  } else {
    ok = Boolean(await handleRemoteRestore(
      restorePasswordSource.value,
      restorePasswordKey.value,
      restorePasswordValue.value
    ))
  }
  restorePasswordBusy.value = false
  if (ok) {
    restorePasswordModalVisible.value = false
    restorePasswordValue.value = ''
  }
}

watch(
  () => selectedProjectId.value,
  () => {
    void loadAllRemoteLists()
  },
  { immediate: true }
)

void nonebotStore.loadBots()
void loadSettings()
</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="rounded-box bg-base-200 p-6 flex flex-col gap-2">
      <div class="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div class="space-y-1">
          <h2 class="text-xl font-semibold">备份恢复</h2>
          <div class="text-sm opacity-70">
            这里可以备份当前实例文件夹到本地、WebDAV 或 S3，也可以从本地压缩包或远端备份恢复。
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <span v-if="selectedProjectName" class="badge badge-primary text-base-100">
            当前实例：{{ selectedProjectName }}
          </span>
          <span v-else class="badge badge-outline">请先选择实例</span>
        </div>
      </div>

      <div class="alert alert-warning text-sm">
        恢复会覆盖当前实例文件夹内容。若实例正在运行，系统会先停止实例，恢复成功后再按原状态自动启动。
      </div>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-2 gap-4 items-start">
      <section class="rounded-box bg-base-200 p-5 flex flex-col gap-4">
        <div class="flex items-center justify-between gap-2">
          <h3 class="text-lg font-semibold">WebDAV 配置</h3>
          <div class="flex items-center gap-2">
            <span
              :class="
                settings.webdav_configured
                  ? 'badge badge-success text-base-100'
                  : 'badge badge-outline'
              "
            >
              {{ settings.webdav_configured ? '已配置' : '未配置' }}
            </span>
            <button
              class="btn btn-sm btn-outline btn-error"
              :disabled="testingSource === 'webdav'"
              @click="handleTestConnection('webdav')"
            >
              {{ testingSource === 'webdav' ? '测试中...' : '测试连接' }}
            </button>
          </div>
        </div>

        <label class="form-control">
          <div class="label py-1"><span class="label-text">WebDAV 地址</span></div>
          <input
            v-model="settings.webdav_url"
            class="input input-bordered font-mono"
            placeholder="https://example.com/dav"
          />
        </label>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label class="form-control">
            <div class="label py-1"><span class="label-text">用户名</span></div>
            <input v-model="settings.webdav_username" class="input input-bordered font-mono" />
          </label>

          <label class="form-control">
            <div class="label py-1"><span class="label-text">密码</span></div>
            <input
              v-model="settings.webdav_password"
              type="password"
              class="input input-bordered font-mono"
            />
          </label>
        </div>

        <label class="form-control">
          <div class="label py-1"><span class="label-text">基础目录</span></div>
          <input
            v-model="settings.webdav_base_path"
            class="input input-bordered font-mono"
            placeholder="/nonebot-backups"
          />
        </label>

        <div class="text-sm opacity-70">
          如果使用中国科技云、Nextcloud 这类服务，请优先填写应用密码或专用认证密钥，不要直接填写网页登录密码。
        </div>
      </section>

      <section class="rounded-box bg-base-200 p-5 flex flex-col gap-4">
        <div class="flex items-center justify-between gap-2">
          <h3 class="text-lg font-semibold">S3 配置</h3>
          <div class="flex items-center gap-2">
            <span
              :class="
                settings.s3_configured
                  ? 'badge badge-success text-base-100'
                  : 'badge badge-outline'
              "
            >
              {{ settings.s3_configured ? '已配置' : '未配置' }}
            </span>
            <button
              class="btn btn-sm btn-outline btn-error"
              :disabled="testingSource === 's3'"
              @click="handleTestConnection('s3')"
            >
              {{ testingSource === 's3' ? '测试中...' : '测试连接' }}
            </button>
          </div>
        </div>

        <label class="form-control">
          <div class="label py-1"><span class="label-text">Endpoint</span></div>
          <input
            v-model="settings.s3_endpoint"
            class="input input-bordered font-mono"
            placeholder="https://s3.amazonaws.com"
          />
        </label>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label class="form-control">
            <div class="label py-1"><span class="label-text">Region</span></div>
            <input v-model="settings.s3_region" class="input input-bordered font-mono" />
          </label>

          <label class="form-control">
            <div class="label py-1"><span class="label-text">Bucket</span></div>
            <input v-model="settings.s3_bucket" class="input input-bordered font-mono" />
          </label>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label class="form-control">
            <div class="label py-1"><span class="label-text">Access Key</span></div>
            <input v-model="settings.s3_access_key" class="input input-bordered font-mono" />
          </label>

          <label class="form-control">
            <div class="label py-1"><span class="label-text">Secret Key</span></div>
            <input
              v-model="settings.s3_secret_key"
              type="password"
              class="input input-bordered font-mono"
            />
          </label>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3 items-end">
          <label class="form-control">
            <div class="label py-1"><span class="label-text">Prefix</span></div>
            <input
              v-model="settings.s3_prefix"
              class="input input-bordered font-mono"
              placeholder="nonebot-backups"
            />
          </label>

          <label class="label cursor-pointer gap-2 justify-start md:justify-end">
            <span class="label-text">Path Style</span>
            <input
              v-model="settings.s3_force_path_style"
              type="checkbox"
              class="checkbox checkbox-sm"
            />
          </label>
        </div>

        <div class="text-sm opacity-70">
          部分对象存储只支持 virtual-hosted style，不支持 path style。测试失败时请优先检查 endpoint、bucket、region 和 path style 是否与服务商文档一致。
        </div>
      </section>
    </div>

    <div v-if="lastTestResult" class="rounded-box bg-base-200 p-5 flex flex-col gap-2">
      <div class="flex items-center gap-2">
        <span
          :class="
            lastTestResult.ok
              ? 'badge badge-success text-base-100'
              : 'badge badge-error text-base-100'
          "
        >
          {{ lastTestResult.source.toUpperCase() }}
        </span>
        <span class="font-medium">{{ lastTestResult.message }}</span>
      </div>
      <div class="text-sm font-mono opacity-70 break-all">
        {{ lastTestResult.detail }}
      </div>
    </div>

    <div class="rounded-box bg-base-200 p-5 flex flex-col gap-5">
      <div class="flex items-center justify-between gap-2 flex-wrap">
        <div class="flex items-center gap-2 flex-wrap">
          <h3 class="text-lg font-semibold">备份设置与操作</h3>
          <span
            :class="
              settings.archive_password_configured
                ? 'badge badge-success text-base-100'
                : 'badge badge-outline'
            "
          >
            {{ settings.archive_password_configured ? '已启用压缩包密码' : '未启用压缩包密码' }}
          </span>
          <span
            :class="
              settings.include_logs ? 'badge badge-info text-base-100' : 'badge badge-outline'
            "
          >
            {{ settings.include_logs ? '已启用日志备份' : '未启用日志备份' }}
          </span>
        </div>
        <button
          class="btn btn-primary text-base-100"
          :disabled="savingSettings || loadingSettings"
          @click="saveSettings"
        >
          {{ savingSettings ? '保存中...' : '保存备份配置' }}
        </button>
      </div>

      <div class="grid grid-cols-1 xl:grid-cols-[1.2fr_auto_1fr_1fr] gap-3 items-end">
        <label class="form-control">
          <div class="label py-1"><span class="label-text">备份压缩包密码</span></div>
          <div class="join w-full">
            <input
              v-model="settings.archive_password"
              :type="showArchivePassword ? 'text' : 'password'"
              class="input input-bordered font-mono join-item w-full"
              placeholder="留空则不加密压缩包"
            />
            <button
              class="btn btn-outline join-item"
              type="button"
              @click="showArchivePassword = !showArchivePassword"
            >
              <span class="material-symbols-outlined text-base">
                {{ showArchivePassword ? 'visibility_off' : 'visibility' }}
              </span>
            </button>
          </div>
        </label>

        <label class="label cursor-pointer gap-2 justify-start">
          <span class="label-text">启用定时备份</span>
          <input
            v-model="settings.auto_backup_enabled"
            type="checkbox"
            class="toggle toggle-error"
          />
        </label>

        <label class="form-control">
          <div class="label py-1"><span class="label-text">备份间隔（小时）</span></div>
          <input
            v-model.number="settings.auto_backup_interval_hours"
            type="number"
            min="1"
            max="720"
            class="input input-bordered font-mono"
          />
        </label>

        <label class="form-control">
          <div class="label py-1"><span class="label-text">保留份数</span></div>
          <input
            v-model.number="settings.keep_count"
            type="number"
            min="1"
            max="200"
            class="input input-bordered font-mono"
          />
        </label>
      </div>

      <div class="grid grid-cols-1 xl:grid-cols-[auto_1fr] gap-4 items-start">
        <label class="label cursor-pointer gap-3 justify-start rounded-box border border-base-300 px-4 py-3">
          <input
            v-model="settings.include_logs"
            type="checkbox"
            class="checkbox checkbox-error"
          />
          <div class="space-y-1">
            <div class="font-medium">日志备份</div>
            <div class="text-sm opacity-70">
              勾选后会把所选实例的全局日志一起打包进备份；不勾选则只备份实例文件夹。
            </div>
          </div>
        </label>

        <label class="form-control">
          <div class="label py-1">
            <span class="label-text">选择要备份日志的实例</span>
            <span class="label-text-alt">
              {{ selectedLogProjectNames.length ? `已选 ${selectedLogProjectNames.length} 个` : '未选择' }}
            </span>
          </div>
          <select
            v-model="settings.log_project_ids"
            multiple
            :disabled="!settings.include_logs || !projectOptions.length"
            class="select select-bordered min-h-40"
          >
            <option v-for="project in projectOptions" :key="project.project_id" :value="project.project_id">
              {{ project.project_name }}
            </option>
          </select>
          <div class="label">
            <span class="label-text-alt">
              {{ settings.include_logs
                ? '按住 Ctrl 或 Shift 可多选，只会备份选中的实例日志。'
                : '启用日志备份后可选择实例日志。' }}
            </span>
          </div>
        </label>
      </div>

      <div class="text-sm opacity-70">
        设置压缩包密码后，本地下载、远端上传和定时备份都会生成加密 zip。恢复时如果检测到压缩包有密码，系统会自动弹窗要求输入密码。
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
        <button
          class="btn btn-error text-base-100"
          :disabled="downloadingBackup"
          @click="handleDownloadBackup"
        >
          {{ downloadingBackup ? '打包中...' : '下载本地备份' }}
        </button>
        <button
          class="btn btn-outline btn-error"
          :disabled="uploadingSource === 'webdav'"
          @click="handleUploadBackup('webdav')"
        >
          {{ uploadingSource === 'webdav' ? '上传中...' : '备份到 WebDAV' }}
        </button>
        <button
          class="btn btn-outline btn-error"
          :disabled="uploadingSource === 's3'"
          @click="handleUploadBackup('s3')"
        >
          {{ uploadingSource === 's3' ? '上传中...' : '备份到 S3' }}
        </button>
      </div>
    </div>

    <div class="rounded-box bg-base-200 p-5 flex flex-col gap-4">
      <div class="flex items-center justify-between gap-2">
        <h3 class="text-lg font-semibold">本地恢复</h3>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3 items-end">
        <label class="form-control">
          <div class="label py-1"><span class="label-text">备份压缩包</span></div>
          <input
            class="file-input file-input-bordered w-full"
            type="file"
            accept=".zip,application/zip"
            @change="handleLocalFileChange"
          />
        </label>
        <button
          class="btn btn-error text-base-100"
          :disabled="restoringLocal"
          @click="handleLocalRestore()"
        >
          {{ restoringLocal ? '恢复中...' : '上传并恢复' }}
        </button>
      </div>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-2 gap-4 items-start">
      <section class="rounded-box bg-base-200 p-5 flex flex-col gap-4">
        <div class="flex items-center justify-between gap-2">
          <h3 class="text-lg font-semibold">WebDAV 备份列表</h3>
          <button
            class="btn btn-sm btn-ghost text-error"
            :disabled="refreshingSource === 'webdav'"
            @click="loadRemoteList('webdav')"
          >
            {{ refreshingSource === 'webdav' ? '刷新中...' : '刷新' }}
          </button>
        </div>

        <div v-if="!webdavItems.length" class="text-sm opacity-60">暂无 WebDAV 备份。</div>

        <div v-else class="overflow-x-auto">
          <table class="table table-sm">
            <thead>
              <tr>
                <th>名称</th>
                <th>大小</th>
                <th>时间</th>
                <th class="text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in webdavItems" :key="item.key">
                <td class="font-mono text-xs">{{ item.name }}</td>
                <td>{{ formatSize(item.size) }}</td>
                <td class="text-xs">{{ item.last_modified || '-' }}</td>
                <td class="text-right">
                  <button
                    class="btn btn-xs btn-error text-base-100"
                    :disabled="restoringKey === `webdav:${item.key}`"
                    @click="handleRemoteRestore('webdav', item.key)"
                  >
                    {{ restoringKey === `webdav:${item.key}` ? '恢复中...' : '恢复' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="rounded-box bg-base-200 p-5 flex flex-col gap-4">
        <div class="flex items-center justify-between gap-2">
          <h3 class="text-lg font-semibold">S3 备份列表</h3>
          <button
            class="btn btn-sm btn-ghost text-error"
            :disabled="refreshingSource === 's3'"
            @click="loadRemoteList('s3')"
          >
            {{ refreshingSource === 's3' ? '刷新中...' : '刷新' }}
          </button>
        </div>

        <div v-if="!s3Items.length" class="text-sm opacity-60">暂无 S3 备份。</div>

        <div v-else class="overflow-x-auto">
          <table class="table table-sm">
            <thead>
              <tr>
                <th>名称</th>
                <th>大小</th>
                <th>时间</th>
                <th class="text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in s3Items" :key="item.key">
                <td class="font-mono text-xs">{{ item.name }}</td>
                <td>{{ formatSize(item.size) }}</td>
                <td class="text-xs">{{ item.last_modified || '-' }}</td>
                <td class="text-right">
                  <button
                    class="btn btn-xs btn-error text-base-100"
                    :disabled="restoringKey === `s3:${item.key}`"
                    @click="handleRemoteRestore('s3', item.key)"
                  >
                    {{ restoringKey === `s3:${item.key}` ? '恢复中...' : '恢复' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <dialog class="modal" :class="{ 'modal-open': restorePasswordModalVisible }">
      <div class="modal-box">
        <h3 class="font-semibold text-lg">请输入备份密码</h3>
        <p class="text-sm opacity-70 mt-2">
          检测到当前压缩包已加密，请输入正确的备份密码后再继续恢复。
        </p>
        <label class="form-control mt-4">
          <div class="label py-1"><span class="label-text">备份密码</span></div>
          <input
            v-model="restorePasswordValue"
            type="password"
            class="input input-bordered font-mono"
            placeholder="请输入压缩包密码"
            @keydown.enter.prevent="submitRestorePassword"
          />
        </label>
        <div class="modal-action">
          <button class="btn btn-ghost" :disabled="restorePasswordBusy" @click="closeRestorePasswordModal">
            取消
          </button>
          <button class="btn btn-error text-base-100" :disabled="restorePasswordBusy" @click="submitRestorePassword">
            {{ restorePasswordBusy ? '恢复中...' : '继续恢复' }}
          </button>
        </div>
      </div>
      <form method="dialog" class="modal-backdrop">
        <button @click.prevent="closeRestorePasswordModal">close</button>
      </form>
    </dialog>
  </div>
</template>
