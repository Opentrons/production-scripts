# 新增测试上传配置流程

这份文档记录手动新增一种测试 CSV 上传能力时，需要同步修改的配置和代码位置。

目标是让一个新的 CSV 测试可以完成完整链路：

1. 解析 CSV metadata、SN、OEM、测试类型、是否 finished。
2. 根据产品和测试类型找到 upload config key。
3. 读取 debug / production YAML。
4. 复制或复用 Google Spreadsheet 模板，写入 CSV。
5. 读取 result_cell / total_result_cell。
6. 写入 MongoDB。
7. 组合测试完成后更新 Unit Tracker。
8. API / Slack / 前端拿到统一上传结果。

## 准备信息

新增前先确认这些信息，不然后面容易配置到一半卡住：

- 产品型号：例如 `P1000M`、`P2HH`、`Robot`、`Gripper`。
- OEM / 产品类型：例如 `Opentrons`、`Ultima`、`Millipore`、`Sophion`。
- 测试类型：系统内部枚举值，例如 `assembly_qc`、`xy_calibration`。
- YAML config key：必须和 `upload_debug.yaml` / `upload_production.yaml` 中的 key 完全一致，例如 `robot_update_leveling`。
- CSV metadata 起止标记：例如 `META_DATA_START` 到 `META_DATA_END`。
- finished 判断方式：普通区间判断，还是自定义函数判断。
- SN 字段来源：例如 `test_tag`、`pipette`、`serial-number`、`test_device_id`。
- Google 模板 ID、目标 sheet name、写入列范围、结果单元格、Unit Tracker paste 信息。
- 是否属于 combined tests：多个 CSV 是否要落到同一个 Google Sheet / upload session。

如果是 combined tests，建议同一批一起加；如果不是 combined tests，就一个个加，减少配置交叉影响。

## 1. 填写 YAML 配置

文件：

- `backend/src/upload_handler/configs/upload_debug.yaml`
- `backend/src/upload_handler/configs/upload_production.yaml`

新增一个和 upload config key 同名的 YAML 节点。key 名后续必须同时出现在 parser definition 和 `product_catalog.py` 中。

常见字段：

```yaml
example_update_test:
- ifupdate: true
  spreadsheet_strategy: reuse_within_workflow
  ifcopytemplate:
    default: GOOGLE_TEMPLATE_ID
  csv_target_sheet_name: Raw Data
  result_cell: '!A1:A1'
  total_result_cell: '!B1:B1'
  Range:
  - A
  - B
  - C
  ifcopydata:
  - off/on: true
    summary_source_sheet_name: Summary
    copyRange:
    - '!A1:Z1'
  ifpaste:
  - off/on: true
    pastefileid: UNIT_TRACKER_FILE_ID
    pastelineRange:
      star: D
      end: Z
    unit_tracker_tab: ''
  unit_tracker_sheet:
    fumulu: DRIVE_FOLDER_ID
    1: ''
    2: ''
    3: MONTH_FOLDER_ID
  ifupdaterawdata:
    fumulu: DRIVE_FOLDER_ID
    1: ''
    2: ''
    3: MONTH_FOLDER_ID
```

配置注意：

- `spreadsheet_strategy: always_new` 表示每个 CSV 新建一个表格。
- `spreadsheet_strategy: reuse_within_workflow` 表示 combined workflow 内复用同一个表格。
- `result_cell` 是当前测试自己的结果。
- `total_result_cell` 是整个 workflow 的总结果；combined tests 通常需要。
- `Range` 是把 CSV 写入 template 的列范围。
- `ifcopydata.copyRange` 是从 template summary 区域复制到 Unit Tracker 的区域。
- `ifpaste.pastelineRange` 是 Unit Tracker 粘贴区间。
- debug 和 production 都要补；如果只补 debug，切回 production 后会找不到配置。

## 2. 检查产品名和测试类型

文件：

- `backend/src/upload_handler/models/domain.py`

检查是否需要新增：

- `Productions`：产品型号枚举。
- `ProductionTypes`：OEM / 产品类型枚举。
- `TestTypes`：测试类型枚举。

示例：

