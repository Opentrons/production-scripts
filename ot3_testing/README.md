# OT3 Testing Module

OT3 Testing Module 是用于 OT3 设备调平测试的 Python 模块，包含 Z 轴、8 通道移液器、96 通道移液器和夹爪的调平测试功能。

## 目录结构

```
ot3_testing/
├── __init__.py              # 包初始化文件
├── __version__.py           # 版本信息
├── __package__.py           # 包配置
├── main.py                  # 命令行入口
├── setup.py                 # 打包配置
├── package.spec             # PyInstaller 打包配置
├── Makefile                 # Make 命令配置
├── README.md                # 项目说明文档
├── http_client.py           # HTTP 客户端
├── ot_type.py               # 类型定义
├── hardware_control/        # 硬件控制模块
│   ├── __init__.py
│   ├── hardware_control.py
│   └── jog.py
├── leveling_test/           # 调平测试模块
│   ├── __init__.py
│   ├── __main__.py          # 调平测试入口
│   ├── config.py            # 配置文件（读取 JSON）
│   ├── type.py              # 类型定义
│   ├── leveling_config.json # 调平配置 JSON 文件
│   ├── leveling_z_stage.py  # Z 轴调平测试
│   ├── leveling_8ch_pipette.py  # 8 通道移液器调平测试
│   ├── leveling_96ch_pipette.py # 96 通道移液器调平测试
│   ├── leveling_gripper.py  # 夹爪调平测试
│   ├── model/               # 模型模块
│   │   ├── __init__.py
│   │   └── base.py          # 测试基类
│   ├── fixture/             # 夹具模块
│   │   ├── __init__.py
│   │   └── reader.py        # 夹具读取器
│   └── report/              # 报告模块
│       ├── __init__.py
│       └── report.py        # 测试报告生成
├── maintenance_api/         # 维护 API 模块
│   ├── __init__.py
│   └── maintenance_run.py
├── protocol/                # 协议模块
│   ├── __init__.py
│   ├── jog.py
│   ├── protocol_context.py
│   └── session.py
└── tests/                   # 测试目录（占位）
    └── base_init.py
```

## 快速开始

### 安装依赖

```bash
cd ot3_testing
make install-deps
```

### 运行调平测试

```bash
# 运行调平测试
make run-leveling-test
```

<br />

## Make 命令

### 运行测试

| 命令                       | 说明     |
| ------------------------ | ------ |
| `make run-leveling-test` | 运行平行测试 |

### 打包命令

| 命令                     | 说明                     |
| ---------------------- | ---------------------- |
| `make build-exe`       | 使用 PyInstaller 构建可执行文件 |
| `make install-package` | 以开发模式安装包               |
| `make build-wheel`     | 构建 wheel 包             |
| `make clean-build`     | 清理构建产物                 |
| `make package`         | 完整打包流程（清理 + 构建 wheel）  |

### 开发命令

| 命令                  | 说明   |
| ------------------- | ---- |
| `make install-deps` | 安装依赖 |

### 配置文件

调平配置文件位于 `leveling_test/leveling_config.json`，包含以下配置：

- `zstage_leveling_config` - Z 轴调平配置
- `pipette_leveling_config` - 移液器调平配置（包含 CH8 和 CH96）
- `gripper_leveling_config` - 夹爪调平配置

## 外部依赖

以下外部驱动作为可选依赖：

- `pyserial` - 串口通信
- `playsound` - 音频播放
- `crcmod` - CRC 计算

安装可选依赖：

```bash
pip install pyserial playsound crcmod
```

## 版本

当前版本：1.0.0
