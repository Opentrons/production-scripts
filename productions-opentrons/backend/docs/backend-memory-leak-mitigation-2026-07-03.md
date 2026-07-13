# Backend Memory Leak Mitigation - 2026-07-03

## Evidence

The issue was reported from the production `systemd` service status. Keep this block as the original evidence for future regression checks:

```text
data-handler.service - Data Handler FastAPI Service
     Loaded: loaded (/etc/systemd/system/data-handler.service; enabled; preset:>
     Active: active (running) since Wed 2026-06-24 14:24:02 CST; 1 week 1 day a>
 Invocation: a8e932f2a6fb4f3c8cd2c6fbc1d6ab08
   Main PID: 1412632 (uv)
      Tasks: 477 (limit: 17968)
     Memory: 11.1G (peak: 11.1G swap: 1.2G swap peak: 1.2G)
        CPU: 2h 7min 26.421s
     CGroup: /system.slice/data-handler.service
             ├─1412632 /root/.local/bin/uv run python -m uvicorn app:app --host>
             └─1412637 /opt/data-handler/backend/.ven
```

Primary symptoms:

- Long-running backend process had `Tasks: 477`.
- Resident memory reached `11.1G`.
- Swap usage reached `1.2G`.
- Service had been running for more than one week.

## Root Risks Found

### GoogleDriveDriver refresh thread leak

`GoogleDriveDriver.__init__()` initialized Google Drive and Sheets clients and started a daemon token refresh thread on every instance.

High-frequency paths that instantiate `GoogleDriveDriver`:

- Online data analysis Google Sheet reads.
- Upload workflows.
- Google Drive helper operations.

Risk:

- Every request path that created a driver could leave another sleeping daemon refresh thread.
- This matches the high `Tasks` count from the systemd evidence.
- Each driver also retained Google service/client references.

Mitigation:

- `GoogleDriveDriver` now uses shared Google service objects.
- Only one `google-token-refresh` thread is started per process.
- `GoogleDriveDriver.shutdown_shared_services()` stops the refresh thread and clears shared references.

Changed file:

- `backend/src/upload_handler/drivers/google_drive.py`

### Global executors without shutdown

Global thread pools existed for robot scanning/commands and manual upload work.

Risk:

- Threads were process-lifetime resources with no explicit shutdown hook.
- Graceful service restarts could leave cleanup dependent on interpreter teardown only.

Mitigation:

- Added `shutdown_robot_service()`.
- Added `shutdown_upload_service()`.
- Wired both into FastAPI lifespan shutdown.

Changed files:

- `backend/src/api/services/robots.py`
- `backend/src/api/services/upload.py`
- `backend/src/app.py`

### Upload workflow lock dictionary growth

Combined upload workflow locks were stored in a global dictionary keyed by `sn:model:workflow`.

Risk:

- New SN/model/workflow combinations could grow the lock dictionary forever.

Mitigation:

- Replaced raw lock storage with `UploadWorkflowLock`.
- Added reference counting.
- Locks are removed after all waiters finish and the lock is released.
- Shutdown clears remaining lock state.

Changed file:

- `backend/src/api/services/upload.py`

### Test execution run/event retention

The test execution manager kept completed runs, plans, and SSH output events in process memory.

Risk:

- Frequent test execution could grow `_runs`, `_plans`, and per-run `events` indefinitely.
- Large SSH output could create large event payloads.

Mitigation:

- Completed runs are pruned by time and count.
- Defaults:
  - `MAX_COMPLETED_RUNS = 200`
  - `COMPLETED_RUN_RETENTION_HOURS = 24`
  - `MAX_EVENTS_PER_RUN = 1000`
  - `MAX_SSH_OUTPUT_EVENT_CHARS = 12000`
- Running and waiting-input sessions are not pruned.

Changed file:

- `backend/src/test_case/execution/manager.py`

### Socket cleanup hardening

`get_local_ip_and_prefix()` created a UDP socket and closed it manually only on the success path.

Risk:

- Low probability descriptor leak on unexpected exceptions.

Mitigation:

- Replaced manual close with a context manager.

Changed file:

- `backend/src/api/services/robots.py`

## Lifecycle Cleanup

FastAPI lifespan shutdown now performs:

```python
shutdown_robot_service()
shutdown_upload_service()
GoogleDriveDriver.shutdown_shared_services()
mongodb.close()
```

Changed file:

- `backend/src/app.py`

## Verification

Commands run locally:

```bash
python -m compileall backend/src
pytest backend/tests/test_data_analysis.py -q
```

Result:

```text
11 passed
```

## Deployment Note

The already-running production process cannot release leaked historical daemon threads or memory just because the source code changed.

Restart the service after deploying this fix:

```bash
sudo systemctl restart data-handler.service
```

## Post-Restart Monitoring

Recommended checks after restart:

```bash
systemctl status data-handler.service
ps -L -p "$(systemctl show -p MainPID --value data-handler.service)" | wc -l
journalctl -u data-handler.service -n 200 --no-pager
```

Expected behavior:

- `Tasks` should stay near normal backend thread-pool size, not climb toward hundreds after repeated online analysis/upload requests.
- Memory should not monotonically climb after similar traffic.
- Logs should show Google service reuse and no repeated token refresh thread creation.

## Remaining Watch Items

These were reviewed but not fully redesigned in this mitigation:

- Large uploaded CSV files are still read into memory before writing to disk in some request handlers.
- MongoDB stats endpoints can materialize full query results for aggregation.
- Google Drive file download/export helpers use `BytesIO` before writing to disk.

These are bounded by request size or endpoint usage and are lower priority than the confirmed thread/task leak, but they should be revisited if memory continues to grow after restart.
