# Upload 配置说明

本文档说明当前上传链路的配置规则，以及接入一个新的 CSV 测试报告时需要修改哪些文件、函数和配置。

上传配置的主线是 `upload_config_key`。同一个 key 必须同时出现在：

- `backend/src/upload_handler/product_catalog.py`
- `backend/src/upload_handler/parsers/definitions.py`
- `backend/src/upload_handler/configs/upload_debug.yaml`
- `backend/src/upload_handler/configs/upload_production.yaml`

## 当前链路

CSV 文件进入系统后的解析和上传顺序如下：

1. `FileDescription.build(file_path)`
2. `parsers/registry.py::extract_csv(file_path)`
3. `parsers/csv_common.py::extract_meta_data_from_csv(file_path)`
4. `product_catalog.get_upload_config_key_from_metadata(metadata)`
5. `product_catalog.get_parser_definition(upload_config_key)`
6. `parsers/csv_common.py::parse_csv_by_definition(file_path, definition)`
7. `repositories/upload_repository.py::UploadRepository.upload(file_desc)`
8. `uploaders/spreadsheet_uploader.py::SpreadsheetUploader.upload(file_desc)`
9. `uploaders/workflows.py::SpreadsheetUploadWorkflow.run(plan)`

当前通用上传流程覆盖这类测试：

- 把 CSV 写入 Google Spreadsheet 模板。
- 从模板 summary tab 读取结果。
- copy summary row。
- 写入业务 MongoDB 和 `upload_sessions`。
- combine 测试全部完成后 append Unit Tracker。
- 上传 raw zip 到 Drive 月份文件夹。

如果新测试也属于这类 Spreadsheet 流程，只需要补 catalog、parser definition 和 YAML 配置，不需要新增 uploader。

## 当前配置 Key

| Key | 用途 |
| --- | --- |
| `1ch_update_volume` | 1ch Gravimetric |
| `8ch_update_volume` | 8ch Gravimetric |
| `1ch_update_assembly_qc` | 1ch Assembly QC |
| `8ch_update_assembly_qc` | 8ch Assembly QC |
| `1ch_update_current_speed` | 1ch Current Speed |
| `8ch_update_current_speed` | 8ch Current Speed |
| `96_p200_update_qc` | 96ch P200 Assembly QC |
| `96_p1000_update_qc` | 96ch P1000 Assembly QC |
| `8ch_update_burn_in_result` | 8ch Burn-in result |
| `8ch_update_burn_in_records` | 8ch Burn-in recorder |

命名约定：

- key 必须包含 `_update_`。
- `_update_` 后面的字符串会作为默认测试字段名来源。
- 例如 `robot_update_diagnostic` 的测试字段是 `diagnostic`。

## Catalog 配置

文件：`backend/src/upload_handler/product_catalog.py`

### `SERIAL_NUMBER_MODEL_MAPPING`

用于通过 SN 前缀识别产品型号。

```python
SERIAL_NUMBER_MODEL_MAPPING = {
    "P1KM": Productions.P1000M,
}
```

新产品如果有新 SN 前缀，需要在这里增加映射。

### `UPLOAD_PRODUCT_PROFILES`

定义产品上传 profile。

```python
UPLOAD_PRODUCT_PROFILES = {
    Productions.P1000M: UploadProductProfile(
        uploader_key="spreadsheet",
        collection_prefix="pipette_8ch",
    ),
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `uploader_key` | 当前 Spreadsheet 流程统一使用 `spreadsheet` |
| `collection_prefix` | MongoDB 业务集合名前缀 |

业务集合名由 `collection_prefix + "_" + collection_workflow` 组成。例如：

```text
pipette_8ch_assembly_qc
```

### `get_test_type_from_name(test_name)`

通过 CSV metadata 里的 `test_name` 识别测试类型。

```python
def get_test_type_from_name(test_name: str) -> str:
    test_name_lower = str(test_name).lower()
    if "diagnostic" in test_name_lower:
        return TestTypes.Robot_Diagnostic.value
    return "NA"
```

如果新测试语义不属于已有 `TestTypes`，先在 `backend/src/upload_handler/models/domain.py` 的 `TestTypes` 中增加枚举。

### `get_upload_config_key(model, test_type)`

通过产品型号和测试类型返回 YAML key。

```python
def get_upload_config_key(model: str, test_type: str | TestTypes | None) -> str:
    production = Productions.from_string(model)
    normalized_test_type = normalize_test_type(test_type)

    if production == Productions.ROBOT:
        if normalized_test_type == TestTypes.Robot_Diagnostic:
            return "robot_update_diagnostic"

    raise ValueError(f"Upload config key not found: model={model}, test_type={test_type}")
