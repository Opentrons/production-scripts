# 新增上传测试接入说明

本文档说明当前代码下新增一个产品/测试需要改哪里，以及“新增 robot 的 5 个测试并配置 combine”是否可以只改入口配置跑通。

## 当前结论

现在还不能做到“只改一个入口配置，就完整接入全新的 robot 5 个组合测试”。

已经通用化的部分：

- CSV 上传入口统一走 `UploadData.update_data_to_google_drive(file_path, zip_file)`。
- 组合测试关系统一读 `product_catalog.UPLOAD_CONFIG_COMBINES`。
- MongoDB 集合名不再写死，会通过产品 profile 和 workflow 拼接。
- 组合测试未全部完成时，不会 append 到 Unit Tracker。
- 组合测试全部完成后，只 append 一次 Unit Tracker，并回写 `unit_tracker_uploaded`。
- 上传失败时会跳过业务数据库写入；API 层会发失败 Slack 和消息库通知。
- Slack 成功消息不需要单独按测试配置，会读统一返回值里的 `production_name`、`test_type`、`test_result`、`unit_tracker_status`。

还没有完全配置化的部分：

- 新产品的 serial number 到 model 的识别仍在 `product_catalog.SERIAL_NUMBER_MODEL_MAPPING`。
- 测试名到 `TestTypes` 的识别仍在 `product_catalog.get_test_type_from_name()`。
- model + test type 到 YAML key 的映射仍在 `product_catalog.get_upload_config_key()`。
- CSV parser definition 仍在 `parsers/definitions.py`，不是 YAML 配置。
- uploader 仍需要配置 `uploader_key` 和 `upload_method`；如果是 CSV 写入模板、读取结果 cell、copy summary、append Unit Tracker 这一类流程，直接使用当前已注册的 `spreadsheet` uploader。
- 模板里的测试结果 cell 已经在 YAML，但文件命名和部分上传策略仍在 uploader 方法里。
- `UploadResult` 已经支持动态测试字段，旧 setter 只作为兼容方法保留。

因此，如果 robot 是全新产品，并且 5 个测试以前没有 uploader 方法，当前最少还需要新增/改代码。只改 YAML 或只改 catalog 还不够。

## 上传链路检查点

1. API 或 CLI 传入 CSV 路径。
   - 入口：`backend/src/upload_handler/upload.py`
   - 方法：`UploadData.update_data_to_google_drive(file_path, zip_file=None)`

2. 构建 `file_desc`。
   - 方法：`UploadData.build_file_description()`
   - 类型：`models/domain.py::FileDescription`
   - CSV 解析入口：`parsers/registry.py::extract_csv()`

3. 第一次读取 CSV metadata。
   - 方法：`parsers/csv_common.py::extract_meta_data_from_csv()`
   - 用途：先拿到 `test_name`、SN 相关字段，再决定使用哪个 parser definition。

4. 通过 metadata 找上传配置 key。
   - 方法：`product_catalog.get_upload_config_key_from_metadata()`
   - 依赖：
     - `get_serial_number_from_metadata()`
     - `get_model_from_serial_number()`
     - `get_test_name_from_metadata()`
     - `get_upload_config_key(model, test_name)`

5. 通过配置 key 找 parser definition。
   - 方法：`product_catalog.get_parser_definition()`
   - 实际定义：`parsers/definitions.py::PARSER_DEFINITIONS`

6. 解析完整 `file_desc`。
   - 方法：`parsers/csv_common.py::parse_csv_by_definition()`
   - 输出关键字段：
     - `upload_config_key`
     - `sn`
     - `model`
     - `kind_stage_type`
     - `kind_oem_type`
     - `test_type`
     - `finished`

7. 找上传 repository。
   - 方法：`repositories/upload_repository.py::resolve_upload_repository()`
   - 判断：`UploadRepository.supports(file_desc)`
   - 依赖：`product_catalog.UPLOAD_HANDLER_CONFIGS`

8. 调用 uploader。
   - 方法：`UploadRepository.upload(file_desc)`
   - 流程：
     - 读 `UploadHandlerConfig.uploader_key`
     - 找注册过的 uploader 实例
     - 通过 `UploadHandlerConfig.upload_method` 反射调用具体方法

9. 写 Google Sheet、raw data、MongoDB、Unit Tracker。
   - 通用 workflow：`uploaders/workflows.py::SpreadsheetUploadWorkflow.run()`
   - 通用 DB 方法：
     - `UploadData.save_upload_result_to_database()`
     - `UploadData.build_upload_db_result()`
     - `UploadData.get_upload_workflow_status()`
     - `UploadData.mark_unit_tracker_uploaded()`

10. API 层通知。
    - 文件：`backend/src/api/routes.py`
    - 成功：发送测试结果 Slack，并写消息库。
    - 失败：发送失败 Slack，并写消息库。

## 新增一个全新测试需要配置哪里

### 1. 类型定义

文件：`backend/src/upload_handler/models/domain.py`

如果是新的产品型号，先确认 `Productions` 是否已有对应枚举。`ROBOT` 已经存在。

