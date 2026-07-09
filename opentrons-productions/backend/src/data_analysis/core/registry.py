from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from .context import AnalysisContext


class Analyzer(Protocol):
    key: str
    view_key: str
    label: str

    def analyze(self, context: AnalysisContext) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class AnalyzerRegistration:
    key: str
    view_key: str
    label: str
    analyzer: Analyzer
    patterns: tuple[str, ...]

    def matches(self, test_name: str) -> bool:
        normalized = test_name.lower()
        return any(re.search(pattern, normalized) for pattern in self.patterns)


class AnalysisRegistry:
    def __init__(self) -> None:
        self._registrations: list[AnalyzerRegistration] = []

    def register(self, registration: AnalyzerRegistration) -> None:
        self._registrations.append(registration)

    def resolve(self, context: AnalysisContext, *, fallback_test_name: str = "") -> AnalyzerRegistration | None:
        test_name = resolve_test_name(context, fallback_test_name=fallback_test_name)
        for registration in self._registrations:
            if registration.matches(test_name):
                return registration
        return None

    @property
    def registrations(self) -> tuple[AnalyzerRegistration, ...]:
        return tuple(self._registrations)


def resolve_test_name(context: AnalysisContext, *, fallback_test_name: str = "") -> str:
    metadata_name = context.metadata.get("test_name") or context.metadata.get("TEST_NAME")
    if metadata_name:
        return str(metadata_name)

    from data_analysis.common import parse_sections, section_key_values

    config = section_key_values(parse_sections(context.rows).get("CONFIG", []))
    return str(config.get("name") or fallback_test_name or "")
