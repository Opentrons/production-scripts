"""Match external QC reports without putting Google requests on the list path."""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import os
import re
import sqlite3
import threading
import time
from collections import OrderedDict, deque
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .products import normalize_product


logger = logging.getLogger(__name__)
MAX_PENDING = 32
MAX_ENTRIES = 1024
MAX_CATALOG_ROWS = 100_000
LOOKUP_TIMEOUT_SECONDS = 180
CACHE_VERSION = 1
_started_service = None
_service_lock = threading.Lock()


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def normalize_report_url(value: object) -> str | None:
    """Discard sharing parameters, retaining the worksheet identity when present."""
    if not isinstance(value, str):
        return None
    try:
        parsed = urlparse(value.strip())
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
            return None
        if parsed.hostname == "docs.google.com":
            match = re.fullmatch(r"/spreadsheets/d/([A-Za-z0-9_-]+)(?:/[^?]*)?", parsed.path)
            if not match:
                return None
            base = f"https://docs.google.com/spreadsheets/d/{match[1]}/edit"
        elif parsed.hostname == "drive.google.com":
            match = re.fullmatch(r"/file/d/([A-Za-z0-9_-]+)(?:/[^?]*)?", parsed.path)
            if not match:
                return None
            base = f"https://drive.google.com/file/d/{match[1]}/view"
        else:
            return None
        gids = parse_qs(parsed.fragment).get("gid", []) + parse_qs(parsed.query).get("gid", [])
        if any(not gid.isdigit() for gid in gids) or len(set(gids)) > 1:
            return None
        return base + (f"#gid={gids[0]}" if gids else "")
    except (ValueError, TypeError):
        return None


class _LinkError(Exception):
    def __init__(self, code: str):
        self.code = code