如果是新的测试语义，新增 `TestTypes`：

```python
class TestTypes(Enum):
    Robot_Diagnostic = "robot_diagnostic"
```

如果测试只是现有语义的别名，可以不新增 enum，但要确保 `get_test_type_from_name()` 能识别。

### 2. 产品 catalog

文件：`backend/src/upload_handler/product_catalog.py`

这是当前最核心的入口配置文件。

需要补齐：

```python
SERIAL_NUMBER_MODEL_MAPPING = {
    "ROBOT_SN_PREFIX": Productions.ROBOT,
}
```

```python
UPLOAD_PRODUCT_PROFILES = {
    Productions.ROBOT: UploadProductProfile(
        uploader_key="spreadsheet",
        collection_prefix="robot",
    ),
}
```

```python
def get_test_type_from_name(test_name: str) -> str:
    if "diagnostic" in test_name_lower:
        return TestTypes.Robot_Diagnostic.value
```

```python
def get_upload_config_key(model: str, test_type: str | TestTypes | None) -> str:
    if production == Productions.ROBOT:
        if normalized_test_type == TestTypes.Robot_Diagnostic:
            return "robot_update_diagnostic"
```

新增 handler 配置：

```python
UPLOAD_HANDLER_CONFIGS = {
    "robot_update_diagnostic": UploadHandlerConfig(
        uploader_key="spreadsheet",
        upload_method="upload",
        test_display_name="Diagnostic",
    ),
}
```

新增 DB 配置：

```python
UPLOAD_DATABASE_CONFIGS = {
    "robot_update_diagnostic": UploadDatabaseConfig(
        collection_workflow="robot_qc",
        test_field="diagnostic",
        upload_flag_field="diagnostic",
    ),
}
```

字段约定：

- 配置 key 必须包含 `_update_`。
- `_update_` 后面的字符串会作为 combine 默认字段来源。
- 例如 `robot_update_pressure_leakage` 会得到字段 `pressure_leakage`。

### 3. combine 关系

文件：`backend/src/upload_handler/product_catalog.py`

如果 robot 的 5 个测试要落到同一个 workflow，并且等全部完成后才 append Unit Tracker：

```python
UPLOAD_CONFIG_COMBINES = [
    (
        "robot_update_diagnostic",
        "robot_update_current",
        "robot_update_motion",
        "robot_update_pressure",
        "robot_update_calibration",
    ),
]
```

运行逻辑：

- 任意一个测试先上传成功，都会在 MongoDB 中插入/更新同一条 workflow 记录。
- 当前测试字段写 `True`，其他 combine 字段默认 `False`。
- 如果还有缺失字段，返回 `unit_tracker_status = "Waiting for combined tests: ..."`。
- 只有全部字段都是 `True` 后，才 append Unit Tracker。
- append 成功后写入 `unit_tracker_uploaded = True`，后续重复上传不会再次 append。

### 4. CSV parser definition

文件：`backend/src/upload_handler/parsers/definitions.py`

每个 YAML key 需要一个 `CsvParserDefinition`：

```python
ROBOT_DIAGNOSTIC_DEFINITION = {
    "metadata_range": CsvSectionDefinition("META_DATA_START", "META_DATA_END"),
    "finish_range": CsvFinishDefinition(
        "RESULTS_OVERVIEW_START",
        "RESULTS_OVERVIEW_END",
        mode="all_present",
        ignore_keys=("SOME_OPTIONAL_KEY",),
    ),
    "sn": CsvFieldDefinition("test_tag", extra_words=("-results",)),
    "kind": CsvFieldDefinition("test_operator"),
    "test_name": CsvFieldDefinition("test_name"),
}

PARSER_DEFINITIONS = {
    "robot_update_diagnostic": CsvParserDefinition(
        upload_config_key="robot_update_diagnostic",
        test_type=TestTypes.Robot_Diagnostic,
        **ROBOT_DIAGNOSTIC_DEFINITION,
    ),
}
```

当前完成度判断默认是：

- 在 `finish_range` 区间内找需要检查的行。
- 如果检查值里出现 `None` 或空字符串，则认为 CSV 没跑完。
- `ignore_keys` 可以排除不应该参与完成度判断的 key。

### 5. YAML 上传配置

文件：

- `backend/src/upload_handler/configs/upload_debug.yaml`
- `backend/src/upload_handler/configs/upload_production.yaml`

每个测试 key 都要在 debug 和 production 里配置同名块：

```yaml
robot_update_diagnostic:
- ifupdate: true
  spreadsheet_strategy: reuse_within_workflow
  ifcopytemplate:
    default: TEMPLATE_ID
    ultima: ULTIMA_TEMPLATE_ID
    millipore: MILLIPORE_TEMPLATE_ID
  csv_target_sheet_name: Diagnostic Raw Data
  result_cell: '!P11:P11'
  total_result_cell: '!O11:O11'
  Range:
  - A
  - B
  - C
  ifcopydata:
  - off/on: true
    summary_source_sheet_name: Diagnostic
    copyRange:
    - '!A1:Z1'
  ifpaste:
  - off/on: true
    pastefileid: UNIT_TRACKER_ID
    pastelineRange:
      star: A
      end: Z
    unit_tracker_tab: ''
  unit_tracker_sheet:
    1: MONTH_FOLDER_ID
  ifupdaterawdata:
    1: RAW_DATA_MONTH_FOLDER_ID
```

