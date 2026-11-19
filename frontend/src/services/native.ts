import { Capacitor } from '@capacitor/core'
import { App as CapApp } from '@capacitor/app'
import { Directory, Filesystem } from '@capacitor/filesystem'
import { Share } from '@capacitor/share'
import { StatusBar, Style } from '@capacitor/status-bar'
import { message } from 'ant-design-vue'

/**
 * 安卓壳专用的能力封装。
 *
 * 所有函数都先判断 isNativeApp，Web 端调用时直接走原来的浏览器逻辑，
 * 保证同一份代码 web / apk 两用。
 */
export const isNativeApp = Capacitor.isNativePlatform()

let lastBackAt = 0

/** 初始化壳：状态栏配色 + 返回键（双击退出） */
export function initNativeShell(): void {
  if (!isNativeApp) return

  document.documentElement.classList.add('native-shell')

  // 默认状态栏是「盖在 WebView 上面」的(overlaysWebView=true)，
  // 会把页面顶部 24dp 连同 header 里的 logo/用户按钮一起遮住，这里关掉。
  StatusBar.setOverlaysWebView({ overlay: false }).catch(() => {})
  StatusBar.setStyle({ style: Style.Dark }).catch(() => {})
  StatusBar.setBackgroundColor({ color: '#001529' }).catch(() => {})

  CapApp.addListener('backButton', () => {
    // 首页再按一次才退出，避免误触直接把 App 关掉
    if (window.location.pathname !== '/' && window.history.length > 1) {
      window.history.back()
      return
    }
    const now = Date.now()
    if (now - lastBackAt < 2000) {
      CapApp.exitApp()
      return
    }
    lastBackAt = now
    message.info('再按一次退出')
  })
}

/** 把 dataURL 写到缓存目录并唤起系统分享面板（可存相册/发给微信） */
export async function saveDataUrl(dataUrl: string, filename: string): Promise<void> {
  const base64 = dataUrl.slice(dataUrl.indexOf(',') + 1)
  const result = await Filesystem.writeFile({
    path: filename,
    data: base64,
    directory: Directory.Cache,
    recursive: true
  })
  await Share.share({
    title: filename,
    files: [result.uri],
    dialogTitle: '保存或分享'
  })
}

/** Blob 版本（jsPDF 产出的 PDF 用这个） */
export async function saveBlob(blob: Blob, filename: string): Promise<void> {
  const dataUrl = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
  await saveDataUrl(dataUrl, filename)
}
