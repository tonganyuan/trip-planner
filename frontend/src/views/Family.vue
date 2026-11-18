<template>
  <div class="family-page">
    <div class="family-shell">
      <router-link to="/" class="back-link">← 返回首页</router-link>

      <div class="family-head">
        <div class="head-icon">👨‍👩‍👧</div>
        <div class="head-text">
          <h1>家庭成员</h1>
          <p>一家人共用一份行程与足迹记录</p>
        </div>
      </div>

      <!-- 家庭信息卡 -->
      <a-card class="info-card" :bordered="false" :loading="loading && !family">
        <template v-if="family">
          <div class="family-title-row">
            <div class="family-name-wrap">
              <template v-if="editingName">
                <a-input
                  v-model:value="draftName"
                  size="small"
                  :maxlength="32"
                  class="name-input"
                  @press-enter="saveName"
                />
                <a-button size="small" type="primary" @click="saveName">保存</a-button>
                <a-button size="small" type="text" @click="editingName = false">取消</a-button>
              </template>
              <template v-else>
                <h2 class="family-name">{{ family.name }}</h2>
                <a-button
                  v-if="family.is_owner"
                  type="link"
                  size="small"
                  class="rename-btn"
                  @click="startRename"
                >
                  改名
                </a-button>
              </template>
            </div>
            <a-tag color="blue">{{ family.member_count }} 位成员</a-tag>
          </div>

          <p class="share-note">
            💡 家庭成员登录的是各自账号，但看到的是同一份数据——
            任何一方添加的城市，全家人都能在足迹地图上看到。
          </p>

          <a-divider style="margin: 16px 0" />

          <div class="member-list">
            <div v-for="m in family.members" :key="m.id" class="member-row">
              <a-avatar class="member-avatar" :style="{ background: avatarColor(m.username) }">
                {{ (m.display_name || m.username).slice(0, 1).toUpperCase() }}
              </a-avatar>
              <div class="member-main">
                <div class="member-line">
                  <span class="member-name">{{ m.display_name }}</span>
                  <a-tag v-if="m.is_owner" color="orange" class="owner-tag">户主</a-tag>
                  <a-tag v-if="m.id === currentUserId" color="green" class="me-tag">我</a-tag>
                </div>
                <div class="member-sub">
                  @{{ m.username }} · 最近登录 {{ formatTime(m.last_login_at) }}
                </div>
              </div>
              <a-popconfirm
                v-if="family.is_owner && !m.is_owner"
                title="移出家庭后，对方账号仍可登录，但不再共享数据。确定吗？"
                ok-text="确定"
                cancel-text="取消"
                @confirm="handleRemove(m)"
              >
                <a-button type="link" danger size="small">移出</a-button>
              </a-popconfirm>
            </div>
          </div>
        </template>
      </a-card>

      <!-- 添加成员 -->
      <a-card class="add-card" title="添加家庭成员" :bordered="false">
        <p class="add-hint">
          为新成员创建一个独立账号（用户名 + 密码），加入后即可登录并共享数据。
          已有账号无法直接加入，避免把其他家庭的数据带过来。
        </p>
        <a-form :model="form" layout="vertical" @finish="handleAdd">
          <div class="form-grid">
            <a-form-item
              label="登录用户名"
              name="username"
              :rules="[
                { required: true, message: '请输入用户名' },
                { min: 3, message: '至少 3 个字符' }
              ]"
            >
              <a-input v-model:value="form.username" placeholder="如 mama123" :maxlength="64" allow-clear />
            </a-form-item>
            <a-form-item label="家庭内称呼" name="display_name">
              <a-input v-model:value="form.display_name" placeholder="如 妈妈" :maxlength="32" allow-clear />
            </a-form-item>
          </div>
          <div class="form-grid">
            <a-form-item
              label="密码"
              name="password"
              :rules="[
                { required: true, message: '请输入密码' },
                { min: 6, message: '密码至少 6 位' }
              ]"
            >
              <a-input-password v-model:value="form.password" placeholder="至少 6 位" autocomplete="new-password" />
            </a-form-item>
            <a-form-item
              label="确认密码"
              name="confirm"
              :rules="[{ required: true, message: '请再输入一次密码' }, { validator: validateConfirm }]"
            >
              <a-input-password v-model:value="form.confirm" placeholder="再输一次" autocomplete="new-password" />
            </a-form-item>
          </div>
          <a-button type="primary" html-type="submit" :loading="adding" class="add-btn">
            添加成员
          </a-button>
        </a-form>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { useAuth } from '@/composables/useAuth'
import { addFamilyMember, fetchFamily, removeFamilyMember, renameFamily } from '@/services/family'
import type { FamilyInfo, FamilyMember } from '@/types'

const { state } = useAuth()
const currentUserId = computed(() => state.user?.id ?? 0)

