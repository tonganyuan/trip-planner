<template>
  <div class="fp-page">
    <div class="fp-shell">
      <router-link to="/" class="back-link">← 返回首页</router-link>

      <header class="fp-head">
        <div class="head-text">
          <h1>我的足迹</h1>
          <p>{{ subtitle }}</p>
        </div>
        <div class="head-actions">
          <a-button class="ghost-btn" :disabled="!stats.city_count" @click="openYearReview">
            年度回顾
          </a-button>
          <a-button class="ghost-btn" :disabled="!stats.city_count" @click="exportPoster">
            生成长图
          </a-button>
          <a-button type="primary" @click="openCreate">＋ 记录足迹</a-button>
        </div>
      </header>

      <a-spin :spinning="loading">
        <section class="stat-grid">
          <div class="stat-card">
            <div class="stat-label">去过的城市</div>
            <div class="stat-value">{{ stats.city_count }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">点亮省份</div>
            <div class="stat-value">
              {{ stats.province_count
              }}<span class="stat-unit">/ {{ stats.province_total }}</span>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-label">在外天数</div>
            <div class="stat-value">{{ stats.day_count }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">累计里程</div>
            <div class="stat-value">
              {{ formatNumber(stats.distance_km) }}<span class="stat-unit">km</span>
            </div>
          </div>
        </section>

        <div class="fp-body">
          <div class="map-card">
            <div class="map-toolbar">
              <div class="map-title">
                中国地图
                <span class="map-hint">{{ visibleProvinceText }}</span>
              </div>
              <label class="route-toggle">
                <span>时间轨迹</span>
                <a-switch v-model:checked="showRoute" size="small" />
              </label>
            </div>

            <div class="map-wrap">
              <div ref="mapEl" class="map-canvas"></div>

              <div v-if="mapFailed" class="map-mask">
                <p>地图暂时加载不出来</p>
                <span>城市列表和统计不受影响，刷新页面可以重试</span>
              </div>

              <div v-else-if="!stats.city_count" class="map-mask">
                <div class="empty-icon">🗺️</div>
                <p>还没有点亮任何地方</p>
                <span>记下第一次旅行，地图上就会亮起来</span>
                <a-button type="primary" size="small" @click="openCreate">记录足迹</a-button>
              </div>
            </div>
          </div>

          <aside class="fp-side">
            <div class="side-card">
              <div class="side-title">谁在走</div>
              <a-radio-group
                v-model:value="activeMember"
                size="small"
                button-style="solid"
                class="member-group"
              >
                <a-radio-button :value="0">全家</a-radio-button>
                <a-radio-button v-for="m in members" :key="m.id" :value="m.id">
                  {{ m.display_name }}
                </a-radio-button>
              </a-radio-group>
            </div>

            <div class="side-card city-card">
              <div class="side-title">
                去过的城市
                <span class="side-count">{{ stats.cities.length }}</span>
              </div>

              <div v-if="stats.cities.length" class="city-list">
                <div
                  v-for="c in stats.cities"
                  :key="c.city"
                  class="city-row"
                  @click="openCity(c)"
                >
                  <div class="city-main">
                    <span class="city-name">{{ c.display_city }}</span>
                    <span class="city-province">{{ c.province || '省份待补全' }}</span>
                  </div>
                  <div class="city-meta">
                    <span v-if="c.visit_count > 1" class="visit-badge">{{ c.visit_count }} 次</span>
                    <span>{{ c.day_count }} 天</span>
                  </div>
                </div>
              </div>

              <p v-else class="side-empty">还没有记录</p>
            </div>
          </aside>
        </div>
      </a-spin>
    </div>

    <!-- 城市详情：居中弹窗，左侧市内轨迹地图，右侧打卡记录 -->
    <a-modal
      v-model:open="cityOpen"
      :width="940"
      :footer="null"
      centered
      destroy-on-close
      wrap-class-name="city-modal-wrap"
      :title="selectedCity ? `${selectedCity.display_city} · ${selectedCity.province}` : ''"
      @after-close="onCityClose"
    >
      <template v-if="selectedCity">
        <div class="city-summary">
          <span>去过 <b>{{ selectedCity.visit_count }}</b> 次</span>
          <span>累计 <b>{{ selectedCity.day_count }}</b> 天</span>
          <span v-if="cityRecords.length">最近 {{ cityRecords[0].start_date }}</span>
        </div>

        <div class="city-body">
          <div class="city-map-panel">
            <div class="city-map-head">
              <span>市内打卡轨迹</span>
              <span class="city-map-meta">{{ trailSummary }}</span>
            </div>
            <div class="city-map-wrap">
              <div ref="cityMapEl" class="city-map-canvas"></div>
              <div v-if="cityMapFailed" class="city-map-mask">
                <p>轨迹地图加载不出来</p>
                <span>右侧的记录和统计不受影响</span>
              </div>
            </div>
            <p class="trail-note" :class="{ muted: !cityTrailPoints.length }">{{ trailNote }}</p>
          </div>

          <div class="city-record-panel">
            <div class="record-list">
              <div v-for="item in cityRecords" :key="item.id" class="record-row">
                <div class="record-head">
                  <span class="record-date">{{ dateRange(item) }}</span>
                  <a-popconfirm
                    title="删除这条足迹？删掉后统计会立即更新"
                    ok-text="删除"
                    cancel-text="取消"
                    @confirm="removeItem(item)"
                  >
                    <a-button type="link" size="small" danger>删除</a-button>
                  </a-popconfirm>
                </div>
                <div class="record-meta">
                  <span>{{ memberNames(item.member_ids) }}</span>
                  <a-button type="link" size="small" @click="openEdit(item)">编辑</a-button>
                </div>
                <p v-if="item.note" class="record-note">{{ item.note }}</p>

                <div v-if="item.checkins && item.checkins.length" class="record-checkins">
                  <div v-for="(c, i) in item.checkins" :key="i" class="checkin-view">
                    <div class="checkin-view-head">
                      <span v-if="trailIndexOf(item.id, i)" class="checkin-order">
                        {{ trailIndexOf(item.id, i) }}
                      </span>
                      <span class="checkin-spot">{{ c.spot || '景点打卡' }}</span>
                      <span v-if="c.time" class="checkin-time">{{ c.time }}</span>
                    </div>
                    <p v-if="c.address" class="checkin-addr">{{ c.address }}</p>
                    <div v-if="c.images.length" class="checkin-thumbs">
                      <a-image
                        v-for="url in c.images"
                        :key="url"
                        :src="url"
                        :width="72"
                        :height="72"
                        class="checkin-thumb"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <a-button block @click="openCreateWithCity(selectedCity.display_city)">
              再记一次 {{ selectedCity.display_city }}
            </a-button>
          </div>
        </div>
      </template>
    </a-modal>

    <!-- 录入 -->
    <a-modal
      v-model:open="createOpen"
      title="记录一次到访"
      :width="520"
      :confirm-loading="saving"
      :body-style="{ maxHeight: '64vh', overflowY: 'auto' }"
      ok-text="记录"
      cancel-text="取消"
      @ok="submitCreate"
    >
      <div class="form-row">
        <label class="form-label">去了哪里</label>
        <div class="region-row">
          <a-select
            v-model:value="formProvince"
            :options="provinceOptions"
            :loading="regionsLoading"
            show-search
            option-filter-prop="label"
            placeholder="选择省份"
            @change="onProvinceChange"
          />
          <a-select
            v-model:value="formCityAdcode"
            :options="cityOptions"
            :disabled="!formProvince"
            show-search
            option-filter-prop="label"
            placeholder="选择城市"
          />
        </div>
        <p class="form-hint" :class="{ warn: regionWarn }">{{ regionHint }}</p>
      </div>

      <div class="form-row">
        <label class="form-label">什么时候</label>
        <div class="date-row">
          <a-date-picker
            v-model:value="formStart"
            value-format="YYYY-MM-DD"
            input-read-only
            placeholder="到达日期"
          />
          <span class="date-dash">至</span>
          <a-date-picker
            v-model:value="formEnd"
            value-format="YYYY-MM-DD"
            input-read-only
            placeholder="离开（可空）"
          />
        </div>
      </div>

      <div class="form-row">
        <label class="form-label">谁去了</label>
        <a-checkbox-group v-model:value="formMembers" :options="memberCheckOptions" />
      </div>

      <div class="form-row">
        <label class="form-label">打卡景点</label>
        <CheckinEditor :items="formCheckins" :oss-ready="ossReady" :city="formCityName" />
      </div>

      <div class="form-row">
        <label class="form-label">备注</label>
        <a-textarea
          v-model:value="formNote"
          :maxlength="200"
          :rows="3"
          placeholder="想记住的事，比如第一次看到海"
        />
      </div>
    </a-modal>

    <!-- 编辑 -->
    <a-modal
      v-model:open="editOpen"
      title="修改这条足迹"
      :width="480"
      :confirm-loading="saving"
      :body-style="{ maxHeight: '64vh', overflowY: 'auto' }"
      ok-text="保存"
      cancel-text="取消"
      @ok="submitEdit"
    >
      <div class="form-row">
        <label class="form-label">城市</label>
        <div class="readonly-city">{{ editItem?.display_city }}</div>
      </div>
      <div class="form-row">
        <label class="form-label">什么时候</label>
        <div class="date-row">
          <a-date-picker v-model:value="editStart" value-format="YYYY-MM-DD" input-read-only placeholder="到达日期" />
          <span class="date-dash">至</span>
          <a-date-picker v-model:value="editEnd" value-format="YYYY-MM-DD" input-read-only placeholder="离开（可空）" />
        </div>
      </div>
      <div class="form-row">
        <label class="form-label">谁去了</label>
        <a-checkbox-group v-model:value="editMembers" :options="memberCheckOptions" />
      </div>
      <div class="form-row">
        <label class="form-label">打卡景点</label>
        <CheckinEditor :items="editCheckins" :oss-ready="ossReady" :city="editItem?.city || ''" />
      </div>
      <div class="form-row">
        <label class="form-label">备注</label>
        <a-textarea v-model:value="editNote" :maxlength="200" :rows="3" />
      </div>
    </a-modal>

    <!-- 年度回顾 -->
    <a-modal v-model:open="yearOpen" title="年度回顾" :footer="null" :width="560">
      <a-empty v-if="!yearList.length" description="还没有足迹记录" />
      <template v-else>
        <a-radio-group v-model:value="activeYear" size="small" button-style="solid" class="year-group">
          <a-radio-button v-for="y in yearList" :key="y.year" :value="y.year">
            {{ y.year }}
          </a-radio-button>
        </a-radio-group>

        <div v-if="currentYear" class="year-body">
          <div class="year-hero">
            <div class="year-title">{{ currentYear.year }} 年，你走了 {{ currentYear.city_count }} 座城市</div>
            <div class="year-sub">{{ currentYear.province_count }} 个省份 · {{ currentYear.day_count }} 天 · {{ formatNumber(currentYear.distance_km) }} km</div>
          </div>

          <div class="year-progress">
            <div class="progress-label">
              <span>全国覆盖</span>
              <span>{{ stats.province_count }} / {{ stats.province_total }}</span>
            </div>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: provincePercent + '%' }"></div>
            </div>
          </div>

          <div class="year-cities">
            <span v-for="name in currentYear.cities" :key="name" class="year-city">{{ name }}</span>
          </div>
        </div>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import AMapLoader from '@amap/amap-jsapi-loader'
import {
  createFootprint,
  deleteFootprint,
  fetchFootprints,
  fetchProvinceShape,
  fetchRegions,
  updateFootprint
} from '@/services/footprint'
import { useAuth } from '@/composables/useAuth'
import { fetchOssConfig } from '@/services/oss'
import { isNativeApp, saveDataUrl } from '@/services/native'
import CheckinEditor from '@/components/CheckinEditor.vue'
import type {
  CheckinDraft,
  FootprintCheckin,
  FootprintCity,
  FootprintItem,
  FootprintMember,
  FootprintRegionProvince,
  FootprintStats,
  FootprintYear
} from '@/types'

const { state } = useAuth()

/* ============ 数据 ============ */
const loading = ref(false)
const saving = ref(false)
const items = ref<FootprintItem[]>([])
const members = ref<FootprintMember[]>([])
const activeMember = ref(0)

/* ============ 地图 ============ */
const mapEl = ref<HTMLDivElement | null>(null)
const mapFailed = ref(false)
const showRoute = ref(true)
let AMap: any = null
let map: any = null
let overlays: any[] = []
/** 省界缓存：一个省只查一次，切成员 / 增删记录重绘时直接复用 */
const provinceRings = new Map<string, number[][][]>()

/* ============ 本地统计 ============
 * 统计全部在本地算，而不是直接用后端的 stats：
 * 切换家庭成员时不需要重新请求，且保证「全家」和「某个人」用的是同一套口径。
 */
function parseDay(value: string): Date | null {
  if (!value) return null
  const [y, m, d] = value.slice(0, 10).split('-').map(Number)
  if (!y || !m || !d) return null
  return new Date(y, m - 1, d)
}

function dayKey(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

function daysOf(item: FootprintItem): string[] {
  const start = parseDay(item.start_date)
  if (!start) return []
  // start 判空之后再算 end，否则 end 的类型会带上 null
  const end = parseDay(item.end_date) || start
  const out: string[] = []
  const cur = new Date(start)
  // 单条最多展开 60 天，防止误填旧日期把统计撑爆
  while (cur <= end && out.length < 60) {
    out.push(dayKey(cur))
    cur.setDate(cur.getDate() + 1)
  }
  return out
}

function haversineKm(a: { lng: number; lat: number }, b: { lng: number; lat: number }): number {
  const rad = (x: number) => (x * Math.PI) / 180
  const dLon = rad(b.lng - a.lng)
  const dLat = rad(b.lat - a.lat)
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2
  return 2 * 6371 * Math.asin(Math.sqrt(h))
}

type CityBucket = FootprintCity & { days: Set<string> }

function computeStats(list: FootprintItem[]): FootprintStats {
  const buckets = new Map<string, CityBucket>()
  const allDays = new Set<string>()

  for (const item of list) {
    const days = daysOf(item)
    days.forEach((d) => allDays.add(d))

    let bucket = buckets.get(item.city)
    if (!bucket) {
      bucket = {
        city: item.city,
        display_city: item.display_city,
        province: item.province,
        adcode: item.adcode,
        lng: item.lng,
        lat: item.lat,
        visit_count: 0,
        day_count: 0,
        first_date: item.start_date,
        last_date: item.end_date || item.start_date,
        member_ids: [],
        days: new Set<string>()
      }
      buckets.set(item.city, bucket)
    }
    bucket.visit_count += 1
    days.forEach((d) => bucket.days.add(d))
    bucket.day_count = bucket.days.size
    if (item.start_date && item.start_date < bucket.first_date) bucket.first_date = item.start_date
    const last = item.end_date || item.start_date
    if (last && last > bucket.last_date) bucket.last_date = last
    for (const id of item.member_ids) {
      if (!bucket.member_ids.includes(id)) bucket.member_ids.push(id)
    }
    if (bucket.lng === null && item.lng !== null) {
      bucket.lng = item.lng
      bucket.lat = item.lat
    }
  }

  const cities: FootprintCity[] = [...buckets.values()]
    .map(({ days, ...rest }) => {
      void days
      return rest
    })
    .sort((a, b) =>
      b.visit_count - a.visit_count || b.last_date.localeCompare(a.last_date)
    )

  const provinces = [...new Set(cities.map((c) => c.province).filter(Boolean))]

  // 里程：按时间把城市串起来，相邻同一城市不重复计
  const ordered = [...list].sort(
    (a, b) => (a.start_date || '9999').localeCompare(b.start_date || '9999') || a.id - b.id
  )
  let distance = 0
  let prev: FootprintItem | null = null
  for (const item of ordered) {
    if (item.lng === null || item.lat === null) continue
    if (prev && prev.city !== item.city && prev.lng !== null && prev.lat !== null) {
      distance += haversineKm(
        { lng: prev.lng, lat: prev.lat },
        { lng: item.lng, lat: item.lat }
      )
    }
    prev = item
  }

  return {
    city_count: cities.length,
    province_count: provinces.length,
    day_count: allDays.size,
    distance_km: Math.round(distance * 10) / 10,
    province_total: 34,
    provinces,
    cities
  }
}

function computeYears(list: FootprintItem[]): FootprintYear[] {
  const buckets = new Map<string, FootprintItem[]>()
  for (const item of list) {
    const year = (item.start_date || item.end_date || '').slice(0, 4) || '未知'
    const arr = buckets.get(year) || []
    arr.push(item)
    buckets.set(year, arr)
  }
  return [...buckets.entries()]
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([year, subset]) => {
      const s = computeStats(subset)
      return {
        year,
        city_count: s.city_count,
        province_count: s.province_count,
        day_count: s.day_count,
        distance_km: s.distance_km,
        cities: s.cities.map((c) => c.display_city)
      }
    })
}

const visibleItems = computed(() =>
  activeMember.value === 0
    ? items.value
    : items.value.filter((i) => i.member_ids.includes(activeMember.value))
)

const stats = computed(() => computeStats(visibleItems.value))
const yearList = computed(() => computeYears(visibleItems.value))

/**
 * 每个城市的封面图：取这座城市最近一次打卡里最新的一张。
 * 地图上只放一个点太单薄，有照片的城市直接显示照片，没有的退回圆点。
 * 按记录日期倒序 + 打卡时间倒序，第一张能用的就是封面。
 */
const cityPhotos = computed(() => {
  const result = new Map<string, string>()
  const items = [...visibleItems.value].sort(
    (a, b) => (b.start_date || '').localeCompare(a.start_date || '') || b.id - a.id
  )
  for (const item of items) {
    if (result.has(item.city)) continue
    const checkins = [...(item.checkins || [])].sort((a, b) =>
      (b.time || '').localeCompare(a.time || '')
    )
    for (const checkin of checkins) {
      const url = (checkin.images || []).find((u) => Boolean(u && u.trim()))
      if (url) {
        result.set(item.city, url)
        break
      }
    }
  }
  return result
})

const subtitle = computed(() => {
  if (!stats.value.city_count) return '记下走过的地方，地图会一点点亮起来'
  const who =
    activeMember.value === 0
      ? '一家人'
      : members.value.find((m) => m.id === activeMember.value)?.display_name || '我'
  return `${who}走过 ${stats.value.city_count} 座城市、${stats.value.province_count} 个省份`
})

const visibleProvinceText = computed(() =>
  stats.value.provinces.length ? stats.value.provinces.join(' · ') : '还没有点亮的省份'
)

const provincePercent = computed(() =>
  Math.min(100, Math.round((stats.value.province_count / stats.value.province_total) * 100))
)

const memberCheckOptions = computed(() =>
  members.value.map((m) => ({ label: m.display_name, value: m.id }))
)

function formatNumber(n: number): string {
  return Math.round(n).toLocaleString('zh-CN')
}

function dateRange(item: FootprintItem): string {
  const start = item.start_date
  const end = item.end_date
  if (!start) return '日期未知'
  if (!end || end === start) return start
  return `${start} 至 ${end}`
}

function memberNames(ids: number[]): string {
  const names = ids
    .map((id) => members.value.find((m) => m.id === id)?.display_name)
    .filter((x): x is string => Boolean(x))
  return names.length ? names.join('、') : '我'
}

/* ============ 地图渲染 ============ */

const CITY_COLOR = '#185FA5'
/** 去过省份的色块：暖珊瑚色，和蓝色海洋分得开，比浅蓝更有生气 */
const LIT_FILL = '#ff6b4a'

/** 地图脚本只加载一次，主地图和城市弹窗里的小地图共用 */
async function loadAMap(): Promise<any> {
  if (AMap) return AMap
  AMap = await AMapLoader.load({
    key: import.meta.env.VITE_AMAP_WEB_JS_KEY,
    version: '2.0',
    plugins: ['AMap.CircleMarker', 'AMap.Text', 'AMap.Polyline', 'AMap.Polygon']
  })
  return AMap
}

async function initMap(): Promise<void> {
  if (!mapEl.value) return
  try {
    const amap = await loadAMap()
    map = new amap.Map(mapEl.value, {
      zoom: 4,
      center: [104.2, 35.5],
      viewMode: '2D'
    })
    drawMap()
  } catch (error) {
    console.error('足迹地图加载失败:', error)
    mapFailed.value = true
  }
}

function clearOverlays(): void {
  if (!map) return
  if (overlays.length) {
    map.remove(overlays)
    overlays = []
  }
}

/**
 * 按 adcode 取省界。边界数据来自高德行政区接口（后端代理），不自己编造。
 * JSAPI 的 DistrictSearch 缺安全密钥会静默不回调，所以只能走后端。
 */
async function fetchProvinceRings(adcode: string): Promise<number[][][]> {
  const cached = provinceRings.get(adcode)
  if (cached) return cached
  const rings = await fetchProvinceShape(adcode)
  if (rings.length) provinceRings.set(adcode, rings)
  return rings
}

/**
 * 点亮去过的省份。
 * 原来用 AMap.DistrictLayer 的 fill 回调，实测这版高德完全不渲染填充，
 * 整张图只剩白点，所以改成拿省界自己画 Polygon，颜色和层级都可控。
 */
let fillToken = 0
async function drawProvinceFill(): Promise<void> {
  const codes = [
    ...new Set(
      stats.value.cities.filter((c) => c.adcode).map((c) => `${c.adcode.slice(0, 2)}0000`)
    )
  ]
  if (!codes.length) return

  fillToken += 1
  const token = fillToken
  const groups = await Promise.all(codes.map((code) => fetchProvinceRings(code)))
  // 等接口这段时间里可能又重绘过（切成员、删记录），旧结果直接丢掉
  if (token !== fillToken || !map) return

  const polygons: any[] = []
  for (const rings of groups) {
    for (const ring of rings) {
      polygons.push(
        new AMap.Polygon({
          path: ring,
          fillColor: LIT_FILL,
          fillOpacity: 0.55,
          strokeColor: '#ffffff',
          strokeWeight: 1.4,
          strokeOpacity: 0.9,
          zIndex: 8,
          // 让鼠标事件穿过色块，不然拖地图会被省份挡住
          bubble: true
        })
      )
    }
  }
  if (!polygons.length) return
  overlays.push(...polygons)
  map.add(polygons)
}

/** Marker 的 content 是拼出来的 HTML，城市名与图片地址都得转义，别让记录里的字符破坏结构 */
function escapeHtml(text: string): string {
  return text.replace(
    /[&<>"']/g,
    (ch) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch] as string
  )
}

function drawMap(): void {
  if (!map || !AMap) return
  clearOverlays()

  const s = stats.value
  // 省份色块是异步拉的省界，自己往 overlays 里加，不参与下面的同步批处理
  void drawProvinceFill()

  for (const city of s.cities) {
    if (city.lng === null || city.lat === null) continue
    const radius = Math.min(15, 6 + (city.visit_count - 1) * 2.5)
    const photo = cityPhotos.value.get(city.city)

    // 有打卡照片的城市直接显示照片：一个点看不出「那里拍过什么」，
    // 照片比圆点更有记忆点，也能一眼分辨自己去过哪几个地方。
    if (photo) {
      const badge =
        city.visit_count > 1 ? `<span class="fp-city-count">${city.visit_count} 次</span>` : ''
      const marker = new AMap.Marker({
        position: [city.lng, city.lat],
        anchor: 'center',
        zIndex: 22,
        cursor: 'pointer',
        content: `
          <div class="fp-city-pin" title="${escapeHtml(city.display_city)}">
            <div class="fp-city-photo">
              <img src="${escapeHtml(photo)}" alt="" onerror="this.parentNode.classList.add('is-broken')" />
            </div>
            ${badge}
            <span class="fp-city-name">${escapeHtml(city.display_city)}</span>
          </div>`
      })
      marker.on('click', () => openCity(city))
      overlays.push(marker)
      continue
    }

    const marker = new AMap.CircleMarker({
      center: [city.lng, city.lat],
      radius,
      fillColor: CITY_COLOR,
      fillOpacity: 1,
      strokeColor: '#ffffff',
      strokeWeight: 2,
      zIndex: 20,
      cursor: 'pointer'
    })
    marker.on('click', () => openCity(city))
    overlays.push(marker)

    const label = new AMap.Text({
      text: city.display_city,
      position: [city.lng, city.lat],
      anchor: 'bottom-center',
      offset: new AMap.Pixel(0, -radius - 2),
      zIndex: 21,
      style: {
        'background-color': 'transparent',
        border: 'none',
        color: '#1f2d3d',
        'font-size': '12px',
        'font-weight': '500',
        padding: '0',
        'text-shadow': '0 1px 2px rgba(255,255,255,0.9)'
      }
    })
    overlays.push(label)
  }

  if (showRoute.value) {
    const path = [...visibleItems.value]
      .filter((i) => i.lng !== null && i.lat !== null)
      .sort(
        (a, b) => (a.start_date || '9999').localeCompare(b.start_date || '9999') || a.id - b.id
      )
      .map((i) => [i.lng as number, i.lat as number])

    if (path.length > 1) {
      overlays.push(
        new AMap.Polyline({
          path,
          strokeColor: CITY_COLOR,
          strokeWeight: 2,
          strokeOpacity: 0.5,
          strokeStyle: 'dashed',
          lineJoin: 'round',
          zIndex: 10
        })
      )
    }
  }

  if (overlays.length) map.add(overlays)
  // 主地图始终是全国视角，点开某个城市不会缩放或移动它
  map.setZoomAndCenter(stats.value.city_count > 12 ? 4 : 4.6, [104.2, 35.5])
}

watch([stats, showRoute, cityPhotos], () => {
  nextTick(() => drawMap())
})

/* ============ 录入 ============ */
const createOpen = ref(false)
const formProvince = ref<string | undefined>(undefined)
const formCityAdcode = ref<string | undefined>(undefined)
const formStart = ref<string>('')
const formEnd = ref<string>('')
const formNote = ref('')
const formMembers = ref<number[]>([])
const formCheckins = ref<CheckinDraft[]>([])

// 对象存储是否可用：只用来决定要不要提示"去配置"，上传本身由后端把关
const ossReady = ref(true)

async function checkOss(): Promise<void> {
  try {
    const data = await fetchOssConfig()
    ossReady.value = data.configured
  } catch {
    // 查不到就当可用，别为了一个辅助提示打扰用户
  }
}

/** 打卡草稿行。key 用时间戳+随机，别用索引，否则删中间一行会让图片错位 */
function newCheckinDraft(): CheckinDraft {
  return {
    key: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    spot: '',
    address: '',
    lng: null,
    lat: null,
    time: undefined,
    urls: [],
    uploading: false,
    pickedName: '',
    hits: [],
    searching: false
  }
}

/** 草稿 → 提交结构；景点名和图都空的整行丢掉，避免存一堆空打卡 */
function toCheckins(rows: CheckinDraft[]): FootprintCheckin[] {
  return rows
    .map((row) => ({
      spot: row.spot.trim(),
      address: row.lng === null ? '' : row.address,
      lng: row.lng,
      lat: row.lat,
      time: (row.time || '').trim(),
      images: [...row.urls]
    }))
    .filter((item) => item.spot || item.images.length)
}

function toCheckinDrafts(list?: FootprintCheckin[]): CheckinDraft[] {
  if (!list || !list.length) return [newCheckinDraft()]
  return list.map((item) => ({
    ...newCheckinDraft(),
    spot: item.spot,
    address: item.address || '',
    lng: item.lng ?? null,
    lat: item.lat ?? null,
    time: item.time || undefined,
    urls: [...item.images],
    // 已存的打卡都带着坐标，视为已选过地点，改字时才需要重新作废
    pickedName: item.lng === null || item.lng === undefined ? '' : item.spot
  }))
}

// 行政区数据来自后端（高德官方数据，落盘缓存），用户只选不输
const regions = ref<FootprintRegionProvince[]>([])
const regionsLoading = ref(false)
let regionsTask: Promise<void> | null = null

const provinceOptions = computed(() =>
  regions.value.map((p) => ({ value: p.adcode, label: p.name }))
)

const currentProvince = computed(
  () => regions.value.find((p) => p.adcode === formProvince.value) || null
)

const cityOptions = computed(() =>
  (currentProvince.value?.cities || []).map((c) => ({ value: c.adcode, label: c.name }))
)

const selectedRegionCity = computed(
  () => currentProvince.value?.cities.find((c) => c.adcode === formCityAdcode.value) || null
)

/** 传给打卡编辑器，把景点搜索限定在选中的城市里 */
const formCityName = computed(() => selectedRegionCity.value?.name || '')

const regionHint = computed(() => {
  const province = currentProvince.value
  const city = selectedRegionCity.value
  if (!province || !city) return '直接从列表里选，省份决定地图上点亮哪一块'
  if (city.lng === null || city.lat === null) {
    return `${province.name} · ${city.name}（缺坐标，地图上不显示点位）`
  }
  return `${province.name} · ${city.name}`
})

const regionWarn = computed(
  () =>
    !!selectedRegionCity.value &&
    (selectedRegionCity.value.lng === null || selectedRegionCity.value.lat === null)
)

/** 一次拉全量省市数据，失败允许下次打开弹窗时重试 */
async function loadRegions(silent = false): Promise<void> {
  if (regions.value.length) return
  if (!regionsTask) {
    regionsLoading.value = true
    regionsTask = (async () => {
      try {
        regions.value = await fetchRegions()
      } catch (error: any) {
        if (!silent) message.error(error?.message || '行政区数据加载失败，请稍后重试')
        regionsTask = null
      } finally {
        regionsLoading.value = false
      }
    })()
  }
  await regionsTask
}

function openCreate(): void {
  formProvince.value = undefined
  formCityAdcode.value = undefined
  formStart.value = ''
  formEnd.value = ''
  formNote.value = ''
  formMembers.value = state.user?.id ? [state.user.id] : []
  formCheckins.value = [newCheckinDraft()]
  createOpen.value = true
  void loadRegions()
}

/** 换省时清空城市；直辖市/港澳台只有一个选项，直接替用户选上 */
function onProvinceChange(): void {
  formCityAdcode.value = undefined
  const cities = currentProvince.value?.cities || []
  if (cities.length === 1) {
    formCityAdcode.value = cities[0].adcode
  }
}

/** 按城市名反查行政区（「苏州」和「苏州市」都认） */
function findRegionCity(name: string): {
  province: FootprintRegionProvince
  city: { name: string; adcode: string }
} | null {
  const key = name.endsWith('市') ? name.slice(0, -1) : name
  for (const province of regions.value) {
    for (const city of province.cities) {
      if (city.name === name || city.name === key) return { province, city }
    }
  }
  return null
}

async function openCreateWithCity(city: string): Promise<void> {
  cityOpen.value = false
  openCreate()
  await loadRegions()
  const hit = findRegionCity(city)
  if (hit) {
    formProvince.value = hit.province.adcode
    formCityAdcode.value = hit.city.adcode
  }
}

async function submitCreate(): Promise<void> {
  const city = selectedRegionCity.value
  if (!city) {
    message.warning('请选择省份和城市')
    return
  }
  if (!formStart.value) {
    message.warning('请选择到达日期')
    return
  }
  saving.value = true
  try {
    const res = await createFootprint({
      city: city.name,
      start_date: formStart.value,
      end_date: formEnd.value || '',
      note: formNote.value,
      member_ids: formMembers.value,
      checkins: toCheckins(formCheckins.value)
    })
    if (res.item) items.value = [res.item, ...items.value]
    createOpen.value = false
    message.success(res.message || '已记录')
  } catch (error: any) {
    message.error(error?.message || '记录失败')
  } finally {
    saving.value = false
  }
}

/* ============ 编辑 / 删除 ============ */
const editOpen = ref(false)
const editItem = ref<FootprintItem | null>(null)
const editStart = ref('')
const editEnd = ref('')
const editNote = ref('')
const editMembers = ref<number[]>([])
const editCheckins = ref<CheckinDraft[]>([])

function openEdit(item: FootprintItem): void {
  // 编辑弹窗和城市详情弹窗是同级，后开的那个不一定压得住，先收起城市详情
  cityOpen.value = false
  editItem.value = item
  editStart.value = item.start_date
  editEnd.value = item.end_date
  editNote.value = item.note
  editMembers.value = [...item.member_ids]
  editCheckins.value = toCheckinDrafts(item.checkins)
  editOpen.value = true
}

async function submitEdit(): Promise<void> {
  if (!editItem.value) return
  saving.value = true
  try {
    const res = await updateFootprint(editItem.value.id, {
      start_date: editStart.value,
      end_date: editEnd.value || '',
      note: editNote.value,
      member_ids: editMembers.value,
      checkins: toCheckins(editCheckins.value)
    })
    if (res.item) {
      items.value = items.value.map((i) => (i.id === res.item!.id ? res.item! : i))
    }
    editOpen.value = false
    message.success('已更新')
  } catch (error: any) {
    message.error(error?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function removeItem(item: FootprintItem): Promise<void> {
  try {
    await deleteFootprint(item.id)
    items.value = items.value.filter((i) => i.id !== item.id)
    message.success('已删除')
    if (selectedCity.value && !items.value.some((i) => i.city === selectedCity.value!.city)) {
      cityOpen.value = false
    }
  } catch (error: any) {
    message.error(error?.message || '删除失败')
  }
}

/* ============ 城市详情弹窗 ============ */
const cityOpen = ref(false)
const selectedCity = ref<FootprintCity | null>(null)

const cityRecords = computed(() => {
  if (!selectedCity.value) return []
  return visibleItems.value
    .filter((i) => i.city === selectedCity.value!.city)
    .sort((a, b) => b.start_date.localeCompare(a.start_date))
})

function openCity(city: FootprintCity): void {
  selectedCity.value = city
  cityMapFailed.value = false
  cityOpen.value = true
  void mountCityMap()
  // 弹窗会给 body 加滚动锁，主地图容器宽度跟着变，高德会自己漂一下。
  // 等动画结束把尺寸重算一遍，中心和缩放保持用户当前看到的样子。
  window.setTimeout(refreshMainMapView, 320)
}

/** 尺寸变化后重算主地图，但不改变用户当前的视野 */
function refreshMainMapView(): void {
  if (!map) return
  const center = map.getCenter()
  const zoom = map.getZoom()
  map.resize()
  map.setZoomAndCenter(zoom, [center.lng, center.lat])
}

/** 弹窗内容是懒渲染的，等容器真的挂上 DOM 再建地图，否则高德拿不到尺寸 */
async function mountCityMap(): Promise<void> {
  for (let i = 0; i < 20; i += 1) {
    await nextTick()
    if (cityMapEl.value) break
    await new Promise((resolve) => window.requestAnimationFrame(resolve))
  }
  if (!cityOpen.value || !cityMapEl.value) return
  await initCityMap()
}

/* ============ 市内轨迹（弹窗内独立小地图） ============ */

const TRAIL_COLOR = '#E8743B'

const cityMapEl = ref<HTMLDivElement | null>(null)
const cityMapFailed = ref(false)
let cityMap: any = null
let cityTrailOverlays: any[] = []

type TrailPoint = {
  lng: number
  lat: number
  spot: string
  time: string
  itemId: number
  /** 这条打卡在该记录 checkins 里的下标，用来和右侧列表对齐 */
  ci: number
}

/** 当前城市里所有带坐标的打卡，按时间排序。没定位的打卡不参与，宁缺毋滥 */
const cityTrailPoints = computed(() => {
  const points: TrailPoint[] = []
  for (const item of cityRecords.value) {
    for (let ci = 0; ci < (item.checkins || []).length; ci += 1) {
      const c = item.checkins[ci]
      if (c.lng === null || c.lng === undefined) continue
      if (c.lat === null || c.lat === undefined) continue
      points.push({
        lng: c.lng,
        lat: c.lat,
        spot: c.spot,
        time: c.time || item.start_date,
        itemId: item.id,
        ci
      })
    }
  }
  // 时间是 YYYY-MM-DD HH:mm，字典序就是时间序；没填时间的退化成出发日期
  return points.sort((a, b) => a.time.localeCompare(b.time))
})

/** 打卡 → 地图序号。两边用同一套编号，用户才能把点对回记录 */
const trailIndexMap = computed(() => {
  const map = new Map<string, number>()
  cityTrailPoints.value.forEach((p, index) => map.set(`${p.itemId}-${p.ci}`, index + 1))
  return map
})

function trailIndexOf(itemId: number, ci: number): number {
  return trailIndexMap.value.get(`${itemId}-${ci}`) || 0
}

const trailSummary = computed(() => {
  const n = cityTrailPoints.value.length
  if (n > 1) return `${n} 个打卡点`
  if (n === 1) return '1 个打卡点'
  return '暂无定位打卡'
})

const trailNote = computed(() => {
  const n = cityTrailPoints.value.length
  if (n > 1) return `按打卡时间连成 ${n} 个点的路线，序号和右侧记录一一对应`
  if (n === 1) return '只标出了这 1 个打卡点，再记一个地方就能连成路线'
  return '还没有带定位的打卡。编辑记录时从下拉里选具体景点，就能画出市内轨迹'
})

/** 这个城市有没有可用坐标：没有就别把地图放大到一个空白区域 */
const cityLocated = computed(() => {
  const c = selectedCity.value
  if (c && c.lng !== null && c.lat !== null) return true
  return cityRecords.value.some((i) => i.lng !== null && i.lat !== null)
})

/** 小地图中心：城市坐标 → 记录坐标 → 第一个打卡点，逐级兜底 */
const cityCenter = computed<[number, number]>(() => {
  const c = selectedCity.value
  if (c && c.lng !== null && c.lat !== null) return [c.lng, c.lat]
  const rec = cityRecords.value.find((i) => i.lng !== null && i.lat !== null)
  if (rec && rec.lng !== null && rec.lat !== null) return [rec.lng, rec.lat]
  const p = cityTrailPoints.value[0]
  if (p) return [p.lng, p.lat]
  return [104.2, 35.5]
})

function clearCityTrail(): void {
  if (cityMap && cityTrailOverlays.length) cityMap.remove(cityTrailOverlays)
  cityTrailOverlays = []
}

function destroyCityMap(): void {
  clearCityTrail()
  if (cityMap) {
    try {
      cityMap.destroy()
    } catch {
      // 地图可能已随弹窗销毁，忽略
    }
    cityMap = null
  }
}

async function initCityMap(): Promise<void> {
  destroyCityMap()
  const el = cityMapEl.value
  if (!el || !selectedCity.value) return
  try {
    const amap = await loadAMap()
    // 脚本是异步加载的，回来时弹窗可能已经被关掉了
    if (!cityMapEl.value) return
    cityMap = new amap.Map(el, {
      zoom: cityTrailPoints.value.length > 1 ? 11 : 12,
      center: cityCenter.value,
      viewMode: '2D',
      // 去掉底图自带的 POI 点标注，只留我们的轨迹，免得一堆红点抢视线
      features: ['bg', 'road', 'building']
    })
    drawCityTrail()
    // 弹窗打开动画还没结束，容器尺寸会变，补一次 resize 让地图变清晰
    window.setTimeout(() => {
      if (cityMap) cityMap.resize()
    }, 280)
  } catch (error) {
    console.error('城市轨迹地图加载失败:', error)
    cityMapFailed.value = true
  }
}

function drawCityTrail(): void {
  if (!cityMap || !AMap) return
  clearCityTrail()

  const points = cityTrailPoints.value
  if (!points.length) {
    // 没有打卡也把城市位置标出来，别留一张空地图
    cityTrailOverlays.push(
      new AMap.CircleMarker({
        center: cityCenter.value,
        radius: 8,
        fillColor: CITY_COLOR,
        fillOpacity: 1,
        strokeColor: '#ffffff',
        strokeWeight: 2,
        zIndex: 20
      })
    )
    cityMap.add(cityTrailOverlays)
    cityMap.setZoomAndCenter(cityLocated.value ? 11 : 4, cityCenter.value)
    return
  }

  if (points.length > 1) {
    cityTrailOverlays.push(
      new AMap.Polyline({
        path: points.map((p) => [p.lng, p.lat]),
        strokeColor: TRAIL_COLOR,
        strokeWeight: 4,
        strokeOpacity: 0.85,
        lineJoin: 'round',
        lineCap: 'round',
        // 箭头指向下一个景点：「走过的路线」和一条普通连线是两回事
        showDir: true,
        zIndex: 30
      })
    )
  }

  points.forEach((point, index) => {
    cityTrailOverlays.push(
      new AMap.CircleMarker({
        center: [point.lng, point.lat],
        radius: 9,
        fillColor: TRAIL_COLOR,
        fillOpacity: 1,
        strokeColor: '#ffffff',
        strokeWeight: 2,
        zIndex: 32
      })
    )
    cityTrailOverlays.push(
      new AMap.Text({
        text: String(index + 1),
        position: [point.lng, point.lat],
        anchor: 'center',
        zIndex: 33,
        style: {
          'background-color': 'transparent',
          border: 'none',
          color: '#ffffff',
          'font-size': '11px',
          'font-weight': '700',
          padding: '0'
        }
      })
    )
  })

  cityMap.add(cityTrailOverlays)
  if (points.length === 1) {
    cityMap.setZoomAndCenter(14, [points[0].lng, points[0].lat])
  } else {
    cityMap.setFitView(cityTrailOverlays, false, [50, 50, 50, 50], 15)
  }
}

/** 关掉弹窗只销毁小地图，主地图保持用户原来的视野 */
function onCityClose(): void {
  destroyCityMap()
  window.setTimeout(refreshMainMapView, 120)
}

watch(cityTrailPoints, () => {
  if (cityOpen.value && cityMap) nextTick(() => drawCityTrail())
})

/* ============ 年度回顾 ============ */
const yearOpen = ref(false)
const activeYear = ref('')

const currentYear = computed(
  () => yearList.value.find((y) => y.year === activeYear.value) || null
)

function openYearReview(): void {
  activeYear.value = yearList.value[0]?.year || ''
  yearOpen.value = true
}

watch(yearList, (list) => {
  if (!activeYear.value && list.length) activeYear.value = list[0].year
})

/* ============ 长图 ============ */
async function exportPoster(): Promise<void> {
  const s = stats.value
  if (!s.city_count) {
    message.info('先记录一次足迹，再来生成长图')
    return
  }

  const dpr = 2
  const W = 750
  const pad = 56
  const cities = s.cities.slice(0, 24)
  const rows = Math.ceil(cities.length / 2)
  const H = 250 + 150 + rows * 54 + 130

  const canvas = document.createElement('canvas')
  canvas.width = W * dpr
  canvas.height = H * dpr
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.scale(dpr, dpr)

  // 底色
  ctx.fillStyle = '#0F172A'
  ctx.fillRect(0, 0, W, H)

  // 顶部光带（纯色块，避免花哨渐变影响文字可读性）
  ctx.fillStyle = '#1E293B'
  ctx.fillRect(0, 0, W, 8)

  ctx.textBaseline = 'alphabetic'
  const font = (size: number, weight = 'normal') =>
    `${weight} ${size}px "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif`

  // 标题
  ctx.fillStyle = '#FFFFFF'
  ctx.font = font(46, 'bold')
  ctx.fillText('我的足迹', pad, 118)

  // 年份跨度
  const yearText = yearList.value.length
    ? yearList.value.length === 1
      ? `${yearList.value[0].year} 年`
      : `${yearList.value[yearList.value.length - 1].year} — ${yearList.value[0].year}`
    : ''
  ctx.fillStyle = '#94A3B8'
  ctx.font = font(20)
  const who =
    activeMember.value === 0
      ? '一家人'
      : members.value.find((m) => m.id === activeMember.value)?.display_name || '我'
  ctx.fillText(`${who}一起走过的地方${yearText ? ' · ' + yearText : ''}`, pad, 156)

  // 统计四格
  const stats4 = [
    { label: '座城市', value: String(s.city_count) },
    { label: '个省份', value: String(s.province_count) },
    { label: '天在外', value: String(s.day_count) },
    { label: '公里', value: formatNumber(s.distance_km) }
  ]
  const cellW = (W - pad * 2) / 4
  stats4.forEach((item, index) => {
    const x = pad + cellW * index
    ctx.fillStyle = '#7FA8FF'
    ctx.font = font(40, 'bold')
    ctx.fillText(item.value, x, 250)
    ctx.fillStyle = '#64748B'
    ctx.font = font(17)
    ctx.fillText(item.label, x, 278)
  })

  // 分割线
  ctx.strokeStyle = '#1E293B'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(pad, 320)
  ctx.lineTo(W - pad, 320)
  ctx.stroke()

  // 城市清单：两列
  const colW = (W - pad * 2) / 2
  cities.forEach((city, index) => {
    const col = index % 2
    const row = Math.floor(index / 2)
    const x = pad + col * colW
    const y = 372 + row * 54

    ctx.fillStyle = '#E2E8F0'
    ctx.font = font(22)
    ctx.fillText(city.display_city, x, y)

    ctx.fillStyle = '#64748B'
    ctx.font = font(16)
    const meta = city.visit_count > 1 ? `${city.visit_count} 次` : `${city.day_count} 天`
    ctx.fillText(meta, x + 108, y)
  })

  if (s.cities.length > cities.length) {
    ctx.fillStyle = '#475569'
    ctx.font = font(16)
    ctx.fillText(`还有 ${s.cities.length - cities.length} 座城市`, pad, 372 + rows * 54 + 6)
  }

  // 底部
  ctx.fillStyle = '#475569'
  ctx.font = font(15)
  ctx.fillText('胖子的智能旅行助手 · 足迹地图', pad, H - 46)

  const filename = `足迹_${who}_${new Date().toISOString().slice(0, 10)}.png`
  const dataUrl = canvas.toDataURL('image/png')
  if (isNativeApp) {
    // 安卓 WebView 不支持 <a download>，走系统分享面板保存到相册/发微信
    await saveDataUrl(dataUrl, filename)
    message.success('长图已生成，可在分享面板里保存或发送')
  } else {
    const a = document.createElement('a')
    a.href = dataUrl
    a.download = filename
    a.click()
    message.success('长图已保存，可以直接分享')
  }
}

/* ============ 生命周期 ============ */
async function load(): Promise<void> {
  loading.value = true
  try {
    const res = await fetchFootprints()
    items.value = res.items || []
    members.value = res.members || []
  } catch (error: any) {
    message.error(error?.message || '加载足迹失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  // 行政区数据先预热，用户点「记录足迹」时下拉能立刻展开
  void loadRegions(true)
  void checkOss()
  await load()
  await nextTick()
  void initMap()
})

onBeforeUnmount(() => {
  destroyCityMap()
  if (map) {
    map.destroy()
    map = null
  }
})
</script>

<style scoped>
.fp-page {
  min-height: calc(100vh - 64px);
  margin: -24px;
  padding: 40px 20px 64px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.fp-shell {
  max-width: 1180px;
  margin: 0 auto;
}

.back-link {
  display: inline-block;
  margin-bottom: 18px;
  color: rgba(255, 255, 255, 0.9);
  font-size: 14px;
  text-decoration: none;
}

.back-link:hover {
  color: #fff;
}

.fp-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 22px;
  color: #fff;
}

.head-text h1 {
  margin: 0;
  font-size: 30px;
  font-weight: 600;
}

.head-text p {
  margin: 6px 0 0;
  color: rgba(255, 255, 255, 0.85);
  font-size: 14px;
}

.head-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.ghost-btn {
  background: rgba(255, 255, 255, 0.16);
  border-color: rgba(255, 255, 255, 0.4);
  color: #fff;
}

.ghost-btn:hover {
  background: rgba(255, 255, 255, 0.26);
  border-color: #fff;
  color: #fff;
}

.ghost-btn[disabled] {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
  color: rgba(255, 255, 255, 0.5);
}

/* ===== 统计条 ===== */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.stat-card {
  padding: 14px 18px;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 6px 18px rgba(23, 20, 60, 0.14);
}

.stat-label {
  color: #7b8798;
  font-size: 13px;
}

.stat-value {
  margin-top: 4px;
  color: #1f2d3d;
  font-size: 30px;
  font-weight: 600;
  line-height: 1.15;
}

.stat-unit {
  margin-left: 4px;
  color: #9aa6b6;
  font-size: 14px;
  font-weight: 400;
}

/* ===== 主体 ===== */
.fp-body {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.map-card {
  overflow: hidden;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(23, 20, 60, 0.16);
}

.map-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid #f0f2f5;
}

.map-title {
  color: #1f2d3d;
  font-size: 14px;
  font-weight: 600;
}

.map-hint {
  margin-left: 8px;
  color: #9aa6b6;
  font-size: 12px;
  font-weight: 400;
}

.route-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #5c6b82;
  font-size: 13px;
  cursor: pointer;
}

.map-wrap {
  position: relative;
  overflow: hidden;
  border-radius: 0 0 12px 12px;
}

.map-canvas {
  width: 100%;
  height: 470px;
  /* 高德默认底图在国界级几乎没有道路和绿地，陆地接近纯白、海洋也偏淡，
     整张图容易显得灰白。这里叠一层暖色 + 提饱和：陆地变暖沙色，
     海洋与省界变蓝，去过的省份色块更实；文字仍是深色，可读性不变。 */
  filter: sepia(0.3) saturate(2.05) contrast(1.06);
}

/* 城市照片点：AMap 只负责定位，外观全在这里控制。
   标记内容是运行时插进 .map-canvas 里的裸 HTML，拿不到 scoped 属性，所以用 :deep。 */
:deep(.fp-city-pin) {
  position: relative;
  width: 54px;
  height: 54px;
  cursor: pointer;
}

:deep(.fp-city-photo) {
  width: 54px;
  height: 54px;
  overflow: hidden;
  border: 3px solid #ffffff;
  border-radius: 50%;
  background: #dfe6f0;
  box-shadow:
    0 3px 10px rgba(24, 45, 74, 0.32),
    0 0 0 2px rgba(255, 255, 255, 0.55);
  transition: transform 0.16s ease, box-shadow 0.16s ease;
}

:deep(.fp-city-photo img) {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

:deep(.fp-city-pin:hover .fp-city-photo) {
  transform: scale(1.08);
  box-shadow: 0 6px 16px rgba(24, 45, 74, 0.34);
}

/* 图片挂了就退回实心圆点，别在图上留一个灰窟窿 */
:deep(.fp-city-photo.is-broken) {
  background: #185fa5;
}

:deep(.fp-city-photo.is-broken img) {
  display: none;
}

:deep(.fp-city-name) {
  position: absolute;
  top: 100%;
  left: 50%;
  margin-top: 3px;
  padding: 0 5px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.86);
  color: #1f2d3d;
  font-size: 12px;
  font-weight: 600;
  line-height: 17px;
  white-space: nowrap;
  transform: translateX(-50%);
}

:deep(.fp-city-count) {
  position: absolute;
  top: -4px;
  right: -7px;
  padding: 0 5px;
  border-radius: 9px;
  background: #ff6b4a;
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
  line-height: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.22);
}

.map-mask {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: #f7f9fc;
  color: #5c6b82;
  font-size: 14px;
  text-align: center;
}

.map-mask p {
  margin: 0;
  color: #1f2d3d;
  font-size: 16px;
  font-weight: 600;
}

.map-mask span {
  color: #9aa6b6;
  font-size: 13px;
}

.empty-icon {
  font-size: 40px;
  line-height: 1;
}

/* ===== 侧栏 ===== */
.fp-side {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.side-card {
  padding: 14px 16px;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 6px 18px rgba(23, 20, 60, 0.14);
}

.side-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  color: #1f2d3d;
  font-size: 14px;
  font-weight: 600;
}

.side-count {
  color: #9aa6b6;
  font-size: 12px;
  font-weight: 400;
}

.member-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.member-group :deep(.ant-radio-button-wrapper) {
  margin-bottom: 2px;
  border-radius: 8px;
  border-inline-start-width: 1px;
}

.city-card {
  max-height: 380px;
  display: flex;
  flex-direction: column;
}

.city-list {
  overflow-y: auto;
  margin: 0 -4px;
  padding: 0 4px;
}

.city-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 9px 8px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.18s;
}

.city-row:hover {
  background: #f5f7fb;
}

.city-main {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.city-name {
  color: #1f2d3d;
  font-size: 14px;
  font-weight: 500;
}

.city-province {
  color: #9aa6b6;
  font-size: 12px;
}

.city-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #7b8798;
  font-size: 12px;
  white-space: nowrap;
}

.visit-badge {
  padding: 1px 7px;
  border-radius: 9px;
  background: rgba(24, 144, 255, 0.1);
  color: #1890ff;
}

.side-empty {
  margin: 4px 0;
  color: #9aa6b6;
  font-size: 13px;
}

/* ===== 城市弹窗 ===== */
.city-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  margin-bottom: 14px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f5f7fb;
  color: #5c6b82;
  font-size: 13px;
}

.city-summary b {
  color: #185fa5;
  font-weight: 600;
}

.city-body {
  display: grid;
  grid-template-columns: 400px minmax(0, 1fr);
  gap: 16px;
  align-items: stretch;
}

.city-map-panel {
  min-width: 0;
}

.city-map-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
  color: #1f2d3d;
  font-size: 13px;
  font-weight: 600;
}

