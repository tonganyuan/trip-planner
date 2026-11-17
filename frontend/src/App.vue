<template>
  <div id="app">
    <a-layout class="app-layout">
      <a-layout-header class="app-header">
        <div class="app-brand" @click="goHome">
          <span class="brand-icon">🌍</span>
          <span class="brand-text">胖子的智能旅行助手</span>
        </div>

        <div class="app-actions">
          <template v-if="isLoggedIn">
            <a-dropdown placement="bottomRight">
              <div class="user-chip">
                <a-avatar :size="28" class="user-avatar">{{ initial }}</a-avatar>
                <span class="user-name">{{ displayName }}</span>
                <span class="user-caret">▾</span>
              </div>
              <template #overlay>
                <a-menu @click="handleMenuClick">
                  <a-menu-item key="home">新建行程</a-menu-item>
                  <a-menu-divider />
                  <a-menu-item key="logout">退出登录</a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </template>
          <a-button v-else class="login-entry" size="small" @click="goLogin">登录</a-button>
        </div>
      </a-layout-header>

      <a-layout-content class="app-content">
        <router-view />
      </a-layout-content>

      <a-layout-footer class="app-footer">
        胖子的智能旅行助手 ©2025 基于HelloAgents框架
      </a-layout-footer>
    </a-layout>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { useAuth } from '@/composables/useAuth'

const router = useRouter()
const { isLoggedIn, displayName, logout, ensureUser } = useAuth()

const initial = computed(() => (displayName.value || '?').slice(0, 1).toUpperCase())

function goHome() {
  router.push('/')
}

function goLogin() {
  const current = router.currentRoute.value
  router.push({
    name: 'Login',
    // 登录后回到当前页；本来就在首页就不带多余参数
    query: current.name && current.name !== 'Home' ? { redirect: current.fullPath } : {}
  })
}

async function handleMenuClick({ key }: { key: string | number }) {
  if (key === 'home') {
    router.push('/')
    return
  }
  if (key === 'logout') {
    await logout()
    message.success('已退出登录')
    // 当前页需要登录态时退回首页，否则停留在原页面会遇到满屏 401
    if (router.currentRoute.value.meta.requiresAuth) {
      router.replace('/')
    }
  }
}

onMounted(() => {
  // 刷新页面后用本地令牌换一次用户信息，令牌失效会自动清掉登录态
  ensureUser()
})
</script>

<style scoped>
#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial,
    'Noto Sans', sans-serif;
}

.app-layout {
  min-height: 100vh;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  padding: 0 50px;
  line-height: 64px;
  background: #001529;
}

.app-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 100%;
  color: #ffffff;
  font-size: 24px;
  font-weight: bold;
  cursor: pointer;
}

/* 长标题在窄屏下省略,不换行、不撑破头部 */
.brand-text {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.app-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 12px;
  margin-left: 16px;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 10px;
  line-height: 1;
  border-radius: 20px;
  cursor: pointer;
  transition: background 0.18s ease;
}

.user-chip:hover {
  background: rgba(255, 255, 255, 0.1);
}

.user-avatar {
  font-size: 13px;
  background: #1890ff;
}

.user-name {
  max-width: 120px;
  overflow: hidden;
  font-size: 14px;
  color: #ffffff;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.user-caret {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.6);
}

.login-entry {
  color: rgba(255, 255, 255, 0.88);
  background: transparent;
  border-color: rgba(255, 255, 255, 0.45);
}

.login-entry:hover {
  color: #ffffff;
  border-color: #1890ff;
}

.app-content {
  padding: 24px;
}

.app-footer {
  padding: 24px 50px;
  text-align: center;
}

/* ===== 移动端 ===== */
@media (max-width: 768px) {
  .app-header {
    height: 52px;
    padding: 0 16px;
    line-height: 52px;
  }

  .app-brand {
    gap: 6px;
    font-size: 16px;
  }

  .brand-icon {
    font-size: 18px;
  }

  /* 窄屏放不下长昵称，只留头像和下拉箭头 */
  .user-name {
    display: none;
  }

  .user-chip {
    gap: 4px;
    padding: 0 4px;
  }

  /* 首页/结果页自带边距,这里去掉外层留白,让内容铺满手机屏宽 */
  .app-content {
    padding: 0;
  }

  .app-footer {
    padding: 14px 12px;
    font-size: 12px;
    line-height: 1.6;
  }
}
</style>
