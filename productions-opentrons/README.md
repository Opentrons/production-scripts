# Productions Opentrons

生产数据中心应用，用于管理 Opentrons 生产测试数据、机器人连接、数据上传、数据分析、测试用例执行和生产状态追踪。

当前目录作为 `production-scripts` monorepo 的一个子项目管理。不要在本目录里再初始化独立 git 仓库；代码、前端和后端配置都由外层仓库统一提交。

## 目录结构

```text
productions-opentrons/
├── Makefile                 # 本项目常用命令入口
├── backend/                 # FastAPI 后端
│   ├── app.py               # uvicorn 入口，加载 src/app.py
│   ├── pyproject.toml       # 后端 Python 依赖，使用 uv 管理
│   ├── uv.lock              # 后端锁定依赖
│   ├── auth/                # 本地凭证目录，不提交
│   ├── datas/               # 测试样本数据；temp/testing_data 不提交
│   ├── src/
│   │   ├── api/             # REST API 和服务
│   │   ├── data_analysis/   # CSV 数据分析
│   │   ├── database/        # MongoDB 访问
│   │   ├── opentrons/       # Robot API / 文件传输
│   │   ├── slack_driver/    # Slack 消息
│   │   ├── test_case/       # 测试用例和执行流程
│   │   └── upload_handler/  # 上传解析、配置、Google Drive/Sheets 写入
│   └── tests/               # 后端测试
├── docs/                    # 项目文档
└── web_ui/                  # Vue 3 + Vite 前端
```

## 依赖管理

后端使用 `uv`，不再使用 `Pipfile` / `pipenv`。

```bash
cd productions-opentrons
make install
```

等价命令：

```bash
cd productions-opentrons/backend
uv sync
```

前端使用 npm：

```bash
cd productions-opentrons/web_ui
npm ci
```

## 本地运行

启动后端开发服务：

```bash
cd productions-opentrons
make backend
```

默认地址：

```text
http://0.0.0.0:8090
```

检查后端健康状态：

```bash
make health
```

启动前端开发服务：

```bash
cd productions-opentrons/web_ui
npm run dev
```

构建前端：

```bash
cd productions-opentrons
make web-ui-build
```

## 常用 Make 命令

```bash
make help
make install
make backend
make backend-prod
make health
make web-ui-build
make update
make update COMPONENT=backend
make update COMPONENT=web
make update DEPLOY_HOST=192.168.0.137
```

部署/更新参数：

| 参数 | 说明 |
| --- | --- |
| `COMPONENT=all|backend|web` | 更新范围，默认 `all` |
| `DEPLOY_HOST=IP` | 给 backend 和 web 上传脚本传入同一个目标主机 |
| `PUSH_ARGS='...'` | 传给 `backend/push-scripts.py` 的额外参数 |
| `WEB_PUSH_ARGS='...'` | 传给 `web_ui/push-scripts.py` 的额外参数 |
| `WEB_UI_BASE_PATH=/` | 前端 Vite base path；通过根目录 index 反代部署时使用 `/productions-opentrons/` |

## 后端能力

后端基于 FastAPI，主要模块包括：

- 数据上传：解析测试 CSV/ZIP，写入 Google Drive、Google Sheets 和 MongoDB。
- 数据分析：按产品和测试类型分析 QC/gravimetric/assembly 数据。
- Robot 管理：扫描、连接、读取文件、运行协议、执行 home/move/reset 等动作。
- 测试用例：维护 test product、test type、test case，并支持远程执行流程。
- 产品管理：同步/查看/更新生产状态。
- 消息和记录：维护上传记录、消息中心、unit tracker 和 Slack 通知。

## 配置和凭证

本地开发默认使用：

```text
productions-opentrons/backend/auth/
```

常见文件：

```text
credentials.json
token.json
sheettoken.json
slack.yaml
robot_key
```

这些文件包含真实凭证，已被 `.gitignore` 忽略，不应提交。

服务端环境默认使用 `/configs`、`/data/temp`、`/data/testing_data` 和 `/var/log`。关键环境变量在 `backend/src/settings.py` 中定义，常用项：

| 环境变量 | 说明 |
| --- | --- |
| `DATA_HANDLER_RUN_ENV` | `dev`、`local`、`development` 或 `server` |
| `DATA_HANDLER_HOST` | 服务访问主机 |
| `DATA_HANDLER_PORT` | 服务端口，默认 `8090` |
| `DATA_HANDLER_BASE_URL` | 对外基础 URL |
| `DATA_HANDLER_MONGO_HOST` | MongoDB 主机 |
| `DATA_HANDLER_MONGO_URI` | MongoDB URI |
| `DATA_HANDLER_ROBOT_KEY_PATH` | robot SSH key 路径 |
| `DATA_HANDLER_ROBOT_TEST_WORKING_DIRECTORY` | 测试管理 SSH 命令的远端工作目录，默认 `/opt/opentrons-robot-server` |
| `DATA_HANDLER_SLACK_CONFIG_PATH` | Slack 配置路径 |
| `DATA_HANDLER_ROBOT_SCAN_INTERVAL_SECONDS` | 后台设备扫描间隔，默认 `180` 秒 |
| `DATA_HANDLER_ROBOT_SCAN_CONNECT_TIMEOUT_SECONDS` | 单个 IP 端口探测超时，默认 `0.5` 秒 |
| `DATA_HANDLER_ROBOT_SCAN_HTTP_TIMEOUT_SECONDS` | Robot health 请求超时，默认 `2` 秒 |
| `DATA_HANDLER_ROBOT_SCAN_MAX_DURATION_SECONDS` | 单次完整扫描最大时长，默认 `120` 秒 |

### Robot 设备缓存

- 后端启动后立即执行一次设备扫描，之后每 3 分钟自动刷新。
- 扫描结果保存在 MongoDB 的 `ProductionsMessage.robot_scan_cache` collection。
- `GET /api/robots` 只读取 MongoDB 缓存，不执行网络扫描。
- `POST /api/robots/scan` 异步触发扫描并立即返回当前缓存；前端轮询缓存直到刷新完成，避免长 HTTP 请求超时。
- 扫描失败时保留最近一次成功结果，并通过 `last_error` 返回本次失败原因。

## 数据目录规则

`backend/datas/` 下保留少量测试样本，用于后端测试和分析回归。

以下目录是运行产物，不提交：

```text
backend/datas/temp/
backend/datas/testing_data/
```

新增测试样本时，优先放在明确的产品目录里，并确认没有包含真实凭证或不应公开的生产数据。

## 测试

后端测试：

```bash
cd productions-opentrons/backend
uv run pytest
```

前端构建校验：

```bash
cd productions-opentrons/web_ui
npm run build
```

## Git 规则

- 本目录没有独立 `.git`，由外层 `production-scripts` 仓库统一管理。
- 不提交 `.venv`、`node_modules`、`dist`、`__pycache__`、`.pytest_cache`、日志、临时数据和凭证。
- 后端依赖只维护 `backend/pyproject.toml` 和 `backend/uv.lock`。
- 前端依赖维护 `web_ui/package.json` 和 `web_ui/package-lock.json`。