```python
class Productions(Enum):
    EXAMPLE = "Example"


class TestTypes(Enum):
    Example_Test = "example_test"
```

如果新增了产品型号，还要继续检查 `product_catalog.py` 里的这些位置：

- `SERIAL_NUMBER_MODEL_MAPPING`：SN 前缀如何映射到产品型号。
- `UPLOAD_PRODUCT_PROFILES`：产品使用哪个 uploader、MongoDB collection prefix 是什么。
- `get_model_from_serial_number()`：如果 SN 规则不是简单前缀，需要补解析逻辑。

如果新增了测试类型，还要检查：

- `get_test_type_from_name()`：CSV 里的 `test_name` 如何识别成内部 `TestTypes`。
- `get_upload_config_key()`：产品 + 测试类型如何映射到 YAML config key。

## 3. 增加上传返回结构

文件：

- `backend/src/upload_handler/models/upload_result.py`

公共字段已经在 `UploadResultFields` 中定义。新增测试如果有自己的非公共字段，需要补三个地方。

第一，给 `UploadResultFields` 增加上传状态字段：

```python
example_test: bool
```

第二，增加对应测试类型的返回结构，方便文档和类型提示：

```python
class ExampleTestUploadResult(UploadResultFields, total=False):
    """Example Test 上传返回值。"""

    example_test: bool
    total_result: str
```

第三，如果希望 `UploadResult` 明确暴露字段和 setter，也补到 dataclass：

```python
example_test: bool | None = None

def set_example_test(
    self,
    *,
    upload_ok: bool,
    result: str = "",
    total_result: str = "",
) -> UploadResult:
    return self.set_test_result(
        upload_flag_field="example_test",
        upload_ok=upload_ok,
        result=result,
        total_result=total_result,
    )
```

当前通用上传流程实际会调用 `set_test_result(upload_flag_field=...)`，所以即使没有专用 setter，只要 `product_catalog.py` 的 `upload_flag_field` 配对正确，也可以通过 `extra_fields` 返回。但为了可读性和长期维护，建议把常用测试字段显式写出来。

API 层的 `UploadApiResponse` 通常不用改，它是对外统一响应结构。

## 4. 更新 Parser Definitions

文件：

- `backend/src/upload_handler/parsers/definitions.py`

这里负责定义 CSV 如何解析。

常用定义由这些结构组成：

- `CsvSectionDefinition`：metadata / config 区域起止标记。
- `CsvFinishDefinition`：普通 finished 判断。
- `CsvFieldDefinition`：SN、OEM、test name 字段来源。
- `CsvParserDefinition`：最终绑定 upload config key 和测试类型。

普通测试可以复用或新建 definition：

```python
EXAMPLE_TEST_DEFINITION = {
    "metadata_range": CsvSectionDefinition("META_DATA_START", "META_DATA_END"),
    "finish_range": CsvFinishDefinition(
        "RESULTS_OVERVIEW_START",
        "RESULTS_OVERVIEW_END",
    ),
    "sn": CsvFieldDefinition("test_tag", extra_words=("-qc", "-recorder", "-results")),
    "kind": CsvFieldDefinition(("operator-name", "test_operator")),
    "test_name": CsvFieldDefinition("test_name"),
}
```

如果普通 `CsvFinishDefinition` 无法判断 finished，可以用函数：

```python
def evaluate_example_finished(rows: list[list[Any]]) -> bool:
    return len(rows) > 100 and all(any(cell for cell in row) for row in rows[:100])


EXAMPLE_TEST_DEFINITION = {
    "metadata_range": CsvSectionDefinition("METADATA", "date"),
    "finish_range": evaluate_example_finished,
    "sn": CsvFieldDefinition("serial-number"),
    "kind": CsvFieldDefinition(("operator-name", "test_operator")),
    "test_name": CsvFieldDefinition("test-name"),
}
```

最后把 config key 加进 `PARSER_DEFINITIONS`：

```python
PARSER_DEFINITIONS: dict[str, CsvParserDefinition] = {
    "example_update_test": CsvParserDefinition(
        upload_config_key="example_update_test",
        test_type=TestTypes.Example_Test,
        **EXAMPLE_TEST_DEFINITION,
    ),
}
```

注意：

