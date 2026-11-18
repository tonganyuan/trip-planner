// 类型定义

export interface UserInfo {
  id: number
  username: string
  display_name: string
  family_id: number
  created_at?: string
  last_login_at?: string | null
}

export interface AuthResponse {
  success: boolean
  message: string
  token?: string | null
  expires_at?: string | null
  user?: UserInfo | null
}

export interface AuthStatus {
  success: boolean
  allow_register: boolean
  has_users: number
}

// ===== 家庭成员 =====
export interface FamilyMember {
  id: number
  username: string
  display_name: string
  is_owner: boolean
  created_at?: string
  last_login_at?: string | null
}

export interface FamilyInfo {
  id: number
  name: string
  owner_id: number
  is_owner: boolean
  member_count: number
  members: FamilyMember[]
}

export interface FamilyMutationResponse {
  success: boolean
  message: string
  member?: FamilyMember | null
  family?: FamilyInfo | null
}

// ===== 家庭模型配置 =====
export interface LlmConfig {
  configured: boolean
  provider: string
  base_url: string
  model: string
  api_key_hint: string
  temperature: number
  updated_at?: string | null
  updated_by_name?: string | null
  verified_at?: string | null
}

export interface LlmPreset {
  id: string
  label: string
  base_url: string
  model: string
  doc_url: string
  note: string
}

export interface LlmConfigResponse {
  success: boolean
  message: string
  config: LlmConfig
  is_owner: boolean
  presets: LlmPreset[]
}

export interface LlmTestResponse {
  success: boolean
  message: string
  latency_ms: number
  reply: string
  model: string
  base_url: string
}

export interface Location {
  longitude: number
  latitude: number
}

export interface Attraction {
  name: string
  address: string
  location: Location
  visit_duration: number
  description: string
  category?: string
  rating?: number
  image_url?: string
  ticket_price?: number
}

export interface Meal {
  type: 'breakfast' | 'lunch' | 'dinner' | 'snack'
  name: string
  address?: string
  location?: Location
  description?: string
  estimated_cost?: number
}

export interface Hotel {
  name: string
  address: string
  location?: Location
  price_range: string
  rating: string
  distance: string
  type: string
  estimated_cost?: number
}

export interface Budget {
  total_attractions: number
  total_hotels: number
  total_meals: number
  total_transportation: number
  total: number
}

export interface DayPlan {
  date: string
  day_index: number
  description: string
  transportation: string
  accommodation: string
  hotel?: Hotel
  attractions: Attraction[]
  meals: Meal[]
}

export interface WeatherInfo {
  date: string
  day_weather: string
  night_weather: string
  day_temp: number
  night_temp: number
  wind_direction: string
  wind_power: string
}

export interface TripPlan {
  city: string
  start_date: string
  end_date: string
  days: DayPlan[]
  weather_info: WeatherInfo[]
  overall_suggestions: string
  budget?: Budget
}

export interface TripFormData {
  city: string
  start_date: string
  end_date: string
  travel_days: number
  transportation: string
  accommodation: string
  preferences: string[]
  free_text_input: string
}

export interface TripPlanResponse {
  success: boolean
  message: string
  data?: TripPlan
  from_cache?: boolean
  trip_id?: number | null
  cached_at?: string | null
}

export interface TripHistoryItem {
  id: number
  city: string
  start_date: string
  end_date: string
  created_by: number
  created_at: string
  updated_at: string
  hit_count: number
}

export interface TripHistoryResponse {
  success: boolean
  items: TripHistoryItem[]
}

/* ============ 足迹 ============ */

/** 一条打卡：去了哪个景点、在哪儿、什么时候、留下的照片 */
export interface FootprintCheckin {
  spot: string
  /** POI 地址，同名景点靠它区分 */
  address?: string
  /** 经度（GCJ-02）。没定位时是 null，这类打卡不参与城市轨迹 */
  lng?: number | null
  lat?: number | null
  /** YYYY-MM-DD HH:mm */
  time: string
  /** 图片地址，最多 9 张 */
  images: string[]
}

/** 高德 POI 检索命中 */
export interface PoiHit {
  name: string
  address: string
  lng: number
  lat: number
  adcode: string
  district: string
}

