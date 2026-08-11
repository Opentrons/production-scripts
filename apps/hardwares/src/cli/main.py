#!/usr/bin/env python3
"""Cross-platform production hardware entry point."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from InquirerPy.base.control import Choice
from cli.__version__ import __author__, __description__, __version__
from cli.interface.prompts import confirm, select, text
from cli.interface import ui


ENTRY_TEST_CHOICES = (
    ("leveling", "Leveling Test"),
    ("jog", "Jog OT3"),
    ("coming-soon-pipette", "Pipette Test (coming soon)"),
    ("coming-soon-module", "Module Test (coming soon)"),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="productions-hardwares",
        description="Production hardware tests for OT3/Flex workflows.",
    )
    parser.add_argument("--debug", action="store_true", help="show full tracebacks on failure")

    subparsers = parser.add_subparsers(dest="command")
    leveling = subparsers.add_parser("leveling", help="run leveling tests")
    leveling.add_argument("--operator-name", default=None, help="operator name for report metadata")
    leveling.add_argument("--robot-ip", default=None, help="robot IP address")
    leveling.add_argument("--robot-sn", default=None, help="robot serial number")
    leveling.add_argument("--simulate", action="store_true", help="run without robot or sensor hardware")
    leveling.add_argument(
        "--test",
        choices=["menu", "z", "ch8", "ch96", "gantry", "gripper", "all"],
        default="menu",
        help="leveling test to run without opening the interactive menu",
    )
    leveling.add_argument(
        "--script-dir",
        default=".",
        help="base directory for generated testing_data reports",
    )

    jog = subparsers.add_parser("jog", help="jog an OT3/Flex robot")
    jog.add_argument("--robot-ip", default=None, help="robot IP address")
    jog.add_argument("--mount", choices=["left", "right"], default=None, help="gantry mount to move")
    jog.add_argument("--simulate", action="store_true", help="run without robot hardware")

    return parser


def _entry_prompt(args: argparse.Namespace) -> argparse.Namespace:
    args.entry_header_printed = False
    if args.command is not None:
        return args

    ui.app_header(__version__, __description__)
    args.entry_header_printed = True
    test_name = select(
        "Select test name",
        [Choice(value, name=name) for value, name in ENTRY_TEST_CHOICES],
        default="leveling",
    )
    simulate = confirm("Simulating mode?", default=False)
    if test_name not in {"leveling", "jog"}:
        raise ValueError("This test entry is not implemented yet.")

    args.command = test_name
    args.robot_ip = None
    args.simulate = simulate
    if test_name == "leveling":
        operator_name = text("Operator name", default="").strip()
        if not operator_name:
            raise ValueError("Operator name cannot be empty")
        args.operator_name = operator_name
        args.robot_sn = None
        args.test = "menu"
        args.script_dir = "."
    else:
        args.operator_name = ""
        args.mount = None
    return args


async def dispatch(args: argparse.Namespace) -> None:
    command = args.command

    if not getattr(args, "entry_header_printed", False):
        ui.app_header(__version__, __description__)
    ui.run_summary(
        [
            ("Command", command),
            ("Author", __author__),
            ("Operator", getattr(args, "operator_name", "") or "-"),
            ("Mode", "SIMULATION" if getattr(args, "simulate", False) else "HARDWARE"),
        ]
    )

    if command == "leveling":
        from leveling_testing.__main__ import run as run_leveling

        await run_leveling(
            script_dir=str(Path(args.script_dir)),
            robot_ip=getattr(args, "robot_ip", None),
            robot_sn=getattr(args, "robot_sn", None),
            operator_name=getattr(args, "operator_name", None),
            simulate=getattr(args, "simulate", False),
            selected_test=getattr(args, "test", "menu"),
            debug=getattr(args, "debug", False),
        )
        return

    if command == "jog":
        from leveling_testing.type import Mount
        from opentonrs_api.maintenance_api.jog import jog_ot3

        simulate = getattr(args, "simulate", False)
        robot_ip = getattr(args, "robot_ip", None)
        if robot_ip is None:
            default_ip = "simulator" if simulate else "192.168.6.1"
            robot_ip = (
                await asyncio.to_thread(text, "Robot IP address", default_ip)
            ).strip()
        if not robot_ip:
            raise ValueError("Robot IP address cannot be empty")

        mount_value = getattr(args, "mount", None)
        if mount_value is None:
            mount_value = await asyncio.to_thread(
                select,
                ui.bilingual("Select mount", "选择 Mount"),
                [Mount.LEFT.value, Mount.RIGHT.value],
                Mount.LEFT.value,
            )
        ui.test_banner("Jog OT3", simulate=simulate)
        await jog_ot3(
            robot_ip,
            mount=Mount(mount_value),
            simulate=simulate,
        )
        return

    raise ValueError(f"Unknown command: {command}")


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        with ui.graceful_errors(debug=args.debug):
            args = _entry_prompt(args)
            asyncio.run(dispatch(args))
    except SystemExit:
        pass
    finally:
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
