from __future__ import annotations

import traceback
from contextlib import contextmanager
from typing import Iterator

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()


def bilingual(en: str, cn: str) -> str:
    return f"{en} ({cn})"


def _mount_label_en(mount: str) -> str:
    labels = {
        "left": "left mount",
        "right": "right mount",
    }
    return labels.get(mount, mount)


def _mount_label_cn(mount: str) -> str:
    labels = {
        "left": "左 mount",
        "right": "右 mount",
    }
    return labels.get(mount, mount)


def app_header(version: str, description: str) -> None:
    title = Text("TEST CLI", style="bold cyan")
    subtitle = Text(f"v{version}  {description}", style="dim")
    console.print()
    console.print(Panel.fit(Text.assemble(title, "\n", subtitle), box=box.DOUBLE, padding=(1, 4)))


def section(title: str, subtitle: str | None = None) -> None:
    text = Text(title.upper(), style="bold magenta")
    if subtitle:
        text.append(f"\n{subtitle}", style="dim")
    console.print()
    console.print(Panel.fit(text, box=box.HEAVY, padding=(1, 4)))


def test_banner(name: str, simulate: bool = False) -> None:
    label = "SIMULATION" if simulate else "HARDWARE"
    color = "yellow" if simulate else "green"
    console.print()
    console.print(Rule(style=color))
    console.print(Panel.fit(Text(name.upper(), style=f"bold {color}"), title=label, box=box.DOUBLE, padding=(1, 6)))
    console.print(Rule(style=color))


def info(message: str) -> None:
    console.print(f"[cyan]INFO[/cyan] {message}")


def success(message: str) -> None:
    console.print(f"[green]OK[/green] {message}")


def warning(message: str) -> None:
    console.print(f"[yellow]WARN[/yellow] {message}")


def bilingual_error(
    title_cn: str,
    title_en: str,
    message_cn: str,
    message_en: str,
    details: str | None = None,
) -> None:
    text = Text()
    text.append(message_en, style="bold red")
    text.append(f" ({message_cn})", style="red")
    if details:
        text.append(f"\n\n{details}", style="dim red")
    console.print()
    console.print(
        Panel(
            text,
            title=bilingual(title_en, title_cn),
            title_align="left",
            style="red",
            box=box.ROUNDED,
        )
    )


def fixture_search(mounts: list[str]) -> None:
    mount_text_en = ", ".join(_mount_label_en(mount) for mount in mounts)
    mount_text_cn = "、".join(_mount_label_cn(mount) for mount in mounts)
    info(bilingual(f"Searching fixture: {mount_text_en}", f"正在寻找工装：{mount_text_cn}"))


def fixture_found(mount: str) -> None:
    success(bilingual(f"Found {_mount_label_en(mount)} fixture", f"找到{_mount_label_cn(mount)}工装"))


def hardware_disconnected(action: str, exc: BaseException) -> None:
    bilingual_error(
        "硬件连接中断",
        "HARDWARE DISCONNECTED",
        f"设备连接中断，正在等待重新连接后继续: {action}",
        f"Hardware connection was interrupted. Waiting to reconnect before continuing: {action}",
        f"{type(exc).__name__}: {exc}",
    )


def hardware_reconnected() -> None:
    success(bilingual("Device reconnected, continuing test", "设备已重新连接，继续测试"))


def csv_locked(path: str, exc: BaseException) -> None:
    bilingual_error(
        "CSV 写入等待",
        "CSV WRITE WAITING",
        "报告文件可能正在被 Excel 或其他程序占用，请关闭后保持 CLI 打开。",
        "The report file may be open in Excel or another program. Close it and keep the CLI open.",
        f"{path}\n{type(exc).__name__}: {exc}",
    )


def spec_exceeded(
    difference: float,
    spec: float,
    attempt: int,
    max_attempts: int,
    slot: str | None = None,
) -> None:
    retry_text_en = (
        f"Auto retry {attempt + 1}/{max_attempts} will start."
        if attempt < max_attempts
        else "Maximum retry count reached. FAIL will be recorded."
    )
    retry_text_cn = (
        f"将自动重测第 {attempt + 1}/{max_attempts} 次。"
        if attempt < max_attempts
        else "已达到最大重测次数，将记录 FAIL。"
    )
    where = f"Slot: {slot}\n" if slot else ""
    bilingual_error(
        "超出规格",
        "OUT OF SPEC",
        f"测试结果超出规格，Difference={difference}, Spec={spec}。{retry_text_cn}",
        f"Result is out of spec. Difference={difference}, Spec={spec}. {retry_text_en}",
        where.strip() or None,
    )


def calibration(default_distance: float, step: float) -> None:
    console.print()
    console.print(Rule("Calibration", style="blue"))
    run_summary(
        [
            ("DefaultDistance", str(round(default_distance, 3))),
            ("Step", str(round(step, 3))),
        ]
    )


def error(message: str) -> None:
    console.print(Panel(str(message), title="ERROR", style="red", box=box.ROUNDED))


def exception_report(exc: BaseException, *, debug: bool = False) -> None:
    if all(hasattr(exc, attr) for attr in ("title_cn", "title_en", "message_cn", "message_en")):
        bilingual_error(
            getattr(exc, "title_cn"),
            getattr(exc, "title_en"),
            getattr(exc, "message_cn"),
            getattr(exc, "message_en"),
            getattr(exc, "details", None),
        )
        if debug:
            console.print(traceback.format_exc(), style="red")
        return
    bilingual_error(
        "发生异常",
        "EXCEPTION",
        f"{type(exc).__name__}: {exc}",
        f"{type(exc).__name__}: {exc}",
    )
    if debug:
        console.print(traceback.format_exc(), style="red")


def run_summary(rows: list[tuple[str, str]]) -> None:
    table = Table(box=box.SIMPLE_HEAVY)
    table.add_column("Item", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    for key, value in rows:
        table.add_row(key, value)
    console.print(table)


@contextmanager
def graceful_errors(debug: bool = False) -> Iterator[None]:
    try:
        yield
    except KeyboardInterrupt:
        warning("User cancelled the run.")
        raise SystemExit(130)
    except Exception as exc:
        exception_report(exc, debug=debug)
        raise SystemExit(1)
