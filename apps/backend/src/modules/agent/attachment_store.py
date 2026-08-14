from __future__ import annotations

import csv
import io
import json
import os
import re
import time
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiofiles
from fastapi import UploadFile

from core import config


MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 256 * 1024
MAX_READ_CHARS = 20_000
SUPPORTED_EXTENSIONS = {
    "csv", "tsv", "txt", "log", "json", "md", "markdown", "xml", "yaml", "yml", "ini", "cfg", "conf",
}
ATTACHMENT_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class AttachmentError(ValueError):
    pass


class AttachmentNotFoundError(AttachmentError):
    pass


class AttachmentTooLargeError(AttachmentError):
    pass


class AttachmentUnsupportedError(AttachmentError):
    pass


_attachment_scope: ContextVar[tuple[str, frozenset[str]] | None] = ContextVar(
    "production_agent_attachment_scope",
    default=None,
)


def set_attachment_scope(owner_id: str, attachment_ids: set[str]) -> Token:
    return _attachment_scope.set((owner_id, frozenset(attachment_ids)))


def reset_attachment_scope(token: Token) -> None:
    _attachment_scope.reset(token)


def _root() -> Path:
    return Path(config.AGENT_ATTACHMENT_DIR)


def _paths(attachment_id: str) -> tuple[Path, Path]:
    if not ATTACHMENT_ID_PATTERN.fullmatch(str(attachment_id or "")):
        raise AttachmentNotFoundError("附件不存在或已过期")
    root = _root()
    return root / f"{attachment_id}.data", root / f"{attachment_id}.json"


def _safe_filename(filename: str | None) -> str:
    name = Path(str(filename or "attachment").replace("\\", "/")).name.strip()
    name = "".join(character for character in name if character >= " " and character != "\x7f")[:255]
    return name or "attachment"


def _is_supported(filename: str, content_type: str | None) -> bool:
    extension = Path(filename).suffix.lower().lstrip(".")
    normalized_type = str(content_type or "").lower()
    return extension in SUPPORTED_EXTENSIONS or normalized_type.startswith("text/") or normalized_type == "application/json"


def _read_metadata(attachment_id: str) -> dict[str, Any]:
    data_path, metadata_path = _paths(attachment_id)
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AttachmentNotFoundError("附件不存在或已过期") from exc
    if not data_path.is_file() or not isinstance(metadata, dict):
        raise AttachmentNotFoundError("附件不存在或已过期")
    return metadata


def cleanup_expired() -> None:
    root = _root()
    if not root.is_dir():
        return
    cutoff = time.time() - config.AGENT_ATTACHMENT_TTL_SECONDS
    for metadata_path in root.glob("*.json"):
        try:
            if metadata_path.stat().st_mtime >= cutoff:
                continue
        except OSError:
            continue
        attachment_id = metadata_path.stem
        data_path = root / f"{attachment_id}.data"
        metadata_path.unlink(missing_ok=True)
        data_path.unlink(missing_ok=True)


def _metadata_for_owner(attachment_id: str, owner_id: str) -> dict[str, Any]:
    cleanup_expired()
    metadata = _read_metadata(attachment_id)
    if metadata.get("owner_id") != owner_id:
        raise AttachmentNotFoundError("附件不存在或已过期")
    return metadata


def validate_references(references: list[Any], owner_id: str) -> list[dict[str, Any]]:
    validated = []
    for reference in references:
        attachment_id = str(getattr(reference, "id", ""))
        metadata = _metadata_for_owner(attachment_id, owner_id)
        validated.append(
            {
                "id": attachment_id,
                "name": metadata["name"],
                "size": metadata["size"],
            }
        )
    return validated


async def save_attachment(upload: UploadFile, owner_id: str) -> dict[str, Any]:
    cleanup_expired()
    filename = _safe_filename(upload.filename)
    if not _is_supported(filename, upload.content_type):
        raise AttachmentUnsupportedError("仅支持 CSV、TXT、JSON 等文本文件")

    root = _root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    attachment_id = uuid4().hex
    data_path, metadata_path = _paths(attachment_id)
    temporary_path = root / f".{attachment_id}.upload"
    size = 0
    try:
        async with aiofiles.open(temporary_path, "wb") as output:
            while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
                size += len(chunk)
                if size > MAX_ATTACHMENT_BYTES:
                    raise AttachmentTooLargeError("单个附件不能超过 5 MB")
                await output.write(chunk)
        os.replace(temporary_path, data_path)
        data_path.chmod(0o600)
        uploaded_at = datetime.now(timezone.utc)
        metadata = {
            "id": attachment_id,
            "name": filename,
            "size": size,
            "content_type": upload.content_type or "text/plain",
            "owner_id": owner_id,
            "uploaded_at": uploaded_at.isoformat(),
            "expires_at": datetime.fromtimestamp(
                uploaded_at.timestamp() + config.AGENT_ATTACHMENT_TTL_SECONDS,
                tz=timezone.utc,
            ).isoformat(),
        }
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        metadata_path.chmod(0o600)
        return {key: metadata[key] for key in ("id", "name", "size", "content_type", "expires_at")}
    except Exception:
        temporary_path.unlink(missing_ok=True)
        data_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def delete_attachment(attachment_id: str, owner_id: str) -> None:
    _metadata_for_owner(attachment_id, owner_id)
    data_path, metadata_path = _paths(attachment_id)
    metadata_path.unlink(missing_ok=True)
    data_path.unlink(missing_ok=True)


