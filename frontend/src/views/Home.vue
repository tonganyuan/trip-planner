<template>
  <div class="home-container">
    <div class="bg-decoration">
      <div class="circle circle-1"></div>
      <div class="circle circle-2"></div>
      <div class="circle circle-3"></div>
    </div>

    <div class="home-inner">
      <!-- 问候 -->
      <header class="greeting">
        <h1 class="greeting-title">
          {{ greeting }}，{{ displayName || '旅行者' }}
          <span class="wave">👋</span>
        </h1>
        <p class="greeting-sub">先看看目的地天气，再决定把哪几天交给 AI 去排。</p>
      </header>

      <!-- 天气卡片 -->
      <section class="weather-card">
        <div class="weather-head">
          <div class="weather-city">
            <span class="pin">📍</span>
            <a-select
              v-model:value="provinceCode"
              class="city-select province-select"
              size="large"
              show-search
              option-filter-prop="label"
              :options="provinceOptions"
              :loading="cityLoading"
              :bordered="false"
              :dropdown-match-select-width="false"
              placeholder="省份"
              @change="onProvinceChange"
            />
            <a-select
              v-model:value="cityCode"
              class="city-select"
              size="large"
              show-search
              option-filter-prop="label"
              :options="cityOptions"
              :disabled="!provinceCode"
              :bordered="false"
              :dropdown-match-select-width="false"
              placeholder="城市"
              @change="onCityChange"
            />
          </div>
          <a class="refresh" :class="{ spinning: weatherLoading }" @click="loadWeather">刷新</a>
        </div>

        <div v-if="weatherLoading && !weatherDays.length" class="weather-placeholder">
          正在获取天气…
        </div>

        <div v-else-if="weatherError" class="weather-placeholder error">
          {{ weatherError }}
          <a class="retry" @click="loadWeather">重试</a>
        </div>

        <template v-else-if="today">
          <div class="weather-now">
            <div class="now-icon">{{ weatherIcon(today.day_weather) }}</div>
            <div class="now-text">
              <div class="now-temp">
                {{ today.day_temp }}<span class="deg">°</span>
              </div>
              <div class="now-desc">
                {{ today.day_weather }}<span class="sep">·</span>夜间 {{ today.night_temp }}°
              </div>
              <div class="now-extra">{{ today.wind_direction }} {{ today.wind_power }}</div>
            </div>
          </div>

          <div class="forecast">
            <div v-for="(d, i) in forecast" :key="d.date" class="forecast-item">
              <div class="fc-day">{{ dayLabel(d.date, i) }}</div>
              <div class="fc-icon">{{ weatherIcon(d.day_weather) }}</div>
              <div class="fc-desc">{{ d.day_weather }}</div>
              <div class="fc-temp">{{ d.day_temp }}° / {{ d.night_temp }}°</div>
            </div>
          </div>
        </template>
      </section>

      <!-- 功能列表 -->
      <section class="feature-section">
        <h2 class="section-title">能帮你做什么</h2>
        <div class="feature-grid">
          <button
            v-for="item in features"
            :key="item.key"
            type="button"
            class="feature-card"
            :class="{ soon: item.soon }"
            @click="openFeature(item)"
          >
            <div class="feature-icon">{{ item.icon }}</div>
            <div class="feature-body">
              <div class="feature-title">
                {{ item.title }}
                <span v-if="item.soon" class="tag tag-soon">即将上线</span>
                <span v-else-if="item.requiresAuth && !isLoggedIn" class="tag tag-lock">需登录</span>
              </div>
              <p class="feature-desc">{{ item.desc }}</p>
            </div>
            <span class="feature-arrow">→</span>
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { getWeather } from '@/services/api'
import { fetchRegions } from '@/services/footprint'
import { useAuth } from '@/composables/useAuth'
import type { WeatherInfo, FootprintRegionProvince } from '@/types'

const router = useRouter()
const { isLoggedIn, displayName, ensureUser } = useAuth()

interface FeatureItem {
  key: string
  icon: string
  title: string
  desc: string
  to: string
  requiresAuth?: boolean
  soon?: boolean
}

