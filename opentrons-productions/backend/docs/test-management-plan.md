# 测试管理模块开发计划

## 1. 背景与目标

当前系统已经具备设备管理、设备操作、文件管理和 Protocol 管理能力。下一阶段需要新增“测试管理”模块，用于统一管理生产线中不同产品的测试用例，执行测试命令，并记录测试历史、异常、失败节点和测试报告。

目标是建设一个面向生产线设备控制台的测试系统：

- 管理所有产品的测试用例。
- 按产品和测试类型组织测试用例。
- 通过可视化节点画布编辑测试流程。
- 通过 SSH 执行测试命令并实时展示输出。
- 根据输出中的 expect 节点暂停并等待前端输入。
- 支持多客户端观察测试过程。
- 限制活跃 SSH 测试连接数量，默认最大 20 个。
- 记录成功、失败、超时、网络异常、设备异常和用户停止等历史结果。
- 支持成功率、失败节点统计、异常类型统计、历史回归和测试报告。

## 2. 左侧菜单与页面结构

左侧主菜单新增一级入口：

```text
测试管理
```

测试管理页面内部使用树状结构组织测试资产：

```text
测试管理
  产品 A
    功能测试
      测试用例 1
      测试用例 2
    出厂测试
      测试用例 3
  产品 B
    老化测试
      测试用例 4
```

建议页面布局：

```text
左侧：产品 / 测试类型 / 测试用例树
中间：测试用例详情或节点画布
右侧：节点属性、用例属性、执行参数、统计摘要
底部或抽屉：执行日志、测试报告、历史记录
```

第一版功能：

- 新建测试用例。
- 编辑测试用例。
- 复制测试用例。
- 归档测试用例。
- 按产品、测试类型搜索过滤。
- 打开测试用例画布。
- 从测试用例启动测试运行。

## 3. 数据模型

### 3.1 test_cases

新增 MongoDB collection：`test_cases`

用途：保存测试用例定义和节点流程。

```json
{
  "_id": "ObjectId",
  "name": "Flex Door Sensor Test",
  "product_id": "flex",
  "product_name": "Flex",
  "test_type": "factory_qc",
  "description": "Factory QC test for Flex door sensor.",
  "version": 1,
  "status": "draft",
  "command": "python -m s.ssssss.fsss",
  "default_timeout_seconds": 600,
  "node_timeout_seconds": 120,
  "error_patterns": [
    {
      "name": "位置错误",
      "pattern": "position error",
      "match_type": "contains",
      "error_type": "device_position_error",
      "severity": "fatal"
    }
  ],
  "nodes": [
    {
      "id": "start",
      "type": "start",
      "name": "开始测试",
      "position": { "x": 80, "y": 120 }
    },
    {
      "id": "node_input_name",
      "type": "expect",
      "name": "输入姓名",
      "expect": "input your name:",
      "match_type": "contains",
      "input_mode": "text",
      "append_newline": true,
      "timeout_seconds": 120,
      "position": { "x": 320, "y": 120 }
    },
    {
      "id": "node_confirm",
      "type": "expect",
      "name": "确认继续",
      "expect": "continue?",
      "match_type": "contains",
      "input_mode": "boolean",
      "true_label": "是",
      "false_label": "否",
      "true_input": "y",
      "false_input": "n",
      "append_newline": true,
      "timeout_seconds": 120,
      "position": { "x": 560, "y": 120 }
    },
    {
      "id": "end",
      "type": "end",
      "name": "结束",
      "position": { "x": 800, "y": 120 }
    }
  ],
  "edges": [
    { "source": "start", "target": "node_input_name" },
    { "source": "node_input_name", "target": "node_confirm" },
    { "source": "node_confirm", "target": "end" }
  ],
  "created_at": "2026-06-10T00:00:00Z",
  "updated_at": "2026-06-10T00:00:00Z",
  "created_by": "system",
  "updated_by": "system"
}
```

字段说明：

| 字段 | 说明 |
|---|---|
| `product_id` / `product_name` | 所属产品 |
| `test_type` | 测试类型，例如 factory_qc、aging、calibration |
| `command` | SSH 中执行的测试命令 |
| `nodes` | 节点画布中的节点 |
| `edges` | 节点连接关系 |
| `error_patterns` | 全局异常匹配规则 |
| `status` | `draft`、`active`、`archived` |

约束：

- 每个测试用例必须有一个开始节点。
- 第一版只允许一个结束节点。
- `expect` 节点必须配置 `expect`。
- `boolean` 输入节点必须配置真实输入值。
- 所有节点必须从开始节点可达。
- 不允许孤立节点。

### 3.2 test_runs

新增 MongoDB collection：`test_runs`

用途：保存每一次测试运行记录。

