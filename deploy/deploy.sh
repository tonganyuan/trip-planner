#!/usr/bin/env bash
#
# trip-planner 一键部署脚本
# 目标系统：Ubuntu 22.04 / 24.04、Debian 12（apt）
#
# 用法：
#   sudo bash deploy.sh [选项]
#
# 典型场景：
#   1) 首次部署：前后端都从 git 拉取，服务器上构建前端（推荐）
#        sudo bash deploy.sh --repo https://github.com/you/trip-planner.git \
#             --frontend-repo https://github.com/you/hello-agents.git \
#             --frontend-subdir code/chapter13/helloagents-trip-planner/frontend \
#             --domain trip.example.com --email you@example.com --tls --swap 2G
#   2) 前端在本地构建、上传产物（服务器不装 Node）：
#        sudo bash deploy.sh --dist /root/trip-dist.tar.gz \
#             --domain trip.example.com --email you@example.com --tls --swap 2G
#   3) 只更新后端代码：
#        sudo bash deploy.sh --repo https://...        # 或 --src 指向新代码目录
#   4) 只更新前端：
#        sudo bash deploy.sh --frontend-repo https://...   # 或 --dist /root/trip-dist.tar.gz
#
set -euo pipefail

APP_NAME="trip-planner"
APP_DIR="/opt/trip-planner"
WEB_ROOT="/var/www/trip-planner"
RUN_USER="www-data"
RUN_HOME="/var/lib/trip-planner"
PORT="8000"
DOMAIN="_"
EMAIL=""
SRC_DIR=""
REPO_URL=""
REPO_REF=""
DIST_PATH=""
FRONTEND_REPO=""
FRONTEND_REF="main"
FRONTEND_SUBDIR=""
FRONTEND_ENV=""
WEB_SRC="/opt/trip-planner-web"
NODE_VERSION="${NODE_VERSION:-20.18.3}"
NODE_MIRROR="${NODE_MIRROR:-https://npmmirror.com/mirrors/node}"
NPM_REGISTRY="${NPM_REGISTRY:-https://registry.npmmirror.com}"
DO_TLS=0
DO_UFW=0
SWAP_SIZE=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# git@github.com:you/repo.git -> https://github.com/you/repo.git
# 服务器上通常没配 SSH key，用户从 GitHub 页面复制的却是 SSH 地址，这里自动转换。
normalize_repo_url() {
  local url="$1"
  if [[ "${url}" =~ ^git@([^:]+):(.+)$ ]]; then
    printf 'https://%s/%s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
  else
    printf '%s\n' "${url}"
  fi
}

