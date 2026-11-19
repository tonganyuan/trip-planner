import type { CapacitorConfig } from '@capacitor/cli'

/**
 * Capacitor 安卓壳配置。
 *
 * 注意 webDir 指向 Vite 的产物 dist：先 `npm run build:android` 再 `npx cap sync android`，
 * 壳里的页面才会更新。
 */
const config: CapacitorConfig = {
  appId: 'cn.jingchucai.tripplanner',
  appName: '胖子的智能旅行助手',
  webDir: 'dist',
  android: {
    // 调试期后端还是 http://106.15.155.60（域名备案未通过、443 未就绪），
    // WebView 页面本身是 https://localhost，跨协议请求会被当成混合内容拦掉，这里先放开。
    // 等 https 域名可用后，把 allowMixedContent 改回 false 并切到 VITE_API_BASE_URL=https://jingchucai.cn
    allowMixedContent: true,
    backgroundColor: '#001529'
  },
  server: {
    androidScheme: 'https'
  },
  plugins: {
    // 状态栏不要盖在页面上面，否则 header 会钻到时间/电量底下，右上角用户按钮看不见
    StatusBar: {
      overlaysWebView: false,
      style: 'DARK',
      backgroundColor: '#001529'
    }
  }
}

export default config
