// 生成 App 图标 / 启动图 + 安卓 mipmap 资源（深色夜空 + 卡通雪山）
// 用法：在 frontend 目录下 `node tools/make-icons.mjs`
import sharp from 'sharp'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const resDir = resolve(root, 'resources')
const androidRes = resolve(root, 'android', 'app', 'src', 'main', 'res')

const DEFS = `
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#0B1E33"/>
      <stop offset="0.62" stop-color="#123049"/>
      <stop offset="1" stop-color="#0A1A2A"/>
    </linearGradient>
    <linearGradient id="rock" x1="0.2" y1="0" x2="0.8" y2="1">
      <stop offset="0" stop-color="#5AD0BF"/>
      <stop offset="0.55" stop-color="#35A79C"/>
      <stop offset="1" stop-color="#1E7C79"/>
    </linearGradient>
    <linearGradient id="snow" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#FFFFFF"/>
      <stop offset="1" stop-color="#D3ECF5"/>
    </linearGradient>
    <linearGradient id="shade" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0.35" stop-color="#000000" stop-opacity="0"/>
      <stop offset="0.75" stop-color="#000000" stop-opacity="0.10"/>
      <stop offset="1" stop-color="#000000" stop-opacity="0.22"/>
    </linearGradient>
    <linearGradient id="ground" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#0C2033"/>
      <stop offset="1" stop-color="#07131F"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#3FA9B4" stop-opacity="0.42"/>
      <stop offset="0.55" stop-color="#2C7F97" stop-opacity="0.16"/>
      <stop offset="1" stop-color="#2C7F97" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="moonGlow" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0.45" stop-color="#FFE7B0" stop-opacity="0.30"/>
      <stop offset="0.72" stop-color="#FFE7B0" stop-opacity="0.10"/>
      <stop offset="1" stop-color="#FFE7B0" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="peak">
      <path d="M512 246 C556 330 640 520 716 660 C748 720 782 772 800 792 C806 800 800 806 790 806 L234 806 C224 806 218 800 224 792 C242 772 276 720 308 660 C384 520 468 330 512 246 Z"/>
    </clipPath>
    <clipPath id="tentClip">
      <path d="M120 806 L236 806 L178 700 Z"/>
    </clipPath>
  </defs>`

const ART = `
  <g>
    <!-- 夜空氛围 -->
    <circle cx="512" cy="470" r="330" fill="url(#glow)"/>
    <!-- 月亮 -->
    <circle cx="748" cy="288" r="150" fill="url(#moonGlow)"/>
    <circle cx="748" cy="288" r="58" fill="#FFE7B0"/>
    <!-- 星星 -->
    <g fill="#DCEFFF">
      <circle cx="214" cy="238" r="7" opacity="0.9"/>
      <circle cx="300" cy="168" r="5" opacity="0.75"/>
      <circle cx="392" cy="272" r="4" opacity="0.6"/>
      <circle cx="858" cy="470" r="6" opacity="0.8"/>
      <circle cx="824" cy="566" r="4" opacity="0.55"/>
      <circle cx="168" cy="392" r="4.5" opacity="0.6"/>
    </g>
    <g fill="#FFFFFF">
      <path d="M318 196 q4 18 20 22 q-16 4 -20 22 q-4 -18 -20 -22 q16 -4 20 -22 Z" opacity="0.92"/>
      <path d="M880 336 q3 13 15 16 q-12 3 -15 16 q-3 -13 -15 -16 q12 -3 15 -16 Z" opacity="0.7"/>
    </g>
    <!-- 飞鸟 -->
    <g fill="none" stroke="#CFE7F5" stroke-width="6" stroke-linecap="round" opacity="0.7">
      <path d="M596 402 q13 -13 26 0 q13 -13 26 0"/>
      <path d="M664 344 q10 -10 20 0 q10 -10 20 0" stroke-width="5" opacity="0.55"/>
    </g>
    <!-- 远山（右侧小峰，制造纵深） -->
    <path d="M762 806 L872 598 L962 806 Z" fill="#1B4A61"/>
    <path d="M872 598 L894 640 L880 634 L868 648 L854 632 L846 640 Z" fill="#C9E4EE" opacity="0.6"/>
    <!-- 主峰 -->
    <path d="M512 246 C556 330 640 520 716 660 C748 720 782 772 800 792 C806 800 800 806 790 806 L234 806 C224 806 218 800 224 792 C242 772 276 720 308 660 C384 520 468 330 512 246 Z" fill="url(#rock)"/>
    <g clip-path="url(#peak)">
      <rect x="0" y="200" width="1024" height="620" fill="url(#shade)"/>
      <!-- 雪线（卡通锯齿） -->
      <path d="M180 500 L268 500 L330 424 L392 500 L452 418 L512 492 L572 418 L632 500 L692 426 L754 500 L850 500 L850 60 L180 60 Z" fill="url(#snow)"/>
    </g>
    <!-- 帐篷 -->
    <path d="M120 806 L236 806 L178 700 Z" fill="#FF8B3E"/>
    <g clip-path="url(#tentClip)">
      <path d="M104 812 L178 812 L178 736 Z" fill="#E0702A" opacity="0.55"/>
    </g>
    <path d="M178 806 L198 806 L188 772 Z" fill="#8C3A12"/>
    <path d="M178 700 L178 646" stroke="#FFE0B0" stroke-width="8" stroke-linecap="round"/>
    <path d="M178 646 L222 660 L178 678 Z" fill="#FFD36E"/>
  </g>`

