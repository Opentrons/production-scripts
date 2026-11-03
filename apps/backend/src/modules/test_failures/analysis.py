"""On-demand, read-only analysis of indexed QC evidence bundles.

The worker never scans a directory or follows paths from a submitted request or
from a report's artifact fields. Only registered attachments are snapshotted.
"""
from __future__ import annotations

import fcntl
import hashlib
import html
import json
import logging
import os
import re
import shutil
import threading
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from core import config
from .filesystem import content_signature, stat_signature
from .parser import parse_report
from .qc_agent import __version__
from .qc_agent.analyzer import ModelAnalysisError, _validate_assessments, analyze_report, render_markdown
from .qc_agent.evidence import prepare_evidence
from .repository import ConflictError, NotFoundError, now
from .service import TestFailureService, get_service

logger = logging.getLogger(__name__)
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 192 * 1024 * 1024
ENV_PREFIX = "PRODUCTION_PLATFORM_TEST_FAILURE_ANALYSIS_"
FINGERPRINT_CACHE_SECONDS = 30
FINGERPRINT_CACHE_ENTRIES = 512


class _AnalysisLocks:
    def __init__(self, *handles):
        self.handles = handles

    def close(self):
        for handle in reversed(self.handles):
            handle.close()


class SourceChangedError(ConflictError):
    pass


class UnsupportedReportError(ValueError):
    pass


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None
    return value if isinstance(value, dict) else None


def _rules_analysis(snapshot: Path, report_name: str, output: Path, settings: dict) -> dict:
    """Use the same reviewed rules without making any model request."""
    evidence = prepare_evidence(snapshot, report_name, settings)
    for index, finding in enumerate(evidence["deterministic_findings"], 1):
        finding["finding_id"] = f"F{index}"
    result = {
        "analysis_schema_version": 1,
        "analyzer_version": __version__,
        "status": "complete",
        "generated_at_utc": now(),
        "source_report": report_name,
        "input_hashes": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(snapshot.iterdir())},
        "evidence": evidence,
        "model_analysis": {"status": "disabled", "model": "未启用（规则分析）", "assessments": [], "requests": []},
    }
    output.mkdir(parents=True, exist_ok=True)
    markdown = render_markdown(result)
    (output / "analysis.md").write_text(markdown, encoding="utf-8")
    (output / "analysis.html").write_text('<!doctype html><meta charset="utf-8"><title>QC 失败分析</title><pre>' + html.escape(markdown) + "</pre>", encoding="utf-8")
    _write_json(output / "analysis.json", result)
    return result


