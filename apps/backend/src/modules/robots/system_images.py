"""Server-side OT3 image library and bounded background update/download jobs.

Like code-flash, run this service in a single API worker. Jobs are journaled so
browser refreshes retain progress; interrupted jobs are never retried implicitly.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import requests

from core.config import DB_BUSINESS_DIR
from modules.robots.upload_ot3_system import (
    Endpoint, EXPECTED_ROBOT_MODEL, RobotUpdateClient, RobotUpdateError, format_status,
)

IMAGE_PATTERN = re.compile(r"ot3-system-(\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?)\.zip")
MAX_IMAGE_BYTES = 4 * 1024**3
ACTIVE = {"queued", "running"}
_LOCK = threading.RLock()
_TASKS: dict[str, dict] = {}
_LOADED = False
_UPDATES = ThreadPoolExecutor(max_workers=4, thread_name_prefix="system-install")
_DOWNLOADS = ThreadPoolExecutor(max_workers=2, thread_name_prefix="system-download")


def image_directory() -> Path:
    return Path(os.getenv("PRODUCTION_PLATFORM_OT3_SYSTEM_DIR", "/opt/ot3-system")).expanduser().resolve()


def _journal_directory() -> Path:
    return Path(os.getenv("PRODUCTION_PLATFORM_OT3_TASK_DIR", str(DB_BUSINESS_DIR / "system-image-tasks")))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save(task: dict) -> None:
    directory = _journal_directory()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{task['id']}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(task, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def _load() -> None:
    global _LOADED
    with _LOCK:
        if _LOADED:
            return
        for path in _journal_directory().glob("*.json"):
            task = json.loads(path.read_text(encoding="utf-8"))
            if task["status"] in ACTIVE:
                task.update(status="failed", stage="interrupted", finished_at=_now(),
                            message="服务重启导致任务中断，请检查设备状态后重试")
                _save(task)
            _TASKS[task["id"]] = task
        _LOADED = True


def _change(task_id: str, *, log: str | None = None, **values) -> None:
    with _LOCK:
        task = _TASKS[task_id]
        task.update(values)
        if log and (not task["logs"] or task["logs"][-1] != log):
            task["logs"] = [*task["logs"][-199:], log[:2000]]
        _save(task)


def list_tasks() -> list[dict]:
    _load()
    with _LOCK:
        ordered = sorted(_TASKS.values(), key=lambda task: task["created_at"], reverse=True)
        # Always include active tasks, plus the most recent completed tasks.
        return deepcopy([t for t in ordered if t["status"] in ACTIVE] +
                        [t for t in ordered if t["status"] not in ACTIVE][:100])


def resolve_image(name: str) -> Path:
    if not IMAGE_PATTERN.fullmatch(name):
        raise ValueError("请选择 ot3-system-版本.zip 镜像")
    directory = image_directory()
    path = directory / name
    if path.is_symlink() or path.resolve().parent != directory:
        raise ValueError("镜像路径无效")
    if not path.is_file():
        raise FileNotFoundError("镜像文件不存在")
    return path


def list_images() -> dict:
    directory = image_directory()
    images = []
    for path in directory.glob("ot3-system-*.zip"):
        match = IMAGE_PATTERN.fullmatch(path.name)
        if not match or path.is_symlink() or not path.is_file():
            continue
        stat = path.stat()
        images.append({"name": path.name, "version": match[1], "size": stat.st_size,
                       "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()})
    images.sort(key=lambda item: (*map(int, item["version"].split("-")[0].split(".")),
                                  "-" not in item["version"], item["version"]), reverse=True)
    return {"directory": str(directory), "images": images}


def _validate_archive(path: Path, image_name: str) -> dict:
    with zipfile.ZipFile(path) as archive:
        required = {"systemfs.xz", "systemfs.xz.sha256", "systemfs.xz.hash.sig", "VERSION.json"}
        if not required.issubset(archive.namelist()):
            raise ValueError("文件不是完整的 OT3 系统镜像")
        if archive.testzip() is not None:
            raise ValueError("镜像 ZIP 校验失败")
        if archive.getinfo("VERSION.json").file_size > 1024 * 1024:
            raise ValueError("镜像版本信息过大")
        metadata = json.loads(archive.read("VERSION.json"))
        if not isinstance(metadata, dict) or metadata.get("robot_type") != EXPECTED_ROBOT_MODEL:
            raise ValueError("镜像设备型号不是 OT-3 Standard")
        if not metadata.get("openembedded_version") or not metadata.get("opentrons_api_version"):
            raise ValueError("镜像缺少系统版本信息")
        if metadata["opentrons_api_version"] != IMAGE_PATTERN.fullmatch(image_name)[1]:
            raise ValueError("镜像文件名与包内版本不一致")
        return metadata


def _new_task(kind: str, image: str, ip: str = "") -> dict:
    return {"id": uuid4().hex, "kind": kind, "image": image, "ip": ip,
            "status": "queued", "stage": "queued", "progress": 0,
            "message": "等待执行", "logs": [], "created_at": _now(), "finished_at": None}


def create_install_tasks(ips: list[str], image: str, port: int = 31950) -> list[dict]:
    path = resolve_image(image)
    if not 1 <= len(ips) <= 100 or not 1 <= port <= 65535:
        raise ValueError("请选择 1–100 个设备和有效端口")
    targets = list(dict.fromkeys(str(ipaddress.ip_address(ip.strip())) for ip in ips))
    _load()
    with _LOCK:
        busy = {t["ip"] for t in _TASKS.values() if t["kind"] == "install" and t["status"] in ACTIVE}
        if busy.intersection(targets):
            raise ValueError(f"设备正在升级: {', '.join(sorted(busy.intersection(targets)))}")
        tasks = [_new_task("install", image, ip) for ip in targets]
        for task in tasks:
            _save(task)
            _TASKS[task["id"]] = task
        for task in tasks:
            try:
                _UPDATES.submit(_install, task["id"], path, port)
            except Exception:
                _change(task["id"], status="failed", message="无法启动升级任务", finished_at=_now())
                raise
        return deepcopy(tasks)


def _install(task_id: str, path: Path, port: int) -> None:
    try:
        _change(task_id, status="running", stage="checking", message="检查镜像和设备")
        metadata = _validate_archive(path, path.name)
        client = RobotUpdateClient(
            Endpoint("http", _TASKS[task_id]["ip"], port),
            on_progress=lambda sent, total, pct: _change(task_id, progress=pct, message=f"上传镜像 {pct}%"),
        )
        health = client.health()
        if health.get("robotModel") != EXPECTED_ROBOT_MODEL:
            raise RobotUpdateError(f"不支持的设备型号: {health.get('robotModel', 'unknown')}")
        _change(task_id, log=f"当前系统: {health.get('systemVersion', 'unknown')}")
        token = str(client.begin()["token"])
        _change(task_id, stage="uploading", message="上传镜像")
        client.upload(token, path)
        _change(task_id, stage="installing", progress=None, message="写入系统")
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            state = client.status(token)
            message = format_status(state)
            _change(task_id, message=message, log=message)
            if state.get("stage") == "error":
                raise RobotUpdateError(f"{state.get('error', 'update error')}: {message}")
            if state.get("stage") == "done":
                break
            time.sleep(2)
        else:
            raise RobotUpdateError("等待系统写入超时，请检查设备更新状态")
        _change(task_id, stage="committing", message="提交更新")
        client.commit(token)
        _change(task_id, stage="rebooting", message="等待设备重启上线")
        client.restart()
        online = client.wait_for_boot(900, 5, health.get("bootId"))
        expected = metadata["openembedded_version"]
        actual = str(online.get("systemVersion", ""))
        expected_api = metadata["opentrons_api_version"]
        actual_api = str(online.get("apiServerVersion", ""))
        if actual != expected or actual_api != expected_api:
            raise RobotUpdateError(
                f"重启后版本不匹配: 系统预期 {expected}，实际 {actual or 'unknown'}; "
                f"API 预期 {expected_api}，实际 {actual_api or 'unknown'}"
            )
        _change(task_id, status="success", stage="done", progress=100,
                message=f"升级完成: {actual}", log=f"重启验证成功: {actual}", finished_at=_now())
    except Exception as exc:
        _change(task_id, status="failed", message=str(exc), log=str(exc), finished_at=_now())


def parse_download_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("请输入 HTTP/HTTPS 镜像下载链接")
    # Validate ports before enqueuing. URL query strings (signed links) are retained.
    _ = parsed.port
    name = unquote(parsed.path.rsplit("/", 1)[-1])
    if not IMAGE_PATTERN.fullmatch(name):
        raise ValueError("下载链接文件名必须为 ot3-system-版本.zip")
    return name


def create_download_task(url: str) -> dict:
    url = url.strip()
    name = parse_download_url(url)
    directory = image_directory()
    directory.mkdir(parents=True, exist_ok=True)
    _load()
    with _LOCK:
        if (directory / name).exists() or (directory / name).is_symlink():
            raise ValueError("该镜像已存在，请选择其他版本")
        if any(t["kind"] == "download" and t["image"] == name and t["status"] in ACTIVE for t in _TASKS.values()):
            raise ValueError("该镜像正在下载")
        task = _new_task("download", name)
        _save(task)
        _TASKS[task["id"]] = task
        try:
            _DOWNLOADS.submit(_download, task["id"], url, directory / name)
        except Exception:
            _change(task["id"], status="failed", message="无法启动下载任务", finished_at=_now())
            raise
        return deepcopy(task)


def _download(task_id: str, url: str, destination: Path) -> None:
    temporary = destination.parent / f".{task_id}.part"
    try:
        _change(task_id, status="running", stage="downloading", message="正在下载")
        deadline = time.monotonic() + 3600
        with requests.get(url, stream=True, timeout=(15, 60)) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length", 0))
            if total > MAX_IMAGE_BYTES:
                raise ValueError("镜像超过 4 GiB 限制")
            size, last_pct, last_saved = 0, -1, 0.0
            with temporary.open("xb") as output:
                for chunk in response.iter_content(1024 * 1024):
                    if time.monotonic() > deadline:
                        raise TimeoutError("镜像下载超时")
                    size += len(chunk)
                    if size > MAX_IMAGE_BYTES:
                        raise ValueError("镜像超过 4 GiB 限制")
                    output.write(chunk)
                    pct = min(99, int(size * 100 / total)) if total else None
                    if pct != last_pct or time.monotonic() - last_saved >= 2:
                        _change(task_id, progress=pct, message=f"已下载 {size // (1024 * 1024)} MiB")
                        last_pct, last_saved = pct, time.monotonic()
            if total and size != total:
                raise ValueError("镜像下载不完整")
        _change(task_id, stage="checking", message="校验镜像", progress=None)
        _validate_archive(temporary, destination.name)
        # Publish atomically without overwriting an image another job/user placed.
        os.link(temporary, destination)
        _change(task_id, status="success", stage="done", progress=100,
                message="镜像下载完成", finished_at=_now())
    except Exception as exc:
        # requests exceptions can contain signed URL credentials; don't persist them.
        message = f"下载失败 ({type(exc).__name__})" if isinstance(exc, requests.RequestException) else str(exc)
        _change(task_id, status="failed", message=message, log=message, finished_at=_now())
    finally:
        temporary.unlink(missing_ok=True)
