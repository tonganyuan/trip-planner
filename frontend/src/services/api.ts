import type {
  TripFormData,
  TripPlanResponse,
  TripHistoryResponse,
  WeatherInfo
} from '@/types'
import apiClient from './http'

/**
 * 生成旅行计划。
 * force=true 时跳过缓存强制重新生成（用户改了偏好想换新方案时用）。
 */
export async function generateTripPlan(
  formData: TripFormData,
  force = false
): Promise<TripPlanResponse> {
  try {
    const response = await apiClient.post<TripPlanResponse>('/api/trip/plan', {
      ...formData,
      force
    })
    return response.data
  } catch (error: any) {
    console.error('生成旅行计划失败:', error)
    throw new Error(error.response?.data?.detail || error.message || '生成旅行计划失败')
  }
}

/** 行程历史列表（家庭共享） */
export async function fetchTripHistory(): Promise<TripHistoryResponse> {
  const response = await apiClient.get<TripHistoryResponse>('/api/trip/history')
  return response.data
}

/** 按 ID 读取历史行程详情 */
export async function fetchTripById(id: number): Promise<TripPlanResponse> {
  const response = await apiClient.get<TripPlanResponse>(`/api/trip/${id}`)
  return response.data
}

/** 删除行程记录 */
export async function deleteTrip(id: number): Promise<void> {
  await apiClient.delete(`/api/trip/${id}`)
}

/**
 * 查询城市天气（首页用，免登录）
 */
export async function getWeather(city: string): Promise<{
  success: boolean
  message: string
  data: WeatherInfo[]
}> {
  try {
    const response = await apiClient.get('/api/map/weather', { params: { city } })
    return response.data
  } catch (error: any) {
    console.error('天气查询失败:', error)
    throw new Error(error.response?.data?.detail || error.message || '天气查询失败')
  }
}

/**
 * 健康检查
 */
export async function healthCheck(): Promise<any> {
  try {
    const response = await apiClient.get('/health')
    return response.data
  } catch (error: any) {
    console.error('健康检查失败:', error)
    throw new Error(error.message || '健康检查失败')
  }
}

export default apiClient
