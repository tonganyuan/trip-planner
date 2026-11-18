import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '@/services/token'

// 路由独立成文件：main.ts 只管挂载，http 层的 401 回调也能安全拿到 router
// （router 不再反向依赖任何 service，避免循环引用）
const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'Home',
      component: () => import('@/views/Home.vue'),
      // 门户页不设 requiresAuth：天气和功能列表是公开的，
      // 真正的权限校验发生在"点某个功能"的那一刻
      meta: { title: '智能旅行助手' }
    },
    {
      path: '/plan',
      name: 'Plan',
      component: () => import('@/views/Plan.vue'),
      meta: { requiresAuth: true, title: '规划新行程' }
    },
    {
      path: '/family',
      name: 'Family',
      component: () => import('@/views/Family.vue'),
      meta: { requiresAuth: true, title: '家庭成员' }
    },
    {
      path: '/settings/model',
      name: 'ModelSettings',
      component: () => import('@/views/ModelSettings.vue'),
      meta: { requiresAuth: true, title: '模型设置' }
    },
    {
      path: '/settings/oss',
      name: 'OssSettings',
      component: () => import('@/views/OssSettings.vue'),
      meta: { requiresAuth: true, title: '对象存储' }
    },
    {
      path: '/history',
      name: 'History',
      component: () => import('@/views/History.vue'),
      meta: { requiresAuth: true, title: '家庭行程' }
    },
    {
      path: '/footprint',
      name: 'Footprint',
      component: () => import('@/views/Footprint.vue'),
      meta: { requiresAuth: true, title: '我的足迹' }
    },
    {
      path: '/result',
      name: 'Result',
      component: () => import('@/views/Result.vue'),
      // 行程详情里有个人行程，必须登录后才能看
      meta: { requiresAuth: true, title: '行程详情' }
    },
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login.vue'),
      meta: { guestOnly: true, title: '登录' }
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/'
    }
  ],
  // 切页面回到顶部，否则从长行程页返回首页会停在半截
  scrollBehavior: () => ({ top: 0 })
})

router.beforeEach((to) => {
  const authed = !!getToken()

  if (to.meta.requiresAuth && !authed) {
    // 带上原地址，登录成功后能回到用户本来想看的那一页
    return { name: 'Login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && authed) {
    return { name: 'Home' }
  }
  return true
})

router.afterEach((to) => {
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} · 胖子的智能旅行助手` : '胖子的智能旅行助手'
})

export default router
