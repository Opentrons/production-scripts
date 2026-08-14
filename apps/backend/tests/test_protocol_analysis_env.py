from __future__ import annotations

from modules.agent.protocol_analysis.opentrons_path import resolve_opentrons_environment


def test_resolve_opentrons_environment_finds_dev_or_prod_root() -> None:
    env = resolve_opentrons_environment()
    assert env.candidates
    assert any(path.endswith("/projects/opentrons") or path == "/opentrons" or "opentrons" in path for path in env.candidates)
    if env.available:
        assert env.root is not None
        assert env.python is not None
        assert (env.root / "api" / "src" / "opentrons").exists()
