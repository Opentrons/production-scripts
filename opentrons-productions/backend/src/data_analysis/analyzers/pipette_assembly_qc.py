from __future__ import annotations

from typing import Any

from data_analysis import pipette_assembly_qc as pipette_assembly_qc_analysis
from data_analysis.core import AnalysisContext


class PipetteAssemblyQcAnalyzer:
    key = "pipette_assembly_qc"
    view_key = "pipette_assembly_qc"
    label = "Pipette Assembly QC"

    def analyze(self, context: AnalysisContext) -> dict[str, Any]:
        result = pipette_assembly_qc_analysis.analyze(context.file_path, context.rows, context.metadata)
        result["analyzer_key"] = self.key
        result["view_key"] = self.view_key
        result["schema_version"] = 1
        result["test_type"] = "pipette_assembly_qc"
        return result