class ReportLinkService:
    """One bounded background worker, with a separate, persistent lookup cache."""

    def __init__(self, cache_path: Path, source=None, enabled: bool = True, refresh_seconds: float = 300):
        self.enabled = enabled
        seconds = float(refresh_seconds)
        self.refresh_seconds = min(86400.0, max(1.0, seconds)) if math.isfinite(seconds) else 300.0
        self.retry_seconds = min(30.0, self.refresh_seconds)
        self.cache_path = Path(cache_path)
        if source is None and enabled:
            try:
                from .report_link_source import GoogleReportLinkSource

                source = GoogleReportLinkSource()
            except Exception as exc:
                logger.warning("Report link source configuration unavailable: %s", type(exc).__name__)
        self.source = source
        namespace = getattr(source, "cache_namespace", None)
        if callable(namespace):
            namespace = namespace()
        if not isinstance(namespace, str):
            namespace = f"{type(source).__module__}.{type(source).__qualname__}"
        self.namespace = hashlib.sha256(f"{CACHE_VERSION}:{namespace}".encode()).hexdigest()
        self._condition = threading.Condition(threading.RLock())
        self._queue: deque[tuple[tuple[str, str], bool]] = deque()
        self._pending: set[tuple[str, str]] = set()
        self._results: OrderedDict[tuple[str, str], dict] = OrderedDict()
        self._identities: OrderedDict[str, dict] = OrderedDict()
        self._catalog: dict | None = None
        self._catalog_error: tuple[str, float] | None = None
        self._identity_errors: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._thread: threading.Thread | None = None
        self._closed = False
        if enabled:
            self._load_cache()

    @staticmethod
    def _empty(key: tuple[str, str], status: str, error_code: str | None = None) -> dict:
        return {"status": status, "sn": key[0], "report_run_id": key[1], "checked_at": None,
                "stale": False, "matches": [], "error_code": error_code}

    @staticmethod
    def _key_string(key: tuple[str, str]) -> str:
        return json.dumps(key, ensure_ascii=False, separators=(",", ":"))

    def lookup(self, report: dict, force: bool = False) -> dict:
        """Return immediately; repeated polling never queues the same key twice."""
        key = (_text(report.get("sn")), _text(report.get("report_run_id")))
        if not self.enabled:
            return self._empty(key, "disabled")
        if not all(key) or key[0].casefold() in {"unknown-sn", "unknown", "none", "n/a", "null"}:
            return self._empty(key, "missing_identity")
        with self._condition:
            entry = self._results.get(key)
            result = copy.deepcopy(entry["result"]) if entry else self._empty(key, "running")
            if entry:
                self._results.move_to_end(key)
            if self._closed:
                result.update(status="unavailable", error_code="closed", stale=bool(result["checked_at"]))
                return result
            if key not in self._pending and not force and entry and entry["expires_at"] > time.time():
                return result
            if key not in self._pending:
                if len(self._pending) >= MAX_PENDING:
                    result.update(status="unavailable", error_code="busy", stale=bool(result["checked_at"]))
                    return result
                self._pending.add(key)
                self._queue.append((key, force))
                if self._thread is None or not self._thread.is_alive():
                    self._thread = threading.Thread(target=self._work, name="failure-report-links", daemon=True)
                    self._thread.start()
                self._condition.notify_all()
            result.update(status="running", error_code=None, stale=bool(result["checked_at"]))
            return result

    def close(self, wait: bool = False) -> None:
        with self._condition:
            self._closed = True
            self._queue.clear()
            self._pending.clear()
            self._condition.notify_all()
        if wait and self._thread:
            self._thread.join(timeout=2)

    def _work(self) -> None:
        while True:
            with self._condition:
                while not self._queue and not self._closed:
                    self._condition.wait()
                if self._closed:
                    return
                key, force = self._queue.popleft()
                previous = copy.deepcopy(self._results.get(key, {}).get("result"))
            try:
                result = self._resolve(key, force)
            except _LinkError as exc:
                result = previous or self._empty(key, "unavailable")
                result.update(status="unavailable", error_code=exc.code, stale=bool(result["checked_at"]))
            except Exception as exc:
                # Log types only: Google errors may contain URL parameters or credentials.
                logger.warning("Report link lookup failed: %s", type(exc).__name__)
                result = previous or self._empty(key, "unavailable")
                result.update(status="unavailable", error_code="lookup_failed", stale=bool(result["checked_at"]))
            completed = time.time()
            duration = self.retry_seconds if result["status"] == "unavailable" else self.refresh_seconds
            entry = {"result": result, "expires_at": completed + duration}
            with self._condition:
                if self._closed:
                    return
                self._results[key] = entry
                self._results.move_to_end(key)
                while len(self._results) > MAX_ENTRIES:
                    self._results.popitem(last=False)
                self._pending.discard(key)
                self._condition.notify_all()
            self._persist("result", self._key_string(key), entry, completed)

    def _get_catalog(self, force: bool) -> list[dict]:
        if self.source is None:
            raise _LinkError("configuration_error")
        if not force and self._catalog_error and self._catalog_error[1] > time.time():
            raise _LinkError(self._catalog_error[0])
        if not force and self._catalog and self._catalog["expires_at"] > time.time():
            return self._catalog["rows"]
        try:
            raw_rows = self.source.read_catalog()
            rows = self._validate_catalog(raw_rows)
        except _LinkError as exc:
            self._catalog_error = (exc.code, time.time() + self.retry_seconds)
            raise
        except Exception as exc:
            logger.warning("Report link catalog unavailable: %s", type(exc).__name__)
            self._catalog_error = ("catalog_unavailable", time.time() + self.retry_seconds)
            raise _LinkError("catalog_unavailable") from exc
        checked = time.time()
        self._catalog_error = None
        self._catalog = {"rows": rows, "expires_at": checked + self.refresh_seconds}
        self._persist("catalog", "catalog", self._catalog, checked)
        return rows

    @staticmethod
    def _validate_catalog(raw_rows: object) -> list[dict]:
        if not isinstance(raw_rows, list) or len(raw_rows) > MAX_CATALOG_ROWS:
            raise _LinkError("invalid_catalog")
        rows = []
        for raw in raw_rows:
            if not isinstance(raw, dict):
                raise _LinkError("invalid_catalog")
            sn = _text(raw.get("sn"))
            if not sn:
                continue
            url = normalize_report_url(raw.get("url"))
            invalid_link = raw.get("error_code") == "invalid_link" and raw.get("url") == ""
            # An unusable candidate cannot safely be treated as an absent report.
            if not url and not invalid_link:
                raise _LinkError("invalid_catalog")
            source_url = _text(raw.get("source_url"))
            if source_url and not normalize_report_url(source_url):
                raise _LinkError("invalid_catalog")
            try:
                sheet_id, row = int(raw.get("sheet_id", 0)), int(raw.get("row", 0))
            except (TypeError, ValueError) as exc:
                raise _LinkError("invalid_catalog") from exc
            rows.append({"sn": sn, "report_run_id": _text(raw.get("report_run_id")), "url": url or "",
                         "sheet_title": _text(raw.get("sheet_title")), "sheet_id": sheet_id,
                         "row": row, "source_url": source_url,
                         **({"error_code": "invalid_link"} if invalid_link else {})})
        return rows

    def _identity(self, url: str, force: bool) -> dict:
        failed = self._identity_errors.get(url)
        if not force and failed and failed[1] > time.time():
            raise _LinkError(failed[0])
        entry = self._identities.get(url)
        if not force and entry and entry["expires_at"] > time.time():
            self._identities.move_to_end(url)
            return entry["identity"]
        try:
            raw = self.source.read_identity(url)
        except Exception as exc:
            logger.warning("Report link identity unavailable: %s", type(exc).__name__)
            self._cache_identity_error(url, "identity_unavailable")
            raise _LinkError("identity_unavailable") from exc
        try:
            identity = self._validated_identity(url, raw)
        except _LinkError as exc:
            self._cache_identity_error(url, exc.code)
            raise
        self._identity_errors.pop(url, None)
        checked = time.time()
        entry = {"identity": identity, "expires_at": checked + self.refresh_seconds}
        self._identities[url] = entry
        self._identities.move_to_end(url)
        while len(self._identities) > MAX_ENTRIES:
            self._identities.popitem(last=False)
        self._persist("identity", url, entry, checked)
        return identity

    @staticmethod
    def _validated_identity(url: str, raw: object) -> dict:
        identity = {key: _text(raw.get(key)) for key in ("sn", "report_run_id")} if isinstance(raw, dict) else {}
        if not all(identity.get(key) for key in ("sn", "report_run_id")):
            raise _LinkError("identity_incomplete")
        if "resolved_url" in raw:
            resolved = normalize_report_url(raw["resolved_url"])
            # Only the source's verified legacy gid=0 repair may change a
            # target, and it must stay inside the same Google spreadsheet.
            if (not resolved or not url.startswith("https://docs.google.com/spreadsheets/d/")
                    or url.partition("#")[2] != "gid=0"
                    or resolved.partition("#")[0] != url.partition("#")[0]
                    or not re.fullmatch(r"gid=[1-9]\d*", resolved.partition("#")[2])):
                raise _LinkError("identity_unavailable")
            identity["resolved_url"] = resolved
        return identity

    def _cache_identity_error(self, url: str, code: str) -> None:
        self._identity_errors[url] = (code, time.time() + self.retry_seconds)
        self._identity_errors.move_to_end(url)
        while len(self._identity_errors) > MAX_ENTRIES:
            self._identity_errors.popitem(last=False)

    def _resolve(self, key: tuple[str, str], force: bool) -> dict:
        deadline = time.monotonic() + LOOKUP_TIMEOUT_SECONDS

        def check_deadline() -> None:
            if self._closed:
                raise _LinkError("closed")
            if time.monotonic() >= deadline:
                raise _LinkError("lookup_timeout")

        candidates: dict[str, list[dict]] = {}
        check_deadline()
        for row in self._get_catalog(force):
            if row["sn"] == key[0]:
                if row.get("error_code") == "invalid_link":
                    raise _LinkError("invalid_link")
                candidates.setdefault(row["url"], []).append(row)
        check_deadline()
        matches = {}
        error_code = None
        for url, rows in candidates.items():
            check_deadline()
            try:
                identity = self._identity(url, force)
            except _LinkError as exc:
                error_code = exc.code
                continue
            selected = None
            # Even a tracker row with its own run column is only a candidate:
            # manual edits and reused destination workbooks require verification.
            if (identity["sn"], identity["report_run_id"]) == key:
                selected = next((row for row in rows if not row["report_run_id"] or row["report_run_id"] == key[1]), None)
            if selected:
                target = identity.get("resolved_url", selected["url"])
                matches.setdefault(target, {**{field: selected[field] for field in ("sheet_title", "sheet_id", "row", "source_url")}, "url": target})
        check_deadline()
        # An unreadable candidate may contain the requested run or another match.
        # Preserve the previous complete result instead of reporting false uniqueness.
        if error_code:
            raise _LinkError(error_code)
        result = self._empty(key, "ambiguous" if len(matches) > 1 else "matched" if matches else "not_found")
        result.update(matches=list(matches.values()), checked_at=_timestamp(time.time()))
        return result

    @contextmanager
    def _connection(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.cache_path, timeout=2)) as connection, connection:
            connection.execute("CREATE TABLE IF NOT EXISTS report_link_cache (namespace TEXT, kind TEXT, cache_key TEXT, payload TEXT NOT NULL, updated_at REAL NOT NULL, PRIMARY KEY(namespace,kind,cache_key))")
            yield connection

    def _load_cache(self) -> None:
        try:
            if not self.cache_path.exists():
                return
            with self._connection() as connection:
                rows = connection.execute("SELECT kind,cache_key,payload FROM report_link_cache WHERE namespace=? ORDER BY updated_at", (self.namespace,)).fetchall()
            for kind, key, payload in rows:
                try:
                    entry = json.loads(payload)
                    if (not isinstance(entry, dict) or type(entry.get("expires_at")) not in (int, float)
                            or not math.isfinite(entry["expires_at"]) or entry["expires_at"] <= 0):
                        continue
                    if kind == "catalog" and isinstance(entry.get("rows"), list) and len(entry["rows"]) <= MAX_CATALOG_ROWS:
                        self._catalog = {**entry, "rows": self._validate_catalog(entry["rows"])}
                    elif (kind == "identity" and isinstance(entry.get("identity"), dict) and normalize_report_url(key) == key
                          and all(_text(entry["identity"].get(field)) for field in ("sn", "report_run_id"))):
                        self._identities[key] = {**entry, "identity": self._validated_identity(key, entry["identity"])}
                    elif kind == "result":
                        identity = json.loads(key)
                        result = entry.get("result")
                        if (isinstance(identity, list) and len(identity) == 2 and all(isinstance(value, str) for value in identity)
                                and self._valid_cached_result(identity, result)):
                            self._results[tuple(identity)] = entry
                except (ValueError, TypeError, _LinkError):
                    continue
            for cache in (self._results, self._identities):
                while len(cache) > MAX_ENTRIES:
                    cache.popitem(last=False)
        except (OSError, sqlite3.Error) as exc:
            logger.warning("Report link cache unavailable: %s", type(exc).__name__)

    @staticmethod
    def _valid_cached_result(identity: list[str], result: object) -> bool:
        if (not isinstance(result, dict) or result.get("status") not in {"matched", "not_found", "ambiguous", "unavailable"}
                or not all(field in result for field in ("sn", "report_run_id", "checked_at", "stale", "matches", "error_code"))
                or [result["sn"], result["report_run_id"]] != identity
                or type(result["stale"]) is not bool or not isinstance(result["matches"], list)):
            return False
        checked_at = result["checked_at"]
        if checked_at is not None:
            if not isinstance(checked_at, str):
                return False
            try:
                if datetime.fromisoformat(checked_at).tzinfo is None:
                    return False
            except ValueError:
                return False
        matches = result["matches"]
        status = result["status"]
        if (len(matches) > MAX_CATALOG_ROWS or status == "matched" and len(matches) != 1
                or status == "not_found" and matches or status == "ambiguous" and len(matches) < 2):
            return False
        if status == "unavailable":
            if not isinstance(result["error_code"], str) or result["stale"] != bool(checked_at) or matches and not checked_at:
                return False
        elif checked_at is None or result["stale"] or result["error_code"] is not None:
            return False
        urls = set()
        for match in matches:
            if (not isinstance(match, dict) or not isinstance(match.get("url"), str)
                    or normalize_report_url(match["url"]) != match["url"]
                    or not isinstance(match.get("sheet_title"), str)
                    or type(match.get("sheet_id")) is not int or match["sheet_id"] < 0
                    or type(match.get("row")) is not int or match["row"] < 1
                    or not isinstance(match.get("source_url"), str)
                    or match["source_url"] and not normalize_report_url(match["source_url"])):
                return False
            urls.add(match["url"])
        return len(urls) == len(matches)

    def _persist(self, kind: str, key: str, value: dict, updated_at: float) -> None:
        try:
            with self._connection() as connection:
                connection.execute("INSERT INTO report_link_cache VALUES(?,?,?,?,?) ON CONFLICT(namespace,kind,cache_key) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at",
                                   (self.namespace, kind, key, json.dumps(value, ensure_ascii=False, allow_nan=False), updated_at))
                if kind != "catalog":
                    connection.execute("DELETE FROM report_link_cache WHERE namespace=? AND kind=? AND cache_key NOT IN (SELECT cache_key FROM report_link_cache WHERE namespace=? AND kind=? ORDER BY updated_at DESC LIMIT ?)",
                                       (self.namespace, kind, self.namespace, kind, MAX_ENTRIES))
                # Keep a few recent source configurations without unbounded growth.
                connection.execute("DELETE FROM report_link_cache WHERE namespace NOT IN (SELECT namespace FROM report_link_cache GROUP BY namespace ORDER BY MAX(updated_at) DESC LIMIT 4)")
        except (OSError, sqlite3.Error, ValueError) as exc:
            logger.warning("Report link cache write failed: %s", type(exc).__name__)