usage() {
  cat <<'EOF'
trip-planner 一键部署脚本（Ubuntu 22.04/24.04、Debian 12）

用法：
  sudo bash deploy.sh [选项]

示例：
  # 首次部署：前后端都从 git 拉，服务器上构建前端，顺带 HTTPS + 2G swap
  sudo bash deploy.sh --repo https://github.com/you/trip-planner.git \
       --frontend-repo https://github.com/you/hello-agents.git \
       --frontend-subdir code/chapter13/helloagents-trip-planner/frontend \
       --domain trip.example.com --email you@example.com --tls --swap 2G

  # 只更新后端代码
  sudo bash deploy.sh --repo https://github.com/you/trip-planner.git

  # 只更新前端（从 git 重新拉取源码并构建）
  sudo bash deploy.sh --frontend-repo https://github.com/you/hello-agents.git \
       --frontend-subdir code/chapter13/helloagents-trip-planner/frontend

  # 前端在本地 build 后只上传产物（服务器不装 Node）
  sudo bash deploy.sh --dist /root/trip-dist.tar.gz

选项：
  --src DIR           从本地目录同步源码到 /opt/trip-planner（rsync，会删除多余文件）
  --repo URL          后端源码 git 地址（私有库请先配好 HTTPS token 或 SSH key）
  --ref REF           后端仓库分支/标签（默认仓库默认分支）
  --frontend-repo URL 前端源码 git 地址；给了它就在服务器上装 Node 并构建
  --frontend-ref REF  前端仓库分支/标签（默认 main）
  --frontend-subdir P 前端在仓库里的相对路径（monorepo 必填，如 code/chapter13/.../frontend）
  --frontend-env FILE 前端构建用 .env（含 VITE_AMAP_WEB_JS_KEY 等；不填则用仓库里的 .env）
  --dist PATH         前端构建产物：dist.tar.gz / dist.tgz / dist.zip / dist 目录
  --domain NAME       站点域名；不填则用 "_"（直接 IP 访问）
  --email MAIL        certbot 证书通知邮箱（与 --tls 同时使用）
  --port N            后端监听端口（默认 8000，只监听 127.0.0.1）
  --tls               用 Let's Encrypt 申请证书并强制 HTTPS（需域名已解析到本机）
  --swap SIZE         创建 swap 文件（如 --swap 2G），2G 内存机器建议加
  --ufw               用 ufw 放行 22/80/443（云厂商安全组仍需单独放行）
  -h, --help          显示帮助

环境变量：NODE_VERSION（默认 20.18.3）、NODE_MIRROR、NPM_REGISTRY、PIP_INDEX_URL
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --src)             SRC_DIR="${2:-}";         shift 2 ;;
    --repo)            REPO_URL="${2:-}";        shift 2 ;;
    --ref)             REPO_REF="${2:-}";        shift 2 ;;
    --dist)            DIST_PATH="${2:-}";       shift 2 ;;
    --frontend-repo)   FRONTEND_REPO="${2:-}";   shift 2 ;;
    --frontend-ref)    FRONTEND_REF="${2:-}";    shift 2 ;;
    --frontend-subdir) FRONTEND_SUBDIR="${2:-}"; shift 2 ;;
    --frontend-env)    FRONTEND_ENV="${2:-}";    shift 2 ;;
    --domain)          DOMAIN="${2:-}";          shift 2 ;;
    --email)           EMAIL="${2:-}";           shift 2 ;;
    --port)            PORT="${2:-}";            shift 2 ;;
    --swap)            SWAP_SIZE="${2:-}";       shift 2 ;;
    --tls)             DO_TLS=1; shift ;;
    --ufw)             DO_UFW=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "未知参数：$1（用 --help 查看用法）" ;;
  esac
done

# ---------------------------------------------------------------- 0. 前置检查
[[ "${EUID}" -eq 0 ]] || die "需要 root 权限：sudo bash ${BASH_SOURCE[0]} ..."
# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-}" in
  ubuntu|debian) ;;
  *) die "本脚本只支持 Ubuntu/Debian，当前系统：${ID:-未知}" ;;
esac
command -v systemctl >/dev/null 2>&1 || die "没有 systemd，本脚本不适用（容器/其他发行版）"

# ---------------------------------------------------------------- 1. swap
if [[ -n "${SWAP_SIZE}" ]]; then
  if swapon --show 2>/dev/null | grep -q .; then
    warn "已存在 swap，跳过"
  else
    log "创建 ${SWAP_SIZE} swap"
    if ! fallocate -l "${SWAP_SIZE}" /swapfile 2>/dev/null; then
      dd if=/dev/zero of=/swapfile bs=1M count="$(echo "${SWAP_SIZE}" | tr -dc '0-9')" status=none
    fi
    chmod 600 /swapfile
    mkswap /swapfile >/dev/null
    swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    sysctl -qw vm.swappiness=10
  fi
fi

# ---------------------------------------------------------------- 2. 系统依赖
log "安装系统依赖"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold \
  ca-certificates curl rsync git unzip nginx \
  python3 python3-venv python3-pip >/dev/null

python3 -c 'import sys; assert sys.version_info[:2] >= (3, 10), sys.version' \
  || die "需要 Python 3.10+，当前：$(python3 -V 2>&1)"

install -d -m 755 "${APP_DIR}" "${WEB_ROOT}" "${RUN_HOME}"

