# Upload File Description Fields

`FileDescription` is the normalized metadata object created for every upload CSV before Google Sheets, Drive, and database work starts. It is built by `FileDescription.build()` from the CSV parser result, then enriched with upload context such as raw-data zip, config environment, and finished-check settings.

## Core Identity

| Field | Type | Source | Meaning |
| --- | --- | --- | --- |
| `file_path` | string | upload request | Server-local CSV path being uploaded. |
| `file_name` | string | CSV parser default | Basename of the CSV file. |
| `sn` | string | parser definition | Unit serial number used as the primary upload identity. |
| `model` | string | serial-number mapping | Product model, for example `P1000M`, `P50S`, `Robot`, `P1KH`. |
| `test_type` | string or `TestTypes` | parser definition | Normalized test type such as `assembly_qc`, `gravimetric`, or `leveling_test`. |
| `upload_config_key` | string | parser registry | YAML config key, for example `8ch_update_assembly_qc`. |
| `upload_uploader_key` | string | product catalog | Uploader implementation key. Current production uploads use `spreadsheet`. |

## OEM And Environment

| Field | Type | Source | Meaning |
| --- | --- | --- | --- |
| `kind_oem_type` | string | CSV operator/kind field | Raw OEM parsed from CSV text. Older code still reads this field. |
| `oem` | string | normalized from `oem` override or `kind_oem_type` | Canonical OEM used for YAML `oem:` selection. Defaults to `Opentrons`. Known values include `Opentrons`, `Ultima`, `BD`, `Millipore`, `Sf`. |
| `kind_stage_type` | string | CSV operator/kind field | Stage parsed from operator/kind text. Defaults to `Production` when absent. |
| `config_environment` | string | upload request meta or backend default | Config environment used for upload YAML selection. `production` reads `upload_production.yaml`; `debug` reads `upload_debug.yaml`. `eng` and `engineering` normalize to `debug`. |
| `config_file` | string | `config_environment` | YAML filename used by this upload, such as `upload_production.yaml` or `upload_debug.yaml`. |

### How OEM Is Selected

Every product/test uses the same OEM resolution rule:

1. If the upload request or manual-upload meta includes `oem`, that value wins.
2. Otherwise the parser reads the CSV operator/kind field defined for that test and stores the raw OEM in `kind_oem_type`.
3. `FileDescription.from_raw()` normalizes that into the canonical `oem` field.
4. If no OEM can be identified, the value defaults to `Opentrons`.

The parser field used to find OEM differs by test family:

| Test family | Parser field | Notes |
| --- | --- | --- |
| 1/8 channel gravimetric | `kind` from the CSV config section | Config-section value such as an operator kind string. |
| 1/8 channel assembly QC | `operator-name` | Read from metadata. |
| 1/8 channel current/speed | `test_operator` | Read from metadata. |
| 96 channel assembly QC | `operator-name` or `test_operator` | First available field wins. |
| 8 channel burn-in result/record | `test_operator` | Read from metadata. |
| Robot Z stage / diagnostic | `operator-name` or `test_operator` | First available field wins. |
| Robot XY calibration | `operator-name` or `test_operator` | First available field wins. |
| Robot gantry stress | `operator-name` or `test_operator` | Metadata section ends at `date`. |
| Robot leveling | `operator-name` | Test CLI leveling report metadata. |

Known canonical OEM values are `Opentrons`, `Ultima`, `BD`, `Millipore`, and `Sf`. The YAML `oem:` block must contain all five for every upload config key.

### How Debug/Production Is Selected

Every product/test uses the same config environment rule:

1. If the upload request includes `environment`, it is passed as metadata and becomes `config_environment`.
2. If manual-upload meta includes `config_environment` or `environment`, that value is used.
3. `eng`, `engineering`, and `debug` normalize to `debug`.
4. Everything else defaults to `production`.
5. `config_file` is derived from `config_environment`:
   - `production` -> `upload_production.yaml`
   - `debug` -> `upload_debug.yaml`

The settings page has a `Production / Eng` switch. `Production` edits `upload_production.yaml`; `Eng` copies production to `upload_debug.yaml` when first selected in the page session, then edits `upload_debug.yaml`. Actual upload execution follows `file_desc.config_environment`, not merely the settings page selection.

## Parse And Completion State

| Field | Type | Source | Meaning |
| --- | --- | --- | --- |
| `metadata` | object | CSV parser | Raw normalized metadata extracted from the CSV metadata section. |
| `finished` | boolean | parser finish rules | Whether the CSV appears complete. |
| `require_finished` | boolean | upload settings | Whether unfinished CSVs should be blocked for this model/test. |
| `finished_bypassed` | boolean | upload flow | Present when `finished` is false but `require_finished` is false. |
| `error` | string | parser | Parser error string. Successful parse uses `False` as a string for legacy compatibility. |
| `failed` | boolean | metadata/parser failure | Present and true when metadata extraction or parser setup failed. |

