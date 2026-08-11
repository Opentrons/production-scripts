from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from leveling_testing.type import Mount, Point
from opentonrs_api.maintenance_api.maintenance_run import MaintenanceApi


@dataclass(frozen=True)
class JogBounds:
    minimum: Point = Point(0.0, 25.0, 300.0)
    maximum: Point = Point(500.0, 500.0, 600.0)

    def contains(self, point: Point) -> bool:
        return all(
            isfinite(value) and lower <= value <= upper
            for value, lower, upper in zip(point, self.minimum, self.maximum)
        )


class MaintenanceJog:
    """Move one gantry mount incrementally within the maintenance run."""

    def __init__(
        self,
        api: MaintenanceApi,
        mount: Mount,
        current_point: Point,
        bounds: JogBounds | None = None,
    ) -> None:
        self.api = api
        self.mount = mount
        self.current_point = current_point
        self.bounds = bounds or JogBounds()

    async def move(self, axis: str, distance: float) -> Point:
        normalized_axis = axis.lower()
        if normalized_axis not in {"x", "y", "z"}:
            raise ValueError(f"Unsupported jog axis: {axis}")
        if not isfinite(distance):
            raise ValueError("Jog distance must be finite")

        offsets = {"x": 0.0, "y": 0.0, "z": 0.0}
        offsets[normalized_axis] = distance
        target = self.current_point + Point(**offsets)
        if not self.bounds.contains(target):
            raise ValueError(
                "Jog target is outside the allowed range: "
                f"x={target.x:.3f}, y={target.y:.3f}, z={target.z:.3f}"
            )

        await self.api.move_to(target._asdict(), mount=self.mount)
        self.current_point = target
        return target
