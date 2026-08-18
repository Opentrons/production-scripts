# Production Platform

生产制造平台仓库，包含统一的 Web 操作界面、FastAPI 服务和产线硬件工具。项目使用 `uv` 管理 Python workspace，使用 Vue 3 + Vite 构建前端，并通过 systemd + Nginx 部署到服务器。

## 项目组成

```text
production-scripts/
├── apps/
│   ├── backend/              # FastAPI API、业务服务、数据持久化和部署配置
│   ├── web-ui/               # Vue 3 管理界面
│   └── hardwares/            # 产线硬件 CLI、驱动、诊断和打包工具
├── deploy/                   # 本机服务器和远程服务器部署脚本
├── csv-samples/              # 测试与分析示例数据
├── Makefile                  # 开发、测试、构建和部署统一入口
├── pyproject.toml            # uv workspace 配置
└── uv.lock                   # Python 依赖锁文件
```

## 功能模块

### Web 平台

- **Dashboard / Downloads**：项目版本、文件资源、消息和下载管理。
- **Productions Testing**：Opentrons 设备发现、设备信息与控制、终端测试、Protocol 房间监控、运行状态和测试数据管理。
- **Flex 远程能力**：ODD 远程屏幕与交互、Protocol 仿真，以及设备卡片上的 Flex 摄像头 HLS 直播、图片切换和放大预览。
- **数据管理**：测试数据上传记录、数据查询、移液器与机器人装配质量分析、数据链接。
- **Productions Versions**：产品工作流、SOP 与 Duro 数据对比、版本历史、Duro API Key 状态与更新。
- **Production Agent**：生产知识、协议分析、附件、计划任务和工具调用。
- **平台能力**：中英文界面、统一登录、角色权限、消息中心、服务器 / Google Drive / Slack 状态。

### 后端服务

- FastAPI 统一 API，覆盖认证、机器人、测试、上传、数据分析、版本、SOP、Duro、工作流和 Agent。
- Opentrons HTTP API 客户端、批量设备操作、日志 / 文件 / Protocol 管理。
- JWT Access Token 默认 5 分钟，登录会话默认 1 小时。
- 非仿真模式使用 MongoDB `ProductionsMessage`；仿真模式使用 `apps/backend/db-storage/simulating/` 下的 SQLite。
- Google Drive、Slack、Duro API Key 和 LLM 等外部服务集成。

### 硬件工具

- 生产硬件交互 CLI，以及串口、SSH、Socket、声音和 Opentrons 驱动。
- 移液器、模块、水平校准、称重和高压等测试工具。
- PyInstaller 可执行文件构建。

## 安装与运行

### 1. 准备环境