- `upload_config_key` 必须和 YAML key 一致。
- `test_type` 必须是 `TestTypes` 枚举。
- `sn` 支持单个字段，也支持多个字段 fallback。
- 如果 CSV metadata 里某些字段不可信，可以通过手动上传 `meta` 覆盖，例如 `{"test_device": "xxx"}`。

## 5. 增加 Product Catalog 配置

文件：

- `backend/src/upload_handler/product_catalog.py`

这是上传路由表，负责把“产品 + 测试类型”映射到具体 YAML、数据库、workflow。

至少检查这些位置。

### 5.1 SN 到产品映射

如果新产品 SN 有新前缀，补 `SERIAL_NUMBER_MODEL_MAPPING`：

```python
SERIAL_NUMBER_MODEL_MAPPING = {
    "EX": Productions.EXAMPLE,
}
```

### 5.2 产品 profile

如果是新产品，补 `UPLOAD_PRODUCT_PROFILES`：

```python
UPLOAD_PRODUCT_PROFILES = {
    Productions.EXAMPLE: UploadProductProfile(
        uploader_key="spreadsheet",
        collection_prefix="example",
    ),
}
```

最终 MongoDB collection 名会由 `collection_prefix` 和 `collection_workflow` 组合。

### 5.3 Handler config

新增 `UPLOAD_HANDLER_CONFIGS`：

```python
"example_update_test": UploadHandlerConfig(
    uploader_key="spreadsheet",
    upload_method="upload",
    test_display_name="Example Test",
    new_filename_template="{sn}-Example-Test-{timestamp}",
),
```

常用字段：

- `uploader_key`：目前通用是 `spreadsheet`。
- `upload_method`：目前通用是 `upload`。
- `test_display_name`：前端 / Slack / API 展示名。
- `new_filename_template`：复制模板后的 Google Sheet 文件名。
- `timestamp_format`：文件名时间格式。
- `tracker_sheet_name_template`：Unit Tracker tab 名规则。
- `sheet_link_index` / `sheet_link_mode`：用于特殊模板中写回 sheet link。

### 5.4 Database config

新增 `UPLOAD_DATABASE_CONFIGS`：

```python
"example_update_test": UploadDatabaseConfig(
    collection_workflow="example",
    test_field="example_test",
    upload_flag_field="example_test",
),
```

字段含义：

- `collection_workflow`：MongoDB collection 后缀 / workflow 类型。
- `test_field`：combined session 里当前测试的字段名。
- `upload_flag_field`：上传结果里判断当前测试是否成功的 bool 字段。

### 5.5 测试名识别

在 `get_test_type_from_name()` 里补 test name 识别：

```python
if "example-test" in test_name_lower:
    return TestTypes.Example_Test.value
```

顺序很重要：更具体的规则放在更通用规则前面。例如 robot assembly 要放在普通 assembly 前面。

### 5.6 产品 + 测试类型到 config key

在 `get_upload_config_key()` 里补映射：

```python
if production == Productions.EXAMPLE:
    if normalized_test_type == TestTypes.Example_Test:
        return "example_update_test"
```

如果这里没补，解析 metadata 后会报：

```text
Upload config key not found: model=..., test_type=...
```

## Combined Tests 配置规则

如果多个 CSV 属于同一个测试流程，例如 Assembly QC + Current/Speed，或 Robot 多个 QC 项目，需要额外配置 `UPLOAD_CONFIG_COMBINES`。

文件：

- `backend/src/upload_handler/product_catalog.py`

示例：

```python
UPLOAD_CONFIG_COMBINES: list[tuple[str, ...]] = [
    (
        "example_update_a",
        "example_update_b",
        "example_update_c",
    ),
]
```

规则：