def report_channels(report: dict) -> tuple[str, ...]:
    """Route only the lookup; the report identity remains the exact SN/run pair."""
    product = normalize_product(report.get("product")).upper()
    product_channel = {"P50S": "1ch", "P1000S": "1ch", "P50M": "8ch", "P1000M": "8ch"}.get(product)
    serial = _text(report.get("sn")).upper()
    serial_channel = next((channel for prefixes, channel in (
        (("P50S", "P1KS", "P1000S"), "1ch"),
        (("P50M", "P1KM", "P1000M"), "8ch"),
    ) if serial.startswith(prefixes)), None)
    channels = {channel for channel in (product_channel, serial_channel) if channel}
    return (next(iter(channels)),) if len(channels) == 1 else ("1ch", "8ch")


class RoutedReportLinkService:
    """Keep each tracker's network queue, failures and cached identities separate."""

    def __init__(self, cache_path: Path, *, enabled: bool = True, refresh_seconds: float = 300, service_factory=None):
        self.cache_path = Path(cache_path)
        self.enabled = enabled
        self.refresh_seconds = refresh_seconds
        self._factory = service_factory or self._create_service
        self._lock = threading.RLock()
        self._children: dict[str, ReportLinkService | None] = {}
        self._complete: OrderedDict[tuple[str, str], dict] = OrderedDict()
        self._closed = False

    def _create_service(self, channel: str) -> ReportLinkService:
        from .report_link_source import GoogleReportLinkSource

        # Construct explicitly: a failed 1ch configuration must never fall back
        # to ReportLinkService's default 8ch source.
        source = GoogleReportLinkSource(channel=channel)
        return ReportLinkService(self.cache_path, source=source, refresh_seconds=self.refresh_seconds)

    def _child(self, channel: str) -> ReportLinkService | None:
        with self._lock:
            if self._closed:
                return None
            if channel not in self._children:
                try:
                    self._children[channel] = self._factory(channel)
                except Exception as exc:
                    logger.warning("Report link %s configuration unavailable: %s", channel, type(exc).__name__)
                    self._children[channel] = None
            return self._children[channel]

    def lookup(self, report: dict, force: bool = False) -> dict:
        key = (_text(report.get("sn")), _text(report.get("report_run_id")))
        empty = ReportLinkService._empty
        if not self.enabled:
            return empty(key, "disabled")
        if not all(key) or key[0].casefold() in {"unknown-sn", "unknown", "none", "n/a", "null"}:
            return empty(key, "missing_identity")
        with self._lock:
            if self._closed:
                return empty(key, "unavailable", "closed")
        results = []
        for channel in report_channels(report):
            child = self._child(channel)
            results.append(child.lookup(report, force=force) if child else empty(key, "unavailable", "configuration_error"))
        if len(results) == 1:
            return results[0]
        # Finish both lookups before returning a unique match or a negative.
        # Running takes priority so the UI keeps polling the remaining source.
        running = any(result["status"] == "running" for result in results)
        incomplete = next((result for result in results if result["status"] not in {"matched", "not_found", "ambiguous", "running"}), None)
        with self._lock:
            if running or incomplete:
                result = copy.deepcopy(self._complete.get(key)) or empty(key, "running")
                result.update(status="running" if running else "unavailable", stale=bool(result["checked_at"]),
                              error_code=None if running else incomplete.get("error_code") or "catalog_unavailable")
                return result
            matches = {}
            for result in results:
                for match in result["matches"]:
                    matches.setdefault(match["url"], match)
            result = empty(key, "ambiguous" if len(matches) > 1 else "matched" if matches else "not_found")
            result.update(matches=list(matches.values()), checked_at=min(item["checked_at"] for item in results))
            self._complete[key] = copy.deepcopy(result)
            self._complete.move_to_end(key)
            while len(self._complete) > MAX_ENTRIES:
                self._complete.popitem(last=False)
            return result

    def close(self, wait: bool = False) -> None:
        with self._lock:
            self._closed = True
            children = [child for child in self._children.values() if child is not None]
            self._complete.clear()
        for child in children:
            child.close(wait=wait)


def get_report_link_service() -> RoutedReportLinkService:
    global _started_service
    from core import config

    with _service_lock:
        if _started_service is not None:
            return _started_service
        enabled = os.getenv("PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_LINKS_ENABLED", "true").strip().lower() in {"true", "1", "yes", "on"}
        try:
            seconds = float(os.getenv("PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_LINK_REFRESH_SECONDS", "300"))
            if not 1 <= seconds <= 86400:
                seconds = 300
        except ValueError:
            seconds = 300
        _started_service = RoutedReportLinkService(Path(config.DATA_DIR) / "defect-search" / "test-failure-report-links.sqlite3",
                                                  enabled=enabled, refresh_seconds=seconds)
        return _started_service


def stop_report_link_service() -> None:
    """Application shutdown must not initialize an unused Google integration."""
    global _started_service
    with _service_lock:
        service, _started_service = _started_service, None
    if service is not None:
        service.close()
