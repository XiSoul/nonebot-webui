import { getAuthToken } from '@/client/auth'
import { generateURLForWebUI } from '@/client/utils'

type GenericResponse<T> = {
  detail: T
}

type Result<T> = {
  data?: T
  error?: string
  status: number
}

const getHeaders = () => ({
  'Content-Type': 'application/json',
  Authorization: `Bearer ${getAuthToken()}`
})

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

export const getProjectPyprojectFile = async (projectId: string): Promise<Result<string>> => {
  const url = generateURLForWebUI(`/v1/project/config/pyproject?project_id=${projectId}`)
  const response = await fetch(url, {
    method: 'GET',
    headers: getHeaders()
  })

  if (!response.ok) {
    return { error: await parseErrorMessage(response), status: response.status }
  }

  const data = (await response.json()) as GenericResponse<string>
  return { data: data.detail, status: response.status }
}

export const saveProjectPyprojectFile = async (
  projectId: string,
  data: string
): Promise<Result<boolean>> => {
  const url = generateURLForWebUI(`/v1/project/config/pyproject?project_id=${projectId}`)
  const response = await fetch(url, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify({ data })
  })

  if (!response.ok) {
    return { error: await parseErrorMessage(response), status: response.status }
  }

  return { data: true, status: response.status }
}

export const getProjectDotenvFile = async (
  projectId: string,
  env: string
): Promise<Result<string>> => {
  const encodedEnv = encodeURIComponent(env)
  const url = generateURLForWebUI(
    `/v1/project/config/dotenv?project_id=${projectId}&env=${encodedEnv}`
  )
  const response = await fetch(url, {
    method: 'GET',
    headers: getHeaders()
  })

  if (!response.ok) {
    return { error: await parseErrorMessage(response), status: response.status }
  }

  const data = (await response.json()) as GenericResponse<string>
  return { data: data.detail, status: response.status }
}

export const saveProjectDotenvFile = async (
  projectId: string,
  env: string,
  data: string
): Promise<Result<boolean>> => {
  const url = generateURLForWebUI(`/v1/project/config/dotenv?project_id=${projectId}`)
  const response = await fetch(url, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify({ env, data })
  })

  if (!response.ok) {
    return { error: await parseErrorMessage(response), status: response.status }
  }

  return { data: true, status: response.status }
}

export const createProjectEnvFile = async (
  projectId: string,
  env: string
): Promise<Result<boolean>> => {
  const encodedEnv = encodeURIComponent(env)
  const url = generateURLForWebUI(
    `/v1/project/config/env/create?project_id=${projectId}&env=${encodedEnv}`
  )
  const response = await fetch(url, {
    method: 'POST',
    headers: getHeaders()
  })

  if (!response.ok) {
    return { error: await parseErrorMessage(response), status: response.status }
  }

  return { data: true, status: response.status }
}
