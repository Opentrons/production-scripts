from __future__ import annotations

import ipaddress
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any


SSH_OT3_DIR_ENV = "PRODUCTION_PLATFORM_SSH_OT3_DIR"
SETUP_SCRIPT_NAME = "setup_ssh_keys.sh"
MAX_OUTPUT_CHARS = 100_000
_SUCCESS_MESSAGE_PATTERN = re.compile(r"^Added ([1-9][0-9]*) new keys$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_robot_ip(ip: str) -> str:
    normalized = str(ip or "").strip()
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError as exc:
        raise ValueError(f"无效设备 IP: {normalized or '(空)'}") from exc
    if address.version != 4 or address.is_unspecified or address.is_loopback or address.is_multicast:
        raise ValueError(f"无效设备 IP: {normalized}")
    return str(address)


def _setup_directories() -> list[Path]:
    configured = str(os.getenv(SSH_OT3_DIR_ENV, "") or "").strip()
    home = Path.home()
    candidates = [
        *(Path(item.strip()).expanduser() for item in configured.split(os.pathsep) if item.strip()),
        Path("/ssh-ot3"),
        home / "ssh-ot3",
        home / "projects" / "ssh-ot3",
    ]
    directories: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
        except (FileNotFoundError, OSError):
            continue
        normalized = str(resolved)
        if resolved.is_dir() and normalized not in seen:
            seen.add(normalized)
            directories.append(resolved)
    return directories


def resolve_setup_script() -> Path:
    for directory in _setup_directories():
        script = directory / SETUP_SCRIPT_NAME
        if script.is_file():
            return script
    raise RuntimeError(
        f"未找到 {SETUP_SCRIPT_NAME}；请将 ssh-ot3 放到 /ssh-ot3、~/ssh-ot3 或 ~/projects/ssh-ot3，"
        f"也可通过 {SSH_OT3_DIR_ENV} 配置目录"
    )


def _truncate(value: str) -> tuple[str, bool]:
    if len(value) <= MAX_OUTPUT_CHARS:
        return value, False
    return value[:MAX_OUTPUT_CHARS], True


def _output_text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def _response_messages(output: str) -> list[str]:
    messages: list[str] = []
    decoder = json.JSONDecoder()
    cursor = 0
    while cursor < len(output):
        start = output.find("{", cursor)
        if start < 0:
            break
        try:
            payload, consumed = decoder.raw_decode(output[start:])
        except json.JSONDecodeError:
            cursor = start + 1
            continue
        cursor = start + consumed
        if isinstance(payload, dict):
            message = str(payload.get("message") or payload.get("detail") or payload.get("error") or "").strip()
            if message:
                messages.append(message)
    return messages


def _installation_outcome(return_code: int, stdout: str, stderr: str) -> tuple[bool, str]:
    messages = _response_messages(f"{stdout}\n{stderr}")
    success_message = next(
        (
            message
            for message in messages
            if _SUCCESS_MESSAGE_PATTERN.fullmatch(message)
        ),
        "",
    )
    if return_code == 0 and success_message:
        return True, success_message
    if return_code != 0:
        return False, f"安装脚本退出码 {return_code}"
    if messages:
        return False, messages[-1]
    combined = f"{stderr}\n{stdout}".casefold()
    if "curl:" in combined:
        return False, "连接设备密钥接口失败"
    return False, "设备未返回密钥安装成功提示"


def install_ssh_key(ip: str, timeout: int = 30, *, script_path: Path | None = None) -> dict[str, Any]:
    normalized_ip = _normalize_robot_ip(ip)
    normalized_timeout = max(1, min(int(timeout), 300))
    script = (script_path or resolve_setup_script()).resolve(strict=True)
    if not script.is_file() or script.name != SETUP_SCRIPT_NAME:
        raise RuntimeError(f"安装脚本不可用: {script}")

    started_at = _utc_now()
    started = perf_counter()
    try:
        completed = subprocess.run(
            ["sh", script.name, "-flex", normalized_ip],
            cwd=script.parent,
            capture_output=True,
            text=True,
            timeout=normalized_timeout,
            check=False,
        )
        stdout, stdout_truncated = _truncate(completed.stdout or "")
        stderr, stderr_truncated = _truncate(completed.stderr or "")
        success, message = _installation_outcome(completed.returncode, stdout, stderr)
        return {
            "ip": normalized_ip,
            "success": success,
            "message": message,
            "exit_code": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "output_truncated": stdout_truncated or stderr_truncated,
            "started_at": started_at,
            "finished_at": _utc_now(),
            "duration_ms": round((perf_counter() - started) * 1000),
        }
    except subprocess.TimeoutExpired as exc:
        stdout, stdout_truncated = _truncate(_output_text(exc.stdout))
        stderr, stderr_truncated = _truncate(_output_text(exc.stderr))
        return {
            "ip": normalized_ip,
            "success": False,
            "message": f"安装超时（{normalized_timeout} 秒）",
            "exit_code": None,
            "stdout": stdout,
            "stderr": stderr,
            "output_truncated": stdout_truncated or stderr_truncated,
            "started_at": started_at,
            "finished_at": _utc_now(),
            "duration_ms": round((perf_counter() - started) * 1000),
        }
    except OSError as exc:
        raise RuntimeError(f"执行密钥安装脚本失败: {exc}") from exc


def install_ssh_keys_batch(
    ips: list[str],
    timeout: int = 30,
    concurrency: int = 4,
) -> dict[str, Any]:
    normalized_ips: list[str] = []
    seen: set[str] = set()
    for ip in ips:
        normalized = _normalize_robot_ip(ip)
        if normalized not in seen:
            seen.add(normalized)
            normalized_ips.append(normalized)
    if not normalized_ips:
        raise ValueError("至少选择一台设备")

    script = resolve_setup_script()
    worker_count = max(1, min(int(concurrency), 10, len(normalized_ips)))
    results_by_ip: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="ssh-key-setup") as executor:
        futures = {
            executor.submit(install_ssh_key, ip, timeout, script_path=script): ip
            for ip in normalized_ips
        }
        for future in as_completed(futures):
            ip = futures[future]
            try:
                results_by_ip[ip] = future.result()
            except Exception as exc:
                results_by_ip[ip] = {
                    "ip": ip,
                    "success": False,
                    "message": str(exc),
                    "exit_code": None,
                    "stdout": "",
                    "stderr": "",
                    "output_truncated": False,
                    "started_at": _utc_now(),
                    "finished_at": _utc_now(),
                    "duration_ms": 0,
                }

    results = [results_by_ip[ip] for ip in normalized_ips]
    success_count = sum(1 for result in results if result["success"])
    return {
        "results": results,
        "total": len(results),
        "success_count": success_count,
        "failed_count": len(results) - success_count,
        "concurrency": worker_count,
    }
