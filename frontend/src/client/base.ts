const SCHEME_RE = /^[a-zA-Z][a-zA-Z\d+\-.]*:\/\//

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, '')
const hasApiPath = (value: string) => /\/api(?:\/|$)/.test(value)

export const getDefaultApiBaseUrl = () => '/api'

const ensureApiPath = (value: string) => {
  const normalized = trimTrailingSlash(value)
  if (!normalized || normalized === '/') {
    return getDefaultApiBaseUrl()
  }

  if (hasApiPath(normalized)) {
    return normalized
  }

  return `${normalized}/api`
}

export const normalizeApiBaseUrl = (base: string) => {
  const value = base.trim()

  if (!value) {
    return getDefaultApiBaseUrl()
  }

  if (value.startsWith('//')) {
    return ensureApiPath(`${window.location.protocol}${value}`)
  }

  if (value.startsWith('/')) {
    return ensureApiPath(value)
  }

  if (SCHEME_RE.test(value)) {
    return ensureApiPath(value)
  }

  return ensureApiPath(`${window.location.protocol}//${value}`)
}

export const createDebugApiBaseUrl = (host: string, port: string) =>
  normalizeApiBaseUrl(`//${host.trim()}:${port.trim()}/api`)

export const joinApiPath = (base: string, path: string) => {
  const normalizedBase = normalizeApiBaseUrl(base).replace(/\/+$/, '')
  const normalizedPath = path.replace(/^\/+/, '')
  return `${normalizedBase}/${normalizedPath}`
}

export const toWebSocketUrl = (url: string) => {
  if (url.startsWith('https://')) {
    return `wss://${url.slice('https://'.length)}`
  }

  if (url.startsWith('http://')) {
    return `ws://${url.slice('http://'.length)}`
  }

  if (url.startsWith('/')) {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${protocol}://${window.location.host}${url}`
  }

  return url
}