.city-map-meta {
  color: #9aa6b6;
  font-size: 12px;
  font-weight: 400;
}

.city-map-wrap {
  position: relative;
  overflow: hidden;
  border: 1px solid #eef1f6;
  border-radius: 12px;
}

.city-map-canvas {
  width: 100%;
  height: 360px;
}

.city-map-mask {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: #f7f9fc;
  color: #9aa6b6;
  font-size: 12px;
  text-align: center;
}

.city-map-mask p {
  margin: 0;
  color: #1f2d3d;
  font-size: 14px;
  font-weight: 600;
}

.trail-note {
  margin: 8px 0 0;
  padding: 8px 10px;
  font-size: 12px;
  line-height: 1.5;
  color: #b0561f;
  background: #fff5ec;
  border: 1px solid #ffd9bb;
  border-radius: 8px;
}

.trail-note.muted {
  color: #7d8899;
  background: #f7f8fa;
  border-color: #e9ecf3;
}

.city-record-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  max-height: 440px;
}

/* 记录多时只在列表里滚，底部「再记一次」始终可见 */
.city-record-panel .record-list {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  margin-bottom: 10px;
  padding-right: 4px;
}

.checkin-order {
  flex: none;
  align-self: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #e8743b;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  line-height: 18px;
  text-align: center;
}