```json
{
  "_id": "ObjectId",
  "test_case_id": "ObjectId",
  "test_case_name": "Flex Door Sensor Test",
  "test_case_version": 1,
  "product_id": "flex",
  "product_name": "Flex",
  "test_type": "factory_qc",
  "device_ip": "192.168.6.52",
  "device_sn": "FLXU3020260603002",
  "command": "python -m s.ssssss.fsss",
  "status": "running",
  "current_node_id": "node_input_name",
  "failed_node_id": null,
  "error_type": null,
  "error_message": null,
  "error_detail": null,
  "started_at": "2026-06-10T00:00:00Z",
  "ended_at": null,
  "duration_ms": null,
  "node_results": [],
  "output_logs": [],
  "operator_events": [],
  "report_id": null
}
```

`status` 枚举：

```text
created
connecting
running
waiting_input
passed
failed
error
timeout
stopped
```

状态含义：

| 状态 | 说明 |
|---|---|
| `passed` | 测试正常完成 |
| `failed` | 测试逻辑失败，例如 expect 不匹配或节点判定失败 |
| `error` | 系统或设备异常，例如 SSH 断开、网络错误、位置错误 |
| `timeout` | 节点等待超时或整条测试超时 |
| `stopped` | 用户手动停止 |

### 3.3 node_results

`test_runs.node_results` 记录节点级结果。

```json
{
  "node_id": "node_input_name",
  "node_name": "输入姓名",
  "status": "matched",
  "expect": "input your name:",
  "matched_text": "input your name:",
  "input_mode": "text",
  "input_value": "Andy",
  "started_at": "2026-06-10T00:00:01Z",
  "ended_at": "2026-06-10T00:00:05Z",
  "duration_ms": 4000,
  "error_type": null,
  "error_message": null,
  "raw_output_excerpt": "..."
}
```

`node_results.status` 枚举：

```text
pending
running
matched
waiting_input
completed
failed
timeout
error
skipped
```

### 3.4 output_logs

`test_runs.output_logs` 记录终端输出。

```json
{
  "timestamp": "2026-06-10T00:00:02Z",
  "stream": "stdout",
  "text": "input your name:",
  "node_id": "node_input_name",
  "sequence": 15
}
```

第一版可以把日志直接保存在 `test_runs` 中。若日志量过大，第二版拆分为 `test_run_logs` collection。

### 3.5 operator_events

记录用户输入和操作。

```json
{
  "timestamp": "2026-06-10T00:00:05Z",
  "event_type": "input_submitted",
  "node_id": "node_input_name",
  "input_mode": "text",
  "display_value": "Andy",
  "actual_input": "Andy\n",
  "operator": "system"
}
```

## 4. 节点画布设计

建议使用成熟画布库，例如 Vue Flow。

节点类型：

| 类型 | 说明 |
|---|---|
| `start` | 开始节点，表示建立 SSH 连接并执行命令 |
| `expect` | 中间节点，等待命令输出命中 expect |
| `end` | 结束节点，表示测试成功结束 |

`expect` 节点属性：

| 字段 | 说明 |
|---|---|
| `name` | 节点名 |
| `expect` | 需要匹配的输出文本 |
| `match_type` | `contains`、`exact`、`regex`，第一版建议支持 contains |
| `input_mode` | `none`、`boolean`、`text` |
| `true_label` / `false_label` | 是/否按钮显示文案 |
| `true_input` / `false_input` | 是/否实际写入终端的内容 |
| `append_newline` | 是否自动追加换行 |
| `timeout_seconds` | 节点等待超时时间 |

画布交互：

- 支持新建节点。
- 支持拖拽节点。
- 支持连线。
- 支持点击节点编辑属性。
- 支持节点复制。
- 支持删除普通节点。
- 开始节点和结束节点不允许直接删除，或需要强确认。
- 保存时校验流程合法性。

## 5. SSH 执行引擎

新增后端服务：`TestExecutionManager`

职责：

- 管理测试运行生命周期。
- 建立 SSH 连接。
- 限制活跃 SSH 测试连接数，默认最大 20。
- 支持多个前端客户端订阅同一个测试运行。
- 执行测试命令。
- 实时读取 stdout / stderr。
- 匹配当前节点 expect。
- 命中节点后进入 `waiting_input`。
- 接收前端输入并写入 SSH stdin。
- 处理超时、断开、网络异常和设备异常。
- 关闭 SSH 连接并持久化结果。

平台状态指标：

```json
{
  "active_ssh_sessions": 7,
  "max_ssh_sessions": 20,
  "observer_clients": 12,
  "running_tests": 7,
  "waiting_input_tests": 2
}
```

连接限制：

