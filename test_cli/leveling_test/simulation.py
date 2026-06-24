from __future__ import annotations

import hashlib
from dataclasses import dataclass

from test_cli.leveling_test.type import Mount, Point


class SimulatedMaintenanceApi:
    def __init__(self, ip_address: str):
        self.ip_address = ip_address
        self.run_id = "simulated-maintenance-run"

    async def create_run(self):
        self.run_id = "simulated-maintenance-run"

    async def delete_run(self):
        self.run_id = None

    async def move_to(self, coordinate: dict[str, float], mount: Mount, speed=567.8):
        return {
            "coordinate": coordinate,
            "mount": mount.value,
            "speed": speed,
        }

    async def home(self):
        return True

    async def home_z(self, mount: Mount, current_position: Point):
        return await self.move_to(current_position.replace({"z": 505})._asdict(), mount=mount)


class SimulatedHardwareControl:
    async def home(self, *args, **kwargs):
        return True


@dataclass
class SimulatedLaserSensor:
    name: str
    distance: float = 30.24

    def close(self):
        return None

    def nudge_towards_target(self, step: float, target: float = 30.0):
        if self.distance > target:
            self.distance = max(target, self.distance - abs(step))
        else:
            self.distance = min(target, self.distance + abs(step))

    def read_sensor_low(self, show_distance: bool = True) -> dict[int, float]:
        seed = int(hashlib.sha256(self.name.encode("utf-8")).hexdigest()[:8], 16)
        base = self.distance + ((seed % 7) - 3) * 0.01
        return {index: round(base + index * 0.018, 3) for index in range(16)}
