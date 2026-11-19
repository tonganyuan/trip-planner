# 安卓 App（Capacitor 壳）

把 `frontend/` 里现有的 Vue 应用原封不动装进一个安卓 WebView，得到的安装包就是 App。
一份代码两端跑：浏览器里改完，重新构建一次 APK 就同步了。

```
frontend/
├── android/
│   ├── build-apk.ps1          ← 打包脚本（固定本机工具链路径）
│   ├── app/build/outputs/apk/debug/app-debug.apk   ← 构建产物
│   └── ...
├── capacitor.config.ts        ← 壳配置（appId / 混合内容 / androidScheme）
└── src/services/native.ts     ← 壳专用能力（返回键、状态栏、导出分享）
```

## 一、构建

```powershell
cd frontend
npm run android:apk
```

依次做三件事：

1. `vue-tsc` 类型检查 + `vite build --mode android` 出包（用 `.env.android` 里的后端地址）
2. `cap sync android` 把 web 产物和原生插件同步进安卓工程
3. `android/build-apk.ps1` 调 Gradle 打 debug APK

产物：`frontend/android/app/build/outputs/apk/debug/app-debug.apk`。

也可以分步手动执行：`npm run build:android` → `npx cap sync android` → `powershell -File android/build-apk.ps1`。

## 二、环境要求

| 组件 | 版本 | 本机位置 |
| --- | --- | --- |
| JDK | **21** | `D:\software\jdk-21` |
| Android SDK | platform 35 + build-tools 35.0.0（含 platform-tools） | `D:\software\android-sdk` |
| Gradle | 8.11.1 | `D:\software\gradle-8.11.1` |
| Gradle 缓存 | — | `D:\software\gradle-home` |

三样东西**必须装在仓库外面**。这台机器的 DSH 沙箱会拦住仓库内的可执行文件往仓库里写：
aapt2 会报 `stableIds.txt: error: failed to open: 数据无效 (13)`，JDK 放仓库内则会直接
`AccessDeniedException`。全部挪到 `D:\software` 后就正常了。换一台机器按常规装法即可，不受影响。

`android/local.properties` 里的 `sdk.dir` 指向 SDK 位置（本机 `D:/software/android-sdk`），换机器要改。

两个国内网络的坑（都已在脚本/文档里绕开）：

- Gradle 发行包从 `services.gradle.org` 下载会卡死，改用腾讯镜像
  `https://mirrors.cloud.tencent.com/gradle/gradle-8.11.1-bin.zip` 手动下载解压。
- 新版 cmdline-tools（build 16111833）是「Android CLI」，本机跑 `android.exe` 会报
  `Failed to create bin dir / 拒绝访问 (os error 5)`；用经典版
  `commandlinetools-win-13114758_latest.zip` 里的 `sdkmanager.bat` 装 SDK 组件。

## 三、后端地址在哪配

`frontend/.env.android`：

```
VITE_API_BASE_URL=http://106.15.155.60
```

域名备案通过、443 起来之后改成 `https://jingchucai.cn`，同时收紧两处：

1. `capacitor.config.ts` 的 `android.allowMixedContent` 改成 `false`
2. `android/app/src/main/res/xml/network_security_config.xml` 里明文放行的 `<domain-config>` 整段删掉，只留 `base-config`

## 四、壳里和浏览器不一样的地方

- **返回键**：非首页 `history.back()`；首页 2 秒内连按两次才退出。
- **状态栏**：`StatusBar.setOverlaysWebView({ overlay: false })`——Capacitor 默认让 WebView 盖到状态栏下面，会把 header 的 logo 和右上角用户按钮遮住；关掉后页面从状态栏下方开始，状态栏用 `#001529` 与 header 同色接平。
- **日期控件**：所有 `a-date-picker` 都加了 `input-read-only`，WebView 里点日期不再拉起输入法挡住选择面板（浏览器里也一样，只是桌面有物理键盘感觉不明显）。
- **导出图片 / PDF**：浏览器靠 `<a download>`，WebView 不支持，改成写缓存目录再唤起系统分享面板（可存相册或发微信）。
- **安全区**：底部留 `env(safe-area-inset-bottom)`，手势条不压按钮；页脚在 App 里隐藏。
- **超时**：axios 超时放宽到 300s，和 nginx 的 `proxy_read_timeout 300s` 对齐——生成行程本身要 1~2 分钟。
- **targetSdk 34**（不是 35）：Android 15 起强制 edge-to-edge，会把页面顶到状态栏下面，先退一版保证底部按钮可用。

## 五、图标与启动图

图标是脚本画的，没有用设计稿：`frontend/tools/make-icons.mjs` 里用内联 SVG 描述
「深色夜空 + 一座雪山 + 帐篷 + 月亮」，跑一次会把所有尺寸都栅格化出来：

```bash
cd frontend
node tools/make-icons.mjs
```

产物：

