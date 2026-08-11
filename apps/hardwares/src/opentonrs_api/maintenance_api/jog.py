from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from math import isfinite

from rich import box
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from cli.interface import ui
from leveling_testing.type import Mount, Point
from opentonrs_api.maintenance_api.maintenance_run import MaintenanceApi


JOG_STEPS = (0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0)
JOG_KEY_MOVES = {
    "a": ("x", -1),
    "d": ("x", 1),
    "w": ("y", 1),
    "s": ("y", -1),
    "i": ("z", 1),
    "k": ("z", -1),
}


@dataclass(frozen=True)
class JogBounds:
    minimum: Point = Point(0.0, 25.0, 300.0)
    maximum: Point = Point(500.0, 500.0, 600.0)

    def contains(self, point: Point) -> bool:
        return all(
            isfinite(value) and lower <= value <= upper
            for value, lower, upper in zip(point, self.minimum, self.maximum)
        )


@dataclass(frozen=True)
class JogKeyResult:
    running: bool
    message: str


def read_jog_key() -> str:
    """Read one key without Enter on Windows, macOS, and other POSIX terminals."""
    if os.name == "nt":
        import msvcrt

        key = msvcrt.getwch()
        if key in {"\x00", "\xe0"}:
            msvcrt.getwch()
            return ""
        return key

    if not sys.stdin.isatty():
        return sys.stdin.read(1) or "q"

    import termios
    import tty

    descriptor = sys.stdin.fileno()
    previous = termios.tcgetattr(descriptor)
    try:
        tty.setraw(descriptor)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, previous)


class MaintenanceJog:
    """Move one gantry mount incrementally within the maintenance run."""

    def __init__(
        self,
        api: MaintenanceApi,
        mount: Mount,
        current_point: Point,
        bounds: JogBounds | None = None,
        steps: tuple[float, ...] = JOG_STEPS,
        initial_step: float = 0.5,
        move_executor: Callable[[dict[str, float], Mount], Awaitable[object]] | None = None,
    ) -> None:
        if not steps or any(not isfinite(step) or step <= 0 for step in steps):
            raise ValueError("Jog steps must contain positive finite values")
        if not isfinite(initial_step):
            raise ValueError("Initial jog step must be finite")
        if not (bounds or JogBounds()).contains(current_point):
            raise ValueError("Initial jog point is outside the allowed range")
        self.api = api
        self.mount = mount
        self.current_point = current_point
        self.bounds = bounds or JogBounds()
        self.steps = tuple(steps)
        self.move_executor = move_executor
        self.step_index = min(
            range(len(self.steps)),
            key=lambda index: abs(self.steps[index] - initial_step),
        )

    @property
    def step(self) -> float:
        return self.steps[self.step_index]

    def change_step(self, direction: int) -> float:
        self.step_index = min(max(self.step_index + direction, 0), len(self.steps) - 1)
        return self.step

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

        if self.move_executor is None:
            await self.api.move_to(target._asdict(), mount=self.mount)
        else:
            await self.move_executor(target._asdict(), self.mount)
        self.current_point = target
        return target

    async def handle_key(self, key: str) -> JogKeyResult:
        normalized = key.casefold()
        if normalized in {"q", "\x1b", "\r", "\n"}:
            return JogKeyResult(False, ui.bilingual("Jog finished", "Jog 已结束"))
        if normalized == "\x03":
            raise KeyboardInterrupt
        if normalized in {"+", "="}:
            step = self.change_step(1)
            return JogKeyResult(True, ui.bilingual(f"Step: {step:.3f} mm", f"步进: {step:.3f} mm"))
        if normalized == "-":
            step = self.change_step(-1)
            return JogKeyResult(True, ui.bilingual(f"Step: {step:.3f} mm", f"步进: {step:.3f} mm"))
        if normalized not in JOG_KEY_MOVES:
            return JogKeyResult(True, ui.bilingual("Unknown key", "无效按键"))

        axis, sign = JOG_KEY_MOVES[normalized]
        point = await self.move(axis, sign * self.step)
        return JogKeyResult(
            True,
            f"{axis.upper()}{'+' if sign > 0 else '-'} -> "
            f"X={point.x:.3f}  Y={point.y:.3f}  Z={point.z:.3f}",
        )


def _jog_panel(jog: MaintenanceJog, message: str = "") -> Panel:
    point = jog.current_point
    table = Table.grid(padding=(0, 2))
    table.add_column(style="cyan", no_wrap=True)
    table.add_column()
    table.add_row("Position", f"X {point.x:.3f}   Y {point.y:.3f}   Z {point.z:.3f}")
    table.add_row("Step", f"{jog.step:.3f} mm")
    table.add_row("Move", "W/S  Y+/Y-    A/D  X-/X+    I/K  Z+/Z-")
    table.add_row("Step size", "- / +")
    table.add_row("Back", "Q / Enter")
    if message:
        table.add_row("Status", message)
    return Panel(
        table,
        title=ui.bilingual("Jog OT3", "OT3 点动"),
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 2),
    )


async def run_jog_interface(
    jog: MaintenanceJog,
    *,
    key_reader: Callable[[], str] = read_jog_key,
    render: bool = True,
) -> Point:
    """Run the shared single-key jog interface and return its final position."""
    live = Live(_jog_panel(jog), console=ui.console, refresh_per_second=12, transient=False) if render else None
    if live is not None:
        live.start()
    try:
        while True:
            key = await asyncio.to_thread(key_reader)
            try:
                result = await jog.handle_key(key)
            except ValueError as exc:
                result = JogKeyResult(True, ui.bilingual(str(exc), f"目标超出安全范围: {exc}"))
            if live is not None:
                live.update(_jog_panel(jog, result.message), refresh=True)
            if not result.running:
                return jog.current_point
    finally:
        if live is not None:
            live.stop()


async def jog_ot3(
    robot_ip_address: str,
    *,
    mount: Mount = Mount.LEFT,
    start_point: Point = Point(60.0, 50.0, 400.0),
    simulate: bool = False,
    key_reader: Callable[[], str] = read_jog_key,
    render: bool = True,
) -> Point:
    """Create a maintenance run and expose a safe interactive OT3 jog session."""
    if simulate:
        from leveling_testing.simulation import SimulatedMaintenanceApi

        api = SimulatedMaintenanceApi(robot_ip_address)
    else:
        api = MaintenanceApi(robot_ip_address)
    jog = MaintenanceJog(api, mount, start_point)

    await api.create_run()
    try:
        await api.home()
        await api.move_to(start_point._asdict(), mount=mount)
        return await run_jog_interface(jog, key_reader=key_reader, render=render)
    finally:
        try:
            await api.home()
        except Exception as exc:
            ui.warning(ui.bilingual(f"Jog cleanup home failed: {exc}", f"Jog 清理归零失败: {exc}"))
        if api.run_id is not None:
            try:
                await api.delete_run()
            except Exception as exc:
                ui.warning(ui.bilingual(f"Jog cleanup failed: {exc}", f"Jog 清理失败: {exc}"))