const features: FeatureItem[] = [
  {
    key: 'plan',
    icon: '✈️',
    title: '规划新行程',
    desc: '给个城市和日期，AI 按天排好景点、餐饮与住宿',
    to: '/plan',
    requiresAuth: true
  },
  {
    key: 'history',
    icon: '🗂️',
    title: '家庭行程',
    desc: '查看一家人共享的行程记录，历史方案随时回看',
    to: '/history',
    requiresAuth: true
  },
  {
    key: 'family',
    icon: '👨‍👩‍👧',
    title: '家庭成员',
    desc: '邀请家人加入同一家庭，共享行程与足迹记录',
    to: '/family',
    requiresAuth: true
  },
  {
    key: 'model',
    icon: '🤖',
    title: '模型设置',
    desc: '填自己家庭的 API Key 与大模型，生成行程只花自己的额度',
    to: '/settings/model',
    requiresAuth: true
  },
  {
    key: 'oss',
    icon: '🖼️',
    title: '对象存储',
    desc: '绑定自己的华为云 OBS 桶，打卡照片直接存进你的云账号',
    to: '/settings/oss',
    requiresAuth: true
  },
  {
    key: 'footprint',
    icon: '🗺️',
    title: '我的足迹',
    desc: '在中国地图上点亮去过的城市，看看自己走过多少地方',
    to: '/footprint',
    requiresAuth: true
  }
]

// 接口不可用时退回这张热门城市表：首页是门户，不能因为一个接口挂了就没法选城市。
// 包成一个虚拟省，这样无论数据真假，省市二级的结构和逻辑都一致。
const FALLBACK_CITIES = [
  '北京', '上海', '广州', '深圳', '成都', '杭州', '西安', '重庆',
  '武汉', '南京', '苏州', '厦门', '青岛', '长沙', '昆明', '三亚',
  '哈尔滨', '拉萨', '大理', '桂林', '合肥'
]

const FALLBACK_PROVINCE: FootprintRegionProvince = {
  name: '热门城市',
  adcode: 'hot',
  cities: FALLBACK_CITIES.map((name) => ({ name, adcode: name, lng: null, lat: null }))
}

const CITY_STORAGE_KEY = 'tp_weather_city'

function initialCity(): string {
  try {
    const saved = window.localStorage.getItem(CITY_STORAGE_KEY)
    if (saved) return saved
  } catch {
    // 隐私模式下读不到，用默认值
  }
  return '合肥'
}

const city = ref(initialCity())
const regions = ref<FootprintRegionProvince[]>([])
const provinceCode = ref<string | undefined>(undefined)
const cityCode = ref<string | undefined>(undefined)
const cityLoading = ref(false)

const provinceOptions = computed(() =>
  regions.value.map((p) => ({ value: p.adcode, label: p.name }))
)

const currentProvince = computed(
  () => regions.value.find((p) => p.adcode === provinceCode.value) || null
)

const cityOptions = computed(() =>
  (currentProvince.value?.cities || []).map((c) => ({ value: c.adcode, label: c.name }))
)

/** 行政区数据来自后端（全国 372 个地级市），与足迹页共用一份缓存 */
async function loadCityOptions(): Promise<void> {
  cityLoading.value = true
  try {
    const provinces = await fetchRegions()
    regions.value = provinces.length ? provinces : [FALLBACK_PROVINCE]
  } catch {
    // 接口不可用时静默降级，热门城市仍然能选
    regions.value = [FALLBACK_PROVINCE]
  } finally {
    cityLoading.value = false
  }

  // 回填上次选过的城市；本地存的值失效（比如城市改名）就退回默认
  if (!restoreSelection(city.value) && restoreSelection('合肥')) {
    if (city.value !== '合肥') {
      city.value = '合肥'
      loadWeather()
    }
  }
}

/** 按城市名反查省市，把两个下拉的值填回去 */
function restoreSelection(name: string): boolean {
  const key = name.endsWith('市') ? name.slice(0, -1) : name
  for (const province of regions.value) {
    const hit = province.cities.find((c) => c.name === name || c.name === key)
    if (hit) {
      provinceCode.value = province.adcode
      cityCode.value = hit.adcode
      return true
    }
  }
  return false
}

function onProvinceChange(): void {
  const cities = currentProvince.value?.cities || []
  if (!cities.length) {
    cityCode.value = undefined
    return
  }
  // 直接落到省会（adcode 最小、也就是列表第一项），直辖市和港澳台则是唯一那项。
  // 不这样做的话，切完省城市框是空的，用户不知道下面这份天气是哪个城市的。
  cityCode.value = cities[0].adcode
  applyCity(cities[0].name)
}

function onCityChange(): void {
  const hit = currentProvince.value?.cities.find((c) => c.adcode === cityCode.value)
  if (hit) applyCity(hit.name)
}

function applyCity(name: string): void {
  if (city.value === name) return
  city.value = name
  loadWeather()
}

const weatherDays = ref<WeatherInfo[]>([])
const weatherLoading = ref(false)
const weatherError = ref('')

const today = computed(() => weatherDays.value[0] ?? null)
const forecast = computed(() => weatherDays.value.slice(0, 4))

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 11) return '早上好'
  if (hour < 13) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

