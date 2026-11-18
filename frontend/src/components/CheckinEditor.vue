<template>
  <div class="checkin-editor">
    <p v-if="ossReady === false" class="oss-missing">
      还没绑定对象存储，照片传不上去 ——
      <router-link to="/settings/oss">去设置</router-link>
    </p>

    <div v-for="(row, index) in items" :key="row.key" class="checkin-card">
      <div class="checkin-head">
        <div class="spot-field">
          <a-auto-complete
            v-model:value="row.spot"
            class="spot-input"
            :options="optionsOf(row)"
            :filter-option="false"
            :placeholder="city ? `搜索${city}的景点，如 拙政园` : '景点名，如 拙政园'"
            @search="(kw: string) => onSearch(row, kw)"
            @select="(_val: any, option: any) => onSelect(row, option)"
          >
            <template #option="item">
              <div class="poi-option">
                <span class="poi-name">{{ optName(item) }}</span>
                <span v-if="optAddress(item)" class="poi-addr">{{ optAddress(item) }}</span>
              </div>
            </template>
          </a-auto-complete>
          <p v-if="row.searching" class="spot-tip">正在搜索…</p>
          <p v-else-if="row.lng !== null" class="spot-tip ok">
            📌 {{ row.address || '已定位到地图上的这个点' }}
          </p>
          <p v-else-if="row.spot.trim()" class="spot-tip miss">
            没选具体地点，这条打卡不会画进城市轨迹
          </p>
        </div>
        <a-date-picker
          v-model:value="row.time"
          class="time-input"
          show-time
          format="YYYY-MM-DD HH:mm"
          value-format="YYYY-MM-DD HH:mm"
          placeholder="打卡时间"
        />
        <a-button type="text" size="small" danger @click="remove(index)">删除</a-button>
      </div>

      <div class="image-row">
        <div v-for="(url, i) in row.urls" :key="url" class="thumb">
          <img :src="url" alt="" />
          <button type="button" class="thumb-del" title="移除这张" @click="removeImage(row, i)">
            ×
          </button>
        </div>
        <label v-if="row.urls.length < MAX_IMAGES" class="thumb-add" :class="{ busy: row.uploading }">
          <input
            type="file"
            accept="image/jpeg,image/png,image/gif,image/webp"
            multiple
            hidden
            :disabled="row.uploading"
            @change="onPick($event, row)"
          />
          <span v-if="row.uploading">上传中…</span>
          <span v-else>＋<br />照片</span>
        </label>
      </div>
    </div>

    <a-button type="dashed" block size="small" @click="add">＋ 添加打卡景点</a-button>
    <p class="editor-hint">
      景点名敲两个字会从高德搜地点，选中后自动记下经纬度——点城市时才能把几个景点连成轨迹。
      照片原图多大都行，会先在本地压到长边 {{ MAX_EDGE }}px（通常几百 KB）再传进你家的对象存储，每条最多 {{ MAX_IMAGES }} 张。
    </p>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount } from 'vue'
import { message } from 'ant-design-vue'
import { uploadCheckinImage } from '@/services/oss'
import { searchPoi } from '@/services/footprint'
import { compressImage } from '@/utils/image'
import type { CheckinDraft } from '@/types'

const MAX_IMAGES = 9
const MAX_MB = 5
const MAX_BYTES = MAX_MB * 1024 * 1024
const MAX_EDGE = 1600

// 父组件持有数组，这里直接往同一个数组里增删：打卡只是表单里的临时结构，
// 多绕一层 emit 反而要维护两份状态，容易漏同步。
const props = defineProps<{
  items: CheckinDraft[]
  /** 家庭是否已配置对象存储；false 时给个跳转提示，别让用户传了半天才发现 */
  ossReady?: boolean
  /** 当前城市，把景点搜索限制在这个城市内，免得搜「西湖」出来一堆外地的 */
  city?: string
}>()

