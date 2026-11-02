"""Recognize reference checkpoints using captured evidence, without robot imports."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _volume(value: object) -> int | None:
    if type(value) is int:
        return value if value > 0 else None
    if isinstance(value, str) and re.fullmatch(r"[1-9]\d*", value):
        return int(value)
    return None


def _mount(value: object) -> str:
    name = str(value).split(".")[-1]
    return name if name in {"LEFT", "RIGHT"} else ""


def reference_stage_volume(stage: object) -> int | None:
    match = re.fullmatch(r"right-reference-([1-9]\d*)ul", stage) if isinstance(stage, str) else None
    return int(match.group(1)) if match else None


@dataclass(frozen=True)
class ReferenceFailureContext:
    volume: int | None
    mount: str
    in_reference: bool


def reference_failure_context(failure: object) -> ReferenceFailureContext:
    failure = _mapping(failure)
    context = failure.get("context")
    scopes = [_mapping(scope) for scope in context] if isinstance(context, list) else []
    scopes.append(failure)
    mount, volume, in_reference = "", None, False
    for scope in reversed(scopes):
        arguments = _mapping(scope.get("arguments"))
        action = scope.get("action")
        in_reference = in_reference or action == "_measure_reference"
        if volume is None:
            for key in ("tip_volume_ul", "tip_volume", "tip_vol"):
                volume = _volume(arguments.get(key))
                if volume is not None:
                    break
        # This outer scope's cfg.mount is the DUT, not the actual operation mount.
        if not mount and action != "_measure_reference":
            candidates = [arguments.get("mount"), _mapping(arguments.get("kwargs")).get("mount")]
            args = arguments.get("args")
            candidates.extend(args if isinstance(args, list) else [])
            mount = next((name for value in candidates if (name := _mount(value))), "")
    label = re.search(r"RIGHT\s+P1000S\s*/\s*(\d+)\s*uL\s*/\s*A12", str(failure.get("error", "")), re.IGNORECASE)
    if label:
        in_reference = True
        if volume is None:
            volume = _volume(label.group(1))
    return ReferenceFailureContext(volume, mount, in_reference)


def reference_event_volume(event: object) -> int | None:
    event = _mapping(event)
    if event.get("action") != "right_reference_failure" or _mount(event.get("mount")) != "RIGHT":
        return None
    return _volume(event.get("tip_volume_ul"))


def _time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _event_matches_failure(event: dict, failure: dict, volume: int) -> bool:
    if not failure:
        return True
    context = reference_failure_context(failure)
    if context.mount == "LEFT" or context.volume != volume:
        return False
    if not context.in_reference and context.mount != "RIGHT":
        return False
    event_id, failure_id = event.get("id"), failure.get("id")
    if type(event_id) is int and type(failure_id) is int and event_id <= failure_id:
        return False
    event_time = _time(event.get("observed_at"))
    failure_time = _time(failure.get("finished_at")) or _time(failure.get("observed_at"))
    if event_time and failure_time:
        try:
            if event_time < failure_time:
                return False
        except TypeError:
            return False
    # A wrapping _ReferenceProbeError retains the inner error's message.
    original_error, event_error = str(failure.get("error", "")).strip(), str(event.get("error", "")).strip()
    if original_error and event_error:
        message = original_error.split(":", 1)[-1].strip()
        if message not in event_error and event_error not in original_error:
            return False
    return True


@dataclass(frozen=True)
class ReferenceSnapshot:
    volume: int
    handled: bool | None
    event_ref: str | None
    event: dict[str, Any] | None


def reference_snapshot(bundle: object) -> ReferenceSnapshot | None:
    bundle = _mapping(bundle)
    volume = reference_stage_volume(bundle.get("stage"))
    if volume is None:
        return None
    unknown = ReferenceSnapshot(volume, None, None, None)
    trace = _mapping(bundle.get("trace"))
    events = trace.get("events")
    if not isinstance(events, list):
        return unknown
    for index in range(len(events) - 1, -1, -1):
        event = _mapping(events[index])
        if event.get("action") != "right_reference_failure":
            continue
        # A newer reference event for another volume makes an older one unsafe.
        if reference_event_volume(event) != volume or not _event_matches_failure(event, _mapping(trace.get("last_failure")), volume):
            return unknown
        handled = event.get("handled")
        return ReferenceSnapshot(volume, handled if type(handled) is bool else None, f"trace.events[{index}]", event)
    return unknown