# ---------------------------------------------------------------- 3. 源码
if [[ -n "${SRC_DIR}" ]]; then
  [[ -d "${SRC_DIR}" ]] || die "--src 目录不存在：${SRC_DIR}"
  log "同步源码 ${SRC_DIR} -> ${APP_DIR}"
  rsync -a --delete \
    --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
    --exclude='.idea' --exclude='.workbuddy' --exclude='*.log' \
    "${SRC_DIR}/" "${APP_DIR}/"
elif [[ -n "${REPO_URL}" ]]; then
  REPO_URL="$(normalize_repo_url "${REPO_URL}")"
  if [[ -d "${APP_DIR}/.git" ]]; then
    log "更新后端仓库 ${REPO_URL}"
    if git -C "${APP_DIR}" remote get-url origin >/dev/null 2>&1; then
      git -C "${APP_DIR}" remote set-url origin "${REPO_URL}"
    else
      git -C "${APP_DIR}" remote add origin "${REPO_URL}"
    fi
    if [[ -n "${REPO_REF}" ]]; then
      git -C "${APP_DIR}" fetch --depth 1 origin "${REPO_REF}"
    else
      git -C "${APP_DIR}" fetch --depth 1 origin
    fi
    git -C "${APP_DIR}" reset --hard FETCH_HEAD
  else
    log "克隆 ${REPO_URL}"
    rm -rf "${APP_DIR:?}"
    if [[ -n "${REPO_REF}" ]]; then
      git clone --depth 1 --branch "${REPO_REF}" "${REPO_URL}" "${APP_DIR}"
    else
      git clone --depth 1 "${REPO_URL}" "${APP_DIR}"
    fi
  fi
elif [[ ! -f "${APP_DIR}/requirements.txt" ]]; then
  die "没给 --src / --repo，且 ${APP_DIR} 里没有代码。请先把代码放上去或指定参数。"
else
  log "使用 ${APP_DIR} 中已有的代码"
fi

# ---------------------------------------------------------------- 4. Python 环境
VENV="${APP_DIR}/.venv"
PIP_INDEX="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"

if [[ ! -x "${VENV}/bin/python" ]]; then
  log "创建虚拟环境 ${VENV}"
  python3 -m venv "${VENV}"
fi
log "安装 Python 依赖（索引：${PIP_INDEX}）"
"${VENV}/bin/python" -m pip install -q --upgrade pip -i "${PIP_INDEX}"
"${VENV}/bin/pip" install -q -r "${APP_DIR}/requirements.txt" -i "${PIP_INDEX}"
# uv 装进 venv 后，app/services/amap_mcp.py:46 的 find_uvx() 能在 .venv/bin 里找到 uvx
"${VENV}/bin/pip" install -q uv -i "${PIP_INDEX}"

# ---------------------------------------------------------------- 5. uv 镜像 + 预热
# 高德 MCP 是 uvx 现拉现跑的；mcp 客户端只把 HOME/PATH 等白名单变量传给子进程，
# 所以镜像配置必须写在 $HOME/.config/uv/uv.toml 里，靠环境变量传不进去。
UV_CONF_DIR="${RUN_HOME}/.config/uv"
install -d -m 755 -o "${RUN_USER}" -g "${RUN_USER}" "${RUN_HOME}/.config" "${UV_CONF_DIR}"
cat > "${UV_CONF_DIR}/uv.toml" <<'EOF'
# 由 deploy.sh 生成：uvx 走国内镜像，避免首次启动 amap-mcp-server 时卡住
[[index]]
url = "https://pypi.tuna.tsinghua.edu.cn/simple"
default = true
EOF
chown "${RUN_USER}:${RUN_USER}" "${UV_CONF_DIR}/uv.toml"
chmod 644 "${UV_CONF_DIR}/uv.toml"

