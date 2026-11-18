import type { LlmConfig, LlmConfigResponse, LlmTestResponse } from '@/types'
import apiClient from './http'
import { extractError } from './auth'

/** 读取当前家庭的模型配置（Key 为脱敏值） */
export async function fetchLlmConfig(): Promise<LlmConfigResponse> {
  try {
    const response = await apiClient.get<LlmConfigResponse>('/api/llm-config')
    return response.data
  } catch (error: any) {
    throw new Error(extractError(error, '获取模型配置失败'))
  }
}

/** 保存模型配置（仅户主）。apiKey 留空表示沿用已保存的 Key */
export async function saveLlmConfig(payload: {
  provider: string
  base_url: string
  model: string
  api_key: string
  temperature: number
}): Promise<LlmConfigResponse> {
  try {
    const response = await apiClient.put<LlmConfigResponse>('/api/llm-config', payload)
    return response.data
  } catch (error: any) {
    throw new Error(extractError(error, '保存模型配置失败'))
  }
}

/** 删除模型配置（仅户主） */
export async function deleteLlmConfig(): Promise<LlmConfigResponse> {
  try {
    const response = await apiClient.delete<LlmConfigResponse>('/api/llm-config')
    return response.data
  } catch (error: any) {
    throw new Error(extractError(error, '删除模型配置失败'))
  }
}

/** 测试连通性：真发一次极短的补全请求 */
export async function testLlmConfig(payload: {
  provider: string
  base_url: string
  model: string
  api_key: string
}): Promise<LlmTestResponse> {
  try {
    // 测试可能要等模型首字，单独放宽到 40s
    const response = await apiClient.post<LlmTestResponse>('/api/llm-config/test', payload, {
      timeout: 40000
    })
    return response.data
  } catch (error: any) {
    throw new Error(extractError(error, '连接测试失败'))
  }
}

/** 供规划页判断能不能开跑 */
export async function isModelReady(): Promise<{ configured: boolean; config: LlmConfig | null }> {
  const data = await fetchLlmConfig()
  return { configured: !!data.config?.configured, config: data.config }
}