class FailureAnalysisService:
    def __init__(self, reports: TestFailureService, cache_dir: Path, *, model_enabled: bool = False, settings: dict | None = None,
                 rules_concurrency: int = 3, model_concurrency: int = 1, retain_results: int = 3):
        self.reports = reports
        self.cache_dir = Path(cache_dir).expanduser().resolve()
        if self.cache_dir == reports.root or reports.root in self.cache_dir.parents:
            raise ValueError("分析缓存必须位于原始报告目录之外")
        self.model_enabled = model_enabled
        self.mode = "model" if model_enabled else "rules_only"
        self.settings = dict(settings or {})
        self._thread: threading.Thread | None = None
        self._threads: dict[str, threading.Thread] = {}
        self._guard = threading.RLock()
        self._active_keys: set[str] = set()
        self.rules_concurrency = max(1, min(16, int(rules_concurrency)))
        self.model_concurrency = max(1, min(16, int(model_concurrency)))
        self.retain_results = max(1, min(100, int(retain_results)))
        self._verified_files: dict[tuple, tuple[float, str]] = {}
        # Code/configuration changes invalidate completed results as well as
        # source changes; a rules-only result cannot masquerade as a model run.
        source_dir = Path(__file__).parent
        code_hashes = {name: hashlib.sha256((source_dir / name).read_bytes()).hexdigest()
                       for name in ("analysis.py", "parser.py", "reference.py", "qc_agent/analyzer.py", "qc_agent/evidence.py")}
        self.settings_key = _digest({"mode": self.mode, "settings": self.settings, "code": code_hashes})

    def _reference_hash(self) -> str | None:
        """The optional trusted protocol can change without restarting the API."""
        reference = self.settings.get("protocol_source_path")
        try:
            return hashlib.sha256(Path(reference).read_bytes()).hexdigest() if reference else None
        except OSError:
            return None

    def _key(self, report: dict) -> str:
        return _digest([self.reports.repository.root_key, report["id"]])

    def _state_path(self, key: str) -> Path:
        return self.cache_dir / key / "state.json"

    def _response(self, report: dict, status: str, *, error=None, state=None, result=None) -> dict:
        return {"status": status, "report_id": report["id"], "report_revision": report["revision"],
                "generated_at": state.get("generated_at") if state else None,
                "mode": self.mode, "error": error, "result": result}

    def _fingerprint(self, report: dict, snapshot: Path | None = None, *, use_cache: bool = False) -> tuple[str, str]:
        """Hash bounded reads through the attachment API, checking both ends."""
        paths = report.get("attachment_paths", {})
        if not paths.get("json"):
            raise UnsupportedReportError("当前报告没有结构化 JSON 证据包，暂不支持自动分析")
        if report.get("parse_status") == "incomplete":
            raise SourceChangedError("报告尚未完整上传，请重新扫描后再分析")
        expected = report.get("attachment_signatures", {})
        expected_hashes = report.get("attachment_hashes", {})
        reference_hash = self._reference_hash()
        name = Path(paths["json"]).name
        stem = Path(name).stem
        names = {"json": name, "log": stem + ".log", "encoder": stem + ".encoder.csv"}
        indexed_identity = _digest({field: report.get(field) for field in (
            "id", "revision", "source_format", "run_id", "report_run_id", "attachment_paths",
            "attachment_signatures", "attachment_hashes",
        )})
        fingerprints, total = {}, 0
        if snapshot:
            snapshot.mkdir(parents=True, exist_ok=True)
        for kind in ("json", "log", "encoder"):
            if not paths.get(kind):
                continue
            if Path(paths[kind]).parent != Path(paths["json"]).parent or Path(paths[kind]).name != names[kind]:
                raise UnsupportedReportError("报告附件名称或目录不属于同一证据包，请重新扫描核对")
            try:
                handle, actual_name = self.reports.open_attachment(report["id"], kind, verify_content=False)
            except NotFoundError as error:
                raise SourceChangedError("报告附件已变化或不可用，请重新扫描后再分析") from error
            with handle:
                before = os.fstat(handle.fileno())
                if list(stat_signature(before)) != expected.get(kind) or actual_name != names[kind]:
                    raise SourceChangedError("报告索引已更新，请刷新后重新分析")
                if before.st_size > MAX_FILE_BYTES:
                    raise UnsupportedReportError("报告附件超过 64 MiB 分析上限")
                cache_key = (indexed_identity, kind, content_signature(before), self.settings_key, reference_hash)
                with self._guard:
                    cached = self._verified_files.get(cache_key) if use_cache and snapshot is None else None
                if cached and cached[0] > time.monotonic():
                    total += before.st_size
                    if total > MAX_TOTAL_BYTES:
                        raise UnsupportedReportError("报告附件超过分析大小上限")
                    if content_signature(os.fstat(handle.fileno())) != content_signature(before):
                        raise SourceChangedError("读取期间报告发生变化，请重新扫描后再分析")
                    fingerprints[kind] = {"path": paths[kind], "signature": expected.get(kind), "sha256": cached[1]}
                    continue
                checksum = hashlib.sha256()
                size = 0
                json_content = bytearray() if kind == "json" else None
                output = (snapshot / names[kind]).open("wb") if snapshot else None
                try:
                    while chunk := handle.read(256 * 1024):
                        size += len(chunk)
                        total += len(chunk)
                        if size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
                            raise UnsupportedReportError("报告附件超过分析大小上限")
                        checksum.update(chunk)
                        if json_content is not None:
                            json_content.extend(chunk)
                        if output:
                            output.write(chunk)
                finally:
                    if output:
                        output.close()
                if content_signature(os.fstat(handle.fileno())) != content_signature(before) or size != before.st_size:
                    raise SourceChangedError("读取期间报告发生变化，请重新扫描后再分析")
            content_hash = checksum.hexdigest()
            if kind in expected_hashes and content_hash != expected_hashes[kind]:
                raise SourceChangedError("报告附件内容与索引不一致，请重新扫描后再分析")
            if json_content is not None:
                # This checks the exact bytes hashed and copied above. Older
                # indexes may have no content hashes, but their semantic revision
                # must still agree with the evidence sent to the analyzer.
                try:
                    parsed = parse_report(bytes(json_content), "json", name)
                except (UnicodeError, json.JSONDecodeError) as error:
                    raise SourceChangedError("结构化报告暂时无法解析，请重新扫描后再分析") from error
                except (ValueError, TypeError, RecursionError) as error:
                    raise UnsupportedReportError("当前报告格式不支持自动分析；需要 schema_version=1 的协议 JSON 证据包") from error
                if parsed["revision"] != report["revision"]:
                    raise SourceChangedError("报告失败证据与索引版本不一致，请重新扫描后再分析")
                # Run IDs determine report identity but are deliberately absent
                # from the failure-only semantic revision. JSON indexes always
                # contain both fields, including empty strings for missing IDs.
                # Logs can omit an ID; any identity they did record must agree.
                if any(
                    (report.get("source_format") == "json" or report.get(field))
                    and parsed.get(field, "") != (report.get(field) or "")
                    for field in ("run_id", "report_run_id")
                ):
                    raise SourceChangedError("报告运行标识与索引不一致，请重新扫描后再分析")
                del parsed
            with self._guard:
                if len(self._verified_files) >= FINGERPRINT_CACHE_ENTRIES:
                    self._verified_files.clear()
                self._verified_files[cache_key] = (time.monotonic() + FINGERPRINT_CACHE_SECONDS, content_hash)
            fingerprints[kind] = {"path": paths[kind], "signature": expected.get(kind), "sha256": content_hash}
        latest = self.reports.repository.get_report(report["id"])
        if (latest["revision"] != report["revision"] or latest.get("attachment_paths") != paths
                or latest.get("attachment_signatures") != expected or latest.get("attachment_hashes", {}) != expected_hashes):
            raise SourceChangedError("报告索引已更新，请刷新后重新分析")
        if self._reference_hash() != reference_hash:
            raise SourceChangedError("核对协议源码期间文件发生变化，请重新分析")
        return _digest({"revision": report["revision"], "attachments": fingerprints,
                        "settings": self.settings_key, "reference": reference_hash}), name

    def _claim_lock(self, key: str):
        directory = self.cache_dir / key
        directory.mkdir(parents=True, exist_ok=True)
        handle = (directory / ".analysis.lock").open("a+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            raise ConflictError("该报告正在分析，请等待完成后重试") from None
        pool = "model" if self.model_enabled else "rules"
        limit = self.model_concurrency if self.model_enabled else self.rules_concurrency
        try:
            for index in range(limit):
                slot = (self.cache_dir / f".{pool}-slot-{index}.lock").open("a+")
                try:
                    fcntl.flock(slot.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    slot.close()
                    continue
                return _AnalysisLocks(handle, slot)
            raise ConflictError("分析任务已达到并发上限，请等待完成后重试")
        except Exception:
            handle.close()
            raise

    def _is_running(self, key: str) -> bool:
        with self._guard:
            if key in self._active_keys:
                return True
            lock_path = self.cache_dir / key / ".analysis.lock"
            if not lock_path.exists():
                return False
            with lock_path.open("r+") as handle:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return True
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                return False

    def _clean_cache(self, key: str, current: str | None = None) -> None:
        """Only run while this report's process lock is owned; never touch sources."""
        directory = self.cache_dir / key
        results = []
        try:
            for path in directory.iterdir():
                if path.is_symlink() or not path.is_dir():
                    continue
                if re.fullmatch(r"\.pending-[0-9a-f]{32}", path.name):
                    shutil.rmtree(path)
                elif re.fullmatch(r"result-[0-9a-f]{32}", path.name):
                    results.append(path)
            results.sort(key=lambda path: (path.name == current, path.stat().st_mtime_ns), reverse=True)
            for path in results[self.retain_results:]:
                shutil.rmtree(path)
        except OSError:
            logger.warning("QC analysis cache cleanup deferred: report_key=%s", key)

    def _valid_result(self, result: dict | None, report: dict, state: dict, name: str) -> bool:
        """Reject incomplete, cross-report, or corrupted cached analyzer output."""
        if not result or type(result.get("analysis_schema_version")) is not int or result["analysis_schema_version"] != 1:
            return False
        if any(result.get(field) != value for field, value in {
            "status": "complete", "analyzer_version": __version__, "source_report": name,
            "report_id": report["id"], "report_revision": report["revision"], "source_fingerprint": state["fingerprint"],
        }.items()):
            return False
        if any(state.get(field) != value for field, value in {
            "report_id": report["id"], "report_revision": report["revision"], "mode": self.mode,
        }.items()):
            return False
        hashes = result.get("input_hashes")
        paths = report.get("attachment_paths", {})
        if not isinstance(hashes, dict) or set(hashes) != {Path(path).name for path in paths.values()} or hashes != state.get("input_hashes"):
            return False
        if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes.values()):
            return False
        if any(hashes.get(Path(paths[kind]).name) != value for kind, value in report.get("attachment_hashes", {}).items() if kind in paths):
            return False
        try:
            generated_at = datetime.fromisoformat(result["generated_at_utc"].replace("Z", "+00:00"))
            if generated_at.tzinfo is None or result["generated_at_utc"] != state.get("generated_at"):
                return False
            if _digest(result) != state.get("result_sha256"):
                return False
        except (KeyError, TypeError, ValueError, AttributeError):
            return False
        evidence = result.get("evidence")
        model = result.get("model_analysis")
        if not isinstance(evidence, dict) or not isinstance(model, dict):
            return False
        if (type(evidence.get("schema_version")) is not int or evidence["schema_version"] != 1
                or evidence.get("source_report") != name or evidence.get("input_sha256") != hashes.get(name)):
            return False
        identity = evidence.get("report_identity")
        if not isinstance(identity, dict) or any((identity.get(field) or "") != (report.get(field) or "") for field in ("run_id", "report_run_id")):
            return False
        findings = evidence.get("deterministic_findings")
        catalog = evidence.get("evidence_catalog")
        if not isinstance(findings, list) or not findings or not isinstance(catalog, dict):
            return False
        seen = set()
        for finding in findings:
            if not isinstance(finding, dict):
                return False
            for field in ("finding_id", "category", "status", "observed", "direction", "retest"):
                if not isinstance(finding.get(field), str) or not finding[field]:
                    return False
            if finding["finding_id"] in seen:
                return False
            seen.add(finding["finding_id"])
            if not isinstance(finding.get("checks"), list) or any(not isinstance(item, str) for item in finding["checks"]):
                return False
            refs = finding.get("evidence_refs")
            if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in catalog for ref in refs):
                return False
            threshold_refs = finding.get("threshold_evidence_refs", [])
            if not isinstance(threshold_refs, list) or any(not isinstance(ref, str) or ref not in catalog for ref in threshold_refs):
                return False
        if not isinstance(evidence.get("blocked_tests"), list) or any(not isinstance(item, dict) for item in evidence["blocked_tests"]):
            return False
        if not isinstance(evidence.get("limitations"), list) or any(not isinstance(item, str) for item in evidence["limitations"]):
            return False
        if not isinstance(model.get("model"), str) or not isinstance(model.get("requests"), list):
            return False
        if self.model_enabled:
            if model.get("status") != "completed":
                return False
            try:
                _validate_assessments({"assessments": model.get("assessments")}, findings)
            except (ModelAnalysisError, TypeError, KeyError):
                return False
        elif model.get("status") != "disabled" or model.get("assessments") != [] or model["requests"]:
            return False
        return True

    def status(self, report_id: str) -> dict:
        report = self.reports.repository.get_report(report_id)
        try:
            fingerprint, name = self._fingerprint(report, use_cache=True)
        except UnsupportedReportError as error:
            return self._response(report, "unsupported", error=str(error))
        except SourceChangedError as error:
            return self._response(report, "stale", error=str(error))
        return self._status(report, fingerprint, name)

    def _status(self, report: dict, fingerprint: str, name: str) -> dict:
        key = self._key(report)
        state = _read_json(self._state_path(key))
        if not state:
            return self._response(report, "idle")
        if state.get("fingerprint") != fingerprint:
            return self._response(report, "stale", error="报告内容、附件或分析配置已更新，请重新分析")
        if state.get("status") == "running" and not self._is_running(key):
            # Workers publish their final state before releasing the lock. Read
            # again after observing an idle lock so a completed job cannot be
            # mistaken for an interrupted one using a stale running marker.
            running_job = state.get("job")
            state = _read_json(self._state_path(key))
            if not state:
                return self._response(report, "failed", error="上次分析已中断，请重新生成")
            if state.get("fingerprint") != fingerprint:
                return self._response(report, "stale", error="报告内容、附件或分析配置已更新，请重新分析")
            if state.get("status") == "running" and state.get("job") == running_job:
                return self._response(report, "failed", error="上次分析已中断，请重新生成")
        if state.get("status") == "complete":
            revision = state.get("result_directory", "")
            if not isinstance(revision, str) or not re.fullmatch(r"result-[0-9a-f]{32}", revision):
                return self._response(report, "failed", error="分析缓存无效，请重新生成")
            result_directory = self.cache_dir / key / revision
            result_path = result_directory / "analysis.json"
            if result_directory.is_symlink() or result_path.is_symlink():
                return self._response(report, "failed", error="分析缓存无效，请重新生成")
            result = _read_json(result_path)
            if not self._valid_result(result, report, state, name):
                return self._response(report, "failed", error="分析结果不可用，请重新生成")
            return self._response(report, "complete", state=state, result=result)
        if state.get("status") not in {"running", "failed", "stale", "unsupported"}:
            return self._response(report, "failed", error="分析缓存无效，请重新生成")
        return self._response(report, state["status"], error=state.get("error"), state=state)

    def request(self, report_id: str, expected_revision: str, *, force: bool = False) -> dict:
        with self._guard:
            report = self.reports.repository.get_report(report_id)
            if report["revision"] != expected_revision:
                raise ConflictError("报告版本已更新，请刷新并核对最新报告后重新生成")
            try:
                fingerprint, name = self._fingerprint(report, use_cache=True)
            except UnsupportedReportError as error:
                return self._response(report, "unsupported", error=str(error))
            current = self._status(report, fingerprint, name)
            if current["status"] in {"running", "unsupported"} or current["status"] == "complete" and not force:
                return current
            key = self._key(report)
            try:
                lock = self._claim_lock(key)
            except ConflictError:
                concurrent = self._status(report, fingerprint, name)
                if concurrent["status"] == "running" and concurrent["report_revision"] == expected_revision:
                    return concurrent
                raise
            job = uuid4().hex
            state = {"status": "running", "fingerprint": fingerprint, "job": job, "report_id": report["id"],
                     "report_revision": report["revision"], "mode": self.mode, "started_at": now(), "error": None}
            try:
                # Another process may have finished after our initial cache read.
                completed = _read_json(self._state_path(key))
                if not force and completed and completed.get("status") == "complete" and completed.get("fingerprint") == fingerprint:
                    current = self._status(report, fingerprint, name)
                    if current["status"] == "complete" and current["report_revision"] == expected_revision:
                        lock.close()
                        return current
                self._clean_cache(key, completed.get("result_directory") if completed else None)
                _write_json(self._state_path(key), state)
                self._active_keys.add(key)
                self._thread = threading.Thread(target=self._perform, args=(report, state, name, lock), name="test-failure-analysis", daemon=True)
                self._threads[key] = self._thread
                self._thread.start()
            except Exception:
                self._active_keys.discard(key)
                self._threads.pop(key, None)
                lock.close()
                raise
            return self._response(report, "running")

    def _perform(self, report: dict, state: dict, name: str, lock) -> None:
        key = self._key(report)
        staging = self.cache_dir / key / (".pending-" + state["job"])
        try:
            fingerprint, actual_name = self._fingerprint(report, staging / "_inputs")
            if fingerprint != state["fingerprint"] or actual_name != name:
                raise SourceChangedError("分析开始前报告或协议源码已变化，请重新分析")
            # Reject unsupported formats before invoking the model.
            evidence = prepare_evidence(staging / "_inputs", name, self.settings)
            if self.model_enabled:
                analyze_report(staging / "_inputs", name, staging, self.settings)
                result = _read_json(staging / "analysis.json")
            else:
                result = _rules_analysis(staging / "_inputs", name, staging, self.settings)
            if not result or result.get("status") != "complete":
                raise RuntimeError("Incomplete analysis output")
            for index, finding in enumerate(evidence["deterministic_findings"], 1):
                finding["finding_id"] = f"F{index}"
            if result.get("evidence") != evidence:
                raise RuntimeError("Analysis evidence does not match the input snapshot")
            result.update(report_id=report["id"], report_revision=report["revision"], source_fingerprint=state["fingerprint"])
            state = {**state, "input_hashes": {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (staging / "_inputs").iterdir()
            }, "generated_at": result.get("generated_at_utc"), "result_sha256": _digest(result)}
            if not self._valid_result(result, report, state, name):
                raise RuntimeError("Analysis output failed validation")
            _write_json(staging / "analysis.json", result)
            after, _ = self._fingerprint(report)
            if after != state["fingerprint"]:
                raise SourceChangedError("分析期间报告或协议源码发生变化，请重新分析")
            directory = "result-" + state["job"]
            staging.rename(self.cache_dir / key / directory)
            _write_json(self._state_path(key), {**state, "status": "complete", "result_directory": directory,
                                               "generated_at": result["generated_at_utc"], "error": None})
            self._clean_cache(key, directory)
        except Exception as error:
            if isinstance(error, SourceChangedError):
                status, message = "stale", str(error)
            elif isinstance(error, UnsupportedReportError) or isinstance(error, ValueError) and str(error).startswith("unsupported_schema:"):
                status, message = "unsupported", "当前报告格式不支持自动分析；需要 schema_version=1 的协议 JSON 证据包"
            elif isinstance(error, ModelAnalysisError):
                status, message = "failed", "本地模型不可用或输出未通过校验，请检查模型配置后重试"
            else:
                status, message = "failed", "分析未完成，请核对报告是否完整后重试"
            logger.warning("QC failure analysis did not complete: report=%s error=%s", report["id"], type(error).__name__)
            _write_json(self._state_path(key), {**state, "status": status, "error": message, "finished_at": now()})
        finally:
            shutil.rmtree(staging, ignore_errors=True)
            with self._guard:
                self._active_keys.discard(key)
                self._threads.pop(key, None)
                lock.close()