log "预热 uv 缓存（下载 amap-mcp-server，首次约 1~3 分钟）"
WARM_DIR="$(mktemp -d /tmp/trip-warm.XXXXXX)"
chmod 777 "${WARM_DIR}"
if sudo -u "${RUN_USER}" env HOME="${RUN_HOME}" "${VENV}/bin/uv" venv \
      --python "$(command -v python3)" "${WARM_DIR}/v" >/dev/null 2>&1; then
  sudo -u "${RUN_USER}" env HOME="${RUN_HOME}" "${VENV}/bin/uv" pip install -q \
    --python "${WARM_DIR}/v/bin/python" "amap-mcp-server" "pydantic<2.12" \
    || warn "uv 预热失败，首次调用高德 MCP 时会重新下载（可稍后手动重试）"
else
  warn "uv 预热环境创建失败，跳过预热"
fi
rm -rf "${WARM_DIR}"

# ---------------------------------------------------------------- 6. 权限与 .env
chown -R root:"${RUN_USER}" "${APP_DIR}" "${WEB_ROOT}"
chmod -R g+rX "${APP_DIR}"
chmod -R 755 "${WEB_ROOT}"

ENV_FILE="${APP_DIR}/.env"
ENV_CREATED=0
if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${SCRIPT_DIR}/env.production.example" "${ENV_FILE}"
  chown root:"${RUN_USER}" "${ENV_FILE}"
  chmod 640 "${ENV_FILE}"
  ENV_CREATED=1
  warn "已生成 ${ENV_FILE}（模板），请填入真实密钥后再重启服务"
fi
chown root:"${RUN_USER}" "${ENV_FILE}"
chmod 640 "${ENV_FILE}"
if [[ "${DOMAIN}" != "_" ]] && ! grep -q "${DOMAIN}" "${ENV_FILE}"; then
  warn "CORS_ORIGINS 里没有 ${DOMAIN}，同源部署不影响，但建议补上以防直连 8000"
fi

# ---------------------------------------------------------------- 7. systemd
log "安装 systemd 服务"
sed -e "s|__APP_DIR__|${APP_DIR}|g" \
    -e "s|__RUN_USER__|${RUN_USER}|g" \
    -e "s|__RUN_HOME__|${RUN_HOME}|g" \
    -e "s|__PORT__|${PORT}|g" \
    -e "s|__VENV__|${VENV}|g" \
    "${SCRIPT_DIR}/systemd/trip-planner.service" > /etc/systemd/system/trip-planner.service
systemctl daemon-reload
systemctl enable trip-planner >/dev/null 2>&1 || true
systemctl restart trip-planner

# ---------------------------------------------------------------- 8. 前端
# A) --frontend-repo：从 git 拉前端源码，服务器上装 Node 构建（推荐，可一键更新）
# B) --dist：用本地构建好的产物（服务器不装 Node，但要手动上传）

ensure_node() {
  local major=""
  if command -v node >/dev/null 2>&1; then
    major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || true)"
    if [[ "${major:-0}" -ge 18 ]]; then
      log "已安装 Node $(node -v)，跳过安装"
      return 0
    fi
    warn "Node 版本过低（$(node -v)），改装 ${NODE_VERSION}"
  fi

  local arch
  arch="$(uname -m)"
  case "${arch}" in
    x86_64|amd64)  arch="x64" ;;
    aarch64|arm64) arch="arm64" ;;
    *) die "不支持的 CPU 架构：$(uname -m)" ;;
  esac

  local name="node-v${NODE_VERSION}-linux-${arch}.tar.gz"
  local tmp
  tmp="$(mktemp -d)"
  log "下载 Node ${NODE_VERSION}（${NODE_MIRROR}/v${NODE_VERSION}/${name}）"
  curl -fL --retry 3 --connect-timeout 15 -o "${tmp}/${name}" \
    "${NODE_MIRROR}/v${NODE_VERSION}/${name}" || die "下载 Node 失败，可用 NODE_MIRROR 换镜像"
  tar -xzf "${tmp}/${name}" -C "${tmp}"
  rm -rf "/opt/node-v${NODE_VERSION}"
  mv "${tmp}/node-v${NODE_VERSION}-linux-${arch}" "/opt/node-v${NODE_VERSION}"
  ln -sfn "/opt/node-v${NODE_VERSION}/bin/node" /usr/local/bin/node
  ln -sfn "/opt/node-v${NODE_VERSION}/bin/npm"  /usr/local/bin/npm
  ln -sfn "/opt/node-v${NODE_VERSION}/bin/npx"  /usr/local/bin/npx
  rm -rf "${tmp}"
  hash -r
  log "Node $(node -v) 已安装到 /opt/node-v${NODE_VERSION}"
}

