from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from modules.robots import code_flash


@pytest.fixture(autouse=True)
def clear_flash_tasks():
    code_flash._TASKS.clear()
    yield
    code_flash._TASKS.clear()


def _opentrons_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "opentrons"
    directory.mkdir()
    (directory / "Makefile").write_text("push-ot3:\n\t@echo ok\n", encoding="utf-8")
    subprocess.run(["git", "init", "-b", "main"], cwd=directory, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Production Test"], cwd=directory, check=True)
    subprocess.run(["git", "config", "user.email", "production@example.com"], cwd=directory, check=True)
    subprocess.run(["git", "add", "Makefile"], cwd=directory, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=directory, check=True, capture_output=True)
    monkeypatch.setenv(code_flash.OPENTRONS_FLASH_DIR_ENV, str(directory))
    return directory


def test_build_make_command_replaces_and_forces_robot_host() -> None:
    command = code_flash.build_make_command(
        "make -C robot-server push-ot3 host=192.168.6.1 version=test",
        "192.168.6.126",
    )

    assert command == [
        "make",
        "-C",
        "robot-server",
        "push-ot3",
        "version=test",
        "host=192.168.6.126",
    ]


def test_build_make_command_accepts_hardware_testing_directory() -> None:
    command = code_flash.build_make_command(
        "make -C hardware-testing push-ot3 host={robot_ip}",
        "192.168.6.126",
    )

    assert command == [
        "make",
        "-C",
        "hardware-testing",
        "push-ot3",
        "host=192.168.6.126",
    ]


def test_resolve_opentrons_directory_falls_back_to_home_projects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    repository = home / "projects" / "opentrons"
    repository.mkdir(parents=True)
    (repository / "Makefile").write_text("push-ot3:\n\t@echo ok\n", encoding="utf-8")
    monkeypatch.delenv(code_flash.OPENTRONS_FLASH_DIR_ENV, raising=False)
    monkeypatch.setattr(code_flash, "DEFAULT_OPENTRONS_FLASH_DIR", tmp_path / "missing")
    monkeypatch.setattr(code_flash.Path, "home", lambda: home)

    assert code_flash.resolve_opentrons_directory() == repository.resolve()


def test_flash_presets_include_hardware_testing() -> None:
    preset = next(item for item in code_flash.FLASH_PRESETS if item["id"] == "hardware-testing")

    assert preset["command"] == "make -C hardware-testing push-ot3 host={robot_ip}"


def test_flash_environment_does_not_inherit_platform_virtualenv(monkeypatch: pytest.MonkeyPatch) -> None:
    platform_venv = "/opt/production-platform/.venv"
    monkeypatch.setenv("VIRTUAL_ENV", platform_venv)
    monkeypatch.setenv("UV_RUN_RECURSION_DEPTH", "1")
    monkeypatch.setenv("UV_PROJECT", "/opt/production-platform")
    monkeypatch.setenv("PIPENV_ACTIVE", "1")
    monkeypatch.setenv("PATH", f"{platform_venv}/bin:/usr/local/bin:/usr/bin")

    environment = code_flash._flash_environment()

    assert "VIRTUAL_ENV" not in environment
    assert "UV_RUN_RECURSION_DEPTH" not in environment
    assert "UV_PROJECT" not in environment
    assert "PIPENV_ACTIVE" not in environment
    assert f"{platform_venv}/bin" not in environment["PATH"].split(":")
    assert environment["OT_PYTHON"] == "python3"
    assert environment["PIPENV_IGNORE_VIRTUALENVS"] == "1"


@pytest.mark.parametrize(
    "command",
    [
        "sh -c make push-ot3",
        "make push-ot3; reboot",
        "make push-ot3 | tee /tmp/output",
        "make push-ot3 value=$(touch /tmp/injected)",
        "make -f /tmp/Makefile push-ot3",
        "make -C /tmp push-ot3",
        "make -C ../outside push-ot3",
        "make clean",
        "make deploy-py",
        "make push-ot3 SHELL=/tmp/run",
    ],
)
def test_build_make_command_rejects_unsafe_custom_commands(command: str) -> None:
    with pytest.raises(ValueError):
        code_flash.build_make_command(command, "192.168.6.126")


def test_classify_result_uses_exit_code_timeout_and_failure_output() -> None:
    assert code_flash._classify_result(0, "Finished successfully", False) == (True, "烧录成功")
    assert code_flash._classify_result(2, "", False) == (False, "烧录失败，make 退出码 2")
    assert code_flash._classify_result(0, "make: *** [push] Error 1", False)[0] is False
    assert code_flash._classify_result(0, "", True)[0] is False


def test_repository_state_lists_current_branch_and_detects_dirty_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workdir = _opentrons_dir(tmp_path, monkeypatch)

    clean_state = code_flash.get_repository_state(workdir)
    (workdir / "untracked.txt").write_text("changed", encoding="utf-8")
    dirty_state = code_flash.get_repository_state(workdir)

    assert clean_state["current_branch"] == "main"
    assert clean_state["clean"] is True
    assert clean_state["branches"] == [
        {"name": "main", "current": True, "local": True, "remote": False}
    ]
    assert dirty_state["clean"] is False
    assert dirty_state["dirty_files"] == ["?? untracked.txt"]


def test_prepare_repository_checks_clean_switches_then_pulls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workdir = _opentrons_dir(tmp_path, monkeypatch)
    calls: list[list[str]] = []

    def fake_git(arguments, *, cwd, timeout=60):
        assert cwd == workdir
        calls.append(arguments)
        if arguments[:2] == ["status", "--porcelain=v1"]:
            return subprocess.CompletedProcess(["git", *arguments], 0, "", "")
        if arguments[:3] == ["show-ref", "--verify", "--quiet"]:
            return subprocess.CompletedProcess(["git", *arguments], 0, "", "")
        return subprocess.CompletedProcess(["git", *arguments], 0, "Already up to date.\n", "")

    monkeypatch.setattr(code_flash, "_run_git_command", fake_git)
    code_flash._TASKS["task-1"] = {"logs": [], "output_size": 0, "output_truncated": False}

    code_flash._prepare_repository("task-1", workdir, "edge", True)

    assert calls == [
        ["status", "--porcelain=v1", "--untracked-files=all"],
        ["show-ref", "--verify", "--quiet", "refs/heads/edge"],
        ["show-ref", "--verify", "--quiet", "refs/remotes/origin/edge"],
        ["switch", "edge"],
        ["pull", "--ff-only", "origin", "edge"],
        ["status", "--porcelain=v1", "--untracked-files=all"],
    ]


def test_prepare_repository_stops_before_switch_when_worktree_is_dirty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workdir = _opentrons_dir(tmp_path, monkeypatch)
    calls: list[list[str]] = []

    def fake_git(arguments, *, cwd, timeout=60):
        calls.append(arguments)
        return subprocess.CompletedProcess(["git", *arguments], 0, " M Makefile\n?? local.txt\n", "")

    monkeypatch.setattr(code_flash, "_run_git_command", fake_git)
    code_flash._TASKS["task-1"] = {"logs": [], "output_size": 0, "output_truncated": False}

    with pytest.raises(RuntimeError, match="工作区不干净"):
        code_flash._prepare_repository("task-1", workdir, "main", False)

    assert calls == [["status", "--porcelain=v1", "--untracked-files=all"]]


def test_restore_repository_to_edge_switches_to_local_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workdir = _opentrons_dir(tmp_path, monkeypatch)
    calls: list[list[str]] = []

    def fake_git(arguments, *, cwd, timeout=60):
        assert cwd == workdir
        calls.append(arguments)
        return subprocess.CompletedProcess(["git", *arguments], 0, "", "")

    monkeypatch.setattr(code_flash, "_run_git_command", fake_git)
    code_flash._TASKS["task-1"] = {"logs": [], "output_size": 0, "output_truncated": False}

    code_flash._restore_repository_to_edge("task-1", workdir)

    assert calls == [
        ["show-ref", "--verify", "--quiet", "refs/heads/edge"],
        ["show-ref", "--verify", "--quiet", "refs/remotes/origin/edge"],
        ["switch", "edge"],
    ]
    assert "[Git] 已切回分支 edge" in code_flash._TASKS["task-1"]["logs"]


def test_flash_task_stops_before_make_when_repository_prepare_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _opentrons_dir(tmp_path, monkeypatch)

    class ImmediateExecutor:
        def submit(self, function, *args):
            function(*args)

    make_called = False

    def fail_prepare(*_args):
        raise RuntimeError("Git 工作区不干净，共 1 项")

    def fake_execute(*_args, **_kwargs):
        nonlocal make_called
        make_called = True
        return 0, False

    monkeypatch.setattr(code_flash, "_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(code_flash, "_prepare_repository", fail_prepare)
    monkeypatch.setattr(code_flash, "_execute_make_process", fake_execute)

    task = code_flash.create_flash_task(
        "192.168.6.126",
        "make push-ot3",
        branch="main",
    )

    assert task["status"] == "failed"
    assert task["success"] is False
    assert task["exit_code"] is None
    assert "烧录准备失败" in task["message"]
    assert make_called is False


@pytest.mark.parametrize(
    ("exit_code", "timed_out", "expected_status"),
    [(0, False, "success"), (1, False, "failed"), (0, True, "failed")],
)
def test_flash_task_restores_edge_after_make_finishes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exit_code: int,
    timed_out: bool,
    expected_status: str,
) -> None:
    workdir = _opentrons_dir(tmp_path, monkeypatch)

    class ImmediateExecutor:
        def submit(self, function, *args):
            function(*args)

    restored: list[Path] = []

    def fake_prepare(task_id, *_args):
        code_flash._TASKS[task_id]["branch_switched"] = True

    def fake_execute(*_args, **_kwargs):
        return exit_code, timed_out

    def fake_restore(_task_id, cwd):
        restored.append(cwd)

    monkeypatch.setattr(code_flash, "_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(code_flash, "_prepare_repository", fake_prepare)
    monkeypatch.setattr(code_flash, "_execute_make_process", fake_execute)
    monkeypatch.setattr(code_flash, "_restore_repository_to_edge", fake_restore)

    task = code_flash.create_flash_task("192.168.6.126", "make push-ot3", branch="main")

    assert task["status"] == expected_status
    assert restored == [workdir]
    assert "branch_switched" not in task


def test_create_flash_task_streams_logs_and_reports_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workdir = _opentrons_dir(tmp_path, monkeypatch)

    class ImmediateExecutor:
        def submit(self, function, *args):
            function(*args)

    def fake_execute(arguments, *, cwd, timeout, on_line):
        assert arguments == ["make", "push-ot3", "host=192.168.6.126"]
        assert cwd == workdir
        assert timeout == 600
        on_line("Building robot-server\n")
        on_line("Pushing to 192.168.6.126\n")
        return 0, False

    prepared: list[tuple[str, bool]] = []

    def fake_prepare(_task_id, cwd, branch, pull):
        assert cwd == workdir
        prepared.append((branch, pull))

    monkeypatch.setattr(code_flash, "_EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(code_flash, "_execute_make_process", fake_execute)
    monkeypatch.setattr(code_flash, "_prepare_repository", fake_prepare)

    task = code_flash.create_flash_task(
        "192.168.6.126",
        "make push-ot3 host={robot_ip}",
        timeout=600,
        branch="main",
        pull=True,
    )

    assert task["status"] == "success"
    assert task["success"] is True
    assert task["exit_code"] == 0
    assert "Building robot-server" in task["logs"]
    assert task["command"] == "make push-ot3 host=192.168.6.126"
    assert task["branch"] == "main"
    assert task["pull"] is True
    assert prepared == [("main", True)]


def test_create_flash_task_rejects_second_running_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _opentrons_dir(tmp_path, monkeypatch)

    class DeferredExecutor:
        def submit(self, *_args):
            return None

    monkeypatch.setattr(code_flash, "_EXECUTOR", DeferredExecutor())
    code_flash.create_flash_task("192.168.6.126", "make push-ot3", timeout=600)

    with pytest.raises(ValueError, match="正在执行"):
        code_flash.create_flash_task("192.168.6.127", "make push-ot3", timeout=600)