// 高德天气给的是中文文本，这里映射成图标；命中不了就用中性天气图标兜底
const WEATHER_ICONS: Array<[string, string]> = [
  ['雷阵雨', '⛈️'],
  ['暴雨', '⛈️'],
  ['雨夹雪', '🌨️'],
  ['小雪', '🌨️'],
  ['中雪', '🌨️'],
  ['大雪', '❄️'],
  ['大雪', '❄️'],
  ['阵雨', '🌦️'],
  ['小雨', '🌦️'],
  ['中雨', '🌧️'],
  ['大雨', '🌧️'],
  ['阴', '☁️'],
  ['多云', '⛅'],
  ['晴', '☀️'],
  ['雾', '🌫️'],
  ['霾', '😷'],
  ['沙尘', '🌪️'],
  ['风', '💨']
]

function weatherIcon(text?: string): string {
  if (!text) return '🌤️'
  for (const [keyword, icon] of WEATHER_ICONS) {
    if (text.includes(keyword)) return icon
  }
  return '🌤️'
}

function dayLabel(date: string, index: number): string {
  if (index === 0) return '今天'
  if (index === 1) return '明天'
  if (index === 2) return '后天'
  const parts = date.split('-')
  return parts.length >= 3 ? `${parts[1]}/${parts[2]}` : date
}

async function loadWeather(): Promise<void> {
  weatherLoading.value = true
  weatherError.value = ''
  try {
    const response = await getWeather(city.value)
    if (!response.success || !response.data?.length) {
      throw new Error(response.message || '暂时取不到这个城市的天气')
    }
    weatherDays.value = response.data
    try {
      window.localStorage.setItem(CITY_STORAGE_KEY, city.value)
    } catch {
      // 存不下就算了
    }
  } catch (error: any) {
    weatherDays.value = []
    weatherError.value = error?.message || '天气加载失败'
  } finally {
    weatherLoading.value = false
  }
}

/**
 * 功能入口统一在这里做权限判断。
 * 门户页本身公开，但「能用什么」取决于登录态：
 * 未登录先引导登录，登录页会带着 redirect 把人送回目标功能。
 */
function openFeature(item: FeatureItem): void {
  if (item.soon) {
    message.info(`${item.title}正在开发中，很快就能用`)
    return
  }
  if (item.requiresAuth && !isLoggedIn.value) {
    message.info(`登录后才能${item.title}`)
    router.push({ name: 'Login', query: { redirect: item.to } })
    return
  }
  router.push(item.to)
}

onMounted(() => {
  ensureUser()
  loadCityOptions()
  loadWeather()
})
</script>

<style scoped>
.home-container {
  position: relative;
  min-height: calc(100vh - 64px);
  /* 抵掉 App 内容区的 24px 内边距，让渐变一直铺到 header 和页面边缘，
     否则四周会露出一圈白边，看着像一张浮在页面上的大卡片 */
  margin: -24px;
  padding: 48px 20px 64px;
  overflow: hidden;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.bg-decoration {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}

.circle {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  animation: float 20s infinite ease-in-out;
}

.circle-1 {
  width: 320px;
  height: 320px;
  top: -120px;
  left: -100px;
}

.circle-2 {
  width: 220px;
  height: 220px;
  top: 46%;
  right: -70px;
  animation-delay: 5s;
}

.circle-3 {
  width: 150px;
  height: 150px;
  bottom: -60px;
  left: 28%;
  animation-delay: 10s;
}

@keyframes float {
  0%,
  100% {
    transform: translateY(0) rotate(0deg);
  }
  50% {
    transform: translateY(-30px) rotate(180deg);
  }
}

.home-inner {
  position: relative;
  z-index: 1;
  max-width: 980px;
  margin: 0 auto;
}

/* ===== 问候 ===== */
.greeting {
  margin-bottom: 28px;
  color: #fff;
}

.greeting-title {
  margin: 0 0 10px;
  font-size: 30px;
  font-weight: 500;
  line-height: 1.3;
}

.wave {
  display: inline-block;
  margin-left: 4px;
}

.greeting-sub {
  margin: 0;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.82);
}

/* ===== 天气卡片 ===== */
.weather-card {
  padding: 22px 26px 18px;
  margin-bottom: 34px;
  background: rgba(255, 255, 255, 0.97);
  border-radius: 20px;
  box-shadow: 0 18px 44px rgba(23, 18, 60, 0.18);
}

.weather-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.weather-city {
  display: flex;
  align-items: center;
  gap: 6px;
}

.pin {
  font-size: 14px;
}

