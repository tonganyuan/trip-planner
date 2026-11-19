import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  build: {
    // 安卓壳（--mode android）里用不到 public/ 下的静态资源：
    // 那张 APK 本身就是 5MB，复制进 assets 只会让安装包白白翻一倍
    copyPublicDir: mode !== 'android'
  },
  server: {
    port: 5173,
    proxy: {
      // 用 127.0.0.1 而不是 localhost：Windows 上 localhost 会优先解析成 IPv6 ::1，
      // 而 uvicorn 默认只监听 IPv4，dev 环境会一直报 ECONNREFUSED / 502
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
}))
