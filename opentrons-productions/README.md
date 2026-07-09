# 数据处理服务

## 项目概述

本项目是一个基于 FastAPI 框架的服务端应用，主要用于自动化处理移液器测试数据。支持从远程服务器拉取测试数据、上传到 Google Drive/Google Sheets、记录到 MongoDB 数据库，并通过 Slack 发送测试结果通知。

## 目录结构

```
data_handler/
├── api/                      # API 路由模块
│   ├── __init__.py
│   └── routes.py             # 路由定义和业务逻辑
├── google_driver/            # Google Drive/Sheets 操作模块
│   ├── configs/             # 配置文件
│   │   └── globalconfig.py
│   ├── drivers/             # 驱动器实现
│   │   ├── csvdriver.py     # CSV 文件处理
│   │   ├── googledrive.py   # Google Drive 操作
│   │   ├── sheetdrive.py    # Google Sheets 操作
│   │   └── yamldrive.py     # YAML 配置读取
│   ├── upload.py            # 数据上传核心类
│   ├── tools.py             # 工具函数
│   └── basic_login.py       # Google 认证
├── slack_driver/            # Slack 消息模块
│   ├── config.py            # Slack 配置类
│   └── message.py           # Slack 消息发送类
├── data_base/               # 数据库模块
│   └── mongodb.py           # MongoDB 操作
├── configs/                 # 配置文件目录
├── app.py                   # 主应用入口
├── setting.py               # 全局配置和日志
└── requirements.txt         # 项目依赖
```

## 核心模块

### 1. API 模块 (api/routes.py)

提供 RESTful API 接口：

#### POST /api/upload-data
上传测试数据到 Google Drive。

**请求参数** (JSON):
- `csv_file_path`: CSV 文件路径
- `zip_file_path`: ZIP 文件路径（可选）

**响应**: 返回上传结果和文件路径

#### POST /api/pull-folder
从远程服务器拉取文件夹。

**请求参数** (FormData):
- `csv_file`: CSV 文件（必需）
- `folder_name`: 远程文件夹名称（必需）
- `pull_method`: 拉取方法，可选 `sftp` 或 `scp`（默认 `sftp`）

**响应**: 返回拉取结果和目标路径

### 2. Google Driver 模块 (google_driver/upload.py)

`UploadData` 类是数据上传的核心类，提供以下功能：

#### 主要方法

| 方法 | 说明 |
|------|------|
| `__init__(mongo=None)` | 初始化，连接 MongoDB（可选） |
| `init_google_driver()` | 初始化 Google Drive 连接 |
| `get_current_month()` | 获取当前年月，返回 `(year, month)` 元组 |
| `is_1ch_8ch(model)` | 判断是否为 1 通道或 8 通道移液器 |
| `update_data_to_google_drive(file_path, zip_file)` | 主方法：更新数据到 Google Drive |
| `query_csv_link(db_name, collection_name, device_sn, my_test_name, search_test_name)` | 查询 CSV 链接 |
| `fill_database_with_result(db_name, collection_name, result)` | 填充数据库结果 |
| `edit_database_with_result(db_name, collection_name, query, result)` | 编辑数据库记录 |
| `update_1ch_8ch_grav(file_desc, note_str)` | 更新 1/8 通道容量测试数据 |
| `update_1ch_8ch_qc(file_desc, note_str)` | 更新 1/8 通道 QC 测试数据 |
| `update_1ch_8ch_current(file_desc, note_str)` | 更新 1/8 通道电流测试数据 |
| `update_96ch_p200_p1000_qc(file_desc, note_str)` | 更新 96 通道 QC 测试数据 |

#### 枚举类

```python
class Productions(Enum):
    Robot = "Robot"
    P50S = "P50S"
    P1000S = "P1000S"
    P50M = "P50M"
    P1000M = "P1000M"

class TestTypes(Enum):
    Assembly_QC = "assembly_qc"
    Speed_Current_Test = "speed_current_test"
    Gravimetric = "gravimetric"
```

