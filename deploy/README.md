# 部署说明

后端是一个 uvicorn 进程 + nginx 反代，没有外部数据库。**前端源码已经并入本仓库**（`frontend/`，Vue 3 + Vite），所以部署只需要一个仓库地址。

前端有两种上线方式：

- **A. 服务器上构建（默认，推荐）**：`--repo` 拉整个仓库后，脚本自动在 `frontend/` 里 `npm ci && npm run build`，前后端一条命令一起更新。服务器会装一份 Node 20（默认 20.18.3，可用 `NODE_VERSION` 覆盖）到 `/opt/node-v20.18.3`。
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
| `deploy.sh` | 主脚本：拉代码、建 venv、装依赖、预热 uv、构建前端、装 systemd、配 nginx、自检、可选 HTTPS |
| `nginx/trip-planner.conf` | 站点配置模板（gzip、SPA 回退、`/api/` 300s 反代） |
| `systemd/trip-planner.service` | 后端服务单元模板（单 worker、HOME 指向可写目录） |
| `env.production.example` | 后端 `.env` 模板，首次部署会复制成 `/opt/trip-planner/.env` |
| `build-frontend.ps1` | 方案 B 用：本地构建 + 校验 + 打 `dist.tar.gz` |

## 一、首次部署（方案 A：服务器构建，推荐）

前提：代码已经 push 到 git（`deploy/` 目录也要提交，以后更新要用），仓库可公开访问或用 token 访问。

```bash
sudo bash deploy.sh \
  --repo https://github.com/tonganyuan/trip-planner.git \
  --domain trip.example.com --email you@example.com \
  --tls --swap 2G
```

要点：

- 仓库根目录就是项目根：`app/`（后端）、`frontend/`（前端）、`deploy/`（部署脚本）。脚本默认构建 `/opt/trip-planner/frontend`，换目录用 `--frontend-dir`（相对路径按 `/opt/trip-planner` 解析）。
- **前端 `.env` 不在 git 里**（被忽略了），服务器上没有 `VITE_AMAP_WEB_JS_KEY` 地图就会空白。三种补法（按优先级）：
  - 部署时加 `--frontend-env /root/frontend.env`；
  - 长期放在 `/opt/trip-planner/.env.frontend`（脚本会自动用它）；
  - 或者把 `frontend/.env` scp 到 `/opt/trip-planner/frontend/.env`（用 `--repo` 更新时 `git reset` 不会删未跟踪文件；但首次用 `--repo` 克隆会覆盖目录，脚本会先把它备份再恢复）。
  都没有时脚本会按 `frontend/.env.example` 生成一份并警告。
- 脚本无论如何都会把 `VITE_API_BASE_URL` 强制置空 —— 同源部署靠的就是这个，写死了 `localhost:8000` 上线必然跨域。
- 2G 内存的机器一定要加 `--swap 2G`，`vue-tsc` + `vite build` 峰值内存不低。

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

## 三、数据库和用户数据（可选）

数据库是 SQLite，**不在 git 里**（根目录 `.gitignore` 把整个 `data/` 忽略了），服务器上也不用手动建库：后端启动时 `init_db()` 会自动建表，库文件位置由 `.env` 的 `DB_PATH` 决定，默认是 `/var/lib/trip-planner/data/app.db`。

- **全新部署**：什么都不用做，第一次启动会生成空库，打开站点注册账号即可。
- **把现有账号/行程/足迹迁到服务器**：只传 `app.db` 不够，`data/` 里这几样要一起带：
  - `.auth_secret`：加密家庭 LLM Key / OBS SK 的密钥（`app/services/crypto.py`）。只传库不传它，库里的密文全部解不开，模型和 OBS 配置要重填；
  - `regions.json`、`province_shapes/`：省市列表和省界缓存。不带也能跑（会重新调高德，或退回内置 88 城），只是足迹页第一次打开慢一点、地图精度差一点。

迁移步骤（先本地打包上传，再让 `deploy.sh` 导入）：

```powershell
# 建议先停掉本地后端，确保 app.db-wal 落盘
scp -r .\data root@<服务器IP>:/root/trip-data
```

```bash
sudo bash /opt/trip-planner/deploy/deploy.sh \
  --repo https://github.com/tonganyuan/trip-planner.git \
  --data /root/trip-data
```

`--data` 会做这些事：

