from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from data_analysis.core import AnalysisContext
from data_analysis import gravimetric as legacy_gravimetric
from data_analysis.spec_store import get_gravimetric_spec


class GravimetricAnalyzer:
    key = "gravimetric"
    view_key = "pipette_gravimetric"
    label = "Pipette Gravimetric"

    def analyze(self, context: AnalysisContext) -> dict[str, Any]:
        result = legacy_gravimetric.analyze(context.file_path, context.rows, context.metadata)
        result["analyzer_key"] = self.key
        result["view_key"] = self.view_key
        result["schema_version"] = 1
        result["test_type"] = "gravimetric"
        single_channel_matrices = build_single_channel_trial_matrices(result)
        result["single_channel_trial_matrices"] = single_channel_matrices
        result["summary"]["single_channel_trial_matrix_count"] = len(single_channel_matrices)
        return result


class P50SingleGravimetricAnalyzer(GravimetricAnalyzer):
    key = "gravimetric.p50_single"


class P1000SingleGravimetricAnalyzer(GravimetricAnalyzer):
    key = "gravimetric.p1000_single"


class P20096GravimetricAnalyzer(GravimetricAnalyzer):
    key = "gravimetric.p200_96"


class P100096GravimetricAnalyzer(GravimetricAnalyzer):
    key = "gravimetric.p1000_96"


class P50MultiGravimetricAnalyzer(GravimetricAnalyzer):
    key = "gravimetric.p50_multi"

    def analyze(self, context: AnalysisContext) -> dict[str, Any]:
        result = super().analyze(context)
        matrices = build_channel_trial_matrices(result)
        result["channel_trial_matrices"] = matrices
        result["summary"]["channel_trial_matrix_count"] = len(matrices)
        return result


class P1000MultiGravimetricAnalyzer(P50MultiGravimetricAnalyzer):
    key = "gravimetric.p1000_multi"


def build_single_channel_trial_matrices(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    trial_series = analysis.get("trial_series") or []
    if not trial_series:
        return []

    spec = get_gravimetric_spec(str(analysis.get("product") or ""))
    matrices: list[dict[str, Any]] = []

    for volume in sorted({clean_number(row.get("volume")) for row in trial_series if clean_number(row.get("volume")) is not None}):
        volume_rows = [
            row
            for row in trial_series
            if clean_number(row.get("volume")) == volume
        ]
        if not volume_rows:
            continue
        rows = []
        for row in sorted(volume_rows, key=lambda item: (int(item.get("trial") or 0), sort_channel(str(item.get("channel") or "")))):
            rows.append(
                {
                    "trial": row.get("trial"),
                    "channel": str(row.get("channel") or ""),
                    "water_remaining": clean_number(row.get("water_remain")),
                    "aspirate_time_s": clean_number(row.get("aspirate_time_s")),
                    "aspirate": clean_number(row.get("aspirate")),
                    "aspirate_d": clean_number(row.get("aspirate_d")),
                    "dispense_time_s": clean_number(row.get("dispense_time_s")),
                    "dispense": clean_number(row.get("dispense")),
                    "dispense_d": clean_number(row.get("dispense_d")),
                    "aspirate_travel": clean_number(row.get("aspirate_travel")),
                }
            )
        matrices.append(
            {
                "volume": volume,
                "label": volume_label(volume),
                "spec": build_volume_spec(volume, spec.get(float(volume))),
                "rows": rows,
                "summary": build_single_channel_summary(rows),
            }
        )

    return matrices


def build_single_channel_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, float | int | None]]:
    return {
        "average": {
            "water_remaining": average_numbers([row.get("water_remaining") for row in rows]),
            "aspirate": average_numbers([row.get("aspirate") for row in rows]),
            "aspirate_d": average_numbers([row.get("aspirate_d") for row in rows]),
            "dispense": average_numbers([row.get("dispense") for row in rows]),
            "dispense_d": average_numbers([row.get("dispense_d") for row in rows]),
        },
        "cv": {
            "aspirate": calculate_cv([row.get("aspirate") for row in rows]),
            "dispense": calculate_cv([row.get("dispense") for row in rows]),
        },
    }


