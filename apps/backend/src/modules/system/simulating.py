from __future__ import annotations

from core import runtime_mode
from modules.system import simulating_seed


def get_status() -> dict:
    status = runtime_mode.get_simulating_status()
    status["fixtures"] = {
        "robots": len(simulating_seed.build_fake_robots()),
        "upload_records": len(simulating_seed.build_fake_upload_records()),
        "messages": len(simulating_seed.build_fake_messages()),
    }
    return status


def set_enabled(enabled: bool) -> dict:
    runtime_mode.set_simulating(enabled)
    if enabled:
        seed_result = simulating_seed.ensure_simulating_seed()
    else:
        seed_result = {"seeded": False, "reason": "simulating disabled"}
    status = get_status()
    status["seed"] = seed_result
    return status