- 活跃测试 SSH session 最大 20 个。
- 超过限制时，新建测试运行返回 429 或业务错误。
- WebSocket 观察客户端不计入 SSH session 限制。

## 6. 执行状态机

测试运行状态流转：

```text
created
  -> connecting
  -> running
  -> waiting_input
  -> running
  -> passed

created / connecting / running / waiting_input
  -> failed
  -> error
  -> timeout
  -> stopped
```

典型流程：

1. 前端选择测试用例和设备。
2. 后端创建 `test_runs`。
3. 后端检查 SSH session 限制。
4. 后端建立 SSH 连接。
5. 后端执行 `test_cases.command`。
6. 后端监听输出。
7. 输出命中当前节点 expect。
8. 如果节点需要输入，状态变为 `waiting_input`。
9. 前端展示输入控件。
10. 用户输入后，后端写入 SSH stdin。
11. 流程继续到下一个节点。
12. 命中结束条件后，测试状态变为 `passed`。
13. 写入完整历史和报告。

## 7. 异常处理

异常必须写入测试历史数据库，不能只在前端提示。

### 7.1 异常类型

建议 `error_type` 枚举：

```text
ssh_connect_failed
ssh_disconnected
network_error
command_start_failed
expect_timeout
node_timeout
test_timeout
device_position_error
device_runtime_error
backend_error
user_stopped
unknown
```

### 7.2 异常分类原则

| 分类 | run 状态 | 说明 |
|---|---|---|
| 测试逻辑失败 | `failed` | expect 未命中、节点判断失败 |
| 系统/设备异常 | `error` | SSH、网络、设备运行时错误、位置错误 |
| 超时 | `timeout` | 节点或整条测试超时 |
| 人工停止 | `stopped` | 用户主动停止 |

不要把所有异常都写成 `failed`。统计时需要区分测试失败、系统异常和超时。

### 7.3 错误匹配规则

测试用例支持 `error_patterns`。

执行引擎监听输出时，优先级：

1. 匹配 fatal error pattern。
2. 匹配当前节点 expect。
3. 判断节点超时。
4. 判断 SSH / 网络状态。

命中 fatal error 后：

- 当前 `test_run.status = error`
- 当前 `node_result.status = error`
- 写入 `error_type`
- 写入 `error_message`
- 保存 `raw_output_excerpt`
- 关闭 SSH session
- 通知前端

示例：

```json
{
  "name": "位置错误",
  "pattern": "position error",
  "match_type": "contains",
  "error_type": "device_position_error",
  "severity": "fatal"
}
```

## 8. 前端运行界面

测试执行页面显示：

- 当前测试用例。
- 当前设备。
- 当前命令。
- 当前状态。
- 当前节点。
- 实时终端输出。
- 节点执行时间线。
- 当前等待输入的节点。
- 输入控件。

输入类型：

### 8.1 是 / 否

前端展示两个按钮。

配置项：

- 是按钮文案。
- 否按钮文案。
- 是对应真实输入。
- 否对应真实输入。
- 是否自动追加换行。

### 8.2 字符串输入

前端展示 input。

提交后：

- 直接把输入值写入 SSH stdin。
- 根据节点配置决定是否追加换行。

## 9. API 设计

### 9.1 测试用例

```text
GET    /api/test-cases
POST   /api/test-cases
GET    /api/test-cases/{id}
PUT    /api/test-cases/{id}
DELETE /api/test-cases/{id}
POST   /api/test-cases/{id}/duplicate
POST   /api/test-cases/{id}/archive
```

### 9.2 测试运行

```text
POST   /api/test-cases/{id}/runs
GET    /api/test-runs
GET    /api/test-runs/{id}
POST   /api/test-runs/{id}/input
POST   /api/test-runs/{id}/stop
GET    /api/test-runs/{id}/report
WS     /api/test-runs/{id}/stream
```

### 9.3 统计

```text
GET /api/test-stats/summary
GET /api/test-stats/failure-nodes
GET /api/test-stats/error-types
GET /api/test-stats/regression
GET /api/test-stats/by-device
GET /api/test-stats/by-product
```

### 9.4 平台执行状态

```text
GET /api/test-execution/status
```

返回：

```json
{
  "active_ssh_sessions": 7,
  "max_ssh_sessions": 20,
  "observer_clients": 12,
  "running_tests": 7,
  "waiting_input_tests": 2
}
```

## 10. 测试报告

测试报告应包含：

- 测试用例名称和版本。
- 产品和测试类型。
- 设备 IP 和 SN。
- 执行命令。
- 开始时间、结束时间、总耗时。
- 最终结果。
- 失败节点或异常节点。
- 节点执行时间线。
- 用户输入记录。
- 完整输出日志。
- 错误摘要。
- 环境信息。