- tuple 里的 key 必须全部存在于 YAML、`UPLOAD_HANDLER_CONFIGS`、`UPLOAD_DATABASE_CONFIGS`、`PARSER_DEFINITIONS`。
- tuple 顺序会参与 workflow 名生成，新增后不要随意重排。
- 同一个 combined workflow 的 YAML 通常使用 `spreadsheet_strategy: reuse_within_workflow`。
- 每个测试的 `UPLOAD_DATABASE_CONFIGS.test_field` 必须不同。
- 每个测试的 `UPLOAD_DATABASE_CONFIGS.upload_flag_field` 要能在 `UploadResult` 里找到或通过 `extra_fields` 返回。
- 如果所有测试完成后才允许 Unit Tracker 粘贴，配置 `total_result_cell`，并确认最终模板能计算总结果。
- 不完整 combined workflow 会被 session repository 识别为缺项，返回 `missing_tests` 和 `Waiting for combined tests: ...`。

建议：如果确定某批 CSV 是 combined tests，一次性把整组都加进去；只加其中一个容易导致 Google Sheet 能生成，但 Unit Tracker 长期等待缺失测试。

## 手动上传验证

推荐先用 debug 环境和手动上传接口验证。

单个 CSV：

```bash
cd backend
uv run python data_center_client.py \
  --base-url http://127.0.0.1:8090 \
  --csv /path/to/test.csv \
  --skip-health
```

需要一起上传原始目录文件：

```bash
cd backend
uv run python data_center_client.py \
  --base-url http://127.0.0.1:8090 \
  --csv /path/to/test.csv \
  --all-files \
  --skip-health
```

metadata 需要手动覆盖时：

```bash
cd backend
uv run python data_center_client.py \
  --base-url http://127.0.0.1:8090 \
  --csv /path/to/test.csv \
  --meta-json '{"test_device":"FLXU3020260603002"}' \
  --skip-health
```

验证重点：

- `success` 是否为 `true`。
- `production_name` 是否正确。
- `test_type` 是否正确。
- `test_result` 是否正确。
- `sn` 是否正确。
- `csv_link` 是否生成。
- `unit_tracker_status` 是否符合预期。
- combined tests 是否返回合理的 `missing_tests`。
- MongoDB collection 是否写入正确。

## 代码检查

改完后至少执行：

```bash
cd backend
uv run python -m py_compile \
  src/upload_handler/models/domain.py \
  src/upload_handler/models/upload_result.py \
  src/upload_handler/parsers/definitions.py \
  src/upload_handler/product_catalog.py
```

如果只想先验证解析，不想真的上传 Google，可以直接走 parser：

```bash
cd backend
uv run python - <<'PY'
from upload_handler.models import FileDescription

path = "/path/to/test.csv"
desc = FileDescription.build(path)
print(desc.to_dict() if desc else "parse failed")
PY
```

重点看：

- `upload_config_key`
- `finished`
- `sn`
- `model`
- `kind_oem_type`
- `test_type`
- `error`

## 常见问题

`Upload config key not found`

- 检查 `get_test_type_from_name()` 是否能识别 CSV 的 `test_name`。
- 检查 `get_upload_config_key()` 是否补了产品 + 测试类型映射。
- 检查 SN 是否能通过 `SERIAL_NUMBER_MODEL_MAPPING` 识别产品。

`Parser definition not found`

- 检查 `PARSER_DEFINITIONS` 是否包含 YAML key。
- 检查 key 拼写是否和 YAML 完全一致。

`Upload config 'xxx' is missing`

- 检查当前环境使用的是 `upload_debug.yaml` 还是 `upload_production.yaml`。
- debug 和 production 是否都补了对应 key。

`File is not finished`

- 检查 `finish_range` 起止标记是否正确。
- 如果 CSV 不是标准结果区间，改为自定义 finish 判断函数。
- 对于异常 CSV，确认是否应该记入失败历史，而不是跳过上传。

`Unit Tracker 一直 Waiting for combined tests`

- 检查 `UPLOAD_CONFIG_COMBINES` 是否包含整组 key。
- 检查每个测试是否写入同一个 workflow。
- 检查 `UPLOAD_DATABASE_CONFIGS.test_field` 是否和 expected missing tests 对应。
- 检查每个测试的 upload flag 是否为 `True`。

`返回字段缺失`

- 非公共字段只在对应测试设置后才会返回。
- 检查 `UPLOAD_DATABASE_CONFIGS.upload_flag_field`。
- 检查 `UploadResult.set_test_result()` 是否被调用。
- 如果需要显式类型提示，补 `UploadResultFields` 和对应测试专用 TypedDict。
