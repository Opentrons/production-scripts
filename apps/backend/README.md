# Backend

The repository's only FastAPI service. It provides uploads, data analysis, robot control, test management, resources, Duro, SOP, and workflows.

The Python source is flat under `src/`: `app.py` is the service entry point, while `api/`, `core/`, and `modules/` are importable top-level packages. `api/router.py` aggregates the domain routers under `api/routers/`. Start Uvicorn with `app:app`.

```bash
make backend-dev
make backend-test
```

Runtime files live in `apps/backend/data/`.

Persistence rule:

- Non-simulating -> MongoDB (`ProductionsMessage`) for workflows, version records, health, and other business documents.
- Development MongoDB connection failure -> SQLite under `db-storage/business/` when `PRODUCTION_PLATFORM_DEV_SQLITE_FALLBACK_ENABLED=true` (the default).
- Simulating -> SQLite under `db-storage/simulating/` with fixture data.

The development fallback is transient for the process and is selected during startup. It does not enable Simulating fixtures or simulated device scanning. Non-development environments still require MongoDB. Authentication storage remains independently controlled by `PRODUCTION_PLATFORM_AUTH_STORAGE`.

`db-storage/business/` may still hold regenerable caches (`duro_cache.sqlite3`, `sop_cache.sqlite3`). Legacy production sqlite files can be migrated with `apps/backend/scripts/migrate_sqlite_to_mongodb.py` then removed.

See [Platform authentication](docs/platform-authentication.md) for first-user and HTTPS deployment instructions.

### OT3 系统镜像安装

- 设备管理 → 设备工作台 → **安装镜像**：选择设备 IP 和服务器镜像。
- **批量处理 → 安装镜像**：复用左侧多选 IP，最多 100 台，每次最多并行升级 4 台；各设备独立显示结果。
- **下载新版本**：填写 HTTP/HTTPS 下载链接（文件名须为 `ot3-system-版本.zip`，支持签名 query 参数），服务器下载到 `/opt/ot3-system`。ZIP 完整性、包内必需文件与设备型号校验通过后才加入列表；同名镜像不会覆盖。
- 使用 `src/modules/robots/upload_ot3_system.py`（由原上传脚本引入）完成上传、写入、提交、重启，依据镜像 `VERSION.json` 校验重启后的系统与 API 版本。已有设备更新会话不会被自动取消。
- 下载、安装均在后台运行，关闭页面不影响任务。写入阶段最长等待 30 分钟，重启最长等待 15 分钟；同一 IP 不允许重复排队。升级设备应处于空闲状态。
- 任务记录保存在 `db-storage/business/system-image-tasks`；服务重启后未完成任务标为中断，检查设备实际状态后再决定是否重试。此执行器与现有代码烧录模块一样要求单 API worker。
- 可通过 `PRODUCTION_PLATFORM_OT3_SYSTEM_DIR` 和 `PRODUCTION_PLATFORM_OT3_TASK_DIR` 配置镜像及任务目录。目录必须对后端服务用户可读写；本地开发可将镜像目录指向 `~/Downloads`。

API（继承平台登录及 CSRF 校验）：`GET /api/robots/system-images`、`GET /api/robots/system-images/tasks`、`POST /api/robots/system-images/install`（`ips`, `image`, `port`）、`POST /api/robots/system-images/download`（`url`）。
