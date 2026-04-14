import { getAuthToken } from '@/client/auth'
import { generateURLForWebUI } from '@/client/utils'

export type BackupSource = 'webdav' | 's3'

export type BackupSettings = {
  webdav_url: string
  webdav_username: string
  webdav_password: string
  webdav_base_path: string
  webdav_configured: boolean
  s3_endpoint: string
  s3_region: string
  s3_bucket: string
  s3_access_key: string
  s3_secret_key: string
  s3_prefix: string
  s3_force_path_style: boolean
  s3_configured: boolean
  archive_password: string
  archive_password_configured: boolean
  auto_backup_enabled: boolean
  auto_backup_interval_hours: number
  keep_count: number
  include_logs: boolean
  log_project_ids: string[]
}

export type BackupRemoteItem = {
  source: BackupSource
  key: string
  name: string
  size: number
  last_modified: string
}

export type BackupRestoreResult = {
  restarted: boolean
  message: string
}

export type BackupConnectivityResult = {
  ok: boolean
  source: BackupSource
  message: string
  detail: string
}

type GenericResponse<T> = {
  detail: T
}

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
    if (Array.isArray(json?.detail)) return JSON.stringify(json.detail)
    if (typeof json?.detail?.message === 'string') return json.detail.message
  } catch {
    // ignore
  }
  return `${response.status} ${response.statusText}`
}

const parseFilename = (response: Response) => {
  const contentDisposition = response.headers.get('content-disposition') || ''
  const matched = contentDisposition.match(/filename="?([^"]+)"?/)
  return matched?.[1] || 'backup.zip'
}

export const getBackupSettings = async () => {
  const response = await fetch(generateURLForWebUI('/v1/backup/settings'), {
    method: 'GET',
    headers: getAuthHeaders('')
  })

  if (!response.ok) {
    return { data: undefined, error: await parseErrorMessage(response) }
  }

  const json = (await response.json()) as GenericResponse<BackupSettings>
  return { data: json.detail, error: undefined }
}

export const updateBackupSettings = async (payload: BackupSettings) => {
  const response = await fetch(generateURLForWebUI('/v1/backup/settings'), {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  })

  if (!response.ok) {
    return { data: undefined, error: await parseErrorMessage(response) }
  }

  return { data: 'success', error: undefined }
}

export const testBackupConnection = async (source: BackupSource, payload: BackupSettings) => {
  const response = await fetch(generateURLForWebUI('/v1/backup/test'), {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      source,
      ...payload
    })
  })

  if (!response.ok) {
    return { data: undefined, error: await parseErrorMessage(response) }
  }

  const json = (await response.json()) as GenericResponse<BackupConnectivityResult>
  return { data: json.detail, error: undefined }
}

export const listRemoteBackups = async (source: BackupSource) => {
  const response = await fetch(
    generateURLForWebUI(`/v1/backup/list?source=${encodeURIComponent(source)}`),
    {
      method: 'GET',
      headers: getAuthHeaders('')
    }
  )

  if (!response.ok) {
    return { data: undefined, error: await parseErrorMessage(response) }
  }

  const json = (await response.json()) as GenericResponse<{
    source: BackupSource
    items: BackupRemoteItem[]
  }>
  return { data: json.detail.items, error: undefined }
}

export const downloadProjectBackup = async (projectId: string) => {
  const response = await fetch(
    generateURLForWebUI(`/v1/backup/download?project_id=${encodeURIComponent(projectId)}`),
    {
      method: 'POST',
      headers: getAuthHeaders('')
    }
  )

  if (!response.ok) {
    return { error: await parseErrorMessage(response) }
  }

  const blob = await response.blob()
  const filename = parseFilename(response)
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)

  return { error: undefined }
}

export const uploadProjectBackupToRemote = async (projectId: string, source: BackupSource) => {
  const response = await fetch(
    generateURLForWebUI(
      `/v1/backup/upload?project_id=${encodeURIComponent(projectId)}&source=${encodeURIComponent(source)}`
    ),
    {
      method: 'POST',
      headers: getAuthHeaders('')
    }
  )

  if (!response.ok) {
    return { data: undefined, error: await parseErrorMessage(response) }
  }

  const json = (await response.json()) as GenericResponse<{
    source: string
    key: string
    name: string
    size: number
    created_at: string
  }>
  return { data: json.detail, error: undefined }
}

export const restoreRemoteBackup = async (
  projectId: string,
  source: BackupSource,
  key: string,
  password = ''
) => {
  const response = await fetch(
    generateURLForWebUI(`/v1/backup/restore/remote?project_id=${encodeURIComponent(projectId)}`),
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ source, key, password })
    }
  )

  if (!response.ok) {
    return { data: undefined, error: await parseErrorMessage(response) }
  }

  const json = (await response.json()) as GenericResponse<BackupRestoreResult>
  return { data: json.detail, error: undefined }
}

export const restoreLocalBackup = async (projectId: string, file: File, password = '') => {
  const response = await fetch(
    generateURLForWebUI(`/v1/backup/restore/local?project_id=${encodeURIComponent(projectId)}`),
    {
      method: 'POST',
      headers: {
        ...getAuthHeaders('application/octet-stream'),
        'X-Backup-Filename': encodeURIComponent(file.name),
        'X-Backup-Password': password
      },
      body: file
    }
  )

  if (!response.ok) {
    return { data: undefined, error: await parseErrorMessage(response) }
  }

  const json = (await response.json()) as GenericResponse<BackupRestoreResult>
  return { data: json.detail, error: undefined }
}
