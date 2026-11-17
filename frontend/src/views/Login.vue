<template>
  <div class="login-page">
    <div class="bg-decoration">
      <div class="circle circle-1"></div>
      <div class="circle circle-2"></div>
      <div class="circle circle-3"></div>
    </div>

    <div class="login-card">
      <!-- 左侧品牌区：桌面端显示，手机端隐藏 -->
      <aside class="brand-panel">
        <div class="brand-badge">✈️</div>
        <h1 class="brand-title">胖子的智能旅行助手</h1>
        <p class="brand-desc">登录后，行程和去过的城市都会跟着账号走</p>
        <ul class="brand-points">
          <li><span class="dot"></span>AI 按天排好景点、餐饮与住宿</li>
          <li><span class="dot"></span>足迹地图点亮每一座去过的城市</li>
          <li><span class="dot"></span>手机、电脑打开都是同一份记录</li>
        </ul>
      </aside>

      <!-- 右侧表单区 -->
      <section class="form-panel">
        <div class="form-head">
          <h2 class="form-title">{{ isRegister ? '创建账号' : '登录' }}</h2>
          <p class="form-subtitle">
            {{ isRegister ? '注册后立即进入助手' : '用账号继续你的旅行计划' }}
          </p>
        </div>

        <div v-if="allowRegister" class="mode-switch">
          <button
            type="button"
            class="mode-item"
            :class="{ active: mode === 'login' }"
            @click="switchMode('login')"
          >
            登录
          </button>
          <button
            type="button"
            class="mode-item"
            :class="{ active: mode === 'register' }"
            @click="switchMode('register')"
          >
            注册
          </button>
        </div>

        <a-form :model="form" layout="vertical" @finish="handleSubmit">
          <a-form-item
            name="username"
            :rules="[{ required: true, message: '请输入用户名' }, { min: 3, message: '至少 3 个字符' }]"
          >
            <template #label><span class="field-label">用户名</span></template>
            <a-input
              v-model:value="form.username"
              size="large"
              placeholder="用户名或邮箱"
              autocomplete="username"
              allow-clear
            >
              <template #prefix><span class="field-icon">👤</span></template>
            </a-input>
          </a-form-item>

          <a-form-item v-if="isRegister" name="display_name">
            <template #label><span class="field-label">昵称（可选）</span></template>
            <a-input
              v-model:value="form.display_name"
              size="large"
              placeholder="页面上怎么称呼你"
              :maxlength="32"
              allow-clear
            >
              <template #prefix><span class="field-icon">🏷️</span></template>
            </a-input>
          </a-form-item>

          <a-form-item
            name="password"
            :rules="[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少 6 位' }
            ]"
          >
            <template #label><span class="field-label">密码</span></template>
            <a-input-password
              v-model:value="form.password"
              size="large"
              placeholder="至少 6 位"
              :autocomplete="isRegister ? 'new-password' : 'current-password'"
            >
              <template #prefix><span class="field-icon">🔒</span></template>
            </a-input-password>
          </a-form-item>

          <a-form-item
            v-if="isRegister"
            name="confirm"
            :rules="[{ required: true, message: '请再输入一次密码' }, { validator: validateConfirm }]"
          >
            <template #label><span class="field-label">确认密码</span></template>
            <a-input-password
              v-model:value="form.confirm"
              size="large"
              placeholder="再输一次"
              autocomplete="new-password"
            >
              <template #prefix><span class="field-icon">🔐</span></template>
            </a-input-password>
          </a-form-item>

          <a-button
            type="primary"
            html-type="submit"
            size="large"
            block
            class="submit-btn"
            :loading="submitting"
          >
            {{ isRegister ? '注册并登录' : '登录' }}
          </a-button>
        </a-form>

        <p class="form-foot">
          <span v-if="isRegister">已有账号？</span>
          <span v-else-if="allowRegister">还没有账号？</span>
          <span v-else>本站未开放注册</span>
          <a v-if="allowRegister" class="foot-link" @click="switchMode(isRegister ? 'login' : 'register')">
            {{ isRegister ? '去登录' : '去注册' }}
          </a>
        </p>

        <p class="back-home">
          <router-link to="/">← 先随便看看，不登录也行</router-link>
        </p>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { useAuth } from '@/composables/useAuth'
import { extractError, fetchAuthStatus } from '@/services/auth'

const router = useRouter()
const route = useRoute()
const { login, register } = useAuth()

const mode = ref<'login' | 'register'>('login')
const submitting = ref(false)
const allowRegister = ref(true)

const isRegister = computed(() => mode.value === 'register' && allowRegister.value)

const form = reactive({
  username: '',
  display_name: '',
  password: '',
  confirm: ''
})

function switchMode(next: 'login' | 'register') {
  if (next === mode.value) return
  mode.value = next
  form.password = ''
  form.confirm = ''
}

function validateConfirm(_rule: unknown, value: string) {
  if (!value) return Promise.reject(new Error('请再输入一次密码'))
  if (value !== form.password) return Promise.reject(new Error('两次输入的密码不一致'))
  return Promise.resolve()
}

