#!/usr/bin/env python3
"""Cross-platform Test CLI entry point."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from InquirerPy.base.control import Choice
from test_cli.__version__ import __author__, __description__, __version__
from test_cli.cli.prompts import confirm, select, text
from test_cli.cli import ui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="test-cli",
        description="Production test CLI for OT3/Flex workflows.",
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
        choices=["menu", "z", "ch8", "ch96", "gripper", "all"],
        default="menu",
        help="leveling test to run without opening the interactive menu",
    )
    leveling.add_argument(
        "--script-dir",
        default=".",
        help="base directory for generated testing_data reports",
    )

    return parser


def _entry_prompt(args: argparse.Namespace) -> argparse.Namespace:
    args.entry_header_printed = False
    if args.command is not None:
        return args

    ui.app_header(__version__, __description__)
    args.entry_header_printed = True
    test_name = select(
        "Select test name",
        [
            Choice("leveling", name="Leveling Test"),
            Choice("coming-soon-pipette", name="Pipette Test (coming soon)"),
            Choice("coming-soon-module", name="Module Test (coming soon)"),
        ],
        default="leveling",
    )
    operator_name = text("Operator name", default="").strip()
    if not operator_name:
        raise ValueError("Operator name cannot be empty")
    simulate = confirm("Simulating mode?", default=False)
    if test_name != "leveling":
        raise ValueError("This test entry is not implemented yet.")

    args.command = "leveling"
    args.operator_name = operator_name
    args.robot_ip = None
    args.robot_sn = None
    args.simulate = simulate
    args.test = "menu"
    args.script_dir = "."
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
        from test_cli.leveling_test.__main__ import run as run_leveling

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

    raise ValueError(f"Unknown command: {command}")


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    with ui.graceful_errors(debug=args.debug):
        args = _entry_prompt(args)
        asyncio.run(dispatch(args))


if __name__ == "__main__":
    main()