.checkin-addr {
  margin: -2px 0 6px;
  font-size: 12px;
  color: #9aa6b6;
  line-height: 1.4;
}

.record-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 14px;
}

.record-row {
  padding: 10px 12px;
  border: 1px solid #eef1f6;
  border-radius: 10px;
}

.record-head,
.record-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.record-date {
  color: #1f2d3d;
  font-size: 14px;
  font-weight: 500;
}

.record-meta {
  margin-top: 2px;
  color: #9aa6b6;
  font-size: 12px;
}

.record-note {
  margin: 6px 0 0;
  color: #5c6b82;
  font-size: 13px;
  line-height: 1.6;
}

.record-checkins {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 10px;
}

.checkin-view-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 6px;
}

.checkin-spot {
  color: #1f2d3d;
  font-size: 13px;
  font-weight: 500;
}

.checkin-time {
  color: #9aa6b6;
  font-size: 12px;
}

.checkin-thumbs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.checkin-thumb :deep(img) {
  border-radius: 6px;
  object-fit: cover;
}

/* ===== 表单 ===== */
.form-row {
  margin-bottom: 16px;
}

.form-label {
  display: block;
  margin-bottom: 6px;
  color: #1f2d3d;
  font-size: 13px;
  font-weight: 500;
}

.form-hint {
  margin: 6px 0 0;
  color: #9aa6b6;
  font-size: 12px;
}

