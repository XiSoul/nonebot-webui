import { client } from './api'

export const resizeProjectTerminal = async (
  projectId: string,
  cols: number,
  rows: number,
  sessionId?: string
) => {
  return client.post<{ detail: string }, { detail?: string }>({
    url: '/v1/process/terminal/resize',
    query: {
      project_id: projectId,
      cols,
      rows,
      session_id: sessionId
    }
  })
}
