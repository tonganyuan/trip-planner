import { createApp } from 'vue'
import Antd from 'ant-design-vue'
import 'ant-design-vue/dist/reset.css'
import './styles/global.css'
import App from './App.vue'
import router from './router'
import { setUnauthorizedHandler } from './services/http'
import { resetAuthState } from './composables/useAuth'
import { initNativeShell } from './services/native'

// 任何接口返回 401 时，统一清登录态并送去登录页（带回来时要去的地址）。
// 放在这里注册而不是写进 http.ts，是为了让 http 层不依赖 router。
setUnauthorizedHandler((redirect) => {
  resetAuthState()
  if (router.currentRoute.value.name === 'Login') return
  router.replace({ name: 'Login', query: redirect ? { redirect } : {} })
})

const app = createApp(App)

app.use(router)
app.use(Antd)

app.mount('#app')

// 安卓壳里补上返回键、状态栏这些浏览器侧没有的能力；Web 端会直接跳过
initNativeShell()
