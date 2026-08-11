from __future__ import annotations

import asyncio
import os
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
    save_gantry_leveling_deck_slot,
    save_gantry_leveling_height,
)
from leveling_testing.report.report import LevelingCSV
from leveling_testing.retry import retry_hardware_action
from leveling_testing.simulation import SimulatedMaintenanceApi
from leveling_testing.type import Mount, Point, TestNameLeveling
from opentonrs_api.maintenance_api.jog import MaintenanceJog, read_jog_key, run_jog_interface
from opentonrs_api.maintenance_api.maintenance_run import MaintenanceApi


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
        self.report: LevelingCSV | None = None
        self.jog_key_reader = read_jog_key
        self.render_jog = True

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
        table.add_row(
            "Deck Slot",
            "Unknown" if self.config.deck_slot is None else self.config.deck_slot,
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

        async def move_with_retry(coordinate: dict[str, float], mount: Mount) -> object:
            return await self._hardware(
                "jog gantry",
                lambda: self.api.move_to(coordinate, mount=mount),
            )

        jog = MaintenanceJog(
            self.api,
            self.config.mount,
            self.current_point,
            move_executor=move_with_retry,
        )
        self.current_point = await run_jog_interface(
            jog,
            key_reader=self.jog_key_reader,
            render=self.render_jog,
        )

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

    async def _update_deck_slot(self) -> None:
        default = self.config.deck_slot or ""
        while True:
            deck_slot = (
                await self._text(
                    ui.bilingual(
                        "Enter deck slot value",
                        "请输入 Deck Slot 内容",
                    ),
                    default,
                )
            ).strip()
            if not deck_slot:
                ui.warning(ui.bilingual("Deck slot cannot be empty", "Deck Slot 不能为空"))
                continue
            break

        save_gantry_leveling_deck_slot(deck_slot, self.config_path)
        self.config.deck_slot = deck_slot
        ui.success(
            ui.bilingual(
                f"Updated deck slot: {deck_slot}",
                f"已更新 Deck Slot: {deck_slot}",
            )
        )

    def _build_report(self) -> None:
        self.report = LevelingCSV(
            "Gantry_Leveling_Test.csv",
            os.path.join(self.script_dir, "testing_data"),
            self.test_name,
            self.robot_sn,
            self.operator_name,
        )
        self.report.update_create_time()
        self.report.create_csv_path()
        self.report.init_title()

    def _finish_report(self) -> None:
        if self.report is None:
            raise RuntimeError("Gantry leveling report is not initialized")
        complete = self.height_diff is not None
        self.report.write_new_results(
            {
                "A1": self.config.heights["A1"] if self.config.heights["A1"] is not None else "UNKNOWN",
                "A3": self.config.heights["A3"] if self.config.heights["A3"] is not None else "UNKNOWN",
                "D1": self.config.heights["D1"] if self.config.heights["D1"] is not None else "UNKNOWN",
                "D3": self.config.heights["D3"] if self.config.heights["D3"] is not None else "UNKNOWN",
                "diff": self.height_diff if self.height_diff is not None else "UNKNOWN",
                "deck_slot": self.config.deck_slot if self.config.deck_slot is not None else "UNKNOWN",
            },
            passed=complete,
        )
        self.report.finish_test(passed=complete)

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
        self._build_report()
        await self._hardware("create maintenance run", self.api.create_run)
        try:
            await self._hardware("home robot", self.api.home)
            point_choices = [
                *[Choice(name, name=ui.bilingual(f"Edit {name}", f"编辑 {name}")) for name in GANTRY_POINT_NAMES],
                Choice("deck-slot", name=ui.bilingual("Update deck slot", "更新 Deck Slot")),
                Choice("exit", name=ui.bilingual("Exit", "退出")),
            ]
            while True:
                self._show_heights()
                name = await self._select(
                    ui.bilingual("Select a gantry point", "选择龙门点位"),
                    point_choices,
                )
                if name == "exit":
                    self._finish_report()
                    return
                if name == "deck-slot":
                    await self._update_deck_slot()
                    continue
                await self._edit_point(name)
        finally:
            await self.cleanup()


if __name__ == "__main__":
    asyncio.run(GantryLeveling("192.168.6.1").run())