const loading = ref(false)
const adding = ref(false)
const family = ref<FamilyInfo | null>(null)

const editingName = ref(false)
const draftName = ref('')

const form = reactive({ username: '', password: '', confirm: '', display_name: '' })

function validateConfirm(_rule: unknown, value: string): Promise<void> {
  if (!value) return Promise.reject(new Error('请再输入一次密码'))
  if (value !== form.password) return Promise.reject(new Error('两次输入的密码不一致'))
  return Promise.resolve()
}

const avatarColors = ['#1890ff', '#52c41a', '#fa8c16', '#722ed1', '#eb2f96', '#13c2c2']

function avatarColor(username: string): string {
  const sum = [...username].reduce((acc, ch) => acc + ch.charCodeAt(0), 0)
  return avatarColors[sum % avatarColors.length]
}

function formatTime(value?: string | null): string {
  if (!value) return '尚未登录'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '尚未登录'
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  })
}

async function loadFamily(): Promise<void> {
  loading.value = true
  try {
    family.value = await fetchFamily()
  } catch (e: any) {
    message.error(e?.message || '加载家庭信息失败')
  } finally {
    loading.value = false
  }
}

function startRename(): void {
  draftName.value = family.value?.name || ''
  editingName.value = true
}

async function saveName(): Promise<void> {
  const name = draftName.value.trim()
  if (!name) {
    message.warning('家庭名称不能为空')
    return
  }
  if (name === family.value?.name) {
    editingName.value = false
    return
  }
  try {
    const res = await renameFamily(name)
    if (res.family) family.value = res.family
    editingName.value = false
    message.success('家庭名称已更新')
  } catch (e: any) {
    message.error(e?.message || '修改失败')
  }
}

async function handleAdd(): Promise<void> {
  adding.value = true
  try {
    const res = await addFamilyMember(
      form.username.trim(),
      form.password,
      form.display_name.trim()
    )
    if (res.family) family.value = res.family
    message.success(`已添加 ${res.member?.display_name || '成员'}，把账号密码告诉 TA 即可登录`)
    form.username = ''
    form.password = ''
    form.confirm = ''
    form.display_name = ''
  } catch (e: any) {
    message.error(e?.message || '添加成员失败')
  } finally {
    adding.value = false
  }
}

async function handleRemove(m: FamilyMember): Promise<void> {
  try {
    const res = await removeFamilyMember(m.id)
    if (res.family) family.value = res.family
    message.success('已移出家庭')
  } catch (e: any) {
    message.error(e?.message || '移除失败')
  }
}

onMounted(loadFamily)
</script>

<style scoped>
.family-page {
  min-height: calc(100vh - 64px);
  margin: -24px;
  padding: 40px 20px 64px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.family-shell {
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

.family-head {
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

.head-text h1 {
  margin: 0;
  font-size: 30px;
}

.head-text p {
  margin: 6px 0 0;
  color: rgba(255, 255, 255, 0.85);
  font-size: 14px;
}

.info-card,
.add-card {
  margin-bottom: 20px;
  border-radius: 14px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
}

.family-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.family-name-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.family-name {
  margin: 0;
  font-size: 20px;
}

.name-input {
  width: 200px;
}

.rename-btn {
  padding: 0 4px;
  font-size: 13px;
}

.share-note {
  margin: 10px 0 0;
  padding: 10px 14px;
  color: #4c5a72;
  font-size: 13px;
  line-height: 1.7;
  background: linear-gradient(135deg, rgba(24, 144, 255, 0.08), rgba(114, 46, 209, 0.06));
  border-radius: 8px;
}

.member-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.member-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 6px;
  border-radius: 8px;
}

.member-row:hover {
  background: #f7f9fc;
}

.member-avatar {
  flex: 0 0 auto;
  font-size: 14px;
}

.member-main {
  flex: 1;
  min-width: 0;
}

.member-line {
  display: flex;
  align-items: center;
  gap: 6px;
}

.member-name {
  font-size: 15px;
  font-weight: 600;
  color: #1f2d3d;
}

.owner-tag,
.me-tag {
  margin: 0;
  transform: scale(0.9);
  transform-origin: left center;
}

.member-sub {
  margin-top: 3px;
  color: #8c96a8;
  font-size: 12px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.add-hint {
  margin: 0 0 16px;
  color: #6b7689;
  font-size: 13px;
  line-height: 1.7;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.add-btn {
  min-width: 140px;
}

@media (max-width: 768px) {
  .family-page {
    margin: 0;
    padding: 24px 14px 40px;
  }

  .head-icon {
    font-size: 38px;
  }

  .head-text h1 {
    font-size: 24px;
  }

  .form-grid {
    grid-template-columns: 1fr;
    gap: 0;
  }

  .member-sub {
    white-space: normal;
  }
}
</style>