## Upload Context

| Field | Type | Source | Meaning |
| --- | --- | --- | --- |
| `zip_file` | string or null | upload request / packaging step | Raw data zip path uploaded to Drive. |

## Product/Test Coverage

The current upload catalog resolves these product/test pairs to YAML config keys:

| Product | Test type | Config key |
| --- | --- | --- |
| `Robot` | `z_stage_test` | `robot_update_z_stage` |
| `Robot` | `diagnostic` | `robot_update_diagnostic` |
| `Robot` | `xy_calibration` | `robot_update_xy_belt_calibration` |
| `Robot` | `gantry_stress_test` | `robot_update_gantry_stress` |
| `Robot` | `leveling_test` | `robot_update_leveling` |
| `P50S`, `P1000S` | `assembly_qc` | `1ch_update_assembly_qc` |
| `P50S`, `P1000S` | `speed_current_test` | `1ch_update_current_speed` |
| `P50S`, `P1000S` | `gravimetric` | `1ch_update_volume` |
| `P50M`, `P1000M` | `assembly_qc` | `8ch_update_assembly_qc` |
| `P50M`, `P1000M` | `speed_current_test` | `8ch_update_current_speed` |
| `P50M`, `P1000M` | `gravimetric` | `8ch_update_volume` |
| `P50M`, `P1000M` | `burn_in_result_test` | `8ch_update_burn_in_result` |
| `P50M`, `P1000M` | `burn_in_record_test` | `8ch_update_burn_in_records` |
| `P2HH` | `assembly_qc` | `96_p200_update_qc` |
| `P1KH` | `assembly_qc` | `96_p1000_update_qc` |

## Upload Config Groups

Some config keys are grouped into a single workflow. Grouped tests share the same copied Google spreadsheet or upload session, wait for peer tests to finish before updating Unit Tracker, and use the joined workflow name in database records.

| Workflow group | Config keys | Database test fields |
| --- | --- | --- |
| 1 channel assembly workflow | `1ch_update_assembly_qc`, `1ch_update_current_speed` | `assembly_qc`, `current_speed` |
| 8 channel assembly workflow | `8ch_update_assembly_qc`, `8ch_update_current_speed` | `assembly_qc`, `current_speed` |
| 8 channel burn-in workflow | `8ch_update_burn_in_result`, `8ch_update_burn_in_records` | `burn_in_result`, `burn_in_records` |
| Robot assembly workflow | `robot_update_diagnostic`, `robot_update_xy_belt_calibration`, `robot_update_gantry_stress`, `robot_update_leveling`, `robot_update_z_stage` | `diagnostic`, `xy_belt_calibration`, `gantry_stress`, `leveling`, `z_stage` |

Ungrouped config keys form a workflow of one key. Current ungrouped keys are:

| Config key | Workflow |
| --- | --- |
| `1ch_update_volume` | `1ch_update_volume` |
| `8ch_update_volume` | `8ch_update_volume` |
| `96_p200_update_qc` | `96_p200_update_qc` |
| `96_p1000_update_qc` | `96_p1000_update_qc` |

The workflow name is the config group joined with `__`, for example `8ch_update_assembly_qc__8ch_update_current_speed`.

## YAML OEM Config Shape

Each upload config in `upload_production.yaml` and `upload_debug.yaml` should include this shape:

```yaml
oem:
  Opentrons:
    copytemplate: <template file id>
    result_cell: <!A1:A1>
    total_result_cell: <!B1:B1 or empty>
    failures: N/A
    copyRange:
      - <!A1:D1>
    pastefileid: <tracker spreadsheet id>
    pastelineRange:
      star: A
      end: D
  Ultima: ...
  BD: ...
  Millipore: ...
  Sf: ...
```

For runtime compatibility, legacy fields such as `ifcopytemplate.default`, `ifcopytemplate.ultima`, `copyRange`, `UltimacopyRange`, `pastefileid`, and `Ultimapastefileid` may still be present. New upload code prefers the `oem:` block and keeps the legacy fields synchronized when settings are saved.

## Notes

- `oem` is the preferred field for new code. `kind_oem_type` is retained for parser compatibility and historical records.
- `config_environment` is the preferred field for config selection. It lets a single upload request explicitly choose production or engineering/debug YAML.
- Settings UI `Production / Eng` changes the YAML file edited by settings. Upload requests must pass `environment` or `config_environment` when they need to use debug YAML for actual upload execution.
- If no environment override is passed, uploads default to backend `ENVIRONMENT` from `core.config`, currently `production`.
- `upload_config_key` is resolved before full parsing from CSV metadata: serial number decides product model, test name decides test type, then `product_catalog.get_upload_config_key()` maps the pair to YAML.
- The same `oem` and `config_environment` fields are stored in upload records through `file_desc`, making later debugging possible from the upload-record detail.
