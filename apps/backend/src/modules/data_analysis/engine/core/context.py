from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnalysisContext:
    file_path: str
    rows: list[list[str]]
    metadata: dict[str, Any]
