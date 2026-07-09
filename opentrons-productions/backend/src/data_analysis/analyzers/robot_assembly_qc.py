from __future__ import annotations

from typing import Any

from data_analysis import robot_assembly_qc as robot_assembly_qc_analysis
from data_analysis.core import AnalysisContext


class RobotAssemblyQcAnalyzer:
    key = "robot_assembly_qc"
    view_key = "robot_assembly_qc"
    label = "Robot Assembly QC"

    def analyze(self, context: AnalysisContext) -> dict[str, Any]:
        result = robot_assembly_qc_analysis.analyze(context.file_path, context.rows, context.metadata)
        result["analyzer_key"] = self.key
        result["view_key"] = self.view_key
        result["schema_version"] = 1
        result["test_type"] = "robot_assembly_qc"
        return result
