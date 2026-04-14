import { getAuthToken } from '@/client/auth'
import { generateURLForWebUI } from '@/client/utils'

export type FileManagerScope = 'mapped' | 'installed'

export type FileManagerEntry = {
  name: string
  is_dir: boolean
  path: string
  modified_time: string
  absolute_path: string
  size: number
}

export type FileManagerRoot = {
  scope: FileManagerScope
  label: string
  description: string
  root_path: string
  available: boolean
  detail: string
}

export type FileManagerRootsResult = {
  project_id: string
  project_name: string
  roots: FileManagerRoot[]
}

export type FileManagerListResult = {
  scope: FileManagerScope
  root_path: string
  current_path: string
  available: boolean
  detail: string
  items: FileManagerEntry[]
}

export type FileManagerContentResult = {
  scope: FileManagerScope
  root_path: string
  path: string
  content: string
  encoding: string
  size: number
}

type GenericResponse<T> = {
  detail: T
}

const unwrapResponseData = <T>(json: GenericResponse<T> | T): T => {
  if (
    json &&
    typeof json === 'object' &&
    'detail' in json &&
    Object.keys(json as Record<string, unknown>).length === 1
  ) {
    return (json as GenericResponse<T>).detail
  }
  return json as T
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

export const getFileManagerRoots = async (projectId: string) => {
  const response = await fetch(
    generateURLForWebUI(`/v1/file/manager/roots?project_id=${encodeURIComponent(projectId)}`),
    {
      method: 'GET',
      headers: getAuthHeaders('')
    }
  )

  if (!response.ok) {
    return { data: undefined, error: await parseErrorMessage(response) }
  }

  const json = (await response.json()) as GenericResponse<FileManagerRootsResult> | FileManagerRootsResult
  return { data: unwrapResponseData(json), error: undefined }
}

export const getFileManagerList = async (
  projectId: string,
  scope: FileManagerScope,
  path = ''
) => {
  const response = await fetch(
    generateURLForWebUI(
      `/v1/file/manager/list?project_id=${encodeURIComponent(projectId)}&scope=${encodeURIComponent(scope)}&path=${encodeURIComponent(path)}`
    ),
    {
      method: 'GET',
      headers: getAuthHeaders('')
    }
  )

  if (!response.ok) {
    return { data: undefined, error: await parseErrorMessage(response) }
  }

  const json = (await response.json()) as GenericResponse<FileManagerListResult> | FileManagerListResult
  return { data: unwrapResponseData(json), error: undefined }
}

export const getFileManagerContent = async (
  projectId: string,
  scope: FileManagerScope,
  path: string
) => {
  const response = await fetch(
    generateURLForWebUI(
      `/v1/file/manager/content?project_id=${encodeURIComponent(projectId)}&scope=${encodeURIComponent(scope)}&path=${encodeURIComponent(path)}`
    ),
    {
      method: 'GET',
      headers: getAuthHeaders('')
    }
  )

  if (!response.ok) {
    return { data: undefined, error: await parseErrorMessage(response) }
  }

  const json = (await response.json()) as GenericResponse<FileManagerContentResult> | FileManagerContentResult
  return { data: unwrapResponseData(json), error: undefined }
}

export const saveFileManagerContent = async (payload: {
  project_id: string
  scope: FileManagerScope
  path: string
  content: string
  encoding: string
}) => {
  const response = await fetch(generateURLForWebUI('/v1/file/manager/content'), {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  })

  if (!response.ok) {
    return { data: undefined, error: await parseErrorMessage(response) }
  }

  const json = (await response.json()) as GenericResponse<FileManagerContentResult> | FileManagerContentResult
  return { data: unwrapResponseData(json), error: undefined }
}

export const createFileManagerEntry = async (payload: {
  project_id: string
  scope: FileManagerScope
  path: string
  name: string
  is_dir: boolean
}) => {
  const response = await fetch(generateURLForWebUI('/v1/file/manager/create'), {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  })

  if (!response.ok) {
    return { data: undefined, error: await parseErrorMessage(response) }
  }

  const json = (await response.json()) as GenericResponse<FileManagerListResult> | FileManagerListResult
  return { data: unwrapResponseData(json), error: undefined }
}

export const deleteFileManagerEntry = async (payload: {
  project_id: string
  scope: FileManagerScope
  path: string
}) => {
  const response = await fetch(generateURLForWebUI('/v1/file/manager/delete'), {
    method: 'DELETE',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  })

  if (!response.ok) {
    return { data: undefined, error: await parseErrorMessage(response) }
  }

  const json = (await response.json()) as GenericResponse<FileManagerListResult> | FileManagerListResult
  return { data: unwrapResponseData(json), error: undefined }
}
