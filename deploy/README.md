# 部署说明

后端是一个 uvicorn 进程 + nginx 反代，没有数据库。前端有两种上线方式：

- **A. 从 git 拉源码，服务器上构建**（推荐）：`--frontend-repo`，一条命令前后端一起更新，服务器会装一份 Node 20 到 `/opt/node-v20.x`。
- **B. 本地构建，只传产物**：`--dist trip-dist.tar.gz`，服务器完全不需要 Node，但要每次手动上传。

```
浏览器 ──80/443──> nginx ──┬─ /            -> /var/www/trip-planner (静态 dist)
                            ├─ /assets/     -> 同上，长缓存
                            ├─ /api/        -> 127.0.0.1:8000 (uvicorn, 300s 超时)
                            └─ /health      -> 127.0.0.1:8000/health
```

## 文件清单

| 文件 | 作用 |
|---|---|
| `deploy.sh` | 主脚本：拉代码、建 venv、装依赖、预热 uv、（可选）装 Node 构建前端、装 systemd、配 nginx、自检、可选 HTTPS |
| `nginx/trip-planner.conf` | 站点配置模板（gzip、SPA 回退、`/api/` 300s 反代） |
| `systemd/trip-planner.service` | 后端服务单元模板（单 worker、HOME 指向可写目录） |
| `env.production.example` | 后端 `.env` 模板，首次部署会复制成 `/opt/trip-planner/.env` |
| `build-frontend.ps1` | 方案 B 用：本地构建 + 校验 + 打 `dist.tar.gz` |

## 一、首次部署（方案 A：全部走 git）

前提：代码已经 push 到 git（`deploy/` 目录也要提交，以后更新要用），仓库可公开访问或用 token 访问。

```bash
sudo bash deploy.sh \
  --repo https://github.com/tonganyuan/trip-planner.git \
  --frontend-repo https://github.com/tonganyuan/hello-agents.git \
  --frontend-subdir code/chapter13/helloagents-trip-planner/frontend \
  --domain trip.example.com --email you@example.com \
  --tls --swap 2G
```

要点：

- **`--frontend-subdir` 在 monorepo 里必填**。仓库根目录没有 `package.json` 时脚本会自己找（找 `frontend` 目录或多个就让你指定），但前端在 `code/chapter13/.../frontend` 这种深路径，直接指定最省事，也才能走稀疏检出（只拉这一个目录，不然整个 hello-agents 仓库几十上百 MB 全下来）。
- **前端 `.env` 不在 git 里**（被忽略了），服务器上没有 `VITE_AMAP_WEB_JS_KEY` 地图就会空白。两种补法：
  - 把本地 `frontend\.env` scp 到服务器，部署时加 `--frontend-env /root/frontend.env`；
  - 或者长期放在 `/opt/trip-planner/.env.frontend`（脚本会自动用它）。
- 脚本无论如何都会把 `VITE_API_BASE_URL` 强制置空 —— 同源部署靠的就是这个，写死了 `localhost:8000` 上线必然跨域。

## 二、首次部署（方案 B：前端本地构建）

```powershell
cd D:\learnspace\trip-planner\deploy
powershell -File .\build-frontend.ps1     # 产出 out\trip-dist.tar.gz
scp .\out\trip-dist.tar.gz root@<服务器IP>:/root/
```

```bash
sudo bash deploy.sh --repo https://github.com/tonganyuan/trip-planner.git \
  --dist /root/trip-dist.tar.gz \
  --domain trip.example.com --email you@example.com --tls --swap 2G
```

`build-frontend.ps1` 会校验 `.env` 里 `VITE_API_BASE_URL` 为空、产物里没有 `localhost:8000`——这两条错了上线必然白屏或跨域。

> 脚本存成 UTF-8 with BOM，Windows PowerShell 5.1 和 pwsh 7 都能直接跑（没有 BOM 时 5.1 会按 GBK 读中文导致语法错误）。

## 三、脚本会做的事

1. 建 `/swapfile`（`--swap 2G`，2G 内存机器建议加；服务器上构建前端更建议加）
2. `apt` 装 nginx / python3-venv / git / unzip
3. 拉代码到 `/opt/trip-planner`（`--repo`/`--src`），建 `.venv`，用清华镜像装 `requirements.txt`
4. 把 `uv` 装进 venv（`app/services/amap_mcp.py:46` 的 `find_uvx()` 靠它找 `uvx`）
5. 在 `/var/lib/trip-planner/.config/uv/uv.toml` 写镜像配置，并预热 `amap-mcp-server` 依赖
6. 生成后端 `.env`（模板）、`chmod 640 root:www-data`
7. 安装并启动 `trip-planner.service`（`uvicorn --host 127.0.0.1 --port 8000 --workers 1`）
8. 前端：方案 A 克隆到 `/opt/trip-planner-web` → 装 Node 20 → `npm ci` → `npm run build` → 同步 `dist`；方案 B 直接解压 tarball
9. 装 nginx 站点、reload，自检 `/health` 与 `index.html`，失败时打印 `journalctl`
10. `--tls` 时用 certbot 申请证书并强制跳转 HTTPS