function newRow(): CheckinDraft {
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

function add(): void {
  props.items.push(newRow())
}

function remove(index: number): void {
  props.items.splice(index, 1)
}

function removeImage(row: CheckinDraft, index: number): void {
  row.urls.splice(index, 1)
}

/* ============ 景点定位 ============ */

const SEARCH_DEBOUNCE = 320
const timers = new Map<string, ReturnType<typeof setTimeout>>()
const seqs = new Map<string, number>()

/** 同一景点名可能对应多个门店，下拉只留第一个，避免选项 key 撞车 */
function optionsOf(row: CheckinDraft) {
  const seen = new Set<string>()
  const out: {
    value: string
    label: string
    address: string
    lng: number
    lat: number
  }[] = []
  for (const hit of row.hits || []) {
    if (!hit.name || seen.has(hit.name)) continue
    seen.add(hit.name)
    out.push({
      value: hit.name,
      label: hit.name,
      address: hit.address,
      lng: hit.lng,
      lat: hit.lat
    })
  }
  return out
}

function clearLocation(row: CheckinDraft): void {
  row.address = ''
  row.lng = null
  row.lat = null
  row.pickedName = ''
}

function onSearch(row: CheckinDraft, keyword: string): void {
  const text = (keyword || '').trim().slice(0, 60)

  // 用户改字了，之前选中的坐标就不再对应当前景点。这里必须作废，
  // 否则轨迹会连到上一个地方去——这种错数据比没有坐标更糟
  if (text !== row.pickedName) clearLocation(row)

  const pending = timers.get(row.key)
  if (pending) clearTimeout(pending)

  if (text.length < 2) {
    row.hits = []
    row.searching = false
    return
  }

  row.searching = true
  const token = (seqs.get(row.key) || 0) + 1
  seqs.set(row.key, token)
  timers.set(
    row.key,
    setTimeout(async () => {
      const hits = await searchPoi(text, props.city || '')
      // 慢请求回来时用户可能已经接着敲了字，只认最后一次
      if (seqs.get(row.key) !== token) return
      row.hits = hits
      row.searching = false
    }, SEARCH_DEBOUNCE)
  )
}

function onSelect(row: CheckinDraft, option: any): void {
  const name = String(option?.label ?? option?.value ?? '').slice(0, 60)
  if (!name) return
  const pending = timers.get(row.key)
  if (pending) clearTimeout(pending)

  row.spot = name
  row.pickedName = name
  row.address = String(option?.address ?? '')
  row.lng = typeof option?.lng === 'number' ? option.lng : null
  row.lat = typeof option?.lat === 'number' ? option.lat : null
  row.hits = []
  row.searching = false
}

function optName(item: any): string {
  return String(item?.label ?? item?.value ?? '')
}

function optAddress(item: any): string {
  return String(item?.address ?? '')
}

onBeforeUnmount(() => {
  timers.forEach((timer) => clearTimeout(timer))
  timers.clear()
})

async function onPick(event: Event, row: CheckinDraft): Promise<void> {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  // 清掉 value，否则连续选同一张照片不会触发 change
  input.value = ''
  if (!files.length) return

  const remain = MAX_IMAGES - row.urls.length
  if (remain <= 0) {
    message.warning(`每条打卡最多 ${MAX_IMAGES} 张照片`)
    return
  }

  row.uploading = true
  try {
    for (const file of files.slice(0, remain)) {
      if (!file.type.startsWith('image/')) {
        message.warning(`${file.name} 不是图片，已跳过`)
        continue
      }
      // iPhone 直出/微信原图常是 HEIC，浏览器解不了码就压不了，
      // 与其让它传到一半被后端拒掉，不如这里说清楚怎么办
      if (/^image\/hei[cf]$/i.test(file.type)) {
        message.warning(`${file.name} 是 HEIC 格式，浏览器读不了，请转成 JPG 再传`)
        continue
      }
      try {
        // 先压再传：手机直出 8MB 的照片压完只剩几百 KB，
        // 既快又不会被反向代理的请求体上限拦成 413。
        // 注意大小判断要放在压缩之后——微信原图动辄 5~10MB，
        // 压缩前就拦掉等于把最常见的照片直接拒了。
        const prepared = await compressImage(file)
        if (prepared.size > MAX_BYTES) {
          message.warning(`${file.name} 压缩后仍有 ${Math.round(prepared.size / 1024 / 1024)}MB，超过 ${MAX_MB}MB，已跳过`)
          continue
        }
        const result = await uploadCheckinImage(prepared)
        // 预览用带签名的地址（桶是私有的），入库时后端会把签名参数剥掉
        row.urls.push(result.preview_url || result.url)
      } catch (error: any) {
        message.error(error?.message || `${file.name} 上传失败`)
      }
    }
  } finally {
    row.uploading = false
  }
}

// 新增时先给一行空的，省得用户还要先点「添加」
if (!props.items.length) add()
</script>

<style scoped>
.checkin-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.checkin-card {
  padding: 10px 12px 12px;
  background: #f8f9fc;
  border: 1px solid #e9ecf3;
  border-radius: 10px;
}

.checkin-head {
  display: flex;
  /* 景点下面可能多一行定位提示，顶部对齐才不会把日期框和删除按钮拽到中间 */
  align-items: flex-start;
  gap: 8px;
}

.spot-field {
  flex: 1;
  min-width: 0;
}

.spot-input {
  width: 100%;
}

.spot-tip {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: #9aa6b6;
}

.spot-tip.ok {
  color: #2f7d32;
}

.spot-tip.miss {
  color: #b45309;
}

.poi-option {
  display: flex;
  flex-direction: column;
  padding: 2px 0;
  line-height: 1.35;
}

.poi-name {
  font-size: 13px;
  color: #1f2d3d;
}

.poi-addr {
  font-size: 11px;
  color: #8c9bab;
}

.time-input {
  width: 168px;
  flex-shrink: 0;
}

.image-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.thumb,
.thumb-add {
  position: relative;
  width: 64px;
  height: 64px;
  border-radius: 8px;
  overflow: hidden;
}

.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.thumb-del {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  padding: 0;
  font-size: 13px;
  line-height: 1;
  color: #fff;
  background: rgba(0, 0, 0, 0.55);
  border: none;
  border-radius: 50%;
  cursor: pointer;
}

.thumb-add {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  line-height: 1.3;
  color: #8c9bab;
  text-align: center;
  background: #fff;
  border: 1px dashed #d6dbe6;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s;
}

.thumb-add:hover {
  color: #1890ff;
  border-color: #1890ff;
}

.thumb-add.busy {
  cursor: default;
  color: #1890ff;
  border-color: #1890ff;
}

.editor-hint {
  margin: 0;
  font-size: 12px;
  color: #9aa6b6;
  line-height: 1.6;
}

.oss-missing {
  margin: 0;
  padding: 8px 10px;
  font-size: 12px;
  color: #b45309;
  background: #fffbe6;
  border: 1px solid #ffe58f;
  border-radius: 8px;
}

.oss-missing a {
  color: #d46b08;
  font-weight: 500;
}

@media (max-width: 520px) {
  .checkin-head {
    flex-wrap: wrap;
  }

  .time-input {
    width: 100%;
  }
}
</style>
