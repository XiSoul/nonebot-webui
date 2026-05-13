import { client } from './api'

export interface TerminalSessionInfo {
  session_id: string
  title: string
  created_at: number
  is_active: boolean
  is_running: boolean
  log_key: string
}

export const executeProjectCommand = async (projectId: string, command: string) => {
  return client.post<{ detail: string }, { detail?: string }>({
    url: '/v1/process/execute',
    query: {
      project_id: projectId,
      command
    }
  })
}

export const openProjectTerminal = async (projectId: string) => {
  return client.post<{ detail: string }, { detail?: string }>({
    url: '/v1/process/terminal/open',
    query: {
      project_id: projectId
    }
  })
}

export const getProjectTerminalLogKey = async (projectId: string) => {
  return client.get<{ detail: string }, { detail?: string }>({
    url: '/v1/process/terminal/log-key',
    query: {
      project_id: projectId
    }
  })
}

export const listProjectTerminalSessions = async (projectId: string) => {
  return client.get<{ detail: TerminalSessionInfo[] }, { detail?: string }>({
    url: '/v1/process/terminal/sessions',
    query: {
      project_id: projectId
    }
  })
}

export const createProjectTerminalSession = async (projectId: string) => {
  return client.post<{ detail: TerminalSessionInfo }, { detail?: string }>({
    url: '/v1/process/terminal/session/create',
    query: {
      project_id: projectId
    }
  })
}

export const switchProjectTerminalSession = async (
  projectId: string,
  sessionId: string
) => {
  return client.post<{ detail: string }, { detail?: string }>({
    url: '/v1/process/terminal/session/switch',
    query: {
      project_id: projectId,
      session_id: sessionId
    }
  })
}

export const deleteProjectTerminalSession = async (
  projectId: string,
  sessionId: string
) => {
  return client.delete<{ detail: string }, { detail?: string }>({
    url: '/v1/process/terminal/session/delete',
    query: {
      project_id: projectId,
      session_id: sessionId
    }
  })
}

export const getProjectRuntimeLogKey = async (projectId: string) => {
  return client.get<{ detail: string }, { detail?: string }>({
    url: '/v1/process/runtime/log-key',
    query: {
      project_id: projectId
    }
  })
}