#### 使用示例

```python
from google_driver.upload import UploadData

upload_handler = UploadData()
upload_handler.init_google_driver()
result = upload_handler.update_data_to_google_drive(csv_path, zip_path)
```

### 3. Slack Driver 模块 (slack_driver/)

#### SlackConfig 类 (config.py)

从 YAML 配置文件加载 Slack 配置。

**配置字段**:
- `bot_token`: Slack Bot Token
- `default_channel`: 默认频道
- `bot_name`: Bot 名称
- `bot_icon`: Bot 图标
- `templates`: 消息模板

**加载方法**:
```python
from slack_driver.config import SlackConfig

config = SlackConfig.from_yaml(
    config_path="/path/to/slack.yaml",
    environment="development"  # 或 "production"
)
```

#### SlackBotMessenger 类 (message.py)

发送测试结果消息到 Slack。

**主要方法**:

| 方法 | 说明 |
|------|------|
| `__init__(environment, webhook_url, bot_name, bot_icon_emoji)` | 初始化 Slack Bot |
| `send_test_result(channel, test_type, test_result, serial_number, test_data_link, tracking_sheet_link, custom_bot_name)` | 发送测试结果 |
| `_send_via_oauth(...)` | 通过 OAuth Token 发送 |
| `_send_via_webhook(...)` | 通过 Webhook 发送 |

**使用示例**:

```python
from slack_driver.message import SlackBotMessenger

bot = SlackBotMessenger(environment="development")

bot.send_test_result(
    channel="production-data-center",
    test_type="Pipette Gravimetric Test",
    test_result="Pass",
    serial_number="P50SV3620250101A01",
    test_data_link="https://docs.google.com/...",
    tracking_sheet_link="https://docs.google.com/..."
)
```

### 4. 数据库模块 (data_base/mongodb.py)

MongoDB 操作封装，提供数据持久化功能。

## 配置说明

### 环境配置 (setting.py)

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DOWNLOAD_DIR` | 下载目录 | `/data/temp` |
| `TESTING_DATA_DIR` | 测试数据目录 | `/data/testing_data` |
| `CONFIG_DIR` | 配置目录 | `/configs` |
| `LOG_FILE` | 日志文件 | `/data/data_handler.app.log` |
| `ENVIRONMENT` | 环境 | `debug` |
| `DATA_DB_NAME` | 数据库名称 | `ProductionsData2026` |
| `EXPIRE_DAYS` | 数据过期天数 | `1` |

### 日志配置

```python
from setting import setup_logging, get_logger

setup_logging()  # 初始化日志
logger = get_logger(__name__)  # 获取日志记录器
```

### Slack 配置 (configs/slack.yaml)

```yaml
slack:
  bot_token: "xoxb-..."
  default_channel: "production-data-center"
  bot_name: "QC Bot"
  bot_icon: ":robot_face:"

  environments:
    development:
      bot_token: "xoxb-dev-..."
      default_channel: "dev-channel"
```

## 部署

### 依赖安装

```bash
cd backend
uv sync
```

### 启动服务

```bash
cd backend
uv run uvicorn app:app --host 0.0.0.0 --port 8090
```

服务将在 `http://0.0.0.0:8090` 上运行。

### 使用 Dockerfile 部署

项目支持 Docker 部署，请参考相关部署文档。

## 数据流程

```
远程服务器 (Robot)
       │
       ▼ (SFTP/SCP)
  本地临时目录
       │
       ▼
  Google Drive 上传
       │
       ├──► Google Sheets (测试数据)
       ├──► Google Drive (原始文件)
       │
       ▼
  MongoDB 数据库
       │
       ▼
  Slack 通知
```

## 依赖

- FastAPI
- uvicorn
- paramiko
- google-api-python-client
- google-auth-oauthlib
- pymongo
- slack-sdk
- pyyaml
- aiofiles