.form-hint.warn {
  color: #d97706;
}

.date-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.region-row {
  display: flex;
  gap: 8px;
}

.region-row :deep(.ant-select) {
  flex: 1;
  min-width: 0;
}

.date-dash {
  color: #9aa6b6;
  font-size: 13px;
}

.readonly-city {
  padding: 5px 11px;
  border-radius: 8px;
  background: #f5f7fb;
  color: #5c6b82;
  font-size: 14px;
}

/* ===== 年度回顾 ===== */
.year-group {
  margin-bottom: 16px;
}

.year-hero {
  padding: 16px 18px;
  border-radius: 12px;
  background: linear-gradient(135deg, #eef4ff 0%, #f6f0ff 100%);
}

.year-title {
  color: #1f2d3d;
  font-size: 19px;
  font-weight: 600;
}

.year-sub {
  margin-top: 6px;
  color: #5c6b82;
  font-size: 13px;
}

.year-progress {
  margin: 16px 0;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  color: #5c6b82;
  font-size: 13px;
}

.progress-bar {
  height: 8px;
  border-radius: 6px;
  background: #eef1f6;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 6px;
  background: linear-gradient(90deg, #667eea, #8f6ee0);
}

.year-cities {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.year-city {
  padding: 4px 12px;
  border-radius: 14px;
  background: #f5f7fb;
  color: #3f4c60;
  font-size: 13px;
}

/* ===== 响应式 ===== */
@media (max-width: 1024px) {
  .fp-body {
    grid-template-columns: minmax(0, 1fr);
  }

  .city-card {
    max-height: 320px;
  }

  .city-body {
    grid-template-columns: minmax(0, 1fr);
  }

  .city-map-canvas {
    height: 300px;
  }

  .city-record-panel {
    max-height: none;
    padding-right: 0;
  }

  .city-record-panel .record-list {
    overflow: visible;
    padding-right: 0;
  }
}

@media (max-width: 768px) {
  .fp-page {
    margin: 0;
    padding: 24px 14px 40px;
  }

  .fp-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .head-text h1 {
    font-size: 25px;
  }

  .head-actions {
    width: 100%;
  }

  .head-actions :deep(.ant-btn) {
    flex: 1;
  }

  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .stat-value {
    font-size: 24px;
  }

  .map-canvas {
    height: 340px;
  }

  .city-map-canvas {
    height: 240px;
  }

  .city-summary {
    gap: 12px;
  }

  .map-hint {
    display: none;
  }
}
</style>

<style>
/* 城市弹窗被 teleport 到 body，scoped 选择器够不到，这里单独写一段，
   全部挂在 .city-modal-wrap 下，不会波及别的弹窗。 */
.city-modal-wrap {
  display: flex;
  padding: 24px 16px;
}

/* flex + margin auto：正常时上下居中，内容超高时还能从顶部滚动，不会被裁掉 */
.city-modal-wrap .ant-modal {
  display: block;
  top: 0;
  margin: auto;
  padding-bottom: 0;
  max-width: calc(100vw - 24px);
}

/* 整窗限高，内容多时只滚 body，标题和关闭按钮始终在视口里 */
.city-modal-wrap .ant-modal-content {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 48px);
}

.city-modal-wrap .ant-modal-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}

@media (max-width: 768px) {
  .city-modal-wrap {
    padding: 12px 8px;
  }
}
</style>
