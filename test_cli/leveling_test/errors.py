from __future__ import annotations

from dataclasses import dataclass

from test_cli.leveling_test.type import Mount


@dataclass
class LevelingError(Exception):
    title_cn: str
    title_en: str
    message_cn: str
    message_en: str
    details: str | None = None

    def __str__(self) -> str:
        return f"{self.message_en} ({self.message_cn})"


class FixtureNotFoundError(LevelingError):
    def __init__(self, mount: Mount | None = None, details: str | None = None):
        if mount is None:
            message_cn = "未找到测试工装，请检查激光传感器连接。"
            message_en = "Fixture not found. Please check the laser sensor connection."
        else:
            message_cn = f"未找到 {mount.value} mount 工装，请检查测试工装连接。"
            message_en = f"{mount.value} mount fixture not found. Please check the fixture connection."
        super().__init__("工装未找到", "FIXTURE NOT FOUND", message_cn, message_en, details)


class SensorReadError(LevelingError):
    def __init__(self, details: str | None = None, *, recoverable: bool = True):
        super().__init__(
            "读取异常",
            "SENSOR READ ERROR",
            "读取激光传感器失败，请检查工装、串口和线缆连接。",
            "Failed to read the laser sensor. Please check the fixture, serial port, and cable.",
            details,
        )
        self.recoverable = recoverable


class CsvWriteError(LevelingError):
    def __init__(self, path: str, details: str | None = None):
        super().__init__(
            "CSV 写入失败",
            "CSV WRITE ERROR",
            "写入报告失败，请检查文件权限或磁盘状态。",
            "Failed to write the report. Please check file permissions or disk status.",
            f"{path}\n{details}" if details else path,
        )


class HardwareDisconnectedError(LevelingError):
    def __init__(self, action: str, details: str | None = None):
        super().__init__(
            "硬件连接中断",
            "HARDWARE DISCONNECTED",
            f"设备连接中断，正在等待重新连接后继续: {action}",
            f"Hardware connection was interrupted. Waiting to reconnect before continuing: {action}",
            details,
        )
