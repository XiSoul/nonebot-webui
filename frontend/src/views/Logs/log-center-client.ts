import { getAuthToken } from '@/client/auth'
import { generateURLForWebUI } from '@/client/utils'

export type LogKind = 'webui' | 'instance'
export type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'

export type GlobalLogSettings = {
  min_level: LogLevel
  retention_days: number
  available_levels: LogLevel[]
}

export type GlobalLogEntry = {
  timestamp: string
  level: LogLevel
  source: string
  message: string
  detail: string
  project_id: string
  project_name: string
}

type GenericResponse<T> = { detail: T }

const getAuthHeaders = (contentType = 'application/json') => {
  const token = getAuthToken()
  return {
    Authorization: `Bearer ${token}`,
    ...(contentType ? { 'Content-Type': contentType } : {})
  }
}

const parseErrorMessage = async (response: Response) => {
  try {
    const json = await response.json()
    if (typeof json?.detail === 'string') return json.detail
    if (typeof json?.detail?.message === 'string') return json.detail.message
  } catch {
    // ignore
  }
  return `${response.status} ${response.statusText}`
}

export const getGlobalLogSettings = async () => {
  const response = await fetch(generateURLForWebUI('/v1/log-center/settings'), {
    method: 'GET',
    headers: getAuthHeaders('')
  })
  if (!response.ok) return { data: undefined, error: await parseErrorMessage(response) }
  const json = (await response.json()) as GenericResponse<GlobalLogSettings>
  return { data: json.detail, error: undefined }
}

export const updateGlobalLogSettings = async (payload: {
  min_level: LogLevel
  retention_days: number
}) => {
  const response = await fetch(generateURLForWebUI('/v1/log-center/settings'), {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  })
  if (!response.ok) return { data: undefined, error: await parseErrorMessage(response) }
  return { data: 'success', error: undefined }
}

export const getGlobalLogCatalog = async (kind: LogKind, projectId = '', projectName = '') => {
  const query = new URLSearchParams({ kind })
  if (projectId) query.set('project_id', projectId)
  if (projectName) query.set('project_name', projectName)
  const response = await fetch(generateURLForWebUI(`/v1/log-center/catalog?${query.toString()}`), {
    method: 'GET',
    headers: getAuthHeaders('')
  })
  if (!response.ok) return { data: undefined, error: await parseErrorMessage(response) }
  const json = (await response.json()) as GenericResponse<{ kind: LogKind; dates: string[] }>
  return { data: json.detail, error: undefined }
}

export const getGlobalLogEntries = async (params: {
  kind: LogKind
  date: string
  level: LogLevel
  search?: string
  project_id?: string
  project_name?: string
}) => {
  const query = new URLSearchParams({
    kind: params.kind,
    date: params.date,
    level: params.level
  })
  if (params.search) query.set('search', params.search)
  if (params.project_id) query.set('project_id', params.project_id)
  if (params.project_name) query.set('project_name', params.project_name)

  const response = await fetch(generateURLForWebUI(`/v1/log-center/entries?${query.toString()}`), {
    method: 'GET',
    headers: getAuthHeaders('')
  })
  if (!response.ok) return { data: undefined, error: await parseErrorMessage(response) }
  const json = (await response.json()) as GenericResponse<{
    kind: LogKind
    date: string
    total: number
    items: GlobalLogEntry[]
  }>
  return { data: json.detail, error: undefined }
}

export const postGlobalLogEvent = async (payload: {
  level: LogLevel
  message: string
  detail?: string
  source?: string
  project_id?: string
  project_name?: string
}) => {
  const token = getAuthToken()
  if (!token) return
  try {
    await fetch(generateURLForWebUI('/v1/log-center/event'), {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload)
    })
  } catch {
    // ignore event logging failures
  }
}
