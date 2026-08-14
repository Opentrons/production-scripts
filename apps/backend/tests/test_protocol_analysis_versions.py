from __future__ import annotations

import pytest

from modules.agent.protocol_analysis.versions import (
    ensure_opentrons_version,
    list_opentrons_versions,
    resolve_default_version,
)
from modules.agent.protocol_analysis.opentrons_path import resolve_opentrons_environment


@pytest.mark.asyncio
async def test_list_and_ensure_opentrons_stable_version() -> None:
    env = resolve_opentrons_environment()
    if not env.available or env.root is None:
        pytest.skip(env.detail)

    versions = await list_opentrons_versions(limit=20)
    assert versions
    assert all(item.startswith("v") for item in versions)
    default = await resolve_default_version()
    assert default == versions[0]

    target = versions[1] if len(versions) > 1 else versions[0]
    worktree = await ensure_opentrons_version(target)
    assert worktree.name == target
    assert (worktree / "api" / "src" / "opentrons" / "_version.py").exists()
    assert (worktree / "api" / "src" / "opentrons").is_dir()
