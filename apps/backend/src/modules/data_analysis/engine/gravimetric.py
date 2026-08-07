from __future__ import annotations

import os
import re
from collections import defaultdict
from statistics import mean
from typing import Any

from .common import (
    build_file_info,
    clean_number,
    first_text,
    get_cell,
    normalize_value,
    parse_sections,
    round_float,
    section_key_values,
    to_number,
)
from .spec_store import DEFAULT_GRAVIMETRIC_SPEC, get_gravimetric_spec

VOLUME_SPEC = DEFAULT_GRAVIMETRIC_SPEC

VOLUME_KEY_PATTERN = re.compile(
    r"^volume-(aspirate|dispense)-([0-9.]+)-(channel_(all|\d+)|trial_(\d+))-(.+)$"
)
TRIAL_KEY_PATTERN = re.compile(
    r"^trial-(\d+)-(aspirate|dispense|liquid_height)-([0-9.]+)-ul-channel_(\d+)$"
)
MEASUREMENT_KEY_PATTERN = re.compile(
    r"^MeasurementType\.([A-Z]+)-(?:(blank)|([0-9.]+)-ul)-channel_(\d+)-trial-(\d+)-(.+)$"
)
MEASURE_KEY_PATTERN = re.compile(
    r"^measure-(init|aspirate|dispense)-(?:(blank)|([0-9.]+)-ul)-channel_(\d+)-trial-(\d+)-(.+)$"
)
ENCODER_KEY_PATTERN = re.compile(
    r"^encoder-volume-([0-9.]+)-channel_(\d+)-trial-(\d+)-(start|end)-(target|encoder|drift)$"
)


def can_analyze(metadata: dict[str, Any], rows: list[list[str]]) -> bool:
    test_name = str(metadata.get("test_name") or metadata.get("test_name".upper()) or "").lower()
    if "gravimetric-ot3-p200-96" in test_name:
        return True

    config = section_key_values(parse_sections(rows).get("CONFIG", []))
    return str(config.get("name") or "").lower() == "gravimetric-ot3-p200-96"


def analyze(file_path: str, rows: list[list[str]], metadata: dict[str, Any]) -> dict[str, Any]:
    sections = parse_sections(rows)
    config = section_key_values(sections.get("CONFIG", []))
    serial_numbers = section_key_values(sections.get("SERIAL-NUMBERS", []))
    environment_overview = section_key_values(sections.get("ENVIRONMENT", []))
    product = resolve_product(metadata, config, serial_numbers)
    volume_metrics, metric_lookup, trial_metric_lookup = parse_volume_metrics(sections.get("VOLUMES", []))
    encoder_lookup = parse_encoder_lookup(sections.get("ENCODER", []))
    trial_series = parse_trial_series(sections.get("TRIALS", []), trial_metric_lookup, encoder_lookup)
    environment_series = parse_environment_series(sections.get("MEASUREMENTS", []))
    environment_summary = summarize_environment_by_volume(environment_series)
    water_remain_summary = summarize_water_remain(trial_series)
    evaluation = evaluate_results(product, metric_lookup)
    volumes = sorted({item["volume"] for item in volume_metrics})

    return {
        "file": build_file_info(file_path),
        "channel": "pipette_gravimetric",
        "channel_label": "Pipette Gravimetric",
        "status": "success",
        "result": "Pass" if evaluation["passed"] else "Fail",
        "passed": evaluation["passed"],
        "product": product,
        "sn": serial_numbers.get("pipette") or metadata.get("test_device_id") or metadata.get("test_tag"),
        "test_name": metadata.get("test_name") or metadata.get("test_name".upper()) or config.get("name"),
        "test_time_utc": metadata.get("test_time_utc"),
        "metadata": metadata,
        "config": config,
        "serial_numbers": serial_numbers,
        "volumes": volumes,
        "volume_metrics": volume_metrics,
        "trial_series": trial_series,
        "environment_series": environment_series,
        "environment_summary": environment_summary,
        "environment_overview": environment_overview,
        "water_remain_summary": water_remain_summary,
        "summary": {
            "volume_count": len(volumes),
            "trial_count": len(trial_series),
            "environment_point_count": len(environment_series),
            "water_remain_avg": average_of(water_remain_summary, "avg"),
            "passed_checks": evaluation["passed_checks"],
            "failed_checks": evaluation["failed_checks"],
            "volume_results": evaluation["volume_results"],
            "failures": evaluation["failures"],
        },
    }


