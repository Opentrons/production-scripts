from __future__ import annotations

import ipaddress
import os
import queue
import re
import shlex
import signal
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic, perf_counter
from typing import Any, Callable
from uuid import uuid4


OPENTRONS_FLASH_DIR_ENV = "PRODUCTION_PLATFORM_OPENTRONS_FLASH_DIR"
DEFAULT_OPENTRONS_FLASH_DIR = Path("/opentrons")
MAX_LOG_CHARS = 500_000

FLASH_PRESETS = (
    {
        "id": "all-flex-services",
        "name": "Flex 全量代码",
        "description": "构建并推送 Flex 的全部后端服务",
        "command": "make push-ot3 host={robot_ip}",
    },
    {
        "id": "robot-server",
        "name": "Robot Server",
        "description": "构建并推送 robot-server",
        "command": "make -C robot-server push-ot3 host={robot_ip}",
    },
    {
        "id": "system-server",
        "name": "System Server",
        "description": "构建并推送 system-server",
        "command": "make -C system-server push-ot3 host={robot_ip}",
    },
    {
        "id": "api",
        "name": "API",
        "description": "构建并推送 Opentrons API",
        "command": "make -C api push-ot3 host={robot_ip}",
    },
    {
        "id": "hardware",
        "name": "Hardware",
        "description": "构建并推送 hardware 包",
        "command": "make -C hardware push-ot3 host={robot_ip}",
    },
    {
        "id": "update-server",
        "name": "Update Server",
        "description": "构建并推送 update-server",
        "command": "make -C update-server push-ot3 host={robot_ip}",
    },
)

_FAILURE_PATTERNS = (
    re.compile(r"(?im)^make(?:\[\d+\])?: \*\*\*"),
    re.compile(r"(?im)^FAILED(?:\s|:|$)"),
    re.compile(r"(?im)^fatal:"),
    re.compile(r"(?im)no rule to make target"),
    re.compile(r"(?im)(connection refused|permission denied|host is down)"),
)
_DISALLOWED_TOKEN_PATTERN = re.compile(r"[;&|<>`$()\n\r\x00]")
_SAFE_ARGUMENT_PATTERN = re.compile(r"^[A-Za-z0-9_./=:+,@%-]+$")
_ALLOWED_COMPONENT_DIRECTORIES = {
    "api",
    "auth-server",
    "hardware",
    "key-server",
    "robot-server",
    "server-utils",
    "shared-data",
    "system-server",
    "update-server",
    "usb-bridge",
}
_ALLOWED_MAKE_VARIABLES = {"BUILD_NUMBER", "quiet", "version"}
_PUSH_TARGET_PATTERN = re.compile(r"^push(?:-[A-Za-z0-9_.-]+)?$")
_SAFE_BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")

_TASKS: dict[str, dict[str, Any]] = {}
_TASKS_LOCK = threading.RLock()
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="opentrons-flash")


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


def resolve_opentrons_directory() -> Path:
    configured = str(os.getenv(OPENTRONS_FLASH_DIR_ENV, "") or "").strip()
    candidate = Path(configured).expanduser() if configured else DEFAULT_OPENTRONS_FLASH_DIR
    try:
        resolved = candidate.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise RuntimeError(f"Opentrons 源码目录不存在: {candidate}") from exc
    if not resolved.is_dir() or not (resolved / "Makefile").is_file():
        raise RuntimeError(f"Opentrons 源码目录缺少 Makefile: {resolved}")
    return resolved


