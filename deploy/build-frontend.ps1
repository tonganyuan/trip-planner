#!/usr/bin/env pwsh
<#
.SYNOPSIS
  本地构建前端并打包 dist，供服务器端 deploy.sh --dist 使用。

.DESCRIPTION
  前端源码已并入本仓库（../frontend）。默认流程是服务器上直接构建：
      sudo bash deploy.sh --repo https://.../trip-planner.git
  只有服务器不打算装 Node 时，才用本脚本在本地构建再传产物（方案 B）。
  脚本会：
    1. 校验 frontend/.env（VITE_API_BASE_URL 必须为空 = 同源）
    2. npm run build
    3. 检查产物里没有写死的 http://localhost:8000
    4. 打成 dist.tar.gz（Windows 自带 tar）

.EXAMPLE
  powershell -File .\build-frontend.ps1
  # 产物：...\deploy\out\trip-dist.tar.gz
#>
param(
    # 前端已并入本仓库：deploy 的上一级就是项目根，frontend 在其下
    [string]$FrontendDir = (Join-Path (Split-Path -Parent $PSScriptRoot) "frontend"),
    [string]$OutFile = (Join-Path $PSScriptRoot "out\trip-dist.tar.gz")
)

$ErrorActionPreference = "Stop"

# 原生命令（npm / tar）往 stderr 写警告时，$ErrorActionPreference=Stop 会误判成异常，
# 所以这里临时降级为 Continue，只看退出码。
function Invoke-Native {
    param([string]$What, [scriptblock]$Action)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $Action
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($code -ne 0) { throw "$What 失败（exit $code）" }
}

if (-not (Test-Path (Join-Path $FrontendDir "package.json"))) {
    throw "找不到前端工程：$FrontendDir"
}

# 1. 同源校验：VITE_API_BASE_URL 必须留空
$envFile = Join-Path $FrontendDir ".env"
if (Test-Path $envFile) {
    $line = Get-Content $envFile | Where-Object { $_ -match '^\s*VITE_API_BASE_URL\s*=' } | Select-Object -First 1
    if ($line -and $line -notmatch '^\s*VITE_API_BASE_URL\s*=\s*$') {
        Write-Warning "frontend/.env 里 VITE_API_BASE_URL 不为空：$line"
        Write-Warning "服务器部署要同源，必须留空，否则浏览器会去连用户自己的 localhost:8000"
    }
} else {
    Write-Warning "找不到 $envFile，确认 VITE_API_BASE_URL 为空再继续"
}

# 2. 构建
Push-Location $FrontendDir
try {
    Write-Host "==> npm run build" -ForegroundColor Green
    Invoke-Native "npm run build" { npm run build }
}
finally {
    Pop-Location
}

$dist = Join-Path $FrontendDir "dist"
if (-not (Test-Path (Join-Path $dist "index.html"))) {
    throw "构建产物缺少 index.html：$dist"
}

# 3. 产物体检
$jsFiles = @(Get-ChildItem (Join-Path $dist "assets") -Filter *.js -ErrorAction SilentlyContinue)
if ($jsFiles.Count -eq 0) { throw "dist/assets 下没有 JS 文件，构建异常" }

$bad = $jsFiles | Select-String -Pattern "localhost:8000" -SimpleMatch -ErrorAction SilentlyContinue
if ($bad) {
    throw "产物里仍有 http://localhost:8000，说明用了旧源码或没走 import.meta.env，先修 src/services/http.ts"
}

$jsSize = ($jsFiles | Measure-Object -Property Length -Sum).Sum
$gzSize = [math]::Round($jsSize * 0.28)
Write-Host ("==> 产物 OK：{0} 个 JS，共 {1:N0} 字节" -f $jsFiles.Count, $jsSize) -ForegroundColor Green
Write-Host ("    线上开了 gzip，实际传输约 {0:N0} 字节" -f $gzSize) -ForegroundColor DarkGray

# 4. 打包
$outDir = Split-Path $OutFile -Parent
New-Item -ItemType Directory -Force $outDir | Out-Null
if (Test-Path $OutFile) { Remove-Item $OutFile -Force }

Push-Location $dist
try {
    Invoke-Native "tar 打包" { tar -czf $OutFile . }
}
finally {
    Pop-Location
}

if (-not (Test-Path $OutFile)) { throw "没有生成 $OutFile" }
$size = (Get-Item $OutFile).Length
Write-Host ("==> 已生成 {0} ({1:N0} 字节)" -f $OutFile, $size) -ForegroundColor Green
Write-Host ""
Write-Host "下一步：" -ForegroundColor Cyan
Write-Host "  scp `"$OutFile`" root@<服务器IP>:/root/trip-dist.tar.gz"
Write-Host "  ssh root@<服务器IP> `"sudo bash /opt/trip-planner/deploy/deploy.sh --dist /root/trip-dist.tar.gz`""
Write-Host ""
Write-Host "提示：如果服务器能装 Node，直接用 deploy.sh --repo 构建更省事（不用每次上传）。" -ForegroundColor DarkGray
