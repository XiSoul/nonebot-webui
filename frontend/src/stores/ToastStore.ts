import { defineStore } from 'pinia'
import { ref } from 'vue'
import { v4 as uuidv4 } from 'uuid'
import {
  getGlobalLogSettings,
  postGlobalLogEvent,
  type LogLevel
} from '@/views/Logs/log-center-client'

const MAX_VISIBLE_TOASTS = 5

export type ToastType = 'success' | 'error' | 'info' | 'warning'

export interface ToastItem {
  id: string
  type: ToastType
  message: string
  detail?: string
  expanded?: boolean
  createdAt: string
  project_id?: string
  project_name?: string
}

const TYPE_LEVEL_MAP: Record<ToastType, LogLevel> = {
  success: 'INFO',
  info: 'INFO',
  warning: 'WARNING',
  error: 'ERROR'
}

const LEVEL_WEIGHT: Record<LogLevel, number> = {
  DEBUG: 10,
  INFO: 20,
  WARNING: 30,
  ERROR: 40,
  CRITICAL: 50
}

const PLACEHOLDER_RE = /\b(undefined|null)\b/gi
const SELECTED_BOT_KEY = 'selectedBot'

const normalizeToastText = (value?: string, fallback = '') => {
  const normalized = `${value ?? ''}`.trim()
  if (!normalized) return fallback
  const replaced = normalized.replace(PLACEHOLDER_RE, '未知错误').trim()
  return replaced || fallback
}

const getSelectedBotContext = () => {
  try {
    const raw = localStorage.getItem(SELECTED_BOT_KEY)
    if (!raw) return { project_id: '', project_name: '' }
    const parsed = JSON.parse(raw) as { project_id?: string; project_name?: string }
    return {
      project_id: `${parsed?.project_id ?? ''}`.trim(),
      project_name: `${parsed?.project_name ?? ''}`.trim()
    }
  } catch {
    return { project_id: '', project_name: '' }
  }
}

export const useToastStore = defineStore('toastStore', () => {
  const toasts = ref<ToastItem[]>([])
  const visibleToasts = ref<ToastItem[]>([])
  const minLevel = ref<LogLevel>('DEBUG')
  const settingsLoaded = ref(false)

  const removeVisibleOnly = (id: string) => {
    const visibleIndex = visibleToasts.value.findIndex((toast) => toast.id === id)
    if (visibleIndex !== -1) {
      visibleToasts.value.splice(visibleIndex, 1)
    }
  }

  const shouldPassFilter = (type: ToastType) => {
    return LEVEL_WEIGHT[TYPE_LEVEL_MAP[type]] >= LEVEL_WEIGHT[minLevel.value]
  }

  const loadSettings = async () => {
    if (settingsLoaded.value) return
    const { data } = await getGlobalLogSettings()
    if (data?.min_level) {
      minLevel.value = data.min_level
    }
    settingsLoaded.value = true
  }

  const setMinLevel = (level: LogLevel) => {
    minLevel.value = level
    settingsLoaded.value = true
  }

  const add = (type: ToastType, message: string, detail?: string, exp?: number) => {
    if (!shouldPassFilter(type)) {
      return
    }

    const normalizedMessage = normalizeToastText(message, '未知错误')
    const normalizedDetail = normalizeToastText(detail, '')
    const selectedBot = getSelectedBotContext()

    void postGlobalLogEvent({
      level: TYPE_LEVEL_MAP[type],
      message: normalizedMessage,
      detail: normalizedDetail,
      source: 'toast-store',
      project_id: selectedBot.project_id,
      project_name: selectedBot.project_name
    })

    void exp

    const id = uuidv4()
    const toast: ToastItem = {
      id: id,
      type,
      message: normalizedMessage,
      detail: normalizedDetail,
      expanded: false,
      createdAt: new Date().toISOString(),
      project_id: selectedBot.project_id,
      project_name: selectedBot.project_name
    }

    if (visibleToasts.value.length >= MAX_VISIBLE_TOASTS) {
      removeVisibleOnly(visibleToasts.value[0].id)
    }
    visibleToasts.value.push(toast)
    toasts.value.unshift(toast)
  }

  const remove = (id: string) => {
    removeVisibleOnly(id)
    const index = toasts.value.findIndex((toast) => toast.id === id)
    if (index !== -1) {
      toasts.value.splice(index, 1)
    }
  }

  const clear = () => {
    toasts.value = []
    visibleToasts.value = []
  }

  return {
    toasts,
    visibleToasts,
    minLevel,
    loadSettings,
    setMinLevel,
    add,
    remove,
    clear
  }
})
