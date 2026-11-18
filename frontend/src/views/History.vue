<template>
  <div class="history-page">
    <div class="history-shell">
      <router-link to="/" class="back-link">← 返回首页</router-link>

      <div class="history-head">
        <div class="head-icon">🗂️</div>
        <div class="head-text">
          <h1>家庭行程</h1>
          <p>一家人共享的行程记录，点开即可查看完整方案</p>
        </div>
        <a-button type="primary" class="new-btn" @click="goPlan">＋ 规划新行程</a-button>
      </div>

      <a-spin :spinning="loading">
        <div v-if="items.length" class="trip-list">
          <a-card
            v-for="item in items"
            :key="item.id"
            class="trip-card"
            :bordered="false"
            hoverable
            @click="openTrip(item)"
          >
            <div class="trip-main">
              <div class="trip-icon">📍</div>
              <div class="trip-info">
                <div class="trip-title">{{ item.city }} · {{ tripDays(item) }}日游</div>
                <div class="trip-dates">{{ item.start_date }} 至 {{ item.end_date }}</div>
                <div class="trip-meta">
                  更新于 {{ formatTime(item.updated_at) }}
                  <span v-if="item.hit_count > 0" class="reuse-tag">被复用 {{ item.hit_count }} 次</span>
                  <span v-if="item.created_by === currentUserId" class="self-tag">我生成的</span>
                </div>
              </div>
            </div>
            <div class="trip-actions" @click.stop>
              <a-button type="link" size="small" @click="openTrip(item)">查看</a-button>
              <a-popconfirm
                title="删除后家庭成员将无法再查看这份方案。确定删除吗？"
                ok-text="确定"
                cancel-text="取消"
                @confirm="handleDelete(item)"
              >
                <a-button type="link" danger size="small">删除</a-button>
              </a-popconfirm>
            </div>
          </a-card>
        </div>

        <a-empty v-else-if="!loading" description="还没有行程记录">
          <template #extra>
            <a-button type="primary" @click="goPlan">去规划第一条行程</a-button>
          </template>
        </a-empty>
      </a-spin>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { deleteTrip, fetchTripHistory } from '@/services/api'
import { useAuth } from '@/composables/useAuth'
import type { TripHistoryItem } from '@/types'

const router = useRouter()
const { state } = useAuth()
const currentUserId = computed(() => state.user?.id ?? 0)

const loading = ref(false)
const items = ref<TripHistoryItem[]>([])

function tripDays(item: TripHistoryItem): number {
  const start = new Date(item.start_date)
  const end = new Date(item.end_date)
  const days = Math.round((end.getTime() - start.getTime()) / 86400000) + 1
  return days > 0 ? days : 1
}

function formatTime(value: string): string {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  })
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const res = await fetchTripHistory()
    items.value = res.items || []
  } catch (e: any) {
    message.error(e?.message || '加载行程历史失败')
  } finally {
    loading.value = false
  }
}

function openTrip(item: TripHistoryItem): void {
  router.push({ name: 'Result', query: { id: String(item.id) } })
}

function goPlan(): void {
  router.push('/plan')
}

async function handleDelete(item: TripHistoryItem): Promise<void> {
  try {
    await deleteTrip(item.id)
    message.success('已删除')
    await load()
  } catch (e: any) {
    message.error(e?.message || '删除失败')
  }
}

onMounted(load)
</script>

<style scoped>
.history-page {
  min-height: calc(100vh - 64px);
  margin: -24px;
  padding: 40px 20px 64px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.history-shell {
  max-width: 880px;
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

.history-head {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  color: #fff;
}

.head-icon {
  font-size: 46px;
  line-height: 1;
}

.head-text {
  flex: 1;
}

.head-text h1 {
  margin: 0;
  font-size: 30px;
}

.head-text p {
  margin: 6px 0 0;
  color: rgba(255, 255, 255, 0.85);
  font-size: 14px;
}

.trip-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.trip-card {
  border-radius: 14px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.1);
}

.trip-main {
  display: flex;
  align-items: center;
  gap: 14px;
}

.trip-icon {
  font-size: 30px;
}

.trip-info {
  flex: 1;
  min-width: 0;
}

.trip-title {
  font-size: 17px;
  font-weight: 600;
  color: #1f2d3d;
}

.trip-dates {
  margin-top: 4px;
  color: #5c6b82;
  font-size: 13px;
}

.trip-meta {
  margin-top: 6px;
  color: #97a2b3;
  font-size: 12px;
}

.reuse-tag,
.self-tag {
  margin-left: 8px;
  padding: 1px 7px;
  border-radius: 10px;
  background: rgba(24, 144, 255, 0.1);
  color: #1890ff;
}

.self-tag {
  background: rgba(82, 196, 26, 0.1);
  color: #52c41a;
}

.trip-actions {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid #f0f2f5;
  text-align: right;
}

@media (max-width: 768px) {
  .history-page {
    margin: 0;
    padding: 24px 14px 40px;
  }

  .head-icon {
    font-size: 36px;
  }

  .head-text h1 {
    font-size: 24px;
  }

  .history-head {
    flex-wrap: wrap;
  }

  .new-btn {
    width: 100%;
  }
}
</style>
