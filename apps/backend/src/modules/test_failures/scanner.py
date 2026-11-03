from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from .filesystem import content_signature, open_source, source_stat, stat_signature
from .parser import digest, parse_report
from .repository import Repository


MAX_REPORT_BYTES = 32 * 1024 * 1024
MAX_SCAN_ERRORS = 50


class PendingFile(Exception):
    pass


class Scanner:
    def __init__(self, root: Path, repository: Repository, stable_seconds: float = 2):
        self.root = root
        self.repository = repository
        self.stable_seconds = stable_seconds
        self._hash_cache: dict[str, tuple[tuple, float, str]] = {}
        self._invalid_json: dict[str, tuple[str, str]] = {}

    def _read(self, relative: str) -> bytes:
        with open_source(self.root, relative) as handle:
            before = os.fstat(handle.fileno())
            if time.time() - before.st_mtime < self.stable_seconds:
                raise PendingFile(relative)
            if before.st_size > MAX_REPORT_BYTES:
                raise ValueError("报告超过 32 MiB 解析限制")
            content = handle.read(MAX_REPORT_BYTES + 1)
            after = os.fstat(handle.fileno())
        current = source_stat(self.root, relative)
        if stat_signature(before) != stat_signature(after) or stat_signature(after) != stat_signature(current):
            raise PendingFile(relative)
        if len(content) > MAX_REPORT_BYTES:
            raise ValueError("报告超过 32 MiB 解析限制")
        return content

    def _fingerprint(self, relative: str) -> tuple[tuple[int, int, int], str]:
        """Read stable bytes even when inode, size and mtime have not changed.

        Encoder and optional log attachments are streamed without the report
        parser's size limit. Keeping hashes separate from semantic revisions
        lets receipt/format changes invalidate analysis without reopening QC.
        """
        checksum = hashlib.sha256()
        size = 0
        with open_source(self.root, relative) as handle:
            before = os.fstat(handle.fileno())
            if time.time() - before.st_mtime < self.stable_seconds:
                raise PendingFile(relative)
            cached = self._hash_cache.get(relative)
            if cached and cached[0] == content_signature(before) and time.monotonic() - cached[1] < 60:
                return stat_signature(before), cached[2]
            while chunk := handle.read(256 * 1024):
                size += len(chunk)
                if size > before.st_size:
                    raise PendingFile(relative)
                checksum.update(chunk)
            after = os.fstat(handle.fileno())
        current = source_stat(self.root, relative)
        if size != before.st_size or content_signature(before) != content_signature(after) or content_signature(after) != content_signature(current):
            raise PendingFile(relative)
        if len(self._hash_cache) >= 4096:
            self._hash_cache.pop(next(iter(self._hash_cache)))
        result = checksum.hexdigest()
        self._hash_cache[relative] = (content_signature(after), time.monotonic(), result)
        return stat_signature(after), result

    def _parse(self, relative: str, kind: str, expected_hash: str) -> dict:
        content = self._read(relative)
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise PendingFile(relative)
        return parse_report(content, kind, Path(relative).name)

    def scan(self) -> dict:
        if not self.root.is_dir():
            raise FileNotFoundError("失败报告目录不存在或未挂载")
        self.repository.prepare_scan()
        groups: dict[str, dict[str, str]] = {}
        errors: list[dict] = []
        pending = 0
        error_count = 0

        def error(path: str, message: str) -> None:
            nonlocal error_count
            error_count += 1
            if len(errors) < MAX_SCAN_ERRORS:
                errors.append({"path": path, "message": message[:500]})

        def walk_error(exc: OSError) -> None:
            error("", f"无法读取报告子目录: {exc.strerror or type(exc).__name__}")

        for directory, subdirs, filenames in os.walk(self.root, followlinks=False, onerror=walk_error):
            subdirs[:] = sorted(name for name in subdirs if not (Path(directory) / name).is_symlink())
            for filename in sorted(filenames):
                path = Path(directory) / filename
                relative = path.relative_to(self.root).as_posix()
                if filename.endswith(".encoder.csv"):
                    stem, kind = relative[:-len(".encoder.csv")], "encoder"
                elif path.suffix.lower() in {".json", ".log"}:
                    stem, kind = relative[:-len(path.suffix)], path.suffix.lower()[1:]
                else:
                    continue
                if path.is_symlink():
                    error(relative, "忽略符号链接附件")
                    continue
                groups.setdefault(stem, {})[kind] = relative
        for group, attachments in groups.items():
            if not ({"json", "log"} & attachments.keys()):
                continue
            try:
                fingerprints = {}
                hashes = {}
                stable_attachments = {}
                for kind, relative in attachments.items():
                    try:
                        fingerprints[kind], hashes[kind] = self._fingerprint(relative)
                    except PendingFile:
                        pending += 1
                    else:
                        stable_attachments[kind] = relative
                signature = digest({
                    "present": sorted(attachments),
                    "attachments": {kind: {"path": stable_attachments[kind], "stat": fingerprints[kind], "sha256": hashes[kind]} for kind in stable_attachments},
                })
                existing = self.repository.source(group)
                if existing and existing["signature"] == signature:
                    if self.repository.get_report(existing["report_id"])["parse_status"] == "incomplete":
                        error(group, "报告证据不完整，未取得明确失败判定或报告提取异常")
                    continue
                invalid = self._invalid_json.get(group)
                if (existing and existing["signature"] == "retry:" + signature) or (invalid and invalid[0] == signature):
                    error(attachments.get("json", group), invalid[1] if invalid and invalid[0] == signature else "JSON 解析失败：文件内容未变化，等待文件更新后重试")
                    continue
                # JSON is uploaded last. Wait for it to finish instead of downgrading.
                if "json" in attachments and "json" not in stable_attachments:
                    continue
                payload = None
                retry_json = False
                if "json" in stable_attachments:
                    try:
                        payload = self._parse(stable_attachments["json"], "json", hashes["json"])
                    except PendingFile:
                        pending += 1
                        continue
                    except (ValueError, UnicodeError, TypeError, RecursionError) as exc:
                        message = f"JSON 解析失败: {exc}"
                        error(stable_attachments["json"], message)
                        if len(self._invalid_json) >= 4096:
                            self._invalid_json.pop(next(iter(self._invalid_json)))
                        self._invalid_json[group] = (signature, message[:500])
                        retry_json = True
                        if existing:
                            # Preserve the last valid structured evidence and its
                            # JSON fingerprint. Optional attachment deletions can
                            # still converge while a replacement JSON is invalid.
                            previous = self.repository.get_report(existing["report_id"])
                            # Legacy indexes could point multiple phase packages
                            # at one report. Never borrow another package's JSON
                            # when this source is temporarily unreadable.
                            if previous.get("source_group") == group:
                                payload = previous
                                stable_attachments.pop("json")
                if payload is None and "log" in stable_attachments:
                    payload = self._parse(stable_attachments["log"], "log", hashes["log"])
                if payload is None:
                    continue
                if not retry_json:
                    self._invalid_json.pop(group, None)
                if payload["parse_status"] == "incomplete":
                    error(group, "报告证据不完整，未取得明确失败判定或报告提取异常")
                payload["attachment_signatures"] = {kind: fingerprints[kind] for kind in stable_attachments}
                payload["attachment_hashes"] = {kind: hashes[kind] for kind in stable_attachments}
                self.repository.upsert(group, "retry:" + signature if retry_json else signature, payload, stable_attachments, present_kinds=set(attachments))
            except PendingFile:
                pending += 1
            except (OSError, ValueError, TypeError, RecursionError) as exc:
                error(group, f"无法读取报告: {exc}")
        return {"errors": errors, "pending_files": pending, "parse_errors": error_count}
