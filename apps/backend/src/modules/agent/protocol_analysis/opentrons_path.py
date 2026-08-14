from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OpentronsEnvironment:
    root: Path | None
    python: Path | None
    available: bool
    candidates: list[str]
    detail: str


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    env_root = os.getenv("PRODUCTION_PLATFORM_OPENTRONS_ROOT", "").strip()
    if env_root:
        roots.append(Path(env_root).expanduser())
    roots.extend(
        [
            Path.home() / "projects" / "opentrons",
            Path("/opentrons"),
        ]
    )
    # Preserve order while de-duplicating.
    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def _looks_like_opentrons_root(path: Path) -> bool:
    return (path / "api" / "src" / "opentrons").is_dir() or (path / "api" / "src" / "opentrons" / "__init__.py").is_file()


def _resolve_python(root: Path) -> Path | None:
    env_python = os.getenv("PRODUCTION_PLATFORM_OPENTRONS_PYTHON", "").strip()
    if env_python:
        candidate = Path(env_python).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate

    for relative in (
        Path("api") / ".venv" / "bin" / "python",
        Path("api") / ".venv" / "bin" / "python3",
        Path(".venv") / "bin" / "python",
        Path(".venv") / "bin" / "python3",
    ):
        candidate = root / relative
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate

    fallback = Path(sys.executable)
    if fallback.is_file():
        return fallback
    return None


def resolve_opentrons_environment() -> OpentronsEnvironment:
    candidates = [str(path) for path in _candidate_roots()]
    for root in _candidate_roots():
        if not root.is_dir() or not _looks_like_opentrons_root(root):
            continue
        python = _resolve_python(root)
        if python is None:
            return OpentronsEnvironment(
                root=root,
                python=None,
                available=False,
                candidates=candidates,
                detail=f"已找到源码 {root}，但未找到可用的 Python（api/.venv）",
            )
        return OpentronsEnvironment(
            root=root,
            python=python,
            available=True,
            candidates=candidates,
            detail=f"使用源码 {root}，解释器 {python}",
        )
    return OpentronsEnvironment(
        root=None,
        python=None,
        available=False,
        candidates=candidates,
        detail="未找到 Opentrons 源码（尝试 ~/projects/opentrons 与 /opentrons）",
    )