def parse_volume_metrics(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[tuple[float, str, str, str], dict[str, Any]], dict[tuple[float, int, str], dict[str, Any]]]:
    lookup: dict[tuple[float, str, str, str], dict[str, Any]] = defaultdict(dict)
    trial_lookup: dict[tuple[float, int, str], dict[str, Any]] = defaultdict(dict)

    for row in rows:
        match = VOLUME_KEY_PATTERN.match(str(row.get("key") or ""))
        if not match:
            continue

        action, volume_raw, scope_raw, channel_id, trial_id, metric = match.groups()
        volume = float(volume_raw)
        value = row.get("value")
        if scope_raw.startswith("channel_"):
            scope = "channel"
            scope_id = channel_id or ""
            lookup[(volume, action, scope, scope_id)][metric] = value
            lookup[(volume, action, scope, scope_id)]["time_s"] = row.get("time_s")
        else:
            trial = int(trial_id or 0)
            trial_lookup[(volume, trial, action)][metric] = value

    metrics = []
    for (volume, action, scope, scope_id), values in sorted(
        lookup.items(),
        key=lambda item: (item[0][0], item[0][1], item[0][2], sort_scope_id(item[0][3])),
    ):
        metrics.append(
            {
                "volume": volume,
                "action": action,
                "scope": scope,
                "scope_id": scope_id,
                "average": clean_number(values.get("average")),
                "cv": clean_number(values.get("cv")),
                "d": clean_number(values.get("d")),
                "celsius_pipette_avg": clean_number(values.get("celsius-pipette-avg")),
                "humidity_pipette_avg": clean_number(values.get("humidity-pipette-avg")),
                "time_s": clean_number(values.get("time_s")),
            }
        )

    return metrics, lookup, trial_lookup


