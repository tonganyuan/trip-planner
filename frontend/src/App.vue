<template>
  <div id="app">
    <a-layout class="app-layout">
      <a-layout-header class="app-header">
        <div class="app-brand">
          <span class="brand-icon">🌍</span>
          <span class="brand-text">胖子的智能旅行助手</span>
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
}

/* 长标题在窄屏下省略,不换行、不撑破头部 */
.brand-text {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
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
