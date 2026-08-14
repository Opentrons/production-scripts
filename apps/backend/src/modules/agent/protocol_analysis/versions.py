from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path

from core import config
from modules.agent.protocol_analysis.opentrons_path import resolve_opentrons_environment


_STABLE_TAG = re.compile(r"^v\d+\.\d+\.\d+$")
_VERSION_LOCKS: dict[str, asyncio.Lock] = {}
_VERSION_LOCKS_GUARD = asyncio.Lock()


def _worktree_root() -> Path:
    root = Path(config.DOWNLOAD_DIR) / "opentrons_worktrees"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _version_key(tag: str) -> tuple[int, ...]:
    body = tag[1:] if tag.startswith("v") else tag
    parts: list[int] = []
    for piece in body.split("."):
        digits = re.match(r"^\d+", piece)
        parts.append(int(digits.group(0)) if digits else 0)
    return tuple(parts)


def _numeric_version(tag: str) -> str:
    return tag[1:] if tag.startswith("v") else tag


def _write_version_stub(path: Path, version: str) -> None:
    parts = tuple(int(piece) for piece in _numeric_version(version).split(".") if piece.isdigit())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# generated for protocol-analysis worktree\n"
        "from __future__ import annotations\n"
        "__all__ = ["
        '"__version__", "__version_tuple__", "version", "version_tuple", '
        '"__commit_id__", "commit_id"'
        "]\n"
        f'version: str = "{_numeric_version(version)}"\n'
        "__version__: str = version\n"
        f"__version_tuple__ = {parts!r}\n"
        "version_tuple = __version_tuple__\n"
        "commit_id = None\n"
        "__commit_id__ = None\n",
        encoding="utf-8",
    )


def _prepare_worktree_runtime_files(worktree: Path, tag: str) -> None:
    _write_version_stub(worktree / "api" / "src" / "opentrons" / "_version.py", tag)
    shared = worktree / "shared-data" / "python" / "opentrons_shared_data" / "_version.py"
    if shared.parent.exists():
        _write_version_stub(shared, tag)


async def _run_git(*args: str, cwd: Path | None = None) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return (
        process.returncode or 0,
        stdout.decode("utf-8", errors="replace").strip(),
        stderr.decode("utf-8", errors="replace").strip(),
    )


async def list_opentrons_versions(limit: int = 40) -> list[str]:
    env = resolve_opentrons_environment()
    if not env.root:
        return []
    code, stdout, _ = await _run_git("tag", "-l", "v*", cwd=env.root)
    if code != 0 or not stdout:
        return []
    tags = [line.strip() for line in stdout.splitlines() if _STABLE_TAG.fullmatch(line.strip())]
    tags.sort(key=_version_key, reverse=True)
    return tags[: max(1, limit)]


async def resolve_default_version() -> str | None:
    versions = await list_opentrons_versions()
    return versions[0] if versions else None


async def _lock_for(tag: str) -> asyncio.Lock:
    async with _VERSION_LOCKS_GUARD:
        lock = _VERSION_LOCKS.get(tag)
        if lock is None:
            lock = asyncio.Lock()
            _VERSION_LOCKS[tag] = lock
        return lock


async def ensure_opentrons_version(tag: str) -> Path:
    """
    Prepare an isolated git worktree for the requested tag.

    This avoids mutating the developer's current checkout (branch / dirty tree).
    Analysis then runs against the worktree sources with the shared api/.venv.
    """
    requested = (tag or "").strip()
    env = resolve_opentrons_environment()
    if not env.available or env.root is None:
        raise RuntimeError(env.detail)

    if not requested:
        requested = await resolve_default_version() or ""
    if not requested:
        raise RuntimeError("未找到可用的 Opentrons 版本 tag（如 v9.1.0）")
    if not _STABLE_TAG.fullmatch(requested):
        raise RuntimeError(f"不支持的版本格式: {requested}（请使用 vX.Y.Z）")

    lock = await _lock_for(requested)
    async with lock:
        code, _, stderr = await _run_git("rev-parse", "-q", "--verify", f"refs/tags/{requested}", cwd=env.root)
        if code != 0:
            fetch_code, _, fetch_err = await _run_git("fetch", "--tags", "--force", cwd=env.root)
            if fetch_code != 0:
                raise RuntimeError(f"拉取 Opentrons tags 失败: {fetch_err or stderr or requested}")
            code, _, stderr = await _run_git("rev-parse", "-q", "--verify", f"refs/tags/{requested}", cwd=env.root)
            if code != 0:
                raise RuntimeError(f"源码中不存在 tag {requested}")

        target = _worktree_root() / requested
        marker = target / "api" / "src" / "opentrons"
        if marker.exists():
            # Keep worktree pinned to the tag tip.
            await _run_git("checkout", "--detach", "--force", requested, cwd=target)
            await _run_git("reset", "--hard", requested, cwd=target)
            _prepare_worktree_runtime_files(target, requested)
            return target

        if target.exists():
            # Incomplete worktree directory — remove and recreate.
            shutil.rmtree(target, ignore_errors=True)

        add_code, _, add_err = await _run_git(
            "worktree",
            "add",
            "--detach",
            str(target),
            requested,
            cwd=env.root,
        )
        if add_code != 0:
            # Recover stale worktree registration then retry once.
            await _run_git("worktree", "prune", cwd=env.root)
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            add_code, _, add_err = await _run_git(
                "worktree",
                "add",
                "--detach",
                str(target),
                requested,
                cwd=env.root,
            )
        if add_code != 0 or not marker.exists():
            raise RuntimeError(f"切换 Opentrons {requested} 失败: {add_err or 'worktree 无效'}")
        _prepare_worktree_runtime_files(target, requested)
        return target