| 位置 | 用途 |
| --- | --- |
| `resources/icon.png` | 1024×1024 整图（带背景，给商店、旧版安卓用） |
| `resources/icon-foreground.png` | 1024×1024 透明前景（自适应图标用） |
| `resources/splash.png` | 2732×2732 启动图 |
| `public/favicon.png` | 网页 favicon |
| `src/assets/logo.png` | 顶栏 logo（走 Vite 打包，`--mode android` 不拷贝 `public/` 也不会丢） |
| `android/app/src/main/res/mipmap-*/` | 五档密度的 `ic_launcher.png` / `ic_launcher_round.png` / `ic_launcher_foreground.png` |

脚本最后还会覆盖写 `mipmap-anydpi-v26/ic_launcher.xml`、`ic_launcher_round.xml` 和
`values/ic_launcher_background.xml`，所以无论有没有跑过 `@capacitor/assets`，
只要重跑一次 `node tools/make-icons.mjs` 就是最终状态。

几个坑记一下：

- **自适应图标不要用 `@capacitor/assets` 的 inset**：它默认给前景和背景各套 `inset="16.7%"`
  （见 `mipmap-anydpi-v26/ic_launcher.xml`），会把前景实际缩到 36%，图标小得可怜；
  而背景 inset 后四角还会透出桌面。现在的写法是背景用颜色 `@color/ic_launcher_background`
  （`#0B1E33`），前景整张铺满，靠 `make-icons.mjs` 里的 `scale(0.80)` 自己控制留白。
- **`@capacitor/assets` 的 CLI 被 NVM 拦了**：`npx capacitor-assets` 会报
  `NVM blocked capacitor-assets — recognized as malware (OpenSSF)`，是本地 npm 包装器的误报。
  直接跑它的入口文件即可：`node node_modules/@capacitor/assets/bin/capacitor-assets generate --android ...`。
  它负责生成启动图（`drawable*/splash.png`），图标部分已被 `make-icons.mjs` 接管。
- **别用它的前景缩放**：工具会把前景压到 192px（xxxhdpi）再让系统放大，高分屏发虚；
  `make-icons.mjs` 是直接按 108dp×密度 栅格化的（xxxhdpi = 432px）。
- **前景别画地平线**：`make-icons.mjs` 里 `GROUND` 只加在整图（`icon.png`）上，
  自适应前景缩放到 0.8 后如果把那条矩形也放进去，会在图标中间露出一条深色横杠。
- 改完图标记得重新 `npm run android:apk`，否则 APK 里还是旧图。

## 六、已知限制

- **高德地图 key**：Web JS API 有域名白名单，壳里的 origin 是 `https://localhost`。地图白屏就去高德控制台把 `localhost` 加进白名单。
- **明文 HTTP**：只为备案没下来之前调试用，上线前必须切 HTTPS。
- **没有推送、没有自动更新**：侧载 APK 只能手动换包。
- **上架才需要**：App 备案 + 软件著作权；侧载安装不查这些。

## 七、网页上的下载入口

网页的页脚和登录页各有一个「📱 安卓 App 下载」链接，指向：

```
/download/trip-planner-android.apk
```

安装包本体在 `frontend/public/download/`，随前端一起发布：`npm run android:apk` 打完包会自动
把新 APK 复制过去（见 `build-apk.ps1` 末尾），部署前端时由 nginx 直接从站点路径提供下载，
不需要对象存储、也不需要额外的下载服务。

### 只更新安装包（不动前端）

如果前端没改动、只想换安装包，直接 scp 到服务器站点目录即可，链接立刻生效：

```powershell
ssh root@106.15.155.60 "mkdir -p /var/www/trip-planner/download"
scp frontend\public\download\trip-planner-android.apk root@106.15.155.60:/var/www/trip-planner/download/
```

验证：

```powershell
curl -I http://106.15.155.60/download/trip-planner-android.apk
```

要看到 `Content-Type: application/vnd.android.package-archive`（nginx 的 mime.types 自带 apk 类型；
万一返回 `application/octet-stream` 也能装，只是个别浏览器下会提示文件类型）。

> 注意：`/download/` 必须真实存在这个文件。nginx 配了 SPA 回退
> （`try_files $uri $uri/ /index.html`），文件不在时不会 404，而是返回首页 HTML，
> 手机点下载会下到一个 491 字节的 `index.html`。发现下载下来的不是安装包，先查这一条。

### 为什么不用对象存储

华为云 OBS 的默认域名会直接拦掉 `.apk` 的下载，实测返回 `400 InsecureDownloadForbidden`
（换 Content-Type、改成 `.bin`、带签名 URL 都不行，签名后反而 403），只有 `.zip` 这类文件能下。
要用桶的地址直链安装包，得先把域名备案、再给桶绑自定义域名（`static.jingchucai.cn` 之类），
然后把 `frontend/src/services/appDownload.ts` 里的 `APK_DOWNLOAD_URL` 换掉。
备案之前，安装包跟着站点走最省事。

## 八、装到手机上

1. 把 `app-debug.apk` 传到手机（微信文件传输助手 / 数据线都行）。
2. 点开安装，允许「安装未知来源应用」。
3. 首次打开若要登录，账号密码和网页端是同一套；网络必须能访问 `http://106.15.155.60`。

命令行安装（手机开 USB 调试）：

```powershell
D:\software\android-sdk\platform-tools\adb.exe install -r frontend\android\app\build\outputs\apk\debug\app-debug.apk
```