def _scoped_attachment(attachment_id: str) -> tuple[dict[str, Any], Path]:
    scope = _attachment_scope.get()
    if scope is None or attachment_id not in scope[1]:
        raise AttachmentNotFoundError("当前对话无权访问该附件")
    metadata = _metadata_for_owner(attachment_id, scope[0])
    data_path, _ = _paths(attachment_id)
    return metadata, data_path


def _decode_attachment(attachment_id: str) -> tuple[dict[str, Any], str, str]:
    metadata, data_path = _scoped_attachment(attachment_id)
    raw = data_path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return metadata, raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return metadata, raw.decode("utf-8", errors="replace"), "utf-8-replace"


def read_attachment(attachment_id: str, offset: int = 0, max_chars: int = 16_000) -> dict[str, Any]:
    metadata, text, encoding = _decode_attachment(attachment_id)
    start = max(0, min(int(offset), len(text)))
    length = max(1_000, min(int(max_chars), MAX_READ_CHARS))
    end = min(start + length, len(text))
    return {
        "attachment_id": attachment_id,
        "name": metadata["name"],
        "size": metadata["size"],
        "encoding": encoding,
        "offset": start,
        "next_offset": end if end < len(text) else None,
        "total_chars": len(text),
        "has_more": end < len(text),
        "content": text[start:end],
    }


def inspect_attachment(attachment_id: str) -> dict[str, Any]:
    metadata, text, encoding = _decode_attachment(attachment_id)
    result: dict[str, Any] = {
        "attachment_id": attachment_id,
        "name": metadata["name"],
        "size": metadata["size"],
        "encoding": encoding,
        "total_chars": len(text),
        "line_count": len(text.splitlines()),
        "complete_file_scanned": True,
    }
    extension = Path(metadata["name"]).suffix.lower()
    if extension not in {".csv", ".tsv"}:
        result["preview"] = text[:4_000]
        return result

    delimiter = "\t" if extension == ".tsv" else ","
    try:
        dialect = csv.Sniffer().sniff(text[:16_384], delimiters=",\t;|")
        delimiter = dialect.delimiter
    except csv.Error:
        pass
    csv.field_size_limit(MAX_ATTACHMENT_BYTES)
    rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))
    if not rows:
        result["csv"] = {"delimiter": delimiter, "row_count": 0, "column_count": 0, "columns": []}
        return result

    headers = [header.strip() or f"column_{index + 1}" for index, header in enumerate(rows[0])]
    data_rows = rows[1:]
    column_count = max([len(headers), *(len(row) for row in data_rows)] or [0])
    if len(headers) < column_count:
        headers.extend(f"column_{index + 1}" for index in range(len(headers), column_count))
    blank_counts = [0] * column_count
    unique_values = [set() for _ in range(column_count)]
    duplicate_rows = 0
    seen_rows: set[tuple[str, ...]] = set()
    inconsistent_rows = 0
    for row in data_rows:
        normalized = tuple(row + [""] * (column_count - len(row)))
        if len(row) != column_count:
            inconsistent_rows += 1
        if normalized in seen_rows:
            duplicate_rows += 1
        else:
            seen_rows.add(normalized)
        for index, value in enumerate(normalized):
            stripped = value.strip()
            if not stripped:
                blank_counts[index] += 1
            else:
                unique_values[index].add(stripped)

    reported_columns = min(column_count, 100)
    result["csv"] = {
        "delimiter": delimiter,
        "row_count": len(data_rows),
        "column_count": column_count,
        "duplicate_rows": duplicate_rows,
        "inconsistent_column_rows": inconsistent_rows,
        "columns": [
            {
                "name": headers[index],
                "blank_count": blank_counts[index],
                "unique_nonblank_count": len(unique_values[index]),
                "duplicate_nonblank_count": max(0, len(data_rows) - blank_counts[index] - len(unique_values[index])),
            }
            for index in range(reported_columns)
        ],
        "omitted_column_count": column_count - reported_columns,
        "sample_rows": [row[:reported_columns] for row in data_rows[:5]],
    }
    return result
