import { computed, reactive } from 'vue'
import type { UserInfo } from '@/types'
import { clearAuth, getCachedUser, getToken } from '@/services/token'
import {
  fetchMe,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister
} from '@/services/auth'

// 模块级单例：所有组件共享同一份登录态。
// 项目没装 pinia，为这一个状态引入状态库不划算，reactive 单例足够。
// token 单独放进 state 是为了让 isLoggedIn 具备响应性：
// getToken() 直接读 localStorage 不是响应式的，computed 不会跟着重算。
const state = reactive({
  user: getCachedUser() as UserInfo | null,
  token: getToken() as string | null,
  initializing: false,
  ready: false
})

/** 令牌被后端拒绝时由 http 拦截器回调，把界面状态一并清掉 */
export function resetAuthState(): void {
  state.user = null
  state.token = null
}

export function useAuth() {
  const isLoggedIn = computed(() => !!state.token)
  const displayName = computed(() => state.user?.display_name || state.user?.username || '')

  /**
   * 确保登录态已校验。
   * 有令牌但还没拉到用户信息时请求一次 /auth/me：令牌可能在别处被吊销或已过期，
   * 只信本地缓存会出现"界面显示已登录、请求全部 401"的错位。
   */
  async function ensureUser(force = false): Promise<UserInfo | null> {
    if (!state.token) {
      state.user = null
      state.ready = true
      return null
    }
    if (state.user && !force) {
      state.ready = true
      return state.user
    }
    if (state.initializing) return state.user

    state.initializing = true
    try {
      state.user = await fetchMe()
    } catch {
      state.user = null
      state.token = null
      clearAuth()
    } finally {
      state.initializing = false
      state.ready = true
    }
    return state.user
  }

  async function login(username: string, password: string): Promise<UserInfo | null> {
    const data = await apiLogin(username, password)
    state.user = data.user ?? null
    state.token = getToken()
    state.ready = true
    return state.user
  }

  async function register(
    username: string,
    password: string,
    displayName = ''
  ): Promise<UserInfo | null> {
    const data = await apiRegister(username, password, displayName)
    state.user = data.user ?? null
    state.token = getToken()
    state.ready = true
    return state.user
  }

  async function logout(): Promise<void> {
    await apiLogout()
    state.user = null
    state.token = null
    state.ready = true
  }

  return {
    state,
    isLoggedIn,
    displayName,
    ensureUser,
    login,
    register,
    logout
  }
}
