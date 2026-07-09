from __future__ import annotations

from data_analysis.analyzers.gravimetric import (
    P100096GravimetricAnalyzer,
    P1000MultiGravimetricAnalyzer,
    P1000SingleGravimetricAnalyzer,
    P20096GravimetricAnalyzer,
    P50MultiGravimetricAnalyzer,
    P50SingleGravimetricAnalyzer,
)
from data_analysis.analyzers.pipette_assembly_qc import PipetteAssemblyQcAnalyzer
from data_analysis.analyzers.robot_assembly_qc import RobotAssemblyQcAnalyzer
from data_analysis.core import AnalysisRegistry, AnalyzerRegistration


def build_registry() -> AnalysisRegistry:
    registry = AnalysisRegistry()
    registry.register(
        AnalyzerRegistration(
            key="gravimetric.p200_96",
            view_key="pipette_gravimetric",
            label="Pipette Gravimetric",
            analyzer=P20096GravimetricAnalyzer(),
            patterns=(
                r"gravimetric-ot3-p200-96",
                r"p200.*grav",
            ),
        )
    )
    registry.register(
        AnalyzerRegistration(
            key="gravimetric.p1000_96",
            view_key="pipette_gravimetric",
            label="Pipette Gravimetric",
            analyzer=P100096GravimetricAnalyzer(),
            patterns=(
                r"gravimetric-ot3-p1000-96",
                r"p1000.*96.*grav",
                r"p1kh.*%d",
            ),
        )
    )
    registry.register(
        AnalyzerRegistration(
            key="gravimetric.p50_single",
            view_key="pipette_gravimetric",
            label="Pipette Gravimetric",
            analyzer=P50SingleGravimetricAnalyzer(),
            patterns=(
                r"gravimetric-ot3-p50-single",
                r"p50.*single.*grav",
                r"p50s.*volume",
            ),
        )
    )
    registry.register(
        AnalyzerRegistration(
            key="gravimetric.p1000_single",
            view_key="pipette_gravimetric",
            label="Pipette Gravimetric",
            analyzer=P1000SingleGravimetricAnalyzer(),
            patterns=(
                r"gravimetric-ot3-p1000-single",
                r"p1000.*single.*grav",
                r"p1ks.*grav",
            ),
        )
    )
    registry.register(
        AnalyzerRegistration(
            key="gravimetric.p50_multi",
            view_key="pipette_gravimetric",
            label="Pipette Gravimetric",
            analyzer=P50MultiGravimetricAnalyzer(),
            patterns=(
                r"gravimetric-ot3-p50-multi",
                r"p50.*multi.*grav",
            ),
        )
    )
    registry.register(
        AnalyzerRegistration(
            key="gravimetric.p1000_multi",
            view_key="pipette_gravimetric",
            label="Pipette Gravimetric",
            analyzer=P1000MultiGravimetricAnalyzer(),
            patterns=(
                r"gravimetric-ot3-p1000-multi",
                r"p1000.*multi.*grav",
            ),
        )
    )
    registry.register(
        AnalyzerRegistration(
            key="pipette_assembly_qc",
            view_key="pipette_assembly_qc",
            label="Pipette Assembly QC",
            analyzer=PipetteAssemblyQcAnalyzer(),
            patterns=(
                r"pipette-assembly-qc-ot3",
                r"ninety-six-assembly-qc-ot3",
                r"assembly.*qc.*pipette",
                r"pipette.*assembly",
            ),
        )
    )
    registry.register(
        AnalyzerRegistration(
            key="robot_assembly_qc",
            view_key="robot_assembly_qc",
            label="Robot Assembly QC",
            analyzer=RobotAssemblyQcAnalyzer(),
            patterns=(
                r"robot-assembly-qc-ot3",
                r"robot.*assembly",
            ),
        )
    )
    return registry


analysis_registry = build_registry()
