import { client } from './api'
import type { nb_cli_plugin_webui__app__models__store__Plugin } from './api'

export const updateProjectPlugin = async (
  projectId: string,
  env: string,
  plugin: nb_cli_plugin_webui__app__models__store__Plugin,
  targetVersion = ''
) => {
  return client.post<{ detail: string }, { detail?: string }>({
    url: '/v1/store/nonebot/update-plugin',
    query: {
      project_id: projectId,
      env,
      target_version: targetVersion
    },
    body: plugin
  })
}
