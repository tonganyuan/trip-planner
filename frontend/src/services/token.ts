import type { UserInfo } from '@/types'

// 令牌与用户缓存的唯一存放点。
// 刻意不放进 http.ts / auth.ts：这两个都要读它，放一处才不会互相 import 成环。
const TOKEN_KEY = 'tp_auth_token'
const USER_KEY = 'tp_auth_user'

// Safari 无痕模式、部分浏览器隐私设置下 localStorage 会直接抛错，
// 这里全部包一层，取不到就当未登录，不要让整个应用白屏。
function safeGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function safeSet(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    // 忽略写入失败
  }
}

function safeRemove(key: string): void {
  try {
    window.localStorage.removeItem(key)
  } catch {
    // 忽略
  }
}

export function getToken(): string | null {
  return safeGet(TOKEN_KEY)
}

export function setToken(token: string): void {
  safeSet(TOKEN_KEY, token)
}

export function getCachedUser(): UserInfo | null {
  const raw = safeGet(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as UserInfo
  } catch {
    return null
  }
}

export function setCachedUser(user: UserInfo): void {
  safeSet(USER_KEY, JSON.stringify(user))
}

export function clearAuth(): void {
  safeRemove(TOKEN_KEY)
  safeRemove(USER_KEY)
}

export function isLoggedIn(): boolean {
  return !!getToken()
}
