from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

import requests
import serial

from test_cli.cli import ui

T = TypeVar("T")


HARDWARE_EXCEPTIONS = (
    requests.exceptions.RequestException,
    ConnectionError,
    TimeoutError,
)

SENSOR_EXCEPTIONS = (
    serial.SerialException,
    OSError,
    AssertionError,
    ValueError,
)


def is_hardware_disconnect(exc: BaseException) -> bool:
    return isinstance(exc, HARDWARE_EXCEPTIONS)


async def retry_hardware_action(
    action: str,
    func: Callable[[], Awaitable[T]],
    *,
    retry_interval: float = 3.0,
    simulate: bool = False,
) -> T:
    notified = False
    while True:
        try:
            result = await func()
            if notified:
                ui.hardware_reconnected()
            return result
        except HARDWARE_EXCEPTIONS as exc:
            if simulate:
                raise
            if not notified:
                ui.hardware_disconnected(action, exc)
                notified = True
            await asyncio.sleep(retry_interval)


def retry_locked_file_action(
    path: str,
    func: Callable[[], T],
    *,
    retry_interval: float = 2.0,
) -> T:
    notified = False
    while True:
        try:
            return func()
        except PermissionError as exc:
            if not notified:
                ui.csv_locked(path, exc)
                notified = True
            time.sleep(retry_interval)
