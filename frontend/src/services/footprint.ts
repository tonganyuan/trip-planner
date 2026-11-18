import type {
  FootprintCreatePayload,
  FootprintListResponse,
  FootprintMutationResponse,
  FootprintRegionProvince,
  FootprintResolveResponse,
  FootprintSuggestItem,
  FootprintUpdatePayload,
  PoiHit
} from '@/types'
import apiClient from './http'

/** 统一从后端 detail 里取中文提示，取不到再用兜底文案 */
function toError(error: any, fallback: string): Error {
  return new Error(error?.response?.data?.detail || error?.message || fallback)
}

/** 足迹总览：全部记录 + 统计 + 年度分组 + 家庭成员 */
export async function fetchFootprints(): Promise<FootprintListResponse> {
  try {
    const response = await apiClient.get<FootprintListResponse>('/api/footprint')
    return response.data
  } catch (error: any) {
    console.error('加载足迹失败:', error)
    throw toError(error, '加载足迹失败')
  }
}

/** 录入一条足迹。写操作会顺带返回最新统计，前端无需二次请求 */
export async function createFootprint(
  payload: FootprintCreatePayload
): Promise<FootprintMutationResponse> {
  try {
    const response = await apiClient.post<FootprintMutationResponse>('/api/footprint', payload)
    return response.data
  } catch (error: any) {
    console.error('录入足迹失败:', error)
    throw toError(error, '录入足迹失败')
  }
}

/** 修改日期 / 备注 / 参与成员 */
export async function updateFootprint(
  id: number,
  payload: FootprintUpdatePayload
): Promise<FootprintMutationResponse> {
  try {
    const response = await apiClient.put<FootprintMutationResponse>(
      `/api/footprint/${id}`,
      payload
    )
    return response.data
  } catch (error: any) {
    console.error('修改足迹失败:', error)
    throw toError(error, '修改足迹失败')
  }
}

export async function deleteFootprint(id: number): Promise<void> {
  try {
    await apiClient.delete(`/api/footprint/${id}`)
  } catch (error: any) {
    console.error('删除足迹失败:', error)
    throw toError(error, '删除足迹失败')
  }
}

/** 城市解析预览：确认「苏州」归到「江苏 · 苏州」 */
export async function resolveCity(name: string): Promise<FootprintResolveResponse> {
  try {
    const response = await apiClient.get<FootprintResolveResponse>('/api/footprint/resolve', {
      params: { name }
    })
    return response.data
  } catch (error: any) {
    throw toError(error, '城市识别失败')
  }
}

/** 城市联想，纯后端本地匹配，敲字时调用不会打网络请求 */
export async function suggestCity(keyword: string): Promise<FootprintSuggestItem[]> {
  try {
    const response = await apiClient.get<{ success: boolean; items: FootprintSuggestItem[] }>(
      '/api/footprint/suggest',
      { params: { keyword } }
    )
    return response.data.items || []
  } catch {
    // 联想失败不该打断输入，静默返回空
    return []
  }
}

/**
 * 按名称搜景点，返回带 GCJ-02 坐标的候选。
 * city 用来把结果限制在当前城市内，避免搜「西湖」出来一堆外地的。
 * 搜不到返回空数组而不是抛错：定位不上只影响轨迹，不该挡住打卡。
 */
export async function searchPoi(keyword: string, city = ''): Promise<PoiHit[]> {
  const text = (keyword || '').trim()
  if (text.length < 2) return []
  try {
    const response = await apiClient.get<{ success: boolean; items: PoiHit[] }>(
      '/api/footprint/poi',
      { params: { keyword: text, city } }
    )
    return response.data.items || []
  } catch {
    return []
  }
}

/**
 * 省市两级行政区数据。首次拉取后端会缓存 30 天，之后是本地文件直读。
 * 前端也留一份：首页天气和足迹页共用，来回切页面不用重复下 31KB。
 */
let regionsCache: FootprintRegionProvince[] | null = null

export async function fetchRegions(force = false): Promise<FootprintRegionProvince[]> {
  if (regionsCache && !force) return regionsCache
  try {
    const response = await apiClient.get<{
      success: boolean
      provinces: FootprintRegionProvince[]
    }>('/api/footprint/regions')
    const provinces = response.data.provinces || []
    if (provinces.length) regionsCache = provinces
    return provinces
  } catch (error: any) {
    throw toError(error, '行政区数据加载失败')
  }
}

/**
 * 省份边界，用来在地图上把去过的省份涂成色块。
 * 后端已经抽稀并缓存，前端再存一份内存缓存，切成员重绘时不用重复请求。
 * 拿不到就返回空数组：地图上少一块颜色，不该影响页面其它部分。
 */
const shapeCache = new Map<string, number[][][]>()

export async function fetchProvinceShape(adcode: string): Promise<number[][][]> {
  const code = (adcode || '').trim()
  if (code.length !== 6) return []
  const cached = shapeCache.get(code)
  if (cached) return cached
  try {
    const response = await apiClient.get<{ success: boolean; rings: number[][][] }>(
      '/api/footprint/province-shape',
      { params: { adcode: code } }
    )
    const rings = response.data.rings || []
    if (rings.length) shapeCache.set(code, rings)
    return rings
  } catch {
    return []
  }
}