报告可以先以 JSON / HTML 形式保存。后续支持 PDF 或下载。

## 11. 历史统计

统计维度：

- 总执行次数。
- passed / failed / error / timeout / stopped 数量。
- 成功率。
- 测试失败率。
- 系统异常率。
- 超时率。
- Top failed nodes。
- Top error types。
- 按产品统计。
- 按测试类型统计。
- 按设备 IP / SN 统计。
- 按测试用例版本统计。
- 历史回归趋势。

成功率建议：

```text
success_rate = passed / finished_runs
```

其中 `finished_runs` 包括：

```text
passed + failed + error + timeout + stopped
```

同时单独展示：

```text
logic_failure_rate = failed / finished_runs
system_error_rate = error / finished_runs
timeout_rate = timeout / finished_runs
```

## 12. 开发阶段计划

### Phase 1：数据模型与基础 API

目标：先把测试用例和测试运行记录存起来。

任务：

- 新增 `test_cases` repository。
- 新增 `test_runs` repository。
- 新增 Pydantic models。
- 新增测试用例 CRUD API。
- 新增测试运行查询 API。
- 新增节点合法性校验。

交付：

- 可以创建、编辑、查询、归档测试用例。
- 可以查询测试历史。

### Phase 2：测试管理前端基础页

目标：先做资产管理界面。

任务：

- 左侧菜单新增 `测试管理`。
- 测试管理页增加产品 / 测试类型 / 用例树。
- 用例详情页。
- 新建 / 编辑用例表单。
- 基础节点列表编辑。

交付：

- 用户可以在页面中管理测试用例。

### Phase 3：节点画布

目标：将节点列表升级为可视化画布。

任务：

- 引入 Vue Flow 或同类画布库。
- 实现 start / expect / end 节点。
- 实现拖拽、连线、节点属性编辑。
- 保存节点位置和 edges。
- 保存前校验流程。

交付：

- 用户可以可视化编辑测试流程。

### Phase 4：SSH 执行引擎

目标：后端可以执行测试命令并实时读取输出。

任务：

- 实现 `TestExecutionManager`。
- 实现 SSH session 管理。
- 实现最大 20 个活跃连接限制。
- 实现命令启动。
- 实现 stdout / stderr 监听。
- 实现 WebSocket 输出推送。
- 实现停止测试。

交付：

- 可以启动测试并实时看到终端输出。

### Phase 5：expect 节点与用户输入

目标：测试执行可以按节点暂停和继续。

任务：

- 实现 expect 匹配。
- 实现节点状态流转。
- 实现 `waiting_input`。
- 实现 boolean 输入。
- 实现 text 输入。
- 输入写入 SSH stdin。
- 记录 operator_events。

交付：

- 测试执行可以按 expect 节点停住，前端输入后继续。

### Phase 6：异常处理与历史入库

目标：所有失败和异常都可追踪。

任务：

- 实现 error_patterns。
- 实现 SSH 断开处理。
- 实现网络异常处理。
- 实现节点超时。
- 实现整条测试超时。
- 实现设备位置错误等 fatal pattern。
- 完善 `test_runs.error_type`、`error_message`、`failed_node_id`。

交付：

- 网络异常、位置报错、超时、用户停止都会写入历史数据库。

### Phase 7：报告与统计

目标：测试结果可分析。

任务：

- 生成测试报告。
- 统计成功率。
- 统计失败节点。
- 统计异常类型。
- 按产品、测试类型、设备统计。
- 历史回归趋势。

交付：

- 可查看测试报告和统计面板。

## 13. MVP 范围

建议第一版 MVP 包含：

- 测试管理菜单。
- 测试用例 collection。
- 产品 / 测试类型 / 用例树。
- 用例 CRUD。
- 简单节点画布。
- 单设备 SSH 执行。
- 实时输出。
- expect 命中后等待输入。
- boolean / text 输入。
- 测试运行历史。
- 异常入库。
- 基础报告。

暂不包含：

- 批量设备并行测试。
- 权限审批。
- PDF 报告。
- 用例版本 diff。
- 复杂条件分支。
- 高级回归分析。

## 14. 风险与注意事项

- SSH session 必须可靠清理，避免连接泄漏。
- 输出日志可能很大，需要后续考虑拆分 collection 或日志压缩。
- expect 匹配规则要先简单稳定，第一版优先 `contains`。
- fatal error pattern 优先级必须高于普通 expect。
- 用户输入要记录 display value 和 actual input。
- 测试运行状态必须持久化，不能只存在内存。
- 服务重启后，内存中的活跃 session 会丢失，需要将未完成 run 标记为 `error` 或 `stopped`。
- 多客户端订阅同一个 run 时，输入权限需要控制。第一版可允许任意客户端输入，后续再加操作者锁。