def parse_trial_series(
    rows: list[dict[str, Any]],
    trial_metric_lookup: dict[tuple[float, int, str], dict[str, Any]],
    encoder_lookup: dict[tuple[float, int], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    trial_lookup: dict[tuple[float, int, str], dict[str, Any]] = defaultdict(dict)

    for row in rows:
        match = TRIAL_KEY_PATTERN.match(str(row.get("key") or ""))
        if not match:
            continue
        trial_raw, metric, volume_raw, channel = match.groups()
        volume = float(volume_raw)
        trial = int(trial_raw)
        entry = trial_lookup[(volume, trial, channel)]
        entry[metric] = clean_number(row.get("value"))
        entry[f"{metric}_time_s"] = clean_number(row.get("time_s"))

    series = []
    for (volume, trial, channel), values in sorted(trial_lookup.items(), key=lambda item: (item[0][0], item[0][1], sort_scope_id(item[0][2]))):
        aspirate = clean_number(values.get("aspirate"))
        dispense = clean_number(values.get("dispense"))
        aspirate_d = clean_number(trial_metric_lookup.get((volume, trial, "aspirate"), {}).get("d"))
        dispense_d = clean_number(trial_metric_lookup.get((volume, trial, "dispense"), {}).get("d"))
        aspirate_cv = clean_cv(trial_metric_lookup.get((volume, trial, "aspirate"), {}).get("cv"))
        dispense_cv = clean_cv(trial_metric_lookup.get((volume, trial, "dispense"), {}).get("cv"))

        if aspirate_d is None and aspirate is not None:
            aspirate_d = round_float((aspirate - volume) / volume * 100)
        if dispense_d is None and dispense is not None:
            dispense_d = round_float((dispense - volume) / volume * 100)

        water_remain = None
        if aspirate is not None and dispense is not None:
            water_remain = round_float(aspirate - dispense)
        encoder_values = (encoder_lookup or {}).get((volume, trial), {})

        series.append(
            {
                "volume": volume,
                "trial": trial,
                "channel": channel,
                "aspirate": aspirate,
                "dispense": dispense,
                "aspirate_d": aspirate_d,
                "dispense_d": dispense_d,
                "aspirate_cv": aspirate_cv,
                "dispense_cv": dispense_cv,
                "water_remain": water_remain,
                "aspirate_time_s": clean_number(values.get("aspirate_time_s")),
                "dispense_time_s": clean_number(values.get("dispense_time_s")),
                "liquid_height": clean_number(values.get("liquid_height")),
                "liquid_height_time_s": clean_number(values.get("liquid_height_time_s")),
                "aspirate_travel": calculate_aspirate_travel(encoder_values),
                "time_s": first_number(
                    values.get("dispense_time_s"),
                    values.get("aspirate_time_s"),
                    values.get("liquid_height_time_s"),
                ),
            }
        )

    return series


def parse_encoder_lookup(rows: list[dict[str, Any]]) -> dict[tuple[float, int], dict[str, Any]]:
    lookup: dict[tuple[float, int], dict[str, Any]] = defaultdict(dict)
    for row in rows:
        match = ENCODER_KEY_PATTERN.match(str(row.get("key") or ""))
        if not match:
            continue
        volume_raw, channel, trial_raw, phase, metric = match.groups()
        volume = float(volume_raw)
        trial = int(trial_raw)
        key = f"{phase}_{metric}"
        lookup[(volume, trial)][key] = clean_number(row.get("value"))
        lookup[(volume, trial)][f"{key}_time_s"] = clean_number(row.get("time_s"))
        lookup[(volume, trial)]["channel"] = channel
    return lookup


def calculate_aspirate_travel(encoder_values: dict[str, Any]) -> float | int | None:
    start_target = clean_number(encoder_values.get("start_target"))
    end_target = clean_number(encoder_values.get("end_target"))
    if start_target is not None and end_target is not None:
        return round_float(end_target - start_target)
    start_encoder = clean_number(encoder_values.get("start_encoder"))
    end_encoder = clean_number(encoder_values.get("end_encoder"))
    if start_encoder is not None and end_encoder is not None:
        return round_float(end_encoder - start_encoder)
    return None


def parse_environment_series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[float, int, str, str], dict[str, Any]] = {}
    metric_names = {
        "celsius-pipette": "celsius_pipette",
        "humidity-pipette": "humidity_pipette",
        "celsius-air": "celsius_air",
        "humidity-air": "humidity_air",
        "celsius-liquid": "celsius_liquid",
        "pascals-air": "pascals_air",
        "grams-average": "grams_average",
        "samples-start-time": "samples_start_time",
        "samples-duration": "samples_duration",
        "samples-count": "samples_count",
    }

    for row in rows:
        parsed = parse_measurement_key(str(row.get("key") or ""))
        if parsed is None:
            continue
        action, volume_raw, channel, trial_raw, metric = parsed
        mapped_metric = metric_names.get(metric)
        if mapped_metric is None:
            continue

        volume = float(volume_raw)
        trial = int(trial_raw)
        key = (volume, trial, channel, action)
        entry = grouped.setdefault(
            key,
            {
                "volume": volume,
                "trial": trial,
                "channel": channel,
                "action": action,
                "time_s": clean_number(row.get("time_s")),
            },
        )
        entry[mapped_metric] = clean_number(row.get("value"))
        entry["time_s"] = min_number(entry.get("time_s"), row.get("time_s"))

    return [
        item
        for _, item in sorted(
            grouped.items(),
            key=lambda item: (item[0][0], item[0][1], sort_scope_id(item[0][2]), item[0][3]),
        )
    ]


def parse_measurement_key(key: str) -> tuple[str, str, str, str, str] | None:
    legacy_match = MEASUREMENT_KEY_PATTERN.match(key)
    if legacy_match:
        action, blank_marker, volume_raw, channel, trial_raw, metric = legacy_match.groups()
        if blank_marker or volume_raw is None:
            return None
        return action.upper(), volume_raw, channel, trial_raw, metric

    measure_match = MEASURE_KEY_PATTERN.match(key)
    if measure_match:
        action, blank_marker, volume_raw, channel, trial_raw, metric = measure_match.groups()
        if blank_marker or volume_raw is None:
            return None
        return action.upper(), volume_raw, channel, trial_raw, metric

    return None


def summarize_environment_by_volume(environment_series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for item in environment_series:
        grouped[item["volume"]].append(item)

    summary = []
    for volume, items in sorted(grouped.items()):
        summary.append(
            {
                "volume": volume,
                "celsius_pipette_avg": average_metric(items, "celsius_pipette"),
                "humidity_pipette_avg": average_metric(items, "humidity_pipette"),
                "celsius_air_avg": average_metric(items, "celsius_air"),
                "humidity_air_avg": average_metric(items, "humidity_air"),
                "celsius_liquid_avg": average_metric(items, "celsius_liquid"),
                "point_count": len(items),
            }
        )
    return summary


def summarize_water_remain(trial_series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[float, list[float]] = defaultdict(list)
    for item in trial_series:
        water_remain = clean_number(item.get("water_remain"))
        if water_remain is not None:
            grouped[item["volume"]].append(water_remain)

    summary = []
    for volume, values in sorted(grouped.items()):
        summary.append(
            {
                "volume": volume,
                "avg": round_float(mean(values)),
                "min": round_float(min(values)),
                "max": round_float(max(values)),
                "count": len(values),
            }
        )
    return summary


def evaluate_results(product: str, metric_lookup: dict[tuple[float, str, str, str], dict[str, Any]]) -> dict[str, Any]:
    spec = get_gravimetric_spec(product)
    failures: list[str] = []
    passed_checks = 0
    failed_checks = 0
    volume_results = []

    for volume in sorted({key[0] for key in metric_lookup}):
        volume_spec = spec.get(volume)
        result_item: dict[str, Any] = {
            "volume": volume,
            "spec": volume_spec,
            "aspirate": build_action_result(metric_lookup, volume, "aspirate", volume_spec),
            "dispense": build_action_result(metric_lookup, volume, "dispense", volume_spec),
        }

        dispense_result = result_item["dispense"]
        for metric in ("cv", "d"):
            metric_result = dispense_result.get(metric)
            if not metric_result or metric_result.get("actual") is None:
                continue
            if metric_result.get("passed"):
                passed_checks += 1
            else:
                failed_checks += 1
                failures.append(
                    f"{volume:g} uL dispense {metric.upper()} {metric_result['actual']} exceeds spec {metric_result['spec']}"
                )

        if not volume_spec:
            failed_checks += 1
            failures.append(f"{volume:g} uL spec not found for {product}")

        volume_results.append(result_item)

    return {
        "passed": failed_checks == 0 and bool(volume_results),
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "failures": failures,
        "volume_results": volume_results,
    }


def build_action_result(
    metric_lookup: dict[tuple[float, str, str, str], dict[str, Any]],
    volume: float,
    action: str,
    spec: dict[str, float] | None,
) -> dict[str, Any]:
    values = metric_lookup.get((volume, action, "channel", "all"), {})
    result: dict[str, Any] = {
        "average": clean_number(values.get("average")),
        "cv": build_metric_result(values.get("cv"), spec.get("cv") if spec else None, absolute=False),
        "d": build_metric_result(values.get("d"), spec.get("d") if spec else None, absolute=True),
    }
    return result


def build_metric_result(actual: Any, spec: float | None, *, absolute: bool) -> dict[str, Any]:
    actual_number = clean_number(actual)
    passed = None
    if actual_number is not None and spec is not None:
        compared = abs(actual_number) if absolute else actual_number
        passed = compared <= spec
    return {
        "actual": actual_number,
        "spec": spec,
        "passed": passed,
    }


def resolve_product(metadata: dict[str, Any], config: dict[str, Any], serial_numbers: dict[str, Any]) -> str:
    test_name = str(metadata.get("test_name") or config.get("name") or "").lower()
    pipette_sn = str(serial_numbers.get("pipette") or metadata.get("test_device_id") or "")
    if "p200-96" in test_name or pipette_sn.startswith("P2HH"):
        return "P200-96"
    if "p1000-96" in test_name or pipette_sn.startswith("P1KH"):
        return "P1000-96"
    if "p1000" in test_name:
        return "P1000M" if "multi" in test_name else "P1000S"
    if "p50" in test_name:
        return "P50M" if "multi" in test_name else "P50S"
    return "Unknown"


def clean_cv(value: Any) -> float | int | None:
    value = clean_number(value)
    if value is None or value < 0:
        return None
    return value


def first_number(*values: Any) -> float | int | None:
    for value in values:
        number = clean_number(value)
        if number is not None:
            return number
    return None


def min_number(left: Any, right: Any) -> float | int | None:
    left_number = clean_number(left)
    right_number = clean_number(right)
    if left_number is None:
        return right_number
    if right_number is None:
        return left_number
    return min(left_number, right_number)


def average_metric(items: list[dict[str, Any]], key: str) -> float | int | None:
    values = [clean_number(item.get(key)) for item in items]
    numbers = [value for value in values if value is not None]
    if not numbers:
        return None
    return round_float(mean(numbers))


def average_of(items: list[dict[str, Any]], key: str) -> float | int | None:
    return average_metric(items, key)


def sort_scope_id(value: str) -> tuple[int, str]:
    if value == "all":
        return (0, value)
    if str(value).isdigit():
        return (1, f"{int(value):04d}")
    return (2, str(value))
