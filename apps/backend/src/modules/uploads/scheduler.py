from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import socket
import threading
from uuid import uuid4

import core.config as setting
from core.logging import get_logger
from modules.uploads import upload_records


logger = get_logger(__name__)


class UploadScheduler:
    """Polls durable upload records and executes claimed work with leases."""

    def __init__(self) -> None:
        self.owner = f"{socket.gethostname()}:{uuid4().hex}"
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._lock = threading.Lock()
        self._upload_futures: set[Future] = set()
        self._notification_futures: set[Future] = set()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        upload_records.ensure_upload_record_indexes()
        upload_records.recover_expired_upload_leases()
        upload_records.recover_expired_upload_notifications()
        self._stop_event.clear()
        self._executor = ThreadPoolExecutor(
            max_workers=setting.UPLOAD_MAX_WORKERS + 1,
            thread_name_prefix="upload-worker",
        )
        self._thread = threading.Thread(
            target=self._run,
            name="upload-scheduler",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "Upload scheduler started: owner=%s workers=%s",
            self.owner,
            setting.UPLOAD_MAX_WORKERS,
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=setting.UPLOAD_SCHEDULER_POLL_SECONDS + 2)
        self._thread = None
        executor = self._executor
        self._executor = None
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)
        with self._lock:
            self._upload_futures.clear()
            self._notification_futures.clear()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                upload_records.recover_expired_upload_leases()
                upload_records.recover_expired_upload_notifications()
                self._dispatch_uploads()
                self._dispatch_notification()
            except Exception as exc:
                logger.error("Upload scheduler poll failed: %s", exc, exc_info=True)
            self._stop_event.wait(setting.UPLOAD_SCHEDULER_POLL_SECONDS)

    def _dispatch_uploads(self) -> None:
        executor = self._executor
        if executor is None:
            return
        while True:
            with self._lock:
                capacity = setting.UPLOAD_MAX_WORKERS - len(self._upload_futures)
            if capacity <= 0:
                return
            record = upload_records.claim_due_upload_record(self.owner)
            if record is None:
                return
            future = executor.submit(self._execute_upload, record)
            self._track_future(future, self._upload_futures)

    def _dispatch_notification(self) -> None:
        executor = self._executor
        if executor is None:
            return
        with self._lock:
            if self._notification_futures:
                return
        record = upload_records.claim_due_upload_notification(self.owner)
        if record is None:
            return
        future = executor.submit(self._execute_notification, record)
        self._track_future(future, self._notification_futures)

    def _track_future(self, future: Future, bucket: set[Future]) -> None:
        with self._lock:
            bucket.add(future)

        def discard(completed: Future) -> None:
            with self._lock:
                bucket.discard(completed)

        future.add_done_callback(discard)

    @staticmethod
    def _execute_upload(record: dict) -> None:
        from modules.uploads import upload as upload_service

        upload_service.run_queued_upload(record)

    @staticmethod
    def _execute_notification(record: dict) -> None:
        from modules.uploads.handler.upload import notify_upload_result_to_slack

        record_id = str(record["_id"])
        expected_attempt = int(record.get("notification_attempt_count") or 0)
        payload = record.get("notification_payload") or {}
        try:
            success = notify_upload_result_to_slack(
                payload.get("result"),
                payload.get("csv_path") or "",
                error_message=payload.get("error_message"),
                zip_path=payload.get("zip_path"),
                record_id=record_id,
                upload_success=payload.get("upload_success"),
                database_success=payload.get("database_success"),
            )
            upload_records.finish_upload_notification(
                record_id,
                success=bool(success),
                error=None if success else "Slack notification returned false",
                expected_attempt=expected_attempt,
            )
        except Exception as exc:
            logger.error("Upload notification failed for %s: %s", record_id, exc, exc_info=True)
            upload_records.finish_upload_notification(
                record_id,
                success=False,
                error=str(exc),
                expected_attempt=expected_attempt,
            )


upload_scheduler = UploadScheduler()
