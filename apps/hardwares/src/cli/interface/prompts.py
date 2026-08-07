from __future__ import annotations

from typing import Any

from InquirerPy import inquirer
from InquirerPy.utils import get_style


STYLE = get_style({
    "questionmark": "#00afff bold",
    "question": "bold",
    "answer": "#00d787 bold",
    "pointer": "#ffaf00 bold",
    "highlighted": "#ffaf00 bold",
    "selected": "#00d787",
    "separator": "#6c6c6c",
    "instruction": "#6c6c6c",
})


def text(message: str, default: str = "") -> str:
    return inquirer.text(message=message, default=default, style=STYLE).execute()


def select(message: str, choices: list[Any], default: Any | None = None) -> Any:
    return inquirer.select(message=message, choices=choices, default=default, style=STYLE).execute()


def confirm(message: str, default: bool = False) -> bool:
    return inquirer.confirm(message=message, default=default, style=STYLE).execute()