/** 只接受站内路径，避免 ?redirect=https://坏事 这种开放重定向 */
function safeRedirect(input: unknown): string {
  if (typeof input !== 'string') return '/'
  if (!input.startsWith('/') || input.startsWith('//')) return '/'
  return input
}

async function handleSubmit() {
  if (submitting.value) return
  submitting.value = true
  try {
    if (isRegister.value) {
      await register(form.username.trim(), form.password, form.display_name.trim())
      message.success('注册成功，开始规划吧')
    } else {
      await login(form.username.trim(), form.password)
      message.success('登录成功')
    }
    router.replace(safeRedirect(route.query.redirect))
  } catch (error: any) {
    message.error(extractError(error, isRegister.value ? '注册失败' : '登录失败'))
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    const status = await fetchAuthStatus()
    allowRegister.value = status.allow_register
    // 一个账号都没有且开放注册时，默认停在注册页，少点一次
    if (status.allow_register && status.has_users === 0) {
      mode.value = 'register'
    }
  } catch {
    // 后端没起来时也要能看见表单，登录时的错误提示更具体
  }
})
</script>

<style scoped>
.login-page {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 200px);
  padding: 24px;
  overflow: hidden;
}

.bg-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.circle {
  position: absolute;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(24, 144, 255, 0.12), rgba(114, 46, 209, 0.08));
}

.circle-1 {
  width: 420px;
  height: 420px;
  top: -160px;
  right: -120px;
}

.circle-2 {
  width: 260px;
  height: 260px;
  bottom: -110px;
  left: -80px;
}

.circle-3 {
  width: 120px;
  height: 120px;
  top: 42%;
  left: 6%;
  opacity: 0.7;
}

.login-card {
  position: relative;
  z-index: 1;
  display: flex;
  width: 100%;
  max-width: 880px;
  background: #fff;
  border-radius: 18px;
  box-shadow: 0 18px 48px rgba(15, 45, 90, 0.12);
  overflow: hidden;
}

.brand-panel {
  flex: 0 0 45%;
  padding: 44px 36px;
  color: #fff;
  background: linear-gradient(150deg, #1890ff 0%, #2f54eb 60%, #722ed1 100%);
}

.brand-badge {
  font-size: 30px;
  line-height: 1;
  margin-bottom: 18px;
}

.brand-title {
  margin: 0 0 12px;
  font-size: 22px;
  font-weight: 500;
  line-height: 1.35;
  color: #fff;
}

.brand-desc {
  margin: 0 0 24px;
  font-size: 13px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.85);
}

.brand-points {
  margin: 0;
  padding: 0;
  list-style: none;
}

.brand-points li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 13px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.92);
}

.dot {
  flex: 0 0 6px;
  width: 6px;
  height: 6px;
  margin-top: 7px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.85);
}

.form-panel {
  flex: 1 1 auto;
  padding: 40px 44px 28px;
}

.form-title {
  margin: 0 0 6px;
  font-size: 20px;
  font-weight: 500;
  color: #1f2d3d;
}

.form-subtitle {
  margin: 0 0 20px;
  font-size: 13px;
  color: #8c9bab;
}

.mode-switch {
  display: inline-flex;
  padding: 3px;
  margin-bottom: 20px;
  background: #f2f5f9;
  border-radius: 10px;
}

.mode-item {
  padding: 7px 22px;
  font-size: 13px;
  color: #5a6b7f;
  background: transparent;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.mode-item.active {
  color: #1890ff;
  font-weight: 500;
  background: #fff;
  box-shadow: 0 2px 6px rgba(24, 144, 255, 0.18);
}

.field-label {
  font-size: 13px;
  color: #48586b;
}

.field-icon {
  font-size: 13px;
  opacity: 0.75;
}

.submit-btn {
  height: 44px;
  margin-top: 4px;
  font-size: 15px;
  border-radius: 10px;
}

.form-foot {
  margin: 18px 0 0;
  font-size: 13px;
  color: #8c9bab;
  text-align: center;
}

.foot-link {
  margin-left: 4px;
  color: #1890ff;
  cursor: pointer;
}

.back-home {
  margin: 10px 0 0;
  font-size: 12px;
  text-align: center;
}

.back-home a {
  color: #98a5b3;
}

.back-home a:hover {
  color: #1890ff;
}

/* ===== 移动端：品牌区收起成一条细横栏 ===== */
@media (max-width: 768px) {
  .login-page {
    min-height: auto;
    padding: 16px 12px 24px;
  }

  .login-card {
    flex-direction: column;
    border-radius: 14px;
  }

  .brand-panel {
    flex: none;
    padding: 20px 20px 18px;
  }

  .brand-badge {
    font-size: 22px;
    margin-bottom: 10px;
  }

  .brand-title {
    font-size: 17px;
    margin-bottom: 6px;
  }

  .brand-desc {
    margin-bottom: 0;
    font-size: 12px;
  }

  .brand-points {
    display: none;
  }

  .form-panel {
    padding: 22px 18px 18px;
  }

  .mode-switch {
    display: flex;
    width: 100%;
  }

  .mode-item {
    flex: 1;
  }
}
</style>
