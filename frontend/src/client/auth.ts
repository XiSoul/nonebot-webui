const TOKEN_KEY = 'token'

export const getAuthToken = () => {
  const sessionToken = sessionStorage.getItem(TOKEN_KEY)
  if (sessionToken) return sessionToken

  // Backward compatibility: migrate old localStorage token once.
  const legacyToken = localStorage.getItem(TOKEN_KEY)
  if (!legacyToken) return ''
  sessionStorage.setItem(TOKEN_KEY, legacyToken)
  localStorage.removeItem(TOKEN_KEY)
  return legacyToken
}

export const setAuthToken = (token: string) => {
  sessionStorage.setItem(TOKEN_KEY, token)
  localStorage.removeItem(TOKEN_KEY)
}

export const clearAuthToken = () => {
  sessionStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(TOKEN_KEY)
}