1. 按 `.env` 的 `DB_PATH` 找到数据目录（默认 `/var/lib/trip-planner/data`）；
2. 停掉 `trip-planner`，把服务器上的旧数据目录备份为 `data.bak-<时间戳>`；
3. 删掉旧的 `-wal/-shm`，把 `--data` 目录 rsync 过去（带上 `-wal`，不带 `-shm`，由 SQLite 重建）；
4. `chown www-data`，目录 750、文件 640、`.auth_secret` 600；
5. 用 `PRAGMA quick_check` 自检，失败时告警但不动数据（旧数据还在备份里）。

注意：

- 迁移会覆盖服务器上的同名文件，并让旧登录 token 失效（`.auth_secret` 换了）；账号密码本身仍可用。
- 如果 `.env` 里显式设置了 `AUTH_SECRET`，它才是真正的加密密钥，必须和源环境一致；否则优先用 `data/.auth_secret`。
- 本地后端如果还开着，`app.db-wal` 可能不是一致快照。迁移前先停本地后端，或执行一次 `PRAGMA wal_checkpoint(TRUNCATE)`。
- **日常更新不要再带 `--data`**，否则会用旧副本覆盖服务器上新产生的数据。

## 四、脚本会做的事

1. 建 `/swapfile`（`--swap 2G`，2G 内存机器建议加；服务器上构建前端更建议加）
2. `apt` 装 nginx / python3-venv / git / unzip
3. 拉整个仓库到 `/opt/trip-planner`（`--repo`/`--src`），建 `.venv`，用清华镜像装 `requirements.txt`
4. 把 `uv` 装进 venv（`app/services/amap_mcp.py:46` 的 `find_uvx()` 靠它找 `uvx`）
5. 在 `/var/lib/trip-planner/.config/uv/uv.toml` 写镜像配置，并预热 `amap-mcp-server` 依赖
6. 生成后端 `.env`（模板）、`chmod 640 root:www-data`
7. 有 `--data` 时：停服 → 备份旧数据目录 → 导入 `app.db`/`.auth_secret`/地区缓存 → 改属主 → 自检
8. 安装并启动 `trip-planner.service`（`uvicorn --host 127.0.0.1 --port 8000 --workers 1`）
9. 前端：默认在 `/opt/trip-planner/frontend` 装 Node 20 → `npm ci`（失败回退 `npm install`）→ `npm run build` → `rsync dist` 到 `/var/www/trip-planner`；`--dist` 时直接解压 tarball，`--no-frontend` 时跳过
10. 装 nginx 站点、reload，自检 `/health` 与 `index.html`，失败时打印 `journalctl`
11. `--tls` 时用 certbot 申请证书并强制跳转 HTTPS

**部署完第一件事是填密钥**：

```bash
sudo nano /opt/trip-planner/.env     # 填 LLM_API_KEY / UNSPLASH_* / AMAP_API_KEY
sudo systemctl restart trip-planner
```

如果 `.env` 里 `AMAP_API_KEY` 还是 `REPLACE_ME`，`validate_config()` 会在启动时直接抛错，`/health` 也就起不来——这是设计如此，不是脚本 bug。

## 五、日常更新

```bash
DEPLOY=/opt/trip-planner/deploy/deploy.sh   # 仓库克隆下来后脚本就在这

# 前后端一起更新（拉代码 + 重建前端）
sudo bash $DEPLOY --repo https://github.com/tonganyuan/trip-planner.git

# 只更新后端（前端产物保持不动，前端没改时用，省 1~3 分钟构建）
sudo bash $DEPLOY --repo https://github.com/tonganyuan/trip-planner.git --no-frontend

# 代码已经拉过、只重新构建前端
sudo bash $DEPLOY

# 前端用本地产物
sudo bash $DEPLOY --dist /root/trip-dist.tar.gz
```

脚本幂等：重复执行只会重启服务、覆盖静态文件。前端依赖缓存在 `/opt/trip-planner/frontend/node_modules`，npm 自身的包缓存（`~/.npm`）也会让第二次构建快很多。**注意静态目录会用 `rsync --delete` 覆盖**，别往 `/var/www/trip-planner` 里放别的东西。

数据库和上传的图片都不在代码目录：库在 `/var/lib/trip-planner/data/app.db`，图片在家庭自己的 OBS 桶里，所以 `--src`/`--repo` 更新代码不会碰它们。只有首次迁移数据时才加 `--data`，日常更新不要带。

