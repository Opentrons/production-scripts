from __future__ import annotations

import asyncio
from math import isfinite
from pathlib import Path
from typing import Any

from InquirerPy.base.control import Choice
from rich import box
from rich.table import Table

from cli.interface import ui
from cli.interface.prompts import select, text
from leveling_testing.config import (
    GANTRY_POINT_NAMES,
    GantryLevelingConfig,
    load_gantry_leveling_config,
    save_gantry_leveling_height,
)
from leveling_testing.retry import retry_hardware_action
from leveling_testing.simulation import SimulatedMaintenanceApi
from leveling_testing.type import Point, TestNameLeveling
from opentonrs_api.maintenance_api.jog import MaintenanceJog
from opentonrs_api.maintenance_api.maintenance_run import MaintenanceApi


JOG_STEPS = (0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0)


class GantryLeveling:
    """Interactively adjust and persist the four gantry leveling points."""

    def __init__(
        self,
        robot_ip_address: str,
        test_name: TestNameLeveling = TestNameLeveling.Gantry_Leveling,
        script_dir: str = "./",
        simulate: bool = False,
        config_path: str | Path | None = None,
    ) -> None:
        self.robot_ip_address = robot_ip_address
        self.test_name = test_name
        self.script_dir = script_dir
        self.simulate = simulate
        self.config_path = Path(config_path) if config_path is not None else None
        self.robot_sn = ""
        self.operator_name = ""
        self.current_point: Point | None = None
        self.selected_point_name: str | None = None

        self.config: GantryLevelingConfig = load_gantry_leveling_config(self.config_path)
        api_type = SimulatedMaintenanceApi if simulate else MaintenanceApi
        self.api: Any = api_type(robot_ip_address)

    @property
    def height_diff(self) -> float | None:
        heights = [self.config.heights[name] for name in GANTRY_POINT_NAMES]
        if any(height is None for height in heights):
            return None
        return round(max(heights) - min(heights), 3)

    async def _hardware(self, action: str, func):
        return await retry_hardware_action(action, func, simulate=self.simulate)

    async def _select(self, message: str, choices: list[Choice]) -> Any:
        return await asyncio.to_thread(select, message, choices)

    async def _text(self, message: str, default: str = "") -> str:
        return await asyncio.to_thread(text, message, default)

    def _show_heights(self) -> None:
        table = Table(
            title=ui.bilingual("Gantry leveling heights", "龙门调平高度"),
            box=box.SIMPLE_HEAVY,
        )
        table.add_column(ui.bilingual("Position", "位置"), style="cyan", no_wrap=True)
        table.add_column(ui.bilingual("Gauge height", "高度计读数"), justify="right")
        for name in GANTRY_POINT_NAMES:
            height = self.config.heights[name]
            table.add_row(name, "Unknown" if height is None else f"{height:.3f}")
        table.add_section()
        height_diff = self.height_diff
        table.add_row(
            "Diff",
            "Unknown" if height_diff is None else f"{height_diff:.3f}",
            style="bold yellow",
        )
        ui.console.print(table)

    async def _move_absolute(self, point: Point, action: str) -> None:
        await self._hardware(
            action,
            lambda: self.api.move_to(point._asdict(), mount=self.config.mount),
        )
        self.current_point = point

    async def move_to_point(self, name: str) -> Point:
        target = self.config.points[name]
        safe_z = self.config.safe_z

        if self.current_point is not None and self.current_point.z != safe_z:
            await self._move_absolute(
                self.current_point.replace({"z": safe_z}),
                f"raise gantry from {self.selected_point_name or 'current point'}",
            )

        safe_target = target.replace({"z": safe_z})
        if self.current_point != safe_target:
            await self._move_absolute(safe_target, f"move gantry above {name}")
        await self._move_absolute(target, f"move gantry to {name}")
        self.selected_point_name = name
        return target

    async def _run_jog(self) -> None:
        if self.current_point is None:
            raise ValueError("Select a gantry point before jogging")

        jog = MaintenanceJog(self.api, self.config.mount, self.current_point)
        step_index = JOG_STEPS.index(0.5)
        actions = [
            Choice(("x", -1), name="X-"),
            Choice(("x", 1), name="X+"),
            Choice(("y", -1), name="Y-"),
            Choice(("y", 1), name="Y+"),
            Choice(("z", -1), name="Z-"),
            Choice(("z", 1), name="Z+"),
            Choice("step-down", name=ui.bilingual("Smaller step", "减小步长")),
            Choice("step-up", name=ui.bilingual("Larger step", "增大步长")),
            Choice("back", name=ui.bilingual("Back", "返回")),
        ]

        while True:
            point = jog.current_point
            ui.run_summary(
                [
                    ("Point", f"X={point.x:.3f}, Y={point.y:.3f}, Z={point.z:.3f}"),
                    ("Step", f"{JOG_STEPS[step_index]:.3f} mm"),
                ]
            )
            action = await self._select(ui.bilingual("Jog gantry", "Jog 龙门"), actions)
            if action == "back":
                self.current_point = jog.current_point
                return
            if action == "step-down":
                step_index = max(0, step_index - 1)
                continue
            if action == "step-up":
                step_index = min(len(JOG_STEPS) - 1, step_index + 1)
                continue

            axis, sign = action
            try:
                self.current_point = await self._hardware(
                    f"jog gantry {axis}{'+' if sign > 0 else '-'}",
                    lambda: jog.move(axis, sign * JOG_STEPS[step_index]),
                )
            except ValueError as exc:
                ui.warning(ui.bilingual(str(exc), f"Jog 目标超出安全范围: {exc}"))

    async def _update_height(self) -> None:
        if self.selected_point_name is None:
            raise ValueError("No gantry point is selected")
        name = self.selected_point_name
        current_height = self.config.heights[name]
        default = "" if current_height is None else f"{current_height:.3f}"
        while True:
            raw_value = (
                await self._text(
                    ui.bilingual(
                        f"Enter height gauge reading for {name}",
                        f"请输入 {name} 的高度计读数",
                    ),
                    default,
                )
            ).strip()
            try:
                height = float(raw_value)
                if not isfinite(height):
                    raise ValueError
            except ValueError:
                ui.warning(
                    ui.bilingual(
                        "Enter a finite numeric height",
                        "请输入有效的数字高度",
                    )
                )
                continue
            break

        save_gantry_leveling_height(name, height, self.config_path)
        self.config.heights[name] = height
        ui.success(
            ui.bilingual(
                f"Updated {name} gauge height: {height:.3f}",
                f"已更新 {name} 高度计读数: {height:.3f}",
            )
        )

    async def _edit_point(self, name: str) -> None:
        await self.move_to_point(name)
        choices = [
            Choice("jog", name="Jog"),
            Choice(
                "update",
                name=ui.bilingual("Update gauge value", "更新高度计读数"),
            ),
            Choice("back", name=ui.bilingual("Back", "返回上一级")),
        ]
        while True:
            action = await self._select(
                ui.bilingual(f"Edit {name}", f"编辑 {name}"),
                choices,
            )
            if action == "jog":
                await self._run_jog()
            elif action == "update":
                await self._update_height()
            else:
                return

    async def cleanup(self) -> None:
        if self.current_point is not None and self.current_point.z != self.config.safe_z:
            try:
                await self._move_absolute(
                    self.current_point.replace({"z": self.config.safe_z}),
                    "raise gantry before cleanup",
                )
            except Exception as exc:
                ui.warning(ui.bilingual(f"Safe Z move failed: {exc}", f"安全抬升失败: {exc}"))
        try:
            await self._hardware("home robot", self.api.home)
        except Exception as exc:
            ui.warning(ui.bilingual(f"Home during cleanup failed: {exc}", f"清理阶段 home 失败: {exc}"))
        if self.api.run_id is not None:
            try:
                await self.api.delete_run()
            except Exception as exc:
                ui.warning(
                    ui.bilingual(
                        f"Release maintenance run failed: {exc}",
                        f"释放 maintenance run 失败: {exc}",
                    )
                )

    async def run(self) -> None:
        await self._hardware("create maintenance run", self.api.create_run)
        try:
            await self._hardware("home robot", self.api.home)
            point_choices = [
                *[Choice(name, name=ui.bilingual(f"Edit {name}", f"编辑 {name}")) for name in GANTRY_POINT_NAMES],
                Choice("exit", name=ui.bilingual("Exit", "退出")),
            ]
            while True:
                self._show_heights()
                name = await self._select(
                    ui.bilingual("Select a gantry point", "选择龙门点位"),
                    point_choices,
                )
                if name == "exit":
                    return
                await self._edit_point(name)
        finally:
            await self.cleanup()


if __name__ == "__main__":
    asyncio.run(GantryLeveling("192.168.6.1").run())