def _run_git_command(arguments: list[str], *, cwd: Path, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Git 命令超时: git {shlex.join(arguments)}") from exc
    except OSError as exc:
        raise RuntimeError(f"无法执行 Git 命令: {exc}") from exc


def _require_git_success(result: subprocess.CompletedProcess[str], action: str) -> str:
    output = "\n".join(value.strip() for value in (result.stdout, result.stderr) if value.strip())
    if result.returncode != 0:
        raise RuntimeError(f"{action}失败: {output or f'git 退出码 {result.returncode}'}")
    return output


def _normalize_branch_name(branch: str) -> str:
    normalized = str(branch or "").strip()
    if not _SAFE_BRANCH_PATTERN.fullmatch(normalized):
        raise ValueError(f"无效 Git 分支: {normalized or '(空)'}")
    if ".." in normalized or "//" in normalized or normalized.endswith(("/", ".")):
        raise ValueError(f"无效 Git 分支: {normalized}")
    return normalized


def get_repository_state(workdir: Path | None = None) -> dict[str, Any]:
    repository = workdir or resolve_opentrons_directory()
    inside_result = _run_git_command(["rev-parse", "--is-inside-work-tree"], cwd=repository)
    if inside_result.returncode != 0 or inside_result.stdout.strip() != "true":
        raise RuntimeError(f"Opentrons 源码目录不是 Git 工作区: {repository}")

    current_result = _run_git_command(["branch", "--show-current"], cwd=repository)
    _require_git_success(current_result, "读取当前分支")
    current_branch = current_result.stdout.strip()

    local_result = _run_git_command(
        ["for-each-ref", "--format=%(refname:short)", "refs/heads"],
        cwd=repository,
    )
    _require_git_success(local_result, "读取本地分支")
    remote_result = _run_git_command(
        ["for-each-ref", "--format=%(refname:short)", "refs/remotes/origin"],
        cwd=repository,
    )
    _require_git_success(remote_result, "读取远程分支")

    local_branches = {
        branch.strip()
        for branch in local_result.stdout.splitlines()
        if branch.strip() and _SAFE_BRANCH_PATTERN.fullmatch(branch.strip())
    }
    remote_branches = {
        branch.strip().removeprefix("origin/")
        for branch in remote_result.stdout.splitlines()
        if branch.strip().startswith("origin/")
        and branch.strip() != "origin/HEAD"
        and _SAFE_BRANCH_PATTERN.fullmatch(branch.strip().removeprefix("origin/"))
    }
    branch_names = local_branches | remote_branches
    if current_branch and _SAFE_BRANCH_PATTERN.fullmatch(current_branch):
        branch_names.add(current_branch)

    preferred_order = {current_branch: 0, "edge": 1, "main": 2, "master": 3}
    branches = [
        {
            "name": name,
            "current": name == current_branch,
            "local": name in local_branches,
            "remote": name in remote_branches,
        }
        for name in sorted(branch_names, key=lambda name: (preferred_order.get(name, 10), name.casefold()))
    ]

    status_result = _run_git_command(
        ["status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repository,
    )
    _require_git_success(status_result, "检查 Git 工作区")
    dirty_files = [line for line in status_result.stdout.splitlines() if line.strip()]
    return {
        "current_branch": current_branch,
        "branches": branches,
        "clean": not dirty_files,
        "dirty_files": dirty_files[:100],
    }


def list_flash_presets() -> dict[str, Any]:
    configured = str(os.getenv(OPENTRONS_FLASH_DIR_ENV, "") or "").strip()
    workdir = str(Path(configured).expanduser() if configured else DEFAULT_OPENTRONS_FLASH_DIR)
    try:
        resolved = resolve_opentrons_directory()
        workdir = str(resolved)
        repository_state = get_repository_state(resolved)
        available = True
        error = None
    except (RuntimeError, ValueError) as exc:
        available = False
        error = str(exc)
        repository_state = {
            "current_branch": "",
            "branches": [],
            "clean": False,
            "dirty_files": [],
        }
    return {
        "presets": [dict(preset) for preset in FLASH_PRESETS],
        "workdir": workdir,
        "available": available,
        "error": error,
        **repository_state,
    }


def build_make_command(command: str, robot_ip: str) -> list[str]:
    normalized_ip = _normalize_robot_ip(robot_ip)
    raw_command = str(command or "").strip().replace("{robot_ip}", normalized_ip)
    if not raw_command:
        raise ValueError("请输入 make 命令")
    try:
        arguments = shlex.split(raw_command, posix=True)
    except ValueError as exc:
        raise ValueError(f"make 命令格式错误: {exc}") from exc
    if not arguments or arguments[0] != "make":
        raise ValueError("自定义命令必须以 make 开头")
    if any(_DISALLOWED_TOKEN_PATTERN.search(argument) for argument in arguments):
        raise ValueError("make 命令不能包含重定向、管道或命令连接符")
    if any(not _SAFE_ARGUMENT_PATTERN.fullmatch(argument) for argument in arguments[1:]):
        raise ValueError("make 命令包含不支持的参数字符")
    if any(".." in Path(argument).parts for argument in arguments[1:] if not argument.startswith("host=")):
        raise ValueError("make 命令不能访问上级目录")

    normalized_arguments = ["make"]
    targets: list[str] = []
    index = 1
    while index < len(arguments):
        argument = arguments[index]
        if argument == "-C":
            if index + 1 >= len(arguments) or arguments[index + 1] not in _ALLOWED_COMPONENT_DIRECTORIES:
                raise ValueError("make -C 仅支持 Opentrons 预设组件目录")
            normalized_arguments.extend((argument, arguments[index + 1]))
            index += 2
            continue
        if argument.startswith("-"):
            raise ValueError("make 命令不支持自定义命令行选项")
        if "=" in argument:
            name, _value = argument.split("=", 1)
            if name == "host":
                index += 1
                continue
            if name not in _ALLOWED_MAKE_VARIABLES:
                raise ValueError(f"make 命令不支持变量: {name}")
            normalized_arguments.append(argument)
            index += 1
            continue
        if not _PUSH_TARGET_PATTERN.fullmatch(argument):
            raise ValueError("自定义 make 命令仅支持 push 烧录目标")
        targets.append(argument)
        normalized_arguments.append(argument)
        index += 1
    if not targets:
        raise ValueError("make 命令至少需要一个 push 烧录目标")

    normalized_arguments.append(f"host={normalized_ip}")
    return normalized_arguments


def _classify_result(exit_code: int, output: str, timed_out: bool) -> tuple[bool, str]:
    if timed_out:
        return False, "烧录超时，进程已终止"
    if exit_code != 0:
        return False, f"烧录失败，make 退出码 {exit_code}"
    for pattern in _FAILURE_PATTERNS:
        match = pattern.search(output)
        if match:
            return False, f"烧录失败，输出检测到异常: {match.group(0).strip()}"
    return True, "烧录成功"


def _append_log(task_id: str, line: str) -> None:
    normalized = str(line).rstrip("\r\n")
    if not normalized:
        return
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        if not task or task["output_truncated"]:
            return
        added_size = len(normalized) + 1
        if task["output_size"] + added_size > MAX_LOG_CHARS:
            task["logs"].append("[平台] 输出过长，后续日志已截断")
            task["output_truncated"] = True
            return
        task["logs"].append(normalized)
        task["output_size"] += added_size


def _log_git_result(task_id: str, label: str, result: subprocess.CompletedProcess[str]) -> None:
    command = shlex.join(["git", *result.args[1:]]) if isinstance(result.args, list) else str(result.args)
    _append_log(task_id, f"[Git] {label}: {command}")
    for output in (result.stdout, result.stderr):
        for line in str(output or "").splitlines():
            _append_log(task_id, line)


def _prepare_repository(task_id: str, workdir: Path, branch: str, pull: bool) -> None:
    status_result = _run_git_command(
        ["status", "--porcelain=v1", "--untracked-files=all"],
        cwd=workdir,
    )
    _log_git_result(task_id, "检查工作区", status_result)
    _require_git_success(status_result, "检查 Git 工作区")
    dirty_files = [line for line in status_result.stdout.splitlines() if line.strip()]
    if dirty_files:
        for line in dirty_files[:100]:
            _append_log(task_id, f"[Git] 未提交文件: {line}")
        raise RuntimeError(f"Git 工作区不干净，共 {len(dirty_files)} 项；请先提交、暂存或清理后再烧录")
    _append_log(task_id, "[Git] 工作区干净")

    target_branch = _normalize_branch_name(branch)
    local_result = _run_git_command(
        ["show-ref", "--verify", "--quiet", f"refs/heads/{target_branch}"],
        cwd=workdir,
    )
    remote_result = _run_git_command(
        ["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{target_branch}"],
        cwd=workdir,
    )
    if local_result.returncode == 0:
        switch_arguments = ["switch", target_branch]
    elif remote_result.returncode == 0:
        switch_arguments = ["switch", "--track", "-c", target_branch, f"origin/{target_branch}"]
    else:
        raise RuntimeError(f"分支不存在: {target_branch}")

    switch_result = _run_git_command(switch_arguments, cwd=workdir, timeout=120)
    _log_git_result(task_id, f"切换分支 {target_branch}", switch_result)
    _require_git_success(switch_result, f"切换分支 {target_branch}")

    if pull:
        pull_result = _run_git_command(
            ["pull", "--ff-only", "origin", target_branch],
            cwd=workdir,
            timeout=300,
        )
        _log_git_result(task_id, f"拉取 origin/{target_branch}", pull_result)
        _require_git_success(pull_result, f"拉取 origin/{target_branch}")
    else:
        _append_log(task_id, "[Git] 未勾选 Pull，跳过远程拉取")

    final_status = _run_git_command(
        ["status", "--porcelain=v1", "--untracked-files=all"],
        cwd=workdir,
    )
    _require_git_success(final_status, "切换分支后检查 Git 工作区")
    if final_status.stdout.strip():
        raise RuntimeError("切换分支后 Git 工作区出现未提交变更，已停止烧录")
    _append_log(task_id, f"[Git] 已准备分支 {target_branch}")


def _execute_make_process(
    arguments: list[str],
    *,
    cwd: Path,
    timeout: int,
    on_line: Callable[[str], None],
) -> tuple[int, bool]:
    process = subprocess.Popen(
        arguments,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        start_new_session=True,
    )
    assert process.stdout is not None

    line_queue: queue.Queue[str | None] = queue.Queue()

    def read_output() -> None:
        try:
            for line in iter(process.stdout.readline, ""):
                line_queue.put(line)
        finally:
            line_queue.put(None)

    reader = threading.Thread(target=read_output, name="opentrons-flash-output", daemon=True)
    reader.start()
    deadline = monotonic() + timeout
    reader_finished = False
    timed_out = False

    while not reader_finished or process.poll() is None:
        remaining = deadline - monotonic()
        if remaining <= 0 and process.poll() is None:
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    process.kill()
            continue
        try:
            line = line_queue.get(timeout=min(0.2, max(0.01, remaining)))
        except queue.Empty:
            continue
        if line is None:
            reader_finished = True
        else:
            on_line(line)

    reader.join(timeout=1)
    process.stdout.close()
    return process.wait(), timed_out


def _run_flash_task(task_id: str, workdir: Path, timeout: int) -> None:
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return
        task["status"] = "running"
        task["started_at"] = _utc_now()
        arguments = list(task["arguments"])
        branch = task["branch"]
        pull = task["pull"]

    started = perf_counter()
    _append_log(task_id, f"[平台] 工作目录: {workdir}")
    try:
        _prepare_repository(task_id, workdir, branch, pull)
        _append_log(task_id, f"[平台] 执行命令: {shlex.join(arguments)}")
        exit_code, timed_out = _execute_make_process(
            arguments,
            cwd=workdir,
            timeout=timeout,
            on_line=lambda line: _append_log(task_id, line),
        )
        with _TASKS_LOCK:
            current = _TASKS.get(task_id)
            output = "\n".join(current["logs"]) if current else ""
        success, message = _classify_result(exit_code, output, timed_out)
    except RuntimeError as exc:
        exit_code = None
        success = False
        message = f"烧录准备失败: {exc}"
        _append_log(task_id, f"[平台] {message}")
    except OSError as exc:
        exit_code = None
        success = False
        message = f"无法启动 make: {exc}"
        _append_log(task_id, f"[平台] {message}")
    except Exception as exc:
        exit_code = None
        success = False
        message = f"烧录任务异常: {exc}"
        _append_log(task_id, f"[平台] {message}")

    _append_log(task_id, f"[平台] {message}")
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return
        task.update(
            status="success" if success else "failed",
            success=success,
            message=message,
            exit_code=exit_code,
            finished_at=_utc_now(),
            duration_ms=round((perf_counter() - started) * 1000),
        )


def create_flash_task(
    ip: str,
    command: str,
    timeout: int = 1800,
    branch: str = "",
    pull: bool = False,
) -> dict[str, Any]:
    normalized_ip = _normalize_robot_ip(ip)
    normalized_timeout = max(30, min(int(timeout), 7200))
    workdir = resolve_opentrons_directory()
    arguments = build_make_command(command, normalized_ip)
    repository_state = get_repository_state(workdir)
    normalized_branch = _normalize_branch_name(branch or repository_state["current_branch"])
    if not any(item["name"] == normalized_branch for item in repository_state["branches"]):
        raise ValueError(f"分支不在服务器预设列表中: {normalized_branch}")
    task_id = uuid4().hex

    with _TASKS_LOCK:
        if any(
            task["status"] in {"queued", "running"}
            for task in _TASKS.values()
        ):
            raise ValueError("服务器 Opentrons 工作区已有正在执行的烧录任务")
        task = {
            "task_id": task_id,
            "ip": normalized_ip,
            "status": "queued",
            "success": None,
            "message": "等待执行",
            "command": shlex.join(arguments),
            "arguments": arguments,
            "workdir": str(workdir),
            "branch": normalized_branch,
            "pull": bool(pull),
            "timeout": normalized_timeout,
            "logs": [],
            "output_size": 0,
            "output_truncated": False,
            "exit_code": None,
            "created_at": _utc_now(),
            "started_at": None,
            "finished_at": None,
            "duration_ms": 0,
        }
        _TASKS[task_id] = task

    _EXECUTOR.submit(_run_flash_task, task_id, workdir, normalized_timeout)
    return get_flash_task(task_id)


def get_flash_task(task_id: str) -> dict[str, Any]:
    with _TASKS_LOCK:
        task = _TASKS.get(str(task_id or "").strip())
        if not task:
            raise KeyError(task_id)
        response = deepcopy(task)
    response.pop("arguments", None)
    response.pop("output_size", None)
    return response