- Git、Make 和 `lsof`。
- Python 3.10。硬件应用要求 Python `>=3.10,<3.11`，因此建议整个项目统一使用 3.10。
- [`uv`](https://docs.astral.sh/uv/)。
- Node.js 20 LTS 或更高版本，以及 npm。
- MongoDB 6.0 或更高版本。完整的非仿真模式需要 MongoDB；仅体验界面时可以使用下文的仿真模式。

确认主要工具已安装：

```bash
python3 --version
uv --version
node --version
npm --version
make --version
```

### 2. 获取源码并安装依赖

```bash
git clone git@github.com:Opentrons/production-scripts.git
cd production-scripts

# 安装后端和硬件 Python workspace 依赖
make sync

# 严格按照 package-lock.json 安装前端依赖
make web-install
```

### 3. 配置后端

复制本地配置文件，并生成至少 32 个字符的 JWT Secret：

```bash
cp apps/backend/.env.example apps/backend/.env
openssl rand -hex 32
```

将 `openssl` 输出写入 `apps/backend/.env`，并确保本地 HTTP 开发配置至少包含以下内容：

```dotenv
PRODUCTION_PLATFORM_RUN_ENV=dev
PRODUCTION_PLATFORM_AUTH_JWT_SECRET=<openssl rand -hex 32 的输出>
PRODUCTION_PLATFORM_AUTH_ACCESS_TOKEN_MINUTES=5
PRODUCTION_PLATFORM_AUTH_REFRESH_TOKEN_HOURS=1
PRODUCTION_PLATFORM_AUTH_COOKIE_SECURE=false
PRODUCTION_PLATFORM_MONGO_URI=mongodb://127.0.0.1:27017
```

`apps/backend/.env` 已被 Git 忽略，不得提交。Duro、Google Drive、Slack 和 LLM 等外部服务的配置可以暂时留空，对应功能会显示为未连接。

### 4. 准备数据存储和管理员

完整运行时，先启动 MongoDB，并确认 `mongodb://127.0.0.1:27017` 可访问。项目会使用 `ProductionsMessage` 数据库，然后创建首个管理员账号：

```bash
uv run --package production-backend \
  python apps/backend/scripts/create_auth_user.py \
  --username admin --display-name "Administrator" --role admin
```

命令会交互式要求输入并确认至少 12 个字符的密码。

没有 MongoDB 时，可以先启用本地 SQLite 仿真模式，再执行同一条管理员创建命令：

```bash
mkdir -p apps/backend/db-storage
printf '{"simulating": true}\n' > apps/backend/db-storage/mode.json

uv run --package production-backend \
  python apps/backend/scripts/create_auth_user.py \
  --username admin --display-name "Administrator" --role admin
```

### 5. 启动并访问

```bash
# 同时启动 FastAPI 和 Vue 开发服务器
make dev
```

- Web 界面：`http://127.0.0.1:8091`
- 后端 API：`http://127.0.0.1:8090`
- OpenAPI 文档：`http://127.0.0.1:8090/docs`
- 健康检查：`make backend-health`

`make dev` 会先停止占用 8090 和 8091 端口的进程。使用 `Ctrl+C` 可以停止两个开发服务；也可以覆盖默认端口：

```bash
make dev API_PORT=8092 WEB_PORT=8093
```

需要单独调试时，可以在不同终端分别运行：

```bash
make backend-dev
make web-dev
```

### 6. 测试与构建

```bash
make backend-test
make hardware-test
make web-build
make build
```

运行 `make help` 可以查看全部 Make 目标。

## 服务器部署

### 远程一键部署

默认服务器为 `root@192.168.6.55`，默认安装目录为 `/opt/production-platform`。部署命令会先构建前端，然后通过 SSH / rsync 同步代码和静态资源，安装 Duro API Key，重启 FastAPI systemd 服务，更新 Nginx，并执行健康检查。

部署前需要：

- 本机已安装 `ssh`、`rsync`、`npm` 和 `uv`。
- 远程服务器已安装 systemd、Nginx 和 `uv`，并可通过 SSH 登录。
- TLS 证书和私钥已存在于远程服务器。
- 本机存在 `apps/backend/auth-files/duro-api-key.txt`，或通过 `DURO_API_KEY_PATH` 指定。

```bash
# 使用 Makefile 默认参数部署
make deploy-remote

# 指定服务器、域名和远程证书
make deploy-remote \
  REMOTE_HOST=192.168.6.55 \
  REMOTE_USER=root \
  REMOTE_ROOT=/opt/production-platform \
  SERVER_NAME=productions.example.com \
  REMOTE_SSL_CERTIFICATE=/etc/ssl/production-platform/production-platform.crt \
  REMOTE_SSL_CERTIFICATE_KEY=/etc/ssl/production-platform/production-platform.key
```

常用远程参数：

| Make 参数 | 默认值 | 用途 |
| --- | --- | --- |
| `REMOTE_HOST` | `192.168.6.55` | 服务器地址 |
| `REMOTE_USER` | `root` | SSH 用户 |
| `REMOTE_SSH_PORT` | `22` | SSH 端口 |
| `REMOTE_ROOT` | `/opt/production-platform` | 远程安装目录 |
| `REMOTE_UV_BIN` | `/root/.local/bin/uv` | 远程 uv 路径 |
| `SERVER_NAME` | `_` | Nginx 域名或服务器名 |
| `DURO_API_KEY_PATH` | `apps/backend/auth-files/duro-api-key.txt` | 本机 Duro Key 文件 |

### 在当前服务器部署

在目标服务器仓库目录内可以分别部署后端和前端：

```bash
# 安装依赖并创建 / 重启 production-backend.service
make deploy-backend API_PORT=8090

# 构建前端并配置 Nginx HTTPS 站点
make deploy-web \
  API_PORT=8090 \
  SERVER_NAME=productions.example.com \
  SSL_CERTIFICATE=/etc/ssl/production-platform/production-platform.crt \
  SSL_CERTIFICATE_KEY=/etc/ssl/production-platform/production-platform.key
```

首次部署后创建管理员：

```bash
sudo "$(command -v uv)" run --package production-backend \
  python apps/backend/scripts/create_auth_user.py --username admin --role admin
```

认证密钥保存在 `/etc/production-platform.env`。部署脚本会生成缺失的 JWT Secret，并将登录会话设置为 1 小时。运行数据、数据库、本地 `.env` 和认证文件不会被远程同步删除。

## 数据持久化

- **非仿真模式**：认证、工作流、机器人版本记录、健康状态和业务文档写入 MongoDB `ProductionsMessage`。
- **仿真模式**：数据写入 `apps/backend/db-storage/simulating/` 下的 SQLite。
- **本地缓存**：Duro 和 SOP 缓存保存在 `apps/backend/db-storage/business/`，部署时保留。
- **敏感文件**：`.env`、JWT Secret、Duro Key、Google / Slack 凭据、数据库和运行数据均已加入 `.gitignore`，不得提交。

旧版生产 SQLite 数据迁移到 MongoDB：

```bash
# 先检查迁移内容
uv run --package production-backend \
  python apps/backend/scripts/migrate_sqlite_to_mongodb.py --dry-run

# 确认后执行迁移
uv run --package production-backend \
  python apps/backend/scripts/migrate_sqlite_to_mongodb.py
```

认证与 HTTPS 的完整说明见 [apps/backend/docs/platform-authentication.md](apps/backend/docs/platform-authentication.md)。
