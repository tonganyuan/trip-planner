import axios from 'axios'
import { clearAuth, getToken } from './token'

// 默认走同源相对路径(生产环境由 nginx 反代 /api 到后端)，
// 需要直连后端时在 .env 里显式设置 VITE_API_BASE_URL，例如 http://localhost:8000
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000 // 2分钟超时
  // 注意：这里不要写死 Content-Type: application/json。
  // axios 1.x 的 transformRequest 看到 JSON 头就会把 FormData 序列化成 JSON，
  // 上传图片时后端收到的 body 变成 {"file":{}}，直接 422 Field required。
  // 普通对象 payload axios 会自动补 application/json，FormData 则交给浏览器带 boundary。
})

// 请求拦截器：自动带上登录令牌
apiClient.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    console.log('发送请求:', config.method?.toUpperCase(), config.url)
    return config
  },
  (error) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 401 统一处理：清掉本地令牌并通知外层跳登录页。
// 用回调注入而不是在这里直接 import router —— router 会 import views，
// views 又 import 到本文件，直接依赖就成环了。
type UnauthorizedHandler = (redirect?: string) => void
let unauthorizedHandler: UnauthorizedHandler | null = null

export function setUnauthorizedHandler(handler: UnauthorizedHandler): void {
  unauthorizedHandler = handler
}

apiClient.interceptors.response.use(
  (response) => {
    console.log('收到响应:', response.status, response.config.url)
    return response
  },
  (error) => {
    const status = error.response?.status
    const url: string = error.config?.url ?? ''
    // 登录/注册接口的 401/409 是业务结果(密码错、已注册)，交给页面自己提示，
    // 不能当成"登录态失效"去跳转，否则用户会被踢回登录页原地打转
    const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/register')

    if (status === 401 && !isAuthEndpoint) {
      clearAuth()
      unauthorizedHandler?.(window.location.pathname + window.location.search)
    }

    console.error('响应错误:', status, error.message)
    return Promise.reject(error)
  }
)

export default apiClient
