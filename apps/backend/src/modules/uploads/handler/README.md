# Upload Handler

Productions testing upload pipeline for parsing test files, copying data into Google Sheets templates, uploading raw artifacts to Google Drive, storing upload records in MongoDB, and reporting status back to the API/UI.

## Structure

```text
upload_handler/
├── upload.py                 # UploadData facade used by API services
├── product_catalog.py        # Product/test-type registry and workflow lookup
├── configs/                  # YAML-driven upload configuration helpers
├── drivers/                  # CSV, Google Drive, Google Sheets, YAML drivers
├── models/                   # FileDescription, test/product enums, result models
├── parsers/                  # CSV metadata extraction and parser registry
├── repositories/             # MongoDB-backed upload/session/config persistence
├── uploaders/                # Spreadsheet workflows and shared uploader helpers
└── utils/                    # Auth, constants, runtime utilities
```

## Main Entry

`UploadData` in `upload.py` is the main facade:

```python
from modules.uploads.handler.upload import UploadData

uploader = UploadData()
uploader.init_upload_handler()
result = uploader.update_data_to_google_drive(file_path, zip_file=zip_path)
```

The returned response includes upload status plus links such as CSV spreadsheet, raw data, and unit tracker when available.

## Supported Product/Test Model

Product and test-type enums live in `models/domain.py`.

Current product families include:

- `Robot`
- `P50S`
- `P1000S`
- `P50M`
- `P1000M`
- `P2HH`
- `P1KH`
- `Gripper`

Current test types include:

- `assembly_qc`
- `speed_current_test`
- `gravimetric`
- `burn_in_result_test`
- `burn_in_record_test`
- `pressure_leakage_test`
- `z_stage_test`
- `diagnostic`
- `xy_calibration`
- `gantry_stress_test`
- `leveling_test`

## Flow

```text
CSV / ZIP input
      |
      v
FileDescription parser
      |
      v
Product catalog resolves upload config and workflow
      |
      v
Google Sheets template copy or reuse
      |
      v
CSV data upload + summary/result extraction
      |
      v
Raw data upload to Google Drive
      |
      v
MongoDB upload/session record
      |
      v
Unit tracker update when workflow is complete
```

## Configuration

Upload behavior is configuration driven. Product/test mappings and workflow selection are centralized in `product_catalog.py`; YAML upload settings and Google sheet IDs are loaded by the config repository and YAML driver.

Credentials are not stored in this package. Local development credentials normally live in:

```text
apps/backend/auth/
```

Server deployments use `/configs` by default. See [../../../README.md](../../../README.md) for the environment variables and credential file names.

## Tests

From the repository root:

```bash
uv run pytest tests/test_datas_csv.py tests/test_data_analysis.py
```

## Notes

- Keep parser behavior deterministic; production uploads rely on extracted serial number, model, test type, and finish status.
- Add new product/test support through the parser registry and product catalog instead of special-casing in API routes.
- Generated upload data under `apps/backend/data/temp/` and `apps/backend/data/testing_data/` is ignored by git.