/** 打卡编辑中的临时结构：urls 为已上传成功的图片地址 */
export interface CheckinDraft {
  /** v-for 的稳定 key，用索引会在删除后错位 */
  key: string
  spot: string
  address: string
  lng: number | null
  lat: number | null
  time?: string
  urls: string[]
  uploading: boolean
  /** 已选中的 POI 名称；用户改字后据此判断坐标是否失效 */
  pickedName: string
  /** 当前候选地址，纯 UI 用，不提交 */
  hits: PoiHit[]
  searching: boolean
}

/** 一条足迹记录 = 一次到访某城市 */
export interface FootprintItem {
  id: number
  /** 归一化城市名，统计按此去重 */
  city: string
  /** 用户输入的原始写法，仅用于展示 */
  display_city: string
  province: string
  adcode: string
  lng: number | null
  lat: number | null
  start_date: string
  end_date: string
  note: string
  /** 本次行程的景点打卡 */
  checkins: FootprintCheckin[]
  /** 这次谁去了 */
  member_ids: number[]
  created_by: number
  created_at: string
  updated_at: string
}

/** 城市聚合：同一城市多次到访合成一条 */
export interface FootprintCity {
  city: string
  display_city: string
  province: string
  adcode: string
  lng: number | null
  lat: number | null
  visit_count: number
  day_count: number
  first_date: string
  last_date: string
  member_ids: number[]
}

export interface FootprintStats {
  city_count: number
  province_count: number
  /** 在外天数，按日期去重 */
  day_count: number
  distance_km: number
  province_total: number
  provinces: string[]
  cities: FootprintCity[]
}

export interface FootprintYear {
  year: string
  city_count: number
  province_count: number
  day_count: number
  distance_km: number
  cities: string[]
}

export interface FootprintMember {
  id: number
  display_name: string
}

export interface FootprintListResponse {
  success: boolean
  message: string
  items: FootprintItem[]
  stats: FootprintStats
  years: FootprintYear[]
  members: FootprintMember[]
}

export interface FootprintMutationResponse {
  success: boolean
  message: string
  item?: FootprintItem | null
  stats?: FootprintStats | null
  years?: FootprintYear[] | null
}

export interface FootprintResolveResponse {
  success: boolean
  message: string
  name: string
  province: string
  adcode: string
  lng: number | null
  lat: number | null
}

export interface FootprintSuggestItem {
  name: string
  province: string
  adcode: string
  lng: number | null
  lat: number | null
}

export interface FootprintCreatePayload {
  city: string
  start_date: string
  end_date?: string
  note?: string
  member_ids?: number[]
  checkins?: FootprintCheckin[]
}

/** 行政区数据：省级 */
export interface FootprintRegionProvince {
  name: string
  adcode: string
  cities: FootprintRegionCity[]
}

/** 行政区数据：市级（坐标来自官方数据，不是模型生成的） */
export interface FootprintRegionCity {
  name: string
  adcode: string
  lng: number | null
  lat: number | null
}

export interface FootprintUpdatePayload {
  start_date?: string
  end_date?: string
  note?: string
  member_ids?: number[]
  /** 不传表示不改打卡；传空数组表示清空 */
  checkins?: FootprintCheckin[]
}

/* ============ 对象存储（华为云 OBS） ============ */

export interface OssConfig {
  configured: boolean
  /** 当前用户是否户主，决定能不能编辑 */
  is_owner: boolean
  provider: string
  endpoint: string
  region: string
  bucket: string
  /** 对象键前缀，默认 footprint */
  prefix: string
  /** 自定义 CDN 域名；为空则用 bucket.endpoint */
  public_domain: string
  ak_hint: string
  sk_hint: string
  updated_at: string | null
  updated_by_name: string | null
  verified_at: string | null
}

export interface OssConfigSavePayload {
  endpoint: string
  bucket: string
  /** 留空表示沿用已存的值 */
  access_key_id?: string
  secret_access_key?: string
  prefix?: string
  public_domain?: string
  region?: string
}

export interface OssTestResponse {
  success: boolean
  message: string
  latency_ms: number
  bucket: string
  endpoint: string
}

export interface UploadResponse {
  success: boolean
  /** 长期地址，随记录入库 */
  url: string
  /** 带签名的临时地址，只用于上传后立刻显示缩略图 */
  preview_url?: string
  key: string
  size: number
  content_type: string
  filename: string
}

