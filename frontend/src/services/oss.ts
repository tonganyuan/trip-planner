import type {
  OssConfig,
  OssConfigSavePayload,
  OssTestResponse,
  UploadResponse
} from '@/types'
import apiClient from './http'

/** 统一从后端 detail 里取中文提示，取不到再用兜底文案 */
function toError(error: any, fallback: string): Error {
  // 413 是反向代理拦下来的（nginx 的 client_max_body_size），后端根本没收到请求，
  // 所以没有 detail 可读，只能按状态码给出能操作的提示
  if (error?.response?.status === 413) {
    return new Error('图片太大了，被服务器拒收（413）。换张小一点的图，或在服务器上调大上传上限')
  }
  const detail = error?.response?.data?.detail
  // FastAPI 422 的 detail 是数组，直接塞给 Error 会显示 [object Object]，等于没报
  if (Array.isArray(detail)) {
    const text = detail
      .map((item: any) => {
        const loc = Array.isArray(item?.loc) ? item.loc[item.loc.length - 1] : ''
        const msg = item?.msg || ''
        return loc ? `${loc} ${msg}` : msg
      })
      .filter(Boolean)
      .join('；')
    if (text) return new Error(`请求参数不合法：${text}`)
  }
  return new Error(detail || error?.message || fallback)
}

function unwrap(data: OssConfig & { success?: boolean }): OssConfig {
  const { success: _ignored, ...rest } = data
  return rest as OssConfig
}

/** 本家庭的对象存储配置（AK/SK 只返回脱敏提示串） */
export async function fetchOssConfig(): Promise<OssConfig> {
  try {
    const response = await apiClient.get<OssConfig>('/api/oss/config')
    return unwrap(response.data)
  } catch (error: any) {
    throw toError(error, '加载对象存储配置失败')
  }
}

export async function saveOssConfig(payload: OssConfigSavePayload): Promise<OssConfig> {
  try {
    const response = await apiClient.put<OssConfig>('/api/oss/config', payload)
    return unwrap(response.data)
  } catch (error: any) {
    throw toError(error, '保存对象存储配置失败')
  }
}

/** 真往桶里写一个测试对象再删掉，验证的是「能不能上传」 */
export async function testOssConfig(payload: OssConfigSavePayload): Promise<OssTestResponse> {
  try {
    const response = await apiClient.post<OssTestResponse>('/api/oss/config/test', payload)
    return response.data
  } catch (error: any) {
    throw toError(error, '连接测试失败')
  }
}

export async function deleteOssConfig(): Promise<OssConfig> {
  try {
    const response = await apiClient.delete<OssConfig>('/api/oss/config')
    return unwrap(response.data)
  } catch (error: any) {
    throw toError(error, '删除配置失败')
  }
}

/**
 * 上传一张打卡图片，返回可直接放进 <img src> 的地址。
 * 这里不手动设 Content-Type：交给浏览器补 multipart 的 boundary，
 * 手写 `multipart/form-data` 反而会因为缺 boundary 让后端解析失败。
 * 真正踩过的坑在 http.ts —— 全局 JSON 默认头会把这个 FormData 转成 JSON。
 */
export async function uploadCheckinImage(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  try {
    const response = await apiClient.post<UploadResponse>('/api/oss/upload', form, {
      // 大图在弱网下传得慢，给足时间，别用全局的 120s 把它掐了
      timeout: 180000
    })
    return response.data
  } catch (error: any) {
    throw toError(error, '图片上传失败')
  }
}