```

这是 CSV 解析和上传配置绑定的入口。新测试必须能从这里拿到唯一的 `upload_config_key`。

### `UPLOAD_HANDLER_CONFIGS`

定义上传方法层配置。

```python
UPLOAD_HANDLER_CONFIGS = {
    "robot_update_diagnostic": UploadHandlerConfig(
        uploader_key="spreadsheet",
        upload_method="upload",
        test_display_name="Diagnostic",
        new_filename_template="{sn}-Diagnostic-{timestamp}",
        timestamp_format="%Y%m%d%H%M%S",
        tracker_sheet_name_template="{oem} {model}",
        sheet_link_index=0,
        sheet_link_mode="insert",
    ),
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `uploader_key` | 当前通用 Spreadsheet 上传使用 `spreadsheet` |
| `upload_method` | 当前通用 Spreadsheet 上传使用 `upload` |
| `test_display_name` | API、Slack、日志里的测试展示名 |
| `new_filename_template` | 复制模板后的 Google Sheet 文件名模板 |
| `timestamp_format` | `{timestamp}` 的格式 |
| `tracker_sheet_name_template` | `unit_tracker_tab` 为空时的默认 tab 名模板 |
| `sheet_link_index` | Unit Tracker row 中 sheet link 写入位置 |
| `sheet_link_mode` | `insert` 表示插入链接列，`set` 表示覆盖该列 |

可用模板变量：

- `{sn}`
- `{model}`
- `{timestamp}`
- `{config_key}`
- `{test_display_name}`
- `{test_slug}`

### `UPLOAD_DATABASE_CONFIGS`

定义数据库写入和 combine 状态字段。

```python
UPLOAD_DATABASE_CONFIGS = {
    "robot_update_diagnostic": UploadDatabaseConfig(
        collection_workflow="robot_qc",
        test_field="diagnostic",
        upload_flag_field="diagnostic",
    ),
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `collection_workflow` | MongoDB 业务集合名后缀 |
| `test_field` | `upload_sessions.tests.<test_field>` 里的测试名 |
| `upload_flag_field` | 上传结果 dict 里的布尔状态字段 |

测试结果固定写入 `total_result`。单一测试和 combine 测试都用这个字段，前端统计也只需要读 `total_result`。

### `UPLOAD_CONFIG_COMBINES`

定义多个测试是否共享同一条 workflow、同一个 Google Sheet 和同一次 Unit Tracker append。

```python
UPLOAD_CONFIG_COMBINES = [
    ("1ch_update_assembly_qc", "1ch_update_current_speed"),
    ("8ch_update_assembly_qc", "8ch_update_current_speed"),
    ("8ch_update_burn_in_result", "8ch_update_burn_in_records"),
]
```

规则：

- 每个 tuple 是一个 workflow 组合。
- tuple 顺序参与 workflow 名生成，配置后保持稳定。
- 同组测试按 `sn + model + workflow` 复用 Google Sheet。
- 同组测试都上传成功后，才 append Unit Tracker。
- 不在任何 tuple 中的 key 以自身作为独立 workflow。

例如：

```python
("robot_update_diagnostic", "robot_update_current", "robot_update_motion")
```

这三个测试会进入同一个 workflow：

```text
robot_update_diagnostic__robot_update_current__robot_update_motion
```

## Parser Definition

文件：`backend/src/upload_handler/parsers/definitions.py`

每个 `upload_config_key` 都需要一个 `CsvParserDefinition`。

```python
ROBOT_DIAGNOSTIC_DEFINITION = {
    "metadata_range": CsvSectionDefinition("META_DATA_START", "META_DATA_END"),
    "finish_range": CsvFinishDefinition(
        "RESULTS_OVERVIEW_START",
        "RESULTS_OVERVIEW_END",
        mode="all_present",
        key_contains_any=("diagnostic",),
        ignore_keys=("optional_note",),
    ),
    "sn": CsvFieldDefinition("test_tag", extra_words=("-results",)),
    "kind": CsvFieldDefinition("test_operator"),
    "test_name": CsvFieldDefinition("test_name"),
}

PARSER_DEFINITIONS["robot_update_diagnostic"] = CsvParserDefinition(
    upload_config_key="robot_update_diagnostic",
    test_type=TestTypes.Robot_Diagnostic,
    **ROBOT_DIAGNOSTIC_DEFINITION,
)
```

### `CsvSectionDefinition`

描述 CSV 中某个区间的起止标记和 key/value 所在列。

```python
CsvSectionDefinition(
    start="META_DATA_START",
    end="META_DATA_END",
    key_name_loc="B",
    value_loc="C",
)
```

### `CsvFieldDefinition`

描述从 metadata 或 config 区间读取某个字段。

```python
CsvFieldDefinition(
    key_name=("operator-name", "test_operator"),
    key_name_loc="B",
    value_loc="C",
    source="metadata",
    extra_words=("-qc", "-recorder", "-results"),
)
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `key_name` | key 名，可以是字符串或多个候选 key |
| `source` | `metadata` 或 `config` |
| `extra_words` | 从字段值中移除的后缀，常用于清理 SN |

### `CsvFinishDefinition`

描述如何判断 CSV 报告是否完整跑完。

```python
CsvFinishDefinition(
    start="RESULTS_OVERVIEW_START",
    end="RESULTS_OVERVIEW_END",
    mode="all_present",
    danger_words=("None", ""),
    key_contains_all=(),
    key_contains_any=("0.75", "1.0"),
    ignore_keys=("RESULT_ENVIRONMENT-SENSOR",),
)
```

当前完成度判断是“报告是否跑完”，不是“测试是否 PASS”。

规则：

- `mode="all_present"`：被检查的 value 不能是 `None` 或空字符串。
- `mode="all_match"`：被检查的 value 需要匹配 `expected_word`。
- `key_contains_all`：key 必须包含所有词才参与检查。
- `key_contains_any`：key 包含任意一个词就参与检查。
- `ignore_keys`：命中的 key 不参与完成度判断。
- `FAIL` 表示测试失败，不表示报告未完成。

### Metadata 首次读取

首次读取发生在 `csv_common.extract_meta_data_from_csv(file_path)`：

- 固定按 B 列读取 key，C 列读取 value。
- 优先通过 metadata 起止标记找到区间。
- metadata 区间找不到时，只扫描 CSV 前 10 行。
- `test-name`、`test_name`、`test name` 会统一写入 `metadata["test_name"]`。

这个阶段只负责拿到足够信息来推导 `upload_config_key`。

## YAML 配置

文件：

- `backend/src/upload_handler/configs/upload_debug.yaml`
- `backend/src/upload_handler/configs/upload_production.yaml`

每个 key 的值必须是 list，并且第一个元素是 dict：

```yaml
robot_update_diagnostic:
- ifupdate: true
  spreadsheet_strategy: reuse_within_workflow
```

`ConfigRepository.get_upload_config(key)` 会读取这个 list 的第一个 dict。

### 顶层字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `ifupdate` | 是 | 是否启用该上传配置 |
| `spreadsheet_strategy` | 是 | `reuse_within_workflow` 或 `always_new` |
| `ifcopytemplate` | 是 | 模板 Spreadsheet ID 配置 |
| `csv_target_sheet_name` | 是 | 原始 CSV 写入模板中的目标 tab |
| `result_cell` | 是 | 从模板 summary tab 读取本次测试结果的位置 |
| `total_result_cell` | 否 | 从模板 summary tab 读取总结果的位置 |
| `Range` | 是 | CSV 写入列范围，用于决定写入宽度 |
| `ifcopydata` | 是 | 从工作表复制 summary/result row |
| `ifpaste` | 是 | 粘贴到 Unit Tracker 的目标配置 |
| `unit_tracker_sheet` | 是 | 测试数据 Spreadsheet 移动到的月份文件夹 |
| `ifupdaterawdata` | 是 | raw zip 上传到的月份文件夹 |

### `spreadsheet_strategy`

| 值 | 行为 |
| --- | --- |
| `reuse_within_workflow` | combine workflow 中优先复用已有 sheet，没有可复用 sheet 时复制模板 |
| `always_new` | 每次上传都复制新模板 |

### `ifcopytemplate`

推荐结构：

```yaml
ifcopytemplate:
  default: DEFAULT_TEMPLATE_SPREADSHEET_ID
  ultima: ULTIMA_TEMPLATE_SPREADSHEET_ID
  millipore: MILLIPORE_TEMPLATE_SPREADSHEET_ID
```

规则：

- 先按 `kind_oem_type` 小写匹配，例如 `ultima`、`millipore`。
- 匹配不到时使用 `default`。
- 只需要一套模板时只配置 `default`。

### `result_cell` / `total_result_cell`

`result_cell` 读取本次测试结果。`total_result_cell` 读取 workflow 总结果。

```yaml
result_cell: '!P11:P11'
total_result_cell: '!O11:O11'
```

如果不同 OEM 使用不同 cell，可以写成 dict：

```yaml
result_cell:
  default: '!AQ11:AQ11'
  ultima: '!BO11:BO11'
total_result_cell: '!O11:O11'
```

写入结果的规则：

- 配置 `total_result_cell` 时，`total_result` 使用该 cell 的值。
- 不配置 `total_result_cell` 时，`total_result` 使用 `result_cell` 的值。
- Unit Tracker append 需要 `total_result` 非空。
- `result_cell` 和 `total_result_cell` 都从 `ifcopydata.summary_source_sheet_name` 指定的 tab 读取。

### `ifcopydata`

```yaml
ifcopydata:
- off/on: true
  summary_source_sheet_name: Diagnostic
  copyRange:
  - '!A11:Z11'
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `off/on` | 是否执行该 copy 配置 |
| `summary_source_sheet_name` | 从复制出的工作 Spreadsheet 的哪个 tab 读取 summary/result |
| `copyRange` | append Unit Tracker 时复制的 row range |
| `UltimacopyRange` | Ultima OEM 使用的 row range |

### `ifpaste`

```yaml
ifpaste:
- off/on: true
  pastefileid: UNIT_TRACKER_SPREADSHEET_ID
  pastelineRange:
    star: D
    end: AO
  unit_tracker_tab: ''
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `off/on` | 是否执行粘贴 |
| `pastefileid` | Unit Tracker Spreadsheet ID |
| `Ultimapastefileid` | Ultima OEM 使用的 Unit Tracker Spreadsheet ID |
| `pastelineRange.star` | append row 起始列 |
| `pastelineRange.end` | append row 结束列 |
| `unit_tracker_tab` | 目标 tab；为空时使用 `tracker_sheet_name_template` |
| `UltimapastelineRange` | Ultima OEM 使用的 append range |

`unit_tracker_tab` 为空时，默认 tab 由 `UploadHandlerConfig.tracker_sheet_name_template` 生成，当前默认是：

```text
{oem} {model}
```

### 月份文件夹

`unit_tracker_sheet` 和 `ifupdaterawdata` 都按当前月份读取。

普通结构：

```yaml
unit_tracker_sheet:
  fumulu: ROOT_FOLDER_ID
  1: JAN_FOLDER_ID
  2: FEB_FOLDER_ID
  3: MAR_FOLDER_ID
```

按 model 分组的结构：

```yaml
unit_tracker_sheet:
  P1KH:
    fumulu: ROOT_FOLDER_ID
    1: JAN_FOLDER_ID
  P2HH:
    fumulu: ROOT_FOLDER_ID
    1: JAN_FOLDER_ID
```

当前月份由运行时计算，只读取 `1` 到 `12` 中对应的月份 key。

## YAML 模板

### 独立测试

```yaml
robot_update_diagnostic:
- ifupdate: true
  spreadsheet_strategy: always_new
  ifcopytemplate:
    default: TEMPLATE_SPREADSHEET_ID
  csv_target_sheet_name: Diagnostic Raw Data
  result_cell: '!P11:P11'
  Range:
  - A
  - B
  - C
  ifcopydata:
  - off/on: true
    summary_source_sheet_name: Diagnostic
    copyRange:
    - '!A11:Z11'
  ifpaste:
  - off/on: true
    pastefileid: UNIT_TRACKER_SPREADSHEET_ID
    pastelineRange:
      star: A
      end: Z
    unit_tracker_tab: ''
  unit_tracker_sheet:
    fumulu: ROOT_FOLDER_ID
    1: JAN_FOLDER_ID
    2: FEB_FOLDER_ID
    3: MAR_FOLDER_ID
    4: APR_FOLDER_ID
    5: MAY_FOLDER_ID
    6: JUN_FOLDER_ID
    7: JUL_FOLDER_ID
    8: AUG_FOLDER_ID
    9: SEP_FOLDER_ID
    10: OCT_FOLDER_ID
    11: NOV_FOLDER_ID
    12: DEC_FOLDER_ID
  ifupdaterawdata:
    fumulu: ROOT_FOLDER_ID
    1: JAN_FOLDER_ID
    2: FEB_FOLDER_ID
    3: MAR_FOLDER_ID
    4: APR_FOLDER_ID
    5: MAY_FOLDER_ID
    6: JUN_FOLDER_ID
    7: JUL_FOLDER_ID
    8: AUG_FOLDER_ID
    9: SEP_FOLDER_ID
    10: OCT_FOLDER_ID
    11: NOV_FOLDER_ID
    12: DEC_FOLDER_ID
```

### Combine 测试

```yaml
robot_update_current:
- ifupdate: true
  spreadsheet_strategy: reuse_within_workflow
  ifcopytemplate:
    default: TEMPLATE_SPREADSHEET_ID
  csv_target_sheet_name: Current Raw Data
  result_cell: '!P11:P11'
  total_result_cell: '!O11:O11'
  Range:
  - A
  - B
  - C
  - D
  ifcopydata:
  - off/on: true
    summary_source_sheet_name: Robot QC
    copyRange:
    - '!A11:Z11'
  ifpaste:
  - off/on: true
    pastefileid: UNIT_TRACKER_SPREADSHEET_ID
    pastelineRange:
      star: A
      end: Z
    unit_tracker_tab: ''
  unit_tracker_sheet:
    1: JAN_FOLDER_ID
  ifupdaterawdata:
    1: JAN_FOLDER_ID
```

combine 测试还需要在 `UPLOAD_CONFIG_COMBINES` 中配置同组 key。

## 新 CSV 测试接入清单

### 1. 确认产品和测试类型

文件：`backend/src/upload_handler/models/domain.py`

需要确认或新增：

- `Productions`
- `TestTypes`

示例：

```python
class Productions(Enum):
    ROBOT = "Robot"

class TestTypes(Enum):
    Robot_Diagnostic = "robot_diagnostic"
```

已有产品或已有测试语义可以复用，不需要新增 enum。

### 2. 配置 catalog

文件：`backend/src/upload_handler/product_catalog.py`

需要检查或修改：

1. `SERIAL_NUMBER_MODEL_MAPPING`
2. `UPLOAD_PRODUCT_PROFILES`
3. `get_test_type_from_name(test_name)`
4. `get_upload_config_key(model, test_type)`
5. `UPLOAD_HANDLER_CONFIGS`
6. `UPLOAD_DATABASE_CONFIGS`
7. `UPLOAD_CONFIG_COMBINES`

最小示例：

```python
SERIAL_NUMBER_MODEL_MAPPING = {
    "RBOT": Productions.ROBOT,
}

UPLOAD_PRODUCT_PROFILES = {
    Productions.ROBOT: UploadProductProfile(
        uploader_key="spreadsheet",
        collection_prefix="robot",
    ),
}

def get_test_type_from_name(test_name: str) -> str:
    test_name_lower = str(test_name).lower()
    if "diagnostic" in test_name_lower:
        return TestTypes.Robot_Diagnostic.value
    return "NA"

def get_upload_config_key(model: str, test_type: str | TestTypes | None) -> str:
    production = Productions.from_string(model)
    normalized_test_type = normalize_test_type(test_type)

    if production == Productions.ROBOT:
        if normalized_test_type == TestTypes.Robot_Diagnostic:
            return "robot_update_diagnostic"

    raise ValueError(f"Upload config key not found: model={model}, test_type={test_type}")

UPLOAD_HANDLER_CONFIGS = {
    "robot_update_diagnostic": UploadHandlerConfig(
        uploader_key="spreadsheet",
        upload_method="upload",
        test_display_name="Diagnostic",
        new_filename_template="{sn}-Diagnostic-{timestamp}",
    ),
}

UPLOAD_DATABASE_CONFIGS = {
    "robot_update_diagnostic": UploadDatabaseConfig(
        collection_workflow="robot_qc",
        test_field="diagnostic",
        upload_flag_field="diagnostic",
    ),
}
```

如果新测试需要和其它测试合并：

```python
UPLOAD_CONFIG_COMBINES = [
    ("robot_update_diagnostic", "robot_update_current", "robot_update_motion"),
]
```

### 3. 配置 parser definition

文件：`backend/src/upload_handler/parsers/definitions.py`

需要增加：

- 一个 definition dict。
- 一个 `PARSER_DEFINITIONS[upload_config_key]` 条目。

示例：

```python
ROBOT_DIAGNOSTIC_DEFINITION = {
    "metadata_range": CsvSectionDefinition("META_DATA_START", "META_DATA_END"),
    "finish_range": CsvFinishDefinition(
        "RESULTS_OVERVIEW_START",
        "RESULTS_OVERVIEW_END",
        mode="all_present",
        ignore_keys=("optional_note",),
    ),
    "sn": CsvFieldDefinition("test_tag", extra_words=("-results",)),
    "kind": CsvFieldDefinition("test_operator"),
    "test_name": CsvFieldDefinition("test_name"),
}

PARSER_DEFINITIONS["robot_update_diagnostic"] = CsvParserDefinition(
    upload_config_key="robot_update_diagnostic",
    test_type=TestTypes.Robot_Diagnostic,
    **ROBOT_DIAGNOSTIC_DEFINITION,
)
```

parser 最终需要输出的核心字段由 `parse_csv_by_definition()` 统一生成：

| 字段 | 说明 |
| --- | --- |
| `upload_config_key` | YAML / catalog / parser 共同使用的 key |
| `sn` | 设备序列号 |
| `model` | 产品型号 |
| `kind_stage_type` | 生产阶段，默认 `Production` |
| `kind_oem_type` | OEM 类型，默认 `Opentrons` |
| `test_type` | `TestTypes` |
| `finished` | CSV 报告是否完整跑完 |

### 4. 配置两份 YAML

文件：

- `backend/src/upload_handler/configs/upload_debug.yaml`
- `backend/src/upload_handler/configs/upload_production.yaml`

两份 YAML 都需要新增同名 key：

```yaml
robot_update_diagnostic:
- ifupdate: true
  spreadsheet_strategy: always_new
  ifcopytemplate:
    default: TEMPLATE_SPREADSHEET_ID
  csv_target_sheet_name: Diagnostic Raw Data
  result_cell: '!P11:P11'
  Range:
  - A
  - B
  - C
  ifcopydata:
  - off/on: true
    summary_source_sheet_name: Diagnostic
    copyRange:
    - '!A11:Z11'
  ifpaste:
  - off/on: true
    pastefileid: UNIT_TRACKER_SPREADSHEET_ID
    pastelineRange:
      star: A
      end: Z
    unit_tracker_tab: ''
  unit_tracker_sheet:
    1: JAN_FOLDER_ID
  ifupdaterawdata:
    1: JAN_FOLDER_ID
```

### 5. 判断是否需要新 uploader

当前默认不需要新 uploader。

只有当新测试不是下面这条通用链路时，才需要新增 uploader：

```text
CSV -> Google Sheet 模板 -> result cell -> copy summary row -> MongoDB -> Unit Tracker -> raw zip
```

如果需要新增 uploader，需要修改：

- `backend/src/upload_handler/uploaders/`
- `backend/src/upload_handler/repositories/upload_repository.py::default_upload_repositories()`
- `product_catalog.UPLOAD_HANDLER_CONFIGS` 中对应的 `uploader_key` 和 `upload_method`

## 调试命令

只解析 CSV，不上传、不写数据库：

```bash
cd backend
uv run python -m src.upload_handler.upload --file datas/example.csv --csv
```

执行完整上传：

```bash
cd backend
uv run python -m src.upload_handler.upload --file datas/example.csv
```

检查配置 key 是否能读取：

```bash
cd backend
PYTHONPATH=src uv run python - <<'PY'
from upload_handler.repositories.config_repository import ConfigRepository

config = ConfigRepository.from_environment()
print(config.get_upload_config("robot_update_diagnostic"))
PY
```

编译检查：

```bash
cd backend
uv run python -m compileall src/upload_handler
```

## 接入完成标准

新 CSV 测试接入后，需要满足：

- `--csv` 能输出正确的 `file_desc`。
- `file_desc.upload_config_key` 能匹配 catalog、parser definition 和 YAML。
- `file_desc.sn`、`model`、`test_type`、`kind_oem_type` 正确。
- `finished` 能准确表达报告是否跑完。
- 上传结果 dict 包含当前测试的 `upload_flag_field: true`。
- 上传结果 dict 包含 `total_result`。
- combine 测试未全部完成时，`unit_tracker_status` 说明缺少哪些测试。
- combine 测试全部完成后，只 append 一次 Unit Tracker。
