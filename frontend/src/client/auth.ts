const TOKEN_KEY = 'token'
const REMEMBER_LOGIN_KEY = 'rememberLogin'

export const getAuthToken = () => {
  const sessionToken = sessionStorage.getItem(TOKEN_KEY)
  if (sessionToken) return sessionToken

  const rememberedToken = localStorage.getItem(TOKEN_KEY)
  if (rememberedToken) return rememberedToken

  return ''
}

export const setAuthToken = (token: string, remember = false) => {
  if (remember) {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(REMEMBER_LOGIN_KEY, '1')
    sessionStorage.removeItem(TOKEN_KEY)
    return
  }

  sessionStorage.setItem(TOKEN_KEY, token)
  sessionStorage.setItem(REMEMBER_LOGIN_KEY, '0')
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REMEMBER_LOGIN_KEY)
}

export const clearAuthToken = () => {
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(REMEMBER_LOGIN_KEY)
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REMEMBER_LOGIN_KEY)
}

export const getRememberLogin = () => localStorage.getItem(REMEMBER_LOGIN_KEY) === '1'
