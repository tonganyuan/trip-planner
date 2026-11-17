import type { AuthResponse, AuthStatus, UserInfo } from '@/types'
import apiClient from './http'
import { clearAuth, setCachedUser, setToken } from './token'

/**
 * 统一抽取后端错误文案。
 * FastAPI 的 422 校验错误是数组，401/409 是字符串，这里都兜住，
 * 免得界面上出现 [object Object]。
 */
export function extractError(error: any, fallback: string): string {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0]
    if (typeof first === 'string') return first
    if (first?.msg) return String(first.msg)
  }
  return error?.message || fallback
}

/** 认证配置：是否开放注册、已有几个账号 */
export async function fetchAuthStatus(): Promise<AuthStatus> {
  const response = await apiClient.get<AuthStatus>('/api/auth/status')
  return response.data
}

/** 登录，成功后令牌与用户信息落本地 */
export async function login(username: string, password: string): Promise<AuthResponse> {
  try {
    const response = await apiClient.post<AuthResponse>('/api/auth/login', { username, password })
    const data = response.data
    if (data.token) {
      setToken(data.token)
    }
    if (data.user) {
      setCachedUser(data.user)
    }
    return data
  } catch (error: any) {
    throw new Error(extractError(error, '登录失败'))
  }
}

/** 注册，成功后直接是登录态 */
export async function register(
  username: string,
  password: string,
  displayName = ''
): Promise<AuthResponse> {
  try {
    const response = await apiClient.post<AuthResponse>('/api/auth/register', {
      username,
      password,
      display_name: displayName
    })
    const data = response.data
    if (data.token) {
      setToken(data.token)
    }
    if (data.user) {
      setCachedUser(data.user)
    }
    return data
  } catch (error: any) {
    throw new Error(extractError(error, '注册失败'))
  }
}

/** 用当前令牌换取用户信息，顺便校验令牌是否还有效 */
export async function fetchMe(): Promise<UserInfo> {
  try {
    const response = await apiClient.get<AuthResponse>('/api/auth/me')
    if (!response.data.user) {
      throw new Error('未获取到用户信息')
    }
    setCachedUser(response.data.user)
    return response.data.user
  } catch (error: any) {
    throw new Error(extractError(error, '获取用户信息失败'))
  }
}

/** 退出登录：后端无状态，主要是清本地令牌 */
export async function logout(): Promise<void> {
  try {
    await apiClient.post('/api/auth/logout')
  } catch {
    // 令牌可能已过期，接口失败不影响退出，本地照清
  } finally {
    clearAuth()
  }
}
