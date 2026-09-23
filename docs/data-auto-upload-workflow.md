# Automated Data Upload Workflow

End-to-end flow from robot test data → Google Drive / Sheets → business DB → Slack.

Diagram: [`data-auto-upload-flowchart.png`](./data-auto-upload-flowchart.png) · Handler details: [`upload-flow.md`](../apps/backend/docs/upload-flow.md)

---

## Overview

```mermaid
flowchart TB
    subgraph S1["01 Device / Input"]
        A1["Client starts upload"]
        A2["Create upload record<br/>POST /api/upload-records/start"]
        A3{"Health OK?<br/>GET /api/health"}
        A4["Pull raw data<br/>POST /api/pull-folder"]
        A5["Enqueue job<br/>POST /api/upload-data → queued"]
        A1 --> A2 --> A3
        A3 -- no --> F1["Mark failed"]
        A3 -- yes --> A4 --> A5
    end

    subgraph S2["02 Upload Worker"]
        B1["Scheduler claims lease"]
        B2["Validate CSV size / SHA-256"]
        B3["Parse FileDescription + config"]
        B4["Create/reuse Sheet + write CSV"]
        A5 --> B1 --> B2 --> B3 --> B4
    end

    subgraph S3["03 Cloud + DB"]
        C1["Read summary / result"]
        C2["Archive sheet + upload raw ZIP"]
        C3["Write MongoDB + upload_sessions"]
        B4 --> C1 --> C2 --> C3
    end

    subgraph S4["04 Notification"]
        D1["Finish record"]
        D2["Queue + send Slack"]
        C3 --> D1 --> D2
    end

    B2 & B3 & B4 & C2 & C3 -.failure.-> E1["failure_stage/code<br/>retry if retryable, else Slack fail"]
```

---

## Stages

| Stage | Steps | Entry |
| --- | --- | --- |
| **01 Input** | Create record → health check → SFTP/SCP pull → enqueue | `data_center_client.upload_data_to_google_drive` |
| **02 Worker** | Claim lease → integrity check → parse → write Sheet | `UploadScheduler` → `run_queued_upload` |
| **03 Cloud+DB** | Summary → Drive archive/raw ZIP → business DB | `SpreadsheetUploadWorkflow` |
| **04 Notify** | Finish record → Slack (separate lease) | `finish_upload_record` / `notify_upload_result_to_slack` |

Manual upload (`POST /api/upload-data/manual`) joins the same worker after enqueue. Same SN + workflow uses `UploadWorkflowLock`.

---

## Call Chain

```text
upload_data_to_google_drive
  → start_upload_record → check_health → pull_folder → upload_data (enqueue)
       → UploadScheduler.claim → run_queued_upload
            → UploadData.update_data_to_google_drive
                 → SpreadsheetUploadWorkflow → Sheets/Drive + MongoDB → Slack
```

**States:** `queued` → `running`/`retrying` → `success`|`failed`  
**Retry:** lease + checkpoint + exponential backoff; Slack retries independently.

---

## Systems & Source

| System | Role |
| --- | --- |
| Robot / `data_center_client` | Produce CSV/raw folder; orchestrate client flow |
| Backend API | Health, pull, records, enqueue |
| `UploadScheduler` | Async upload + Slack workers |
| Google Sheets / Drive | Template, CSV, Unit Tracker, month archive, raw ZIP |
| MongoDB | `upload_records`, `upload_sessions`, business collections, messages |
| Slack | Success / failure notify |

| Path | Purpose |
| --- | --- |
| `apps/backend/scripts/data_center_client.py` | Client orchestration |
| `apps/backend/src/api/routers/uploads.py` | Upload APIs |
| `apps/backend/src/api/routers/file_transfer.py` | Pull folder |
| `apps/backend/src/modules/uploads/{upload,upload_records,scheduler}.py` | Worker, records, scheduler |
| `apps/backend/src/modules/uploads/handler/` | Parse, catalog, Spreadsheet workflow |
| `apps/web-ui/src/views/data/UploadRecordsView.vue` | Upload records UI |
