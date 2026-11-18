/** 上传前的图片压缩。
 *
 * 手机直出的照片动辄 5~12MB，原样上传有两个问题：
 * 1. 慢——4G 下 3MB 得传十几秒，用户以为卡住了；
 * 2. 被拦——服务器上的反向代理（nginx 默认 client_max_body_size 只有 1m，
 *    花生壳/frp 这类内网穿透也常有请求体上限）会直接返回 413。
 *
 * 网页上看的缩略图最大也就几百像素，压到长边 1600、JPEG 0.86 后
 * 通常只剩 200~500KB，肉眼几乎看不出差别。
 */

const MAX_EDGE = 1600
const QUALITY = 0.86
/** 小于这个体积的原图没必要重编码，重压反而可能变大 */
const SKIP_BYTES = 400 * 1024

/** GIF 可能是动图，压成 JPEG 就只剩第一帧；SVG 是矢量，都不用碰 */
const PASS_TYPES = new Set(['image/gif', 'image/svg+xml'])

function loadBitmap(file: File): Promise<{ width: number; height: number; draw: (ctx: CanvasRenderingContext2D) => void }> {
  if (typeof createImageBitmap === 'function') {
    return createImageBitmap(file, { imageOrientation: 'from-image' }).then((bitmap) => ({
      width: bitmap.width,
      height: bitmap.height,
      draw: (ctx: CanvasRenderingContext2D) => ctx.drawImage(bitmap, 0, 0),
    }))
  }
  // Safari 14 及以下没有 createImageBitmap，退回 <img>
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      resolve({
        width: img.naturalWidth,
        height: img.naturalHeight,
        draw: (ctx: CanvasRenderingContext2D) => ctx.drawImage(img, 0, 0),
      })
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('图片解码失败'))
    }
    img.src = url
  })
}

function toBlob(canvas: HTMLCanvasElement): Promise<Blob | null> {
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', QUALITY))
}

/** 文件名换成 .jpg，后端按魔数嗅探类型，不看扩展名，但名字对得上更好排查 */
function renameToJpg(name: string): string {
  const base = name.replace(/\.[^./\\]+$/, '') || 'photo'
  return `${base}.jpg`
}

export async function compressImage(file: File): Promise<File> {
  if (PASS_TYPES.has(file.type) || file.size <= SKIP_BYTES) return file

  try {
    const source = await loadBitmap(file)
    const scale = Math.min(1, MAX_EDGE / Math.max(source.width, source.height))
    const width = Math.max(1, Math.round(source.width * scale))
    const height = Math.max(1, Math.round(source.height * scale))

    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')
    if (!ctx) return file
    ctx.imageSmoothingQuality = 'high'
    // JPEG 没有透明通道，PNG 截图压成 JPEG 后透明处会变黑，先铺白底
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, width, height)
    source.draw(ctx)

    const blob = await toBlob(canvas)
    // 压完反而更大（原图本来就窄且压缩率高）就保留原图
    if (!blob || blob.size >= file.size) return file
    return new File([blob], renameToJpg(file.name), { type: 'image/jpeg' })
  } catch {
    // 压缩只是优化，失败就传原图，别让用户传不了照片
    return file
  }
}
