<script setup lang="ts">
import { ref, watch } from 'vue'
import { useNoneBotStore, useToastStore } from '@/stores'
import {
  createProjectEnvFile,
  getProjectDotenvFile,
  getProjectPyprojectFile,
  saveProjectDotenvFile,
  saveProjectPyprojectFile
} from './workbench-client'

type EnvPreset = {
  host: string
  port: string
  superusers: string
  nickname: string
  commandStart: string
  commandSep: string
  token: string
  tokenKey: string
}

type EnvCardState = {
  name: string
  title: string
  description: string
  exists: boolean
  rawText: string
  preset: EnvPreset
  savingPreset: boolean
  savingRaw: boolean
}

const TOKEN_KEY_CANDIDATES = ['ONEBOT_ACCESS_TOKEN', 'ACCESS_TOKEN', 'TOKEN']

const nonebotStore = useNoneBotStore()
const toast = useToastStore()

const loading = ref(false)
const pyprojectText = ref('')
const pyprojectSaving = ref(false)

const createEmptyPreset = (): EnvPreset => ({
  host: '',
  port: '',
  superusers: '',
  nickname: '',
  commandStart: '',
  commandSep: '',
  token: '',
  tokenKey: 'TOKEN'
})

const createEnvCard = (name: string, title: string, description: string): EnvCardState => ({
  name,
  title,
  description,
  exists: false,
  rawText: '',
  preset: createEmptyPreset(),
  savingPreset: false,
  savingRaw: false
})

const envCards = ref<EnvCardState[]>([
  createEnvCard('.env', '基础环境 .env', '适合放实例通用配置，当前激活环境也由这里控制。'),
  createEnvCard('.env.prod', '生产环境 .env.prod', '适合放正式运行配置。文件不存在时首次保存会自动创建。')
])

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const normalizeRawText = (value: string) => {
  const normalized = value.replace(/\r\n/g, '\n').trimEnd()
  return normalized ? `${normalized}\n` : ''
}

const parseEnvRecord = (rawText: string) => {
  const record: Record<string, string> = {}
  for (const line of rawText.replace(/\r\n/g, '\n').split('\n')) {
    const match = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/)
    if (!match) continue
    record[match[1]] = match[2]
  }
  return record
}