def build_channel_trial_matrices(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    trial_series = analysis.get("trial_series") or []
    if not trial_series:
        return []

    metric_lookup = {
        (
            clean_number(item.get("volume")),
            str(item.get("action") or ""),
            str(item.get("scope_id") or ""),
        ): item
        for item in analysis.get("volume_metrics") or []
        if str(item.get("scope") or "") == "channel"
    }
    spec = get_gravimetric_spec(str(analysis.get("product") or ""))
    matrices: list[dict[str, Any]] = []

    for volume in sorted({clean_number(row.get("volume")) for row in trial_series if clean_number(row.get("volume")) is not None}):
        volume_rows = [row for row in trial_series if clean_number(row.get("volume")) == volume]
        trials = sorted({int(row["trial"]) for row in volume_rows if row.get("trial") is not None})
        channels = sorted(
            {str(row.get("channel") or "") for row in volume_rows if row.get("channel") not in (None, "")},
            key=sort_channel,
        )
        if not trials or not channels:
            continue

        for action in ("aspirate", "dispense"):
            matrix_rows = build_channel_rows(volume, action, trials, channels, volume_rows, metric_lookup)
            matrices.append(
                {
                    "volume": volume,
                    "action": action,
                    "trials": trials,
                    "channels": channels,
                    "spec": build_volume_spec(volume, spec.get(float(volume))),
                    "rows": matrix_rows,
                    "trial_summary": build_trial_summary(volume, action, trials, volume_rows),
                }
            )

    return matrices


def build_channel_rows(
    volume: float | int,
    action: str,
    trials: list[int],
    channels: list[str],
    volume_rows: list[dict[str, Any]],
    metric_lookup: dict[tuple[float | int | None, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    row_lookup = {
        (int(row["trial"]), str(row.get("channel") or "")): row
        for row in volume_rows
        if row.get("trial") is not None
    }
    matrix_rows = []

    for channel in channels:
        values = []
        water_remaining = []
        trial_values = []
        for trial in trials:
            source = row_lookup.get((trial, channel), {})
            value = clean_number(source.get(action))
            water_remain = clean_number(source.get("water_remain"))
            values.append(value)
            if water_remain is not None:
                water_remaining.append(water_remain)
            trial_values.append(
                {
                    "trial": trial,
                    "value": value,
                    "d": calculate_d(value, volume),
                    "water_remain": water_remain,
                }
            )

        metric = metric_lookup.get((volume, action, channel), {})
        matrix_rows.append(
            {
                "channel": channel,
                "label": f"CH{channel}",
                "trial_values": trial_values,
                "average": first_number(metric.get("average"), average_numbers(values)),
                "cv": first_number(metric.get("cv"), calculate_cv(values)),
                "d": first_number(metric.get("d"), calculate_d(average_numbers(values), volume)),
                "avg_water_remaining": average_numbers(water_remaining),
            }
        )

    return matrix_rows


def build_trial_summary(
    volume: float | int,
    action: str,
    trials: list[int],
    volume_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows_by_trial: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in volume_rows:
        if row.get("trial") is not None:
            rows_by_trial[int(row["trial"])].append(row)

    summary = []
    for trial in trials:
        values = [clean_number(row.get(action)) for row in rows_by_trial.get(trial, [])]
        average = average_numbers(values)
        summary.append(
            {
                "trial": trial,
                "average": average,
                "cv": calculate_cv(values),
                "d": calculate_d(average, volume),
            }
        )
    return summary


def build_volume_spec(volume: float | int, spec: dict[str, float] | None) -> dict[str, Any]:
    d_spec = clean_number((spec or {}).get("d"))
    cv_spec = clean_number((spec or {}).get("cv"))
    return {
        "target": volume,
        "min": round_number(float(volume) * (1 - d_spec / 100)) if d_spec is not None else None,
        "max": round_number(float(volume) * (1 + d_spec / 100)) if d_spec is not None else None,
        "d": d_spec,
        "cv": cv_spec,
    }


def volume_label(volume: float | int) -> str:
    volume_number = clean_number(volume)
    if volume_number is None:
        return str(volume)
    return f"{volume_number:g} uL"


def calculate_d(value: Any, volume: float | int) -> float | int | None:
    value_number = clean_number(value)
    volume_number = clean_number(volume)
    if value_number is None or volume_number in (None, 0):
        return None
    return round_number((value_number - volume_number) / volume_number * 100)


def calculate_cv(values: list[Any]) -> float | int | None:
    numbers = [clean_number(value) for value in values]
    numbers = [value for value in numbers if value is not None]
    if len(numbers) < 2:
        return None
    avg = mean(numbers)
    if avg == 0:
        return None
    variance = sum((value - avg) ** 2 for value in numbers) / (len(numbers) - 1)
    return round_number((variance ** 0.5) / abs(avg) * 100)


def average_numbers(values: list[Any]) -> float | int | None:
    numbers = [clean_number(value) for value in values]
    numbers = [value for value in numbers if value is not None]
    if not numbers:
        return None
    return round_number(mean(numbers))


def first_number(*values: Any) -> float | int | None:
    for value in values:
        number = clean_number(value)
        if number is not None:
            return number
    return None


def clean_number(value: Any) -> float | int | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round_number(number)


def round_number(value: float | int, digits: int = 4) -> float | int:
    rounded = round(float(value), digits)
    if rounded.is_integer():
        return int(rounded)
    return rounded


def sort_channel(value: str) -> tuple[int, str]:
    return (0, f"{int(value):04d}") if str(value).isdigit() else (1, str(value))
