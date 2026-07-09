from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from upload_handler.parsers.csv_common import extract_meta_data_from_csv, read_csv_rows

from .core import AnalysisContext, AnalyzerRegistration
from .registry import analysis_registry


def analyze_file(file_path: str) -> dict[str, Any]:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    metadata = extract_meta_data_from_csv(str(path))
    if metadata.get("failed"):
        raise ValueError(str(metadata.get("error") or "CSV metadata parse failed"))

    rows = read_csv_rows(str(path))
    context = AnalysisContext(file_path=str(path), rows=rows, metadata=metadata)
    registration = resolve_channel(context, fallback_test_name=path.name)
    if registration is None:
        test_name = metadata.get("test_name") or metadata.get("test_name".upper()) or path.name
        raise ValueError(f"No analysis channel matched: {test_name}")

    return registration.analyzer.analyze(context)


def analyze_file_paths(file_paths: list[str]) -> dict[str, Any]:
    analyses = []
    errors = []

    for file_path in file_paths:
        try:
            analyses.append(analyze_file(file_path))
        except Exception as exc:
            errors.append(
                {
                    "file": {
                        "name": Path(file_path).name,
                        "path": file_path,
                    },
                    "message": str(exc),
                }
            )

    return {
        "analyses": analyses,
        "summary": summarize_analyses(analyses, errors),
        "errors": errors,
    }


def resolve_channel(context: AnalysisContext, *, fallback_test_name: str = "") -> AnalyzerRegistration | None:
    return analysis_registry.resolve(context, fallback_test_name=fallback_test_name)


def summarize_analyses(analyses: list[dict[str, Any]], errors: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(analyses)
    passed = sum(1 for item in analyses if item.get("passed"))
    failed = total - passed
    by_product = Counter(str(item.get("product") or "Unknown") for item in analyses)
    by_channel = Counter(str(item.get("channel_label") or item.get("channel") or "Unknown") for item in analyses)

    return {
        "total_files": total + len(errors),
        "analyzed": total,
        "pass": passed,
        "fail": failed,
        "error": len(errors),
        "yield_rate": round((passed / total) * 100, 1) if total else 0,
        "products": [
            {"product": product, "count": count}
            for product, count in sorted(by_product.items(), key=lambda item: (-item[1], item[0]))
        ],
        "channels": [
            {"channel": channel, "count": count}
            for channel, count in sorted(by_channel.items(), key=lambda item: (-item[1], item[0]))
        ],
    }
