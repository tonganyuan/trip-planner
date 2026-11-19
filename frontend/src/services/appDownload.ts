/** 安卓安装包的下载地址与版本号。
 *
 * APK 跟着前端一起发布（frontend/public/download/），部署时随 dist 一起进服务器，
 * 由 nginx 直接从站点路径提供下载（`/download/trip-planner-android.apk`）。
 * 不走对象存储：华为云 OBS 的默认域名会拦掉 .apk（400 InsecureDownloadForbidden），
 * 想用桶的自定义域名又要求域名先备案通过。
 */
export const APK_VERSION = '1.0.1'
export const APK_SIZE_MB = '≈7'
export const APK_DOWNLOAD_URL = `${import.meta.env.BASE_URL}download/trip-planner-android.apk`