// 地平线只画在整图里；自适应前景不放，否则图层缩放到 0.8 后会露出一条矩形
const GROUND = `<rect x="0" y="806" width="1024" height="218" fill="url(#ground)"/>`

const svg = (body) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">${DEFS}${body}</svg>`

const svgFull = svg(`<rect width="1024" height="1024" fill="url(#sky)"/>${GROUND}${ART}`)
const svgForeground = svg(`<g transform="translate(512 512) scale(0.80) translate(-512 -512)">${ART}</g>`)

const render = (s, size) => sharp(Buffer.from(s), { density: 96 }).resize(size, size).png().toBuffer()

await mkdir(resDir, { recursive: true })
const fullPng = await render(svgFull, 1024)
await writeFile(resolve(resDir, 'icon.png'), fullPng)
await writeFile(resolve(resDir, 'icon-foreground.png'), await render(svgForeground, 1024))

// 启动图：深色底 + 居中图标
const splash = await sharp({ create: { width: 2732, height: 2732, channels: 4, background: '#0B1E33' } })
  .composite([{ input: await render(svgForeground, 1180), gravity: 'centre' }])
  .png()
  .toBuffer()
await writeFile(resolve(resDir, 'splash.png'), splash)

// 网页 favicon
await sharp(Buffer.from(svgFull), { density: 96 }).resize(256, 256).png().toFile(resolve(root, 'public', 'favicon.png'))
// 顶栏 logo 走 src/assets 让 Vite 打包（android 模式不拷贝 public/，用 /favicon.png 会 404）
await mkdir(resolve(root, 'src', 'assets'), { recursive: true })
await sharp(Buffer.from(svgFull), { density: 96 }).resize(128, 128).png().toFile(resolve(root, 'src', 'assets', 'logo.png'))

// 安卓 mipmap：直接按各密度栅格化，避免工具把前景压到 192px 再放大
const densities = { 'mipmap-mdpi': 1, 'mipmap-hdpi': 1.5, 'mipmap-xhdpi': 2, 'mipmap-xxhdpi': 3, 'mipmap-xxxhdpi': 4 }
const circle = (size) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}"><circle cx="${size / 2}" cy="${size / 2}" r="${size / 2}" fill="#fff"/></svg>`

for (const [dir, scale] of Object.entries(densities)) {
  const legacy = Math.round(48 * scale)
  const foreground = Math.round(108 * scale)
  const out = resolve(androidRes, dir)
  await mkdir(out, { recursive: true })

  const legacyPng = await render(svgFull, legacy)
  await writeFile(resolve(out, 'ic_launcher.png'), legacyPng)
  await writeFile(
    resolve(out, 'ic_launcher_round.png'),
    await sharp(legacyPng)
      .composite([{ input: Buffer.from(circle(legacy)), blend: 'dest-in' }])
      .png()
      .toBuffer(),
  )
  await writeFile(resolve(out, 'ic_launcher_foreground.png'), await render(svgForeground, foreground))
}

console.log('icons: resources/*.png, public/favicon.png, android mipmap-* 已生成')

// 自适应图标：背景用纯色、前景整张铺满。
// @capacitor/assets 默认会套 inset="16.7%"，把前景缩到 36% 且背景四角透出，这里覆盖掉。
const adaptiveXml = `<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/ic_launcher_background" />
    <foreground android:drawable="@mipmap/ic_launcher_foreground" />
</adaptive-icon>
`
for (const file of ['ic_launcher.xml', 'ic_launcher_round.xml']) {
  await writeFile(resolve(androidRes, 'mipmap-anydpi-v26', file), adaptiveXml)
}
await mkdir(resolve(androidRes, 'values'), { recursive: true })
await writeFile(
  resolve(androidRes, 'values', 'ic_launcher_background.xml'),
  `<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="ic_launcher_background">#0B1E33</color>
</resources>
`,
)
console.log('adaptive-icon xml 已写入（无 inset）')