> 旧版本的前端参数 `--frontend-repo` / `--frontend-ref` / `--frontend-subdir` 已经废弃：前端现在就在本仓库的 `frontend/` 里，脚本会直接报错退出，把这些参数删掉即可。

> 从旧版本升级：旧脚本把前端单独克隆在 `/opt/trip-planner-web`，现在用不到了，可以 `sudo rm -rf /opt/trip-planner-web` 回收磁盘。

## 六、排错

| 现象 | 原因 / 处理 |
|---|---|
| 502 Bad Gateway | 后端没起来：`journalctl -u trip-planner -n 50`；多数是 `.env` 缺 `AMAP_API_KEY` |
| 504，页面转圈 1 分钟后失败 | nginx 超时太短。本项目必须 `proxy_read_timeout 300s`（模板已设）；确认没被别的 conf 覆盖 |
| `/docs` 能开，页面白屏 | 静态站点没部署：`ls /var/www/trip-planner/index.html` |
| 刷新 `/result` 404 | 缺 `try_files $uri $uri/ /index.html`（模板已设） |
| 地图白板、控制台报 key 不合法 | 高德 **Web 端 JS Key** 的域名白名单里没有新域名；改了要**重新 build 前端**，因为 key 烧在 bundle 里 |
| 首屏加载 5 秒以上 | gzip 没生效：`curl -I -H 'Accept-Encoding: gzip' https://域名/assets/xxx.js` 看有没有 `content-encoding: gzip` |
| `npm run build` 被 Killed | 内存不够：加 `--swap 2G`，或改用方案 B 本地构建 |
| `vue-tsc` 报类型错误，构建失败 | 先在本机 `cd frontend && npm run build` 复现修掉；类型检查是构建的一部分 |
| `npm ci` 卡住 / 太慢 | 检查能否访问 `registry.npmmirror.com`；可用 `NPM_REGISTRY=...` 覆盖 |
| 克隆失败（私有库） | 地址是 `git@github.com:...` 但服务器没配 SSH key（脚本会自动转成 `https://`，私有库需要 token） |
| 前端目录空、站点 403 | 用了 `--no-frontend` 但 `/var/www/trip-planner` 本来就没内容；去掉该参数或加 `--dist` |
| 改 `.env` 不生效 | 必须 `systemctl restart trip-planner`，`--reload` 只监视 `.py` |
| 迁移后模型/OBS 配置解不开 | 只迁了 `app.db`，没带 `.auth_secret`（加密密钥）。从源 `data/` 补上它再重启；或让家庭重新填一次 Key |
| 迁移后所有人都要重新登录 | 正常：`.auth_secret` 换了，旧 token 失效；账号密码仍可用 |
| `--data` 之后 502 | `journalctl -u trip-planner -n 50`；确认库属主是 `www-data`、`quick_check` 没告警，旧数据在 `/var/lib/trip-planner/data.bak-*` |
| 图片接口经常卡 20 秒 | 见下面「已知问题」第 1 条 |
| `address already in use` | `ss -lptn 'sport = :8000'`，杀掉残留的 uvicorn |

## 七、已知问题（上线前建议修）

1. **`app/services/unsplash_service.py:25` 是同步 `requests.get(..., timeout=20)`，却在 async 路由里调用**。单 worker 下它会阻塞整个事件循环：一个图片请求卡 20 秒，所有用户一起等；国内机房访问 `api.unsplash.com` 还经常超时。建议改成 `httpx.AsyncClient` + `timeout=5`，或加一层本地缓存。
2. **`.env` 里现在是真实密钥**。上线时建议重新申请一套（DeepSeek / Unsplash / 高德），旧的如果进过 git 历史就算泄露。
3. **`config.py:35-45` 把 key 写成了默认值**。目前 .env 缺失时也能跑，但意味着密钥进了代码库，建议后续删掉这些默认值。
4. **`/opt/trip-planner/frontend/node_modules` 会占几百 MB**。2C2G 的轻量盘一般 50G 起，问题不大；真要省空间可以部署完删掉，下次构建会重装。

## 八、备案提醒

大陆机器 + 域名走 80/443 必须 ICP 备案，否则会被运营商拦截。不备案的选择：用 IP + 非标端口访问、或者部署到香港/新加坡节点。这一步不在脚本范围内，买机器前先决定。
tar -xzf /root/trip-dist.tar.gz -C /var/www/trip-planner
systemctl restart trip-planner