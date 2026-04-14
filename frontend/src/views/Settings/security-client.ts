import { generateURLForWebUI } from '@/client/utils'
import { getAuthToken } from '@/client/auth'

export type SecuritySettings = {
  is_docker: boolean
  service_host: string
  service_port: number
  token_hint: string
  token_mode: 'permanent' | 'random'
  random_token_expire_hours: number
  token_expires_at: number
}

export type SecuritySettingsUpdateResult = {
  token_changed: boolean
  reauth_required: boolean
  port_changed: boolean
  restart_scheduled: boolean
  service_port: number
  message: string
  token_mode: 'permanent' | 'random'
  random_token_expire_hours: number
  token_expires_at: number
}

type GenericResponse<T> = {
  detail: T
}

const getAuthHeaders = () => {
  const token = getAuthToken()
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`
  }
}

const parseErrorMessage = async (response: Response) => {
  try {
    const json = await response.json()
    if (typeof json?.detail === 'string') return json.detail
    if (Array.isArray(json?.detail)) return JSON.stringify(json.detail)
  } catch {
    // ignore json parse errors
  }
  return `${response.status} ${response.statusText}`
}

export const getSecuritySettings = async () => {
  const response = await fetch(generateURLForWebUI('/v1/system/security'), {
    method: 'GET',
    headers: getAuthHeaders()
  })

  if (!response.ok) {
    return { data: undefined, error: await parseErrorMessage(response) }
  }

  const json = (await response.json()) as GenericResponse<SecuritySettings>
  return { data: json.detail, error: undefined }
}

export const updateSecuritySettings = async (payload: {
  current_token: string
  new_token: string
  service_port: number
  token_mode: 'permanent' | 'random'
  random_token_expire_hours: number
}) => {
  const response = await fetch(generateURLForWebUI('/v1/system/security'), {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  })

  if (!response.ok) {
    return { data: undefined, error: await parseErrorMessage(response) }
  }

  const json = (await response.json()) as GenericResponse<SecuritySettingsUpdateResult>
  return { data: json.detail, error: undefined }
}
