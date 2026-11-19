// 通用下载器：node tools/android/dl.mjs <url> <outFile>
// 走 node 的 TLS 栈（本机 schannel 的 curl/PowerShell 会报 SEC_E_NO_CREDENTIALS）
import { createWriteStream } from 'node:fs'
import { mkdir } from 'node:fs/promises'
import { Readable } from 'node:stream'
import { pipeline } from 'node:stream/promises'
import { dirname } from 'node:path'

const [, , url, out] = process.argv
if (!url || !out) {
  console.error('usage: node tools/android/dl.mjs <url> <outFile>')
  process.exit(2)
}
await mkdir(dirname(out), { recursive: true })
const res = await fetch(url)
if (!res.ok || !res.body) {
  console.error(`HTTP ${res.status} for ${url}`)
  process.exit(1)
}
const total = Number(res.headers.get('content-length') || 0)
let seen = 0
const src = Readable.fromWeb(res.body)
src.on('data', (chunk) => {
  seen += chunk.length
  if (total) process.stdout.write(`\r${((seen / total) * 100).toFixed(1)}% ${(seen / 1048576).toFixed(1)}MB`)
})
await pipeline(src, createWriteStream(out))
console.log(`\nsaved ${out} ${(seen / 1048576).toFixed(1)}MB`)
