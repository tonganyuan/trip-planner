// 预览安卓自适应图标（背景色 + 前景，圆形/圆角方形遮罩）
import sharp from 'sharp'

const res = 'android/app/src/main/res/mipmap-xxxhdpi'
const size = 432
const bg = '#0B1E33'

const fg = await sharp(`${res}/ic_launcher_foreground.png`).resize(size, size).png().toBuffer()
const base = await sharp({ create: { width: size, height: size, channels: 4, background: bg } }).png().toBuffer()
const flat = await sharp(base).composite([{ input: fg }]).png().toBuffer()

const circleMask = Buffer.from(
  `<svg width="${size}" height="${size}"><circle cx="${size / 2}" cy="${size / 2}" r="${size / 2}" fill="#fff"/></svg>`,
)
const round = await sharp(flat)
  .composite([{ input: await sharp(circleMask).png().toBuffer(), blend: 'dest-in' }])
  .png()
  .toBuffer()

const squircleMask = Buffer.from(
  `<svg width="${size}" height="${size}"><rect x="0" y="0" width="${size}" height="${size}" rx="${size * 0.22}" fill="#fff"/></svg>`,
)
const squircle = await sharp(flat)
  .composite([{ input: await sharp(squircleMask).png().toBuffer(), blend: 'dest-in' }])
  .png()
  .toBuffer()

await sharp(round).toFile('../.preview/adaptive-round.png')
await sharp(squircle).toFile('../.preview/adaptive-squircle.png')
await sharp(`${res}/ic_launcher.png`).toFile('../.preview/legacy.png')
console.log('previews written')