# monorepo 里自动找前端工程（含 package.json 的目录）
FE_DIR=""
find_frontend_dir() {
  local root="$1"
  if [[ -n "${FRONTEND_SUBDIR}" ]]; then
    [[ -f "${root}/${FRONTEND_SUBDIR}/package.json" ]] \
      || die "--frontend-subdir 里没有 package.json：${root}/${FRONTEND_SUBDIR}"
    FE_DIR="${root}/${FRONTEND_SUBDIR}"
    log "前端工程目录：${FE_DIR}"
    return 0
  fi
  if [[ -f "${root}/package.json" ]]; then
    FE_DIR="${root}"
    log "前端工程目录：${FE_DIR}"
    return 0
  fi
  local found=() p d preferred=""
  while IFS= read -r p; do
    found+=("$(dirname "${p}")")
  done < <(find "${root}" -maxdepth 5 -name package.json \
             -not -path "*/node_modules/*" -not -path "*/dist/*" 2>/dev/null | sort)
  [[ ${#found[@]} -gt 0 ]] || die "仓库里找不到 package.json，请用 --frontend-subdir 指定前端目录"
  for d in "${found[@]}"; do
    [[ "$(basename "${d}")" == "frontend" ]] && preferred="${d}"
  done
  if [[ -n "${preferred}" ]]; then
    FE_DIR="${preferred}"
  else
    FE_DIR="${found[0]}"
    [[ ${#found[@]} -gt 1 ]] && warn "找到多个 package.json，默认用第一个：${FE_DIR}"
  fi
  log "前端工程目录：${FE_DIR}"
}

prepare_frontend_env() {
  local fe="$1"
  local target="${fe}/.env"
  if [[ -n "${FRONTEND_ENV}" ]]; then
    [[ -f "${FRONTEND_ENV}" ]] || die "--frontend-env 不存在：${FRONTEND_ENV}"
    install -m 644 "${FRONTEND_ENV}" "${target}"
    log "前端 .env 使用 --frontend-env 指定的文件"
  elif [[ -f "${APP_DIR}/.env.frontend" ]]; then
    install -m 644 "${APP_DIR}/.env.frontend" "${target}"
    log "前端 .env 使用 ${APP_DIR}/.env.frontend"
  elif [[ -f "${target}" ]]; then
    log "前端 .env 使用仓库自带的 ${target}"
  else
    : > "${target}"
    warn "仓库里没有前端 .env（有 .env.example 可参考），已生成空白模板"
  fi

  # 无论如何强制同源：VITE_API_BASE_URL 必须为空，否则线上会去连用户自己的 localhost:8000
  sed -i '/^[[:space:]]*VITE_API_BASE_URL[[:space:]]*=/d' "${target}"
  if [[ -s "${target}" && "$(tail -c 1 "${target}" | od -An -tx1 | tr -d ' \n')" != "0a" ]]; then
    printf '\n' >> "${target}"
  fi
  printf 'VITE_API_BASE_URL=\n' >> "${target}"

  if ! grep -q '^VITE_AMAP_WEB_JS_KEY=.\+' "${target}"; then
    warn "前端 .env 缺少 VITE_AMAP_WEB_JS_KEY，上线后地图会空白（不是 CORS）"
    warn "  解法：把本地的 frontend/.env scp 上来，用 --frontend-env 指定"
  fi
}

build_frontend_git() {
  FRONTEND_REPO="$(normalize_repo_url "${FRONTEND_REPO}")"
  install -d -m 755 "$(dirname "${WEB_SRC}")"

  if [[ -d "${WEB_SRC}/.git" ]]; then
    log "更新前端仓库 ${FRONTEND_REPO}（${FRONTEND_REF}）"
    if git -C "${WEB_SRC}" remote get-url origin >/dev/null 2>&1; then
      git -C "${WEB_SRC}" remote set-url origin "${FRONTEND_REPO}"
    else
      git -C "${WEB_SRC}" remote add origin "${FRONTEND_REPO}"
    fi
    git -C "${WEB_SRC}" fetch --depth 1 origin "${FRONTEND_REF}" \
      || die "拉取前端仓库失败（分支：${FRONTEND_REF}）"
    git -C "${WEB_SRC}" reset --hard FETCH_HEAD >/dev/null
    [[ -n "${FRONTEND_SUBDIR}" ]] && git -C "${WEB_SRC}" sparse-checkout set "${FRONTEND_SUBDIR}" 2>/dev/null || true
  else
    rm -rf "${WEB_SRC}"
    log "克隆前端仓库 ${FRONTEND_REPO}（${FRONTEND_REF}）"
    if [[ -n "${FRONTEND_SUBDIR}" ]] && \
       git clone --depth 1 --filter=blob:none --sparse \
         --branch "${FRONTEND_REF}" "${FRONTEND_REPO}" "${WEB_SRC}" 2>/dev/null; then
      # monorepo 只检出前端目录，省流量（git < 2.25 不支持，会走下面的完整克隆）
      git -C "${WEB_SRC}" sparse-checkout set "${FRONTEND_SUBDIR}"
      log "已稀疏检出：只拉取 ${FRONTEND_SUBDIR}"
    else
      rm -rf "${WEB_SRC}"
      git clone --depth 1 --branch "${FRONTEND_REF}" "${FRONTEND_REPO}" "${WEB_SRC}" \
        || die "克隆前端仓库失败（检查地址/分支；私有库需要 token 或 SSH key）"
    fi
  fi

  find_frontend_dir "${WEB_SRC}"
  prepare_frontend_env "${FE_DIR}"
  ensure_node

  log "安装前端依赖并构建（首次约 1~3 分钟）"
  (
    cd "${FE_DIR}"
    export npm_config_registry="${NPM_REGISTRY}"
    export npm_config_fund=false
    export npm_config_audit=false
    export NODE_OPTIONS="--max-old-space-size=1024"
    if [[ -f package-lock.json ]]; then
      npm ci --prefer-offline --no-audit --no-fund
    else
      npm install --prefer-offline --no-audit --no-fund
    fi
    rm -rf dist
    log "npm run build"
    npm run build
  ) || die "前端构建失败，看上面的 npm 输出（内存不够可加 --swap 2G）"

  [[ -f "${FE_DIR}/dist/index.html" ]] || die "构建完成但没有 ${FE_DIR}/dist/index.html"

  log "部署产物 ${FE_DIR}/dist -> ${WEB_ROOT}"
  rsync -a --delete "${FE_DIR}/dist/" "${WEB_ROOT}/"
  chown -R root:"${RUN_USER}" "${WEB_ROOT}"
  chmod -R 755 "${WEB_ROOT}"
  chmod -R a+rX "${WEB_SRC}"
  if grep -Rqs "localhost:8000" "${WEB_ROOT}/assets" 2>/dev/null; then
    warn "产物里仍有 localhost:8000（前端把 API 地址写死了），线上会跨域"
  fi
}

if [[ -n "${FRONTEND_REPO}" ]]; then
  if [[ -n "${DIST_PATH}" ]]; then
    warn "同时给了 --frontend-repo 和 --dist，以 git 构建为准"
  fi
  build_frontend_git
elif [[ -n "${DIST_PATH}" ]]; then
  [[ -e "${DIST_PATH}" ]] || die "--dist 不存在：${DIST_PATH}"
  TMPD="$(mktemp -d)"
  log "部署前端产物 ${DIST_PATH} -> ${WEB_ROOT}"
  case "${DIST_PATH}" in
    *.tar.gz|*.tgz) tar -xzf "${DIST_PATH}" -C "${TMPD}" ;;
    *.zip)          unzip -q "${DIST_PATH}" -d "${TMPD}" ;;
    *)              [[ -d "${DIST_PATH}" ]] || die "无法识别的 --dist 类型：${DIST_PATH}"
                    cp -a "${DIST_PATH}/." "${TMPD}/" ;;
  esac
  # 兼容打包时多套了一层 dist/ 的情况
  if [[ ! -f "${TMPD}/index.html" && -f "${TMPD}/dist/index.html" ]]; then
    TMPD="${TMPD}/dist"
  fi
  [[ -f "${TMPD}/index.html" ]] || die "产物里找不到 index.html，请检查 --dist 内容"
  rsync -a --delete "${TMPD}/" "${WEB_ROOT}/"
  rm -rf "${TMPD}"
  chown -R root:"${RUN_USER}" "${WEB_ROOT}"
  chmod -R 755 "${WEB_ROOT}"
else
  [[ -f "${WEB_ROOT}/index.html" ]] \
    || warn "前端目录为空（${WEB_ROOT}），站点会 403/404，请用 --frontend-repo 或 --dist"
fi

# ---------------------------------------------------------------- 9. nginx
log "配置 nginx"

# TLS 片段：证书存在就生成 443 监听 + 80->443 跳转，否则留一行注释。
# 单独拆成 include 是为了让「重新部署」不会把 certbot 配好的 HTTPS 冲掉。
NGINX_VER="$(nginx -v 2>&1 | sed -n 's#.*nginx/\([0-9][0-9.]*\).*#\1#p')"
if [[ -n "${NGINX_VER}" ]] && \
   [[ "$(printf '1.25.1\n%s\n' "${NGINX_VER}" | sort -V | head -1)" == "1.25.1" ]]; then
  TLS_LISTEN="listen 443 ssl;
listen [::]:443 ssl;"
  TLS_HTTP2="http2 on;"
else
  # nginx < 1.25.1 不支持独立的 http2 指令
  TLS_LISTEN="listen 443 ssl http2;
listen [::]:443 ssl http2;"
  TLS_HTTP2=""
fi

write_tls_snippet() {
  local conf="/etc/nginx/snippets/trip-planner-tls.conf"
  install -d -m 755 /etc/nginx/snippets
  if [[ "${DOMAIN}" != "_" && -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
    cat > "${conf}" <<EOF
# 由 deploy.sh 生成：Let's Encrypt 证书（nginx ${NGINX_VER}）
${TLS_LISTEN}
${TLS_HTTP2}

ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
ssl_protocols       TLSv1.2 TLSv1.3;
ssl_ciphers         HIGH:!aNULL:!MD5;
ssl_session_cache   shared:SSL:10m;
ssl_session_timeout 1d;
ssl_session_tickets off;

add_header Strict-Transport-Security "max-age=31536000" always;

# HTTP 一律跳 HTTPS
if (\$scheme = http) {
    return 301 https://\$host\$request_uri;
}
EOF
  else
    printf '# TLS 未启用（未指定 --domain 或证书尚未申请）\n' > "${conf}"
  fi
  chmod 644 "${conf}"
}

write_tls_snippet
sed -e "s|__DOMAIN__|${DOMAIN}|g" \
    -e "s|__ROOT__|${WEB_ROOT}|g" \
    -e "s|__PORT__|${PORT}|g" \
    "${SCRIPT_DIR}/nginx/trip-planner.conf" > /etc/nginx/sites-available/trip-planner
ln -sfn /etc/nginx/sites-available/trip-planner /etc/nginx/sites-enabled/trip-planner
if [[ -e /etc/nginx/sites-enabled/default ]]; then
  rm -f /etc/nginx/sites-enabled/default
  warn "已禁用 nginx 默认站点（避免与本站抢占 80 端口）"
fi
nginx -t
systemctl enable nginx >/dev/null 2>&1 || true
systemctl reload nginx || systemctl restart nginx

# ---------------------------------------------------------------- 10. 自检
log "等待后端就绪"
READY=0
for _ in $(seq 1 40); do
  if curl -fsS --max-time 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done

if [[ "${READY}" -eq 1 ]]; then
  log "后端健康检查通过"
else
  warn "后端健康检查失败，最近日志："
  journalctl -u trip-planner -n 30 --no-pager || true
  [[ "${ENV_CREATED}" -eq 1 ]] && warn "多半是 ${ENV_FILE} 还没填密钥（AMAP_API_KEY / LLM_API_KEY）"
fi

CHECK_HOST="${DOMAIN}"
[[ "${CHECK_HOST}" == "_" ]] && CHECK_HOST="localhost"
CODE="$(curl -fsS -o /dev/null -w '%{http_code}' -H "Host: ${CHECK_HOST}" \
  "http://127.0.0.1/index.html" 2>/dev/null || echo 000)"
[[ "${CODE}" == "200" ]] && log "nginx 静态站点正常（index.html 200）" || warn "静态站点返回 ${CODE}，检查 ${WEB_ROOT}"

# ---------------------------------------------------------------- 11. HTTPS / 防火墙
if [[ "${DO_TLS}" -eq 1 ]]; then
  [[ "${DOMAIN}" != "_" ]] || die "--tls 需要同时指定 --domain"
  [[ -n "${EMAIL}" ]] || die "--tls 需要同时指定 --email"
  log "申请 Let's Encrypt 证书（${DOMAIN}）"
  apt-get install -y -qq certbot python3-certbot-nginx >/dev/null
  # certonly 只签证书、不改配置；443 由上面的 tls 片段负责
  certbot certonly --nginx -d "${DOMAIN}" -m "${EMAIL}" \
    --agree-tos --non-interactive --keep-until-expiring
  write_tls_snippet
  nginx -t
  systemctl reload nginx
fi

if [[ "${DO_UFW}" -eq 1 ]]; then
  log "配置 ufw"
  apt-get install -y -qq ufw >/dev/null
  ufw allow OpenSSH >/dev/null
  ufw allow 80/tcp >/dev/null
  ufw allow 443/tcp >/dev/null
  ufw --force enable >/dev/null
  ufw status | sed 's/^/    /'
fi

# ---------------------------------------------------------------- 12. 汇总
SCHEME="http"
[[ "${DOMAIN}" != "_" && -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]] && SCHEME="https"
HOST_SHOWN="${DOMAIN}"
[[ "${HOST_SHOWN}" == "_" ]] && HOST_SHOWN="$(curl -fsS --max-time 3 https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')"
if [[ -n "${FRONTEND_REPO}" ]]; then
  FE_SRC="git 构建（${FRONTEND_REPO}）"
elif [[ -n "${DIST_PATH}" ]]; then
  FE_SRC="上传产物（${DIST_PATH}）"
else
  FE_SRC="未变更"
fi
echo
log "部署完成"
cat <<EOF
    站点      : ${SCHEME}://${HOST_SHOWN}
    接口      : ${SCHEME}://${HOST_SHOWN}/api/...   (nginx -> 127.0.0.1:${PORT})
    API 文档  : ${SCHEME}://${HOST_SHOWN}/docs
    后端目录  : ${APP_DIR}
    前端目录  : ${WEB_ROOT}
    前端来源  : ${FE_SRC}
    服务管理  : systemctl status|restart trip-planner
    查看日志  : journalctl -u trip-planner -f
    配置文件  : ${ENV_FILE}（改完必须 systemctl restart trip-planner）
EOF
if [[ "${ENV_CREATED}" -eq 1 ]]; then
  echo
  warn "记得先编辑 ${ENV_FILE} 填入真实密钥，然后 systemctl restart trip-planner"
fi
