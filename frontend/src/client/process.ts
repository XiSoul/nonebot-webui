import { client } from './api'

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
