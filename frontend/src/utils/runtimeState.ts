import type { NoneBotProjectMeta } from '@/client/api'

export type RuntimeState = 'stopped' | 'starting' | 'running'

type RuntimeStateLike = Pick<NoneBotProjectMeta, 'is_running'> & {
  runtime_state?: string
}

export const getRuntimeState = (bot?: RuntimeStateLike | null): RuntimeState => {
  const state = String(bot?.runtime_state ?? '').trim().toLowerCase()
  if (state === 'starting' || state === 'running' || state === 'stopped') {
    return state
  }
  return bot?.is_running ? 'running' : 'stopped'
}

export const isRuntimeActive = (bot?: RuntimeStateLike | null) => {
  const state = getRuntimeState(bot)
  return state === 'starting' || state === 'running'
}