`result_cell` 是从模板 summary tab 读取本次测试 PASS/FAIL 的位置。`total_result_cell` 是读取总结果的位置。

最终返回和入库的结果字段固定为 `total_result`：

- 如果配置了 `total_result_cell`，`total_result` 使用这个 cell 读到的值。
- 如果没有配置 `total_result_cell`，`total_result` 使用 `result_cell` 读到的值。
- Unit Tracker append 需要总结果时，会检查 `total_result` 是否为空。

如果不同 OEM 的模板 cell 不一样，可以写成：

```yaml
result_cell:
  default: '!AQ11:AQ11'
  ultima: '!BO11:BO11'
total_result_cell: '!O11:O11'
```

### 6. uploader 注册和方法

文件：`backend/src/upload_handler/repositories/upload_repository.py`

当前只注册通用 uploader：

```python
uploaders={
    "spreadsheet": SpreadsheetUploader(context),
}
```

新增测试如果可以走通用 Spreadsheet 流程，`UPLOAD_HANDLER_CONFIGS` 直接配置：

```python
UploadHandlerConfig(
    uploader_key="spreadsheet",
    upload_method="upload",
    test_display_name="Diagnostic",
    new_filename_template="{sn}-Diagnostic-{timestamp}",
)
```

通用 uploader 已经从 catalog/YAML 读取这些差异：

- `new_filename` 模板
- `spreadsheet_strategy`
- `csv_target_sheet_name`
- `Range`
- `upload_flag_field`
- `result_cell`
- `total_result_cell`
- `sheet_link_index`
- `sheet_link_mode`

如果某个测试不是 CSV 写入模板、读取 result cell、copy summary、append Unit Tracker 这类 Spreadsheet 流程，才需要新增专门 uploader。

### 7. UploadResult 动态字段

文件：`backend/src/upload_handler/models/upload_result.py`

当前 `UploadResult` 已经支持动态上传状态字段。新增测试不需要再新增 `set_xxx()`，只要在 `product_catalog.UPLOAD_DATABASE_CONFIGS` 里配置上传状态字段：

```python
UploadDatabaseConfig(
    collection_workflow="robot_qc",
    test_field="diagnostic",
    upload_flag_field="diagnostic",
)
```

通用 workflow 会根据 `file_desc.upload_config_key` 读取这份配置，并调用：

```python
set_test_result(
    upload_flag_field="diagnostic",
    upload_ok=True,
    result="PASS",
)
```

最终返回和入库 dict 会包含 `diagnostic: true` 和 `total_result: PASS`。

## robot 5 个 combine 测试的最小接入清单

如果今天要接 robot 5 个测试，最小改动是：

- `models/domain.py`：补 5 个 `TestTypes`，除非复用已有类型。
- `product_catalog.py`：
  - robot serial prefix 到 `Productions.ROBOT`
  - `Productions.ROBOT` 的 `UPLOAD_PRODUCT_PROFILES`
  - 5 个测试名识别
  - 5 个 `get_upload_config_key` 分支
  - 5 个 `UPLOAD_HANDLER_CONFIGS`
  - 5 个 `UPLOAD_DATABASE_CONFIGS`
  - 1 个包含 5 个 key 的 `UPLOAD_CONFIG_COMBINES`
- `parsers/definitions.py`：5 个 `CsvParserDefinition`
- `upload_debug.yaml` / `upload_production.yaml`：5 个同名 YAML 配置块

完成这些后，上传到 Google Sheet、上库、combine 状态检查、Unit Tracker 最终 append、Slack 通知才能闭环跑通。

## 建议下一步

如果目标是让后续新测试尽量只改入口配置，优先改这三件事：

1. 把 `TestTypes` 和 `get_upload_config_key()` 继续数据化，减少新增测试时的代码分支。
2. 评估是否把 `parsers/definitions.py` 也迁入 catalog 或 YAML。
3. 只在遇到非 Spreadsheet 流程时新增专用 uploader。

这三步做完以后，新增 robot 5 个测试时，代码改动会收敛到 catalog、parser definition、YAML；再往后如果 parser definition 也 YAML 化，才是真正的“配置化新增测试”。

## 调试命令

只验证 CSV 是否能解析出 `file_desc`，不连接 MongoDB，不上传 Google Drive：

```bash
cd backend
uv run python -m src.upload_handler.upload --file /path/to/report.csv --csv
```

从项目根目录运行：

```bash
uv run python -m backend.src.upload_handler.upload --file /path/to/report.csv --csv
```

完整上传：

```bash
cd backend
uv run python -m src.upload_handler.upload --file /path/to/report.csv --zip /path/to/raw.zip
```