.city-select {
  width: 108px;
  font-size: 16px;
  font-weight: 500;
  color: #1f2d3d;
}

/* 省名最长三个字（内蒙古/黑龙江），窄一点给城市名留空间 */
.province-select {
  width: 86px;
}

.city-select :deep(.ant-select-selector) {
  padding-left: 4px !important;
  background: transparent !important;
  box-shadow: none !important;
}

.refresh {
  font-size: 12px;
  color: #8c9bab;
  cursor: pointer;
}

.refresh:hover {
  color: #1890ff;
}

.weather-placeholder {
  padding: 28px 0;
  font-size: 13px;
  color: #8c9bab;
  text-align: center;
}

.weather-placeholder.error {
  color: #d4380d;
}

.retry {
  margin-left: 6px;
  color: #1890ff;
  cursor: pointer;
}

.weather-now {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 6px 0 14px;
}

.now-icon {
  font-size: 52px;
  line-height: 1;
}

.now-temp {
  font-size: 38px;
  font-weight: 500;
  line-height: 1.1;
  color: #1f2d3d;
}

.deg {
  font-size: 24px;
  vertical-align: top;
}

.now-desc {
  margin-top: 2px;
  font-size: 14px;
  color: #48586b;
}

.sep {
  margin: 0 6px;
  color: #c3ccd6;
}

.now-extra {
  margin-top: 4px;
  font-size: 12px;
  color: #8c9bab;
}

.forecast {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  padding-top: 14px;
  border-top: 1px solid #eef2f7;
}

.forecast-item {
  padding: 8px 4px;
  text-align: center;
  border-radius: 12px;
  transition: background 0.18s ease;
}

.forecast-item:hover {
  background: #f5f8fc;
}

.fc-day {
  font-size: 12px;
  color: #8c9bab;
}

.fc-icon {
  margin: 6px 0 2px;
  font-size: 22px;
  line-height: 1;
}

.fc-desc {
  font-size: 12px;
  color: #48586b;
}

.fc-temp {
  margin-top: 2px;
  font-size: 12px;
  color: #1f2d3d;
}

/* ===== 功能列表 ===== */
.section-title {
  margin: 0 0 14px;
  font-size: 15px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.92);
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.feature-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 22px 22px;
  text-align: left;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.97);
  border: none;
  border-radius: 18px;
  box-shadow: 0 14px 34px rgba(23, 18, 60, 0.14);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.feature-card:hover:not(.soon) {
  transform: translateY(-4px);
  box-shadow: 0 20px 46px rgba(23, 18, 60, 0.22);
}

.feature-card.soon {
  cursor: default;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: none;
}

.feature-icon {
  flex: 0 0 46px;
  width: 46px;
  height: 46px;
  font-size: 24px;
  line-height: 46px;
  text-align: center;
  background: linear-gradient(135deg, #eef3ff, #f6efff);
  border-radius: 14px;
}

.feature-body {
  flex: 1 1 auto;
  min-width: 0;
}

.feature-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 500;
  color: #1f2d3d;
}

.tag {
  padding: 1px 8px;
  font-size: 11px;
  font-weight: 400;
  border-radius: 9px;
}

.tag-soon {
  color: #8c6d1f;
  background: #fff7e6;
}

.tag-lock {
  color: #0958d9;
  background: #e6f0ff;
}

.feature-desc {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: #7c8b9c;
}

.feature-arrow {
  flex: 0 0 auto;
  font-size: 16px;
  color: #c3ccd6;
}

.feature-card:hover:not(.soon) .feature-arrow {
  color: #1890ff;
}

/* ===== 移动端 ===== */
@media (max-width: 768px) {
  .home-container {
    min-height: auto;
    /* 窄屏下 App 内容区没有内边距，负边距会让页面左右溢出 */
    margin: 0;
    padding: 24px 14px 36px;
  }

  .greeting-title {
    font-size: 21px;
  }

  .greeting-sub {
    font-size: 13px;
  }

  .weather-card {
    padding: 16px 16px 12px;
    margin-bottom: 24px;
    border-radius: 16px;
  }

  .now-icon {
    font-size: 42px;
  }

  .now-temp {
    font-size: 30px;
  }

  /* 四天预报在窄屏改成两行，字不至于挤成一条 */
  .forecast {
    grid-template-columns: repeat(2, 1fr);
    gap: 6px;
  }

  .feature-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .feature-card {
    padding: 16px;
    gap: 12px;
    border-radius: 14px;
  }

  .feature-icon {
    flex-basis: 40px;
    width: 40px;
    height: 40px;
    font-size: 20px;
    line-height: 40px;
  }

  .feature-title {
    font-size: 15px;
  }
}
</style>