**部署完第一件事是填密钥**：

```bash
sudo nano /opt/trip-planner/.env     # 填 LLM_API_KEY / UNSPLASH_* / AMAP_API_KEY
sudo systemctl restart trip-planner
```

如果 `.env` 里 `AMAP_API_KEY` 还是 `REPLACE_ME`，`validate_config()` 会在启动时直接抛错，`/health` 也就起不来——这是设计如此，不是脚本 bug。

## 四、日常更新

```bash
DEPLOY=/opt/trip-planner/deploy/deploy.sh   # 仓库克隆下来后脚本就在这

sudo bash $DEPLOY --repo https://github.com/tonganyuan/trip-planner.git   # 只更新后端
sudo bash $DEPLOY --frontend-repo https://github.com/tonganyuan/hello-agents.git \
     --frontend-subdir code/chapter13/helloagents-trip-planner/frontend   # 只更新前端
sudo bash $DEPLOY --repo ... --frontend-repo ...                          # 两个一起
```

脚本幂等：重复执行只会重启服务、覆盖静态文件。前端源码缓存保留在 `/opt/trip-planner-web`（`node_modules` 也在里面，`npm ci` 有缓存，第二次构建快很多）。**注意静态目录会用 `rsync --delete` 覆盖**，别往 `/var/www/trip-planner` 里放别的东西。

## 五、排错

| 现象 | 原因 / 处理 |
|---|---|
| 502 Bad Gateway | 后端没起来：`journalctl -u trip-planner -n 50`；多数是 `.env` 缺 `AMAP_API_KEY` |
| 504，页面转圈 1 分钟后失败 | nginx 超时太短。本项目必须 `proxy_read_timeout 300s`（模板已设）；确认没被别的 conf 覆盖 |
| `/docs` 能开，页面白屏 | 静态站点没部署：`ls /var/www/trip-planner/index.html` |
| 刷新 `/result` 404 | 缺 `try_files $uri $uri/ /index.html`（模板已设） |
| 地图白板、控制台报 key 不合法 | 高德 **Web 端 JS Key** 的域名白名单里没有新域名；改了要**重新 build 前端**，因为 key 烧在 bundle 里 |
| 首屏加载 5 秒以上 | gzip 没生效：`curl -I -H 'Accept-Encoding: gzip' https://域名/assets/xxx.js` 看有没有 `content-encoding: gzip` |
| `npm run build` 被 Killed | 内存不够：加 `--swap 2G`，或改用方案 B 本地构建 |
| `npm ci` 卡住 / 太慢 | 检查能否访问 `registry.npmmirror.com`；可用 `NPM_REGISTRY=...` 覆盖 |
| 克隆前端失败 | 地址是 `git@github.com:...` 但服务器没配 SSH key（脚本会自动转成 `https://`，私有库需要 token） |
| 改 `.env` 不生效 | 必须 `systemctl restart trip-planner`，`--reload` 只监视 `.py` |
| 图片接口经常卡 20 秒 | 见下面「已知问题」第 1 条 |
| `address already in use` | `ss -lptn 'sport = :8000'`，杀掉残留的 uvicorn |

## 六、已知问题（上线前建议修）

1. **`app/services/unsplash_service.py:25` 是同步 `requests.get(..., timeout=20)`，却在 async 路由里调用**。单 worker 下它会阻塞整个事件循环：一个图片请求卡 20 秒，所有用户一起等；国内机房访问 `api.unsplash.com` 还经常超时。建议改成 `httpx.AsyncClient` + `timeout=5`，或加一层本地缓存。
2. **`.env` 里现在是真实密钥**。上线时建议重新申请一套（DeepSeek / Unsplash / 高德），旧的如果进过 git 历史就算泄露。
3. **`config.py:35-45` 把 key 写成了默认值**。目前 .env 缺失时也能跑，但意味着密钥进了代码库，建议后续删掉这些默认值。
4. **`/opt/trip-planner-web/node_modules` 会占几百 MB**。2C2G 的轻量盘一般 50G 起，问题不大；真要省空间可以部署完删掉，下次构建会重装。

## 七、备案提醒

大陆机器 + 域名走 80/443 必须 ICP 备案，否则会被运营商拦截。不备案的选择：用 IP + 非标端口访问、或者部署到香港/新加坡节点。这一步不在脚本范围内，买机器前先决定。