@lru_cache(maxsize=1)
def get_analysis_service() -> FailureAnalysisService:
    settings = {
        "model_base_url": os.getenv(ENV_PREFIX + "MODEL_BASE_URL", "http://127.0.0.1:11434"),
        "model": os.getenv(ENV_PREFIX + "MODEL", "qwen3:8b"),
        "model_timeout_seconds": float(os.getenv(ENV_PREFIX + "MODEL_TIMEOUT_SECONDS", "240")),
        "protocol_source_path": os.getenv(ENV_PREFIX + "PROTOCOL_SOURCE_PATH", ""),
    }
    return FailureAnalysisService(
        get_service(), Path(os.getenv(ENV_PREFIX + "DIR", str(Path(config.DATA_DIR) / "defect-search" / "test-failure-analysis"))),
        model_enabled=os.getenv(ENV_PREFIX + "MODEL_ENABLED", "false").strip().lower() in {"true", "1", "yes"}, settings=settings,
        rules_concurrency=int(os.getenv(ENV_PREFIX + "RULES_CONCURRENCY", "3")),
        model_concurrency=int(os.getenv(ENV_PREFIX + "MODEL_CONCURRENCY", "1")),
        retain_results=int(os.getenv(ENV_PREFIX + "RETAIN_RESULTS", "3")),
    )
