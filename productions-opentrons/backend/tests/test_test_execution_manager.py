from __future__ import annotations

import pytest

from test_case.execution.manager import TestExecutionManager as ExecutionManager, build_remote_test_command
from test_case.models.domain import (
    TestCase as DomainTestCase,
    TestCaseEdge as DomainTestCaseEdge,
    TestCaseNode as DomainTestCaseNode,
    TestExecutionInputRequest as ExecutionInputRequest,
    TestExecutionRunResponse as ExecutionRunResponse,
)


def test_build_remote_test_command_sets_robot_working_directory() -> None:
    assert (
        build_remote_test_command(
            "python3 -m hardware_testing.scripts.jaw_lifetime",
            "/opt/opentrons-robot-server",
        )
        == "cd /opt/opentrons-robot-server && exec python3 -m hardware_testing.scripts.jaw_lifetime"
    )


def test_build_remote_test_command_quotes_working_directory() -> None:
    assert build_remote_test_command("echo 'hello world'", "/tmp/hardware testing") == (
        "cd '/tmp/hardware testing' && exec echo 'hello world'"
    )


@pytest.mark.parametrize("command, working_directory", [("", "/tmp"), ("echo ok", "")])
def test_build_remote_test_command_rejects_missing_values(command: str, working_directory: str) -> None:
    with pytest.raises(ValueError):
        build_remote_test_command(command, working_directory)


def _make_flow_run() -> tuple[ExecutionManager, ExecutionRunResponse, str, str, str]:
    manager = ExecutionManager()
    start = DomainTestCaseNode(id="start", name="开始", kind="start")
    expect = DomainTestCaseNode(id="expect", name="等待脚本", kind="expect", expect="READY")
    end = DomainTestCaseNode(id="end", name="结束", kind="end")
    case = DomainTestCase(
        name="测试流程",
        product_id="product",
        product_name="产品",
        test_type="功能",
        command="echo READY",
        nodes=[start, expect, end],
        edges=[
            DomainTestCaseEdge(id="edge-start", source=start.id, target=expect.id),
            DomainTestCaseEdge(id="edge-expect", source=expect.id, target=end.id),
        ],
    )
    run = ExecutionRunResponse(
        id="run-test",
        case_id=case.id,
        case_name=case.name,
        command=case.command,
        status="running",
    )
    manager._runs[run.id] = run
    manager._plans[run.id] = manager._build_plan(case)
    return manager, run, start.id, expect.id, end.id


def test_reaching_end_node_waits_for_remote_process_exit() -> None:
    manager, run, start_id, _, end_id = _make_flow_run()
    manager._mark_node_running(run, start_id)

    manager._advance_flow_from_output(run.id, run, "READY")

    assert run.status == "running"
    assert run.current_node_id == end_id
    assert not any(event.type == "completed" for event in run.events)


def test_submitting_input_to_end_node_keeps_run_active(monkeypatch: pytest.MonkeyPatch) -> None:
    manager, run, _, expect_id, end_id = _make_flow_run()
    expect = manager._plans[run.id].node_map[expect_id]
    expect.input_kind = "text"
    run.status = "waiting_input"
    run.current_node_id = expect_id
    run.waiting_node_id = expect_id
    run.waiting_input_kind = "text"
    monkeypatch.setattr(manager, "_write_to_ssh_stdin", lambda *_args: None)

    manager.submit_input(run.id, ExecutionInputRequest(node_id=expect_id, value="ok"))

    assert run.status == "running"
    assert run.current_node_id == end_id
    assert not any(event.type == "completed" for event in run.events)
