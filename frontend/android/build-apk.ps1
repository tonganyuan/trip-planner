# 打包安卓 App（debug APK）
#
# 前置：
#   1. JDK 21、Android SDK、Gradle 都装在仓库外面（这台机器是 D:\software）。
#      DSH 的沙箱不让仓库内的可执行文件往仓库里写，工具链放仓库外最省事。
#   2. 先 npm run build:android && npx cap sync android（npm run android:apk 会自动做）。
#
# 用法：npm run android:apk

$ErrorActionPreference = 'Stop'

$jdkHome = 'D:\software\jdk-21'
$sdkHome = 'D:\software\android-sdk'
$gradleHome = 'D:\software\gradle-home'
$gradleBat = 'D:\software\gradle-8.11.1\bin\gradle.bat'

foreach ($p in @($jdkHome, $sdkHome, $gradleHome, $gradleBat)) {
    if (-not (Test-Path $p)) { throw "缺少打包依赖：$p" }
}

$env:JAVA_HOME = $jdkHome
$env:ANDROID_HOME = $sdkHome
$env:ANDROID_SDK_ROOT = $sdkHome
$env:GRADLE_USER_HOME = $gradleHome

Push-Location $PSScriptRoot
try {
    & $gradleBat assembleDebug --no-daemon --console=plain
    if ($LASTEXITCODE -ne 0) { throw "Gradle 构建失败（exit $LASTEXITCODE）" }
    $apk = Join-Path $PSScriptRoot 'app\build\outputs\apk\debug\app-debug.apk'
    if (Test-Path $apk) {
        $size = [math]::Round((Get-Item $apk).Length / 1MB, 2)
        Write-Output "APK 已生成：$apk（$size MB）"

        # 同步一份到前端的下载目录：网页上的「安卓 App 下载」指向它，
        # 重新部署前端（npm run build + deploy.sh）之后才会生效
        $downloadDir = Join-Path $PSScriptRoot '..\public\download'
        New-Item -ItemType Directory -Force $downloadDir | Out-Null
        Copy-Item $apk (Join-Path $downloadDir 'trip-planner-android.apk') -Force
        Write-Output '已同步到前端下载目录：frontend/public/download/trip-planner-android.apk'
    }
} finally {
    Pop-Location
}