const parseEnvValue = (rawValue?: string) => {
  if (!rawValue) return ''
  const trimmed = rawValue.trim()
  if (!trimmed) return ''

  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
  ) {
    return trimmed.slice(1, -1)
  }

  if (
    (trimmed.startsWith('[') && trimmed.endsWith(']')) ||
    (trimmed.startsWith('{') && trimmed.endsWith('}'))
  ) {
    try {
      return JSON.parse(trimmed)
    } catch {
      const inner = trimmed.slice(1, -1).trim()
      return inner
        ? inner.split(',').map((item) => item.trim().replace(/^['"]|['"]$/g, ''))
        : []
    }
  }

  return trimmed
}

const toCommaText = (value: unknown) => {
  if (Array.isArray(value)) {
    return value
      .map((item) => String(item).trim())
      .filter(Boolean)
      .join(', ')
  }

  return String(value ?? '').trim()
}

const buildPresetFromRaw = (rawText: string): EnvPreset => {
  const record = parseEnvRecord(rawText)
  const tokenKey =
    TOKEN_KEY_CANDIDATES.find((key) => Object.prototype.hasOwnProperty.call(record, key)) ||
    'TOKEN'

  return {
    host: String(parseEnvValue(record.HOST) || ''),
    port: String(parseEnvValue(record.PORT) || ''),
    superusers: toCommaText(parseEnvValue(record.SUPERUSERS)),
    nickname: toCommaText(parseEnvValue(record.NICKNAME)),
    commandStart: toCommaText(parseEnvValue(record.COMMAND_START)),
    commandSep: toCommaText(parseEnvValue(record.COMMAND_SEP)),
    token: String(parseEnvValue(record[tokenKey]) || ''),
    tokenKey
  }
}

const splitCommaValues = (value: string) =>
  value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

const formatScalarValue = (key: string, value: string) => {
  const trimmed = value.trim()
  if (!trimmed) return ''
  if (key === 'PORT' && /^\d+$/.test(trimmed)) return trimmed
  return JSON.stringify(trimmed)
}

const formatListValue = (value: string) => {
  const items = splitCommaValues(value)
  if (!items.length) return ''
  return JSON.stringify(items)
}

const upsertEnvEntry = (rawText: string, key: string, value: string) => {
  const lines = rawText.replace(/\r\n/g, '\n').split('\n')
  const pattern = new RegExp(`^\\s*${escapeRegExp(key)}\\s*=`, 'i')
  const filtered = lines.filter((line) => !pattern.test(line))

  if (value) {
    filtered.push(`${key}=${value}`)
  }

  return normalizeRawText(filtered.join('\n'))
}

const removeEnvEntries = (rawText: string, keys: string[]) => {
  const lines = rawText.replace(/\r\n/g, '\n').split('\n')
  const patterns = keys.map((key) => new RegExp(`^\\s*${escapeRegExp(key)}\\s*=`, 'i'))
  return normalizeRawText(
    lines.filter((line) => !patterns.some((pattern) => pattern.test(line))).join('\n')
  )
}

const mergePresetIntoRaw = (rawText: string, preset: EnvPreset) => {
  let nextRaw = normalizeRawText(rawText)

  nextRaw = upsertEnvEntry(nextRaw, 'HOST', formatScalarValue('HOST', preset.host))
  nextRaw = upsertEnvEntry(nextRaw, 'PORT', formatScalarValue('PORT', preset.port))
  nextRaw = upsertEnvEntry(nextRaw, 'SUPERUSERS', formatListValue(preset.superusers))
  nextRaw = upsertEnvEntry(nextRaw, 'NICKNAME', formatListValue(preset.nickname))
  nextRaw = upsertEnvEntry(nextRaw, 'COMMAND_START', formatListValue(preset.commandStart))
  nextRaw = upsertEnvEntry(nextRaw, 'COMMAND_SEP', formatListValue(preset.commandSep))
  nextRaw = removeEnvEntries(nextRaw, TOKEN_KEY_CANDIDATES)
  nextRaw = upsertEnvEntry(nextRaw, preset.tokenKey || 'TOKEN', formatScalarValue('TOKEN', preset.token))

  return normalizeRawText(nextRaw)
}

const loadPyproject = async (projectId: string) => {
  const { data, error } = await getProjectPyprojectFile(projectId)
  if (error) {
    toast.add('error', `加载 pyproject.toml 失败：${error}`, '', 5000)
    return
  }

  pyprojectText.value = data ?? ''
}

const loadEnvCard = async (projectId: string, card: EnvCardState) => {
  const { data, error, status } = await getProjectDotenvFile(projectId, card.name)
  if (error) {
    if (status === 404) {
      card.exists = false
      card.rawText = ''
      card.preset = createEmptyPreset()
      return
    }

    toast.add('error', `加载 ${card.name} 失败：${error}`, '', 5000)
    return
  }

  card.exists = true
  card.rawText = data ?? ''
  card.preset = buildPresetFromRaw(card.rawText)
}

const loadWorkbench = async () => {
  if (!nonebotStore.selectedBot) return

  loading.value = true
  const projectId = nonebotStore.selectedBot.project_id
  await loadPyproject(projectId)
  for (const card of envCards.value) {
    await loadEnvCard(projectId, card)
  }
  loading.value = false
}

const savePyproject = async () => {
  if (!nonebotStore.selectedBot) return

  const wasRunning = Boolean(nonebotStore.selectedBot.is_running)

  pyprojectSaving.value = true
  const { error } = await saveProjectPyprojectFile(
    nonebotStore.selectedBot.project_id,
    pyprojectText.value
  )
  pyprojectSaving.value = false

  if (error) {
    toast.add('error', `保存 pyproject.toml 失败：${error}`, '', 5000)
    return
  }

  await nonebotStore.loadBots()
  await loadWorkbench()
  toast.add('success', wasRunning ? 'pyproject.toml 已保存，实例已自动重启' : 'pyproject.toml 已保存', '', 4000)
}

const persistEnvCard = async (card: EnvCardState, rawText: string, sourceLabel: string) => {
  if (!nonebotStore.selectedBot) return

  const projectId = nonebotStore.selectedBot.project_id
  const wasRunning = Boolean(nonebotStore.selectedBot.is_running)
  const nextRawText = normalizeRawText(rawText)

  if (!card.exists) {
    const { error, status } = await createProjectEnvFile(projectId, card.name)
    if (error && status !== 400) {
      toast.add('error', `创建 ${card.name} 失败：${error}`, '', 5000)
      return
    }
    card.exists = true
  }

  const { error } = await saveProjectDotenvFile(projectId, card.name, nextRawText)
  if (error) {
    toast.add('error', `保存 ${card.name} 失败：${error}`, '', 5000)
    return
  }

  card.rawText = nextRawText
  card.preset = buildPresetFromRaw(card.rawText)
  await nonebotStore.loadBots()
  toast.add(
    'success',
    wasRunning ? `${card.name}${sourceLabel}已保存，实例已自动重启` : `${card.name}${sourceLabel}已保存`,
    '',
    4000
  )
}

const savePreset = async (card: EnvCardState) => {
  card.savingPreset = true
  await persistEnvCard(card, mergePresetIntoRaw(card.rawText, card.preset), '预设项')
  card.savingPreset = false
}

const saveRawText = async (card: EnvCardState) => {
  card.savingRaw = true
  await persistEnvCard(card, card.rawText, '原始内容')
  card.savingRaw = false
}

watch(
  () => `${nonebotStore.selectedBot?.project_id ?? ''}:${nonebotStore.selectedBot?.use_env ?? ''}`,
  () => {
    void loadWorkbench()
  },
  { immediate: true }
)
</script>

<template>
  <div v-if="!nonebotStore.selectedBot" class="rounded-box bg-base-200 p-6 text-center">
    请先选择实例。
  </div>

  <div v-else class="flex flex-col gap-4">
    <div class="rounded-box bg-base-200 p-6 flex flex-col gap-2">
      <div class="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div class="space-y-1">
          <h2 class="text-xl font-semibold">实例设置</h2>
          <div class="text-sm opacity-70">
            这里统一编辑 `pyproject.toml`、`.env`、`.env.prod`。上方预设项和下方原始文本都可以使用，保存后会自动同步。
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <span class="badge badge-primary text-base-100">
            当前实例：{{ nonebotStore.selectedBot.project_name }}
          </span>
          <span class="badge badge-outline">
            当前环境：{{ nonebotStore.selectedBot.use_env || '.env' }}
          </span>
        </div>
      </div>
    </div>

    <div v-if="loading" class="rounded-box bg-base-200 p-6 text-center">加载中...</div>

    <div v-else class="grid grid-cols-1 xl:grid-cols-3 gap-4 items-stretch">
      <section class="rounded-box bg-base-200 p-5 flex h-full min-h-[760px] flex-col gap-4">
        <div class="flex flex-col gap-2">
          <h3 class="text-lg font-semibold">pyproject.toml</h3>
          <div class="text-sm opacity-70">
            适配器、插件目录和项目元信息都在这里。保存后会自动同步实例元数据。
          </div>
          <div class="bg-base-content/10 h-px"></div>
        </div>

        <textarea
          v-model="pyprojectText"
          class="textarea textarea-bordered min-h-0 flex-1 font-mono text-xs leading-6"
          spellcheck="false"
        ></textarea>

        <div class="flex justify-end">
          <button
            class="btn btn-sm btn-primary text-base-100"
            :disabled="pyprojectSaving"
            @click="savePyproject"
          >
            {{ pyprojectSaving ? '保存中...' : '保存 pyproject.toml' }}
          </button>
        </div>
      </section>

      <section
        v-for="card in envCards"
        :key="card.name"
        class="rounded-box bg-base-200 p-5 flex h-full min-h-[760px] flex-col gap-4"
      >
        <div class="flex flex-col gap-2">
          <div class="flex items-center justify-between gap-2">
            <h3 class="text-lg font-semibold">{{ card.title }}</h3>
            <span
              v-if="nonebotStore.selectedBot.use_env === card.name"
              class="badge badge-success text-base-100"
            >
              当前环境
            </span>
          </div>
          <div class="text-sm opacity-70">
            {{ card.description }}
            <span v-if="!card.exists">当前文件不存在，首次保存时会自动创建。</span>
          </div>
          <div class="bg-base-content/10 h-px"></div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label class="form-control">
            <div class="label py-1"><span class="label-text">HOST</span></div>
            <input v-model="card.preset.host" class="input input-sm input-bordered font-mono" />
          </label>

          <label class="form-control">
            <div class="label py-1"><span class="label-text">PORT</span></div>
            <input v-model="card.preset.port" class="input input-sm input-bordered font-mono" />
          </label>

          <label class="form-control">
            <div class="label py-1"><span class="label-text">SUPERUSERS</span></div>
            <input
              v-model="card.preset.superusers"
              class="input input-sm input-bordered font-mono"
              placeholder="多个值用逗号分隔"
            />
          </label>

          <label class="form-control">
            <div class="label py-1"><span class="label-text">NICKNAME</span></div>
            <input
              v-model="card.preset.nickname"
              class="input input-sm input-bordered font-mono"
              placeholder="多个值用逗号分隔"
            />
          </label>

          <label class="form-control">
            <div class="label py-1"><span class="label-text">COMMAND_START</span></div>
            <input
              v-model="card.preset.commandStart"
              class="input input-sm input-bordered font-mono"
              placeholder="例如 /, #"
            />
          </label>

          <label class="form-control">
            <div class="label py-1"><span class="label-text">COMMAND_SEP</span></div>
            <input
              v-model="card.preset.commandSep"
              class="input input-sm input-bordered font-mono"
              placeholder="例如 . 或空格"
            />
          </label>

          <label class="form-control md:col-span-2">
            <div class="label py-1"><span class="label-text">TOKEN</span></div>
            <input v-model="card.preset.token" class="input input-sm input-bordered font-mono" />
          </label>
        </div>

        <div class="flex justify-end">
          <button
            class="btn btn-sm btn-outline btn-primary"
            :disabled="card.savingPreset"
            @click="savePreset(card)"
          >
            {{ card.savingPreset ? '保存中...' : '保存上方预设项' }}
          </button>
        </div>

        <textarea
          v-model="card.rawText"
          class="textarea textarea-bordered min-h-0 flex-1 font-mono text-xs leading-6"
          spellcheck="false"
        ></textarea>

        <div class="flex justify-end">
          <button
            class="btn btn-sm btn-primary text-base-100"
            :disabled="card.savingRaw"
            @click="saveRawText(card)"
          >
            {{ card.savingRaw ? '保存中...' : `保存 ${card.name}` }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>
