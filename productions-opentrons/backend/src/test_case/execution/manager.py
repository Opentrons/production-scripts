from __future__ import annotations

import re
import shlex
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock, Thread
from uuid import uuid4

import paramiko

import settings as setting
from test_case.models.domain import (
    ExecutionStatusResponse,
    TestCase,
    TestCaseNode,
    TestExecutionCompleteRequest,
    TestExecutionEvent,
    TestExecutionInputRequest,
    TestExecutionRunResponse,
    TestExecutionStartRequest,
    TestExecutionWaitingInputRequest,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TestExecutionLimitError(RuntimeError):
    pass


class TestExecutionNotFoundError(KeyError):
    pass


class TestExecutionStateError(RuntimeError):
    pass


class TestExecutionSshError(RuntimeError):
    pass


def build_remote_test_command(command: str, working_directory: str) -> str:
    """Run a test command from the robot's hardware-testing project root."""
    normalized_command = (command or "").strip()
    if not normalized_command:
        raise ValueError("测试命令不能为空")
    normalized_directory = (working_directory or "").strip()
    if not normalized_directory:
        raise ValueError("测试工作目录不能为空")
    return f"cd {shlex.quote(normalized_directory)} && exec {normalized_command}"


@dataclass
class TestFlowPlan:
    nodes: list[TestCaseNode]
    node_map: dict[str, TestCaseNode]
    next_node_by_source: dict[str, str]


@dataclass
class SshRuntimeSession:
    client: paramiko.SSHClient
    channel: paramiko.Channel
    stop_event: threading.Event
    worker: Thread


class TestExecutionManager:
    MAX_ACTIVE_SESSIONS = 20
    MAX_COMPLETED_RUNS = 200
    COMPLETED_RUN_RETENTION_HOURS = 24
    MAX_EVENTS_PER_RUN = 1000
    MAX_SSH_OUTPUT_EVENT_CHARS = 12000
    SSH_CONNECT_TIMEOUT = 30
    SSH_READ_SLEEP_SECONDS = 0.05

    def __init__(self) -> None:
        self.observer_clients = 0
        self.queued_tests = 0
        self._runs: dict[str, TestExecutionRunResponse] = {}
        self._plans: dict[str, TestFlowPlan] = {}
        self._sessions: dict[str, SshRuntimeSession] = {}
        self._lock = RLock()

    def get_status(self) -> ExecutionStatusResponse:
        with self._lock:
            self._prune_completed_runs_locked()
            active_ssh_sessions = sum(1 for run in self._runs.values() if run.status in {"running", "waiting_input"})
            waiting_input_tests = sum(1 for run in self._runs.values() if run.status == "waiting_input")
            running_tests = sum(1 for run in self._runs.values() if run.status == "running")
            available_sessions = max(0, self.MAX_ACTIVE_SESSIONS - active_ssh_sessions)

        return ExecutionStatusResponse(
            max_sessions=self.MAX_ACTIVE_SESSIONS,
            active_ssh_sessions=active_ssh_sessions,
            observer_clients=self.observer_clients,
            running_tests=running_tests,
            waiting_input_tests=waiting_input_tests,
            queued_tests=self.queued_tests,
            available_sessions=available_sessions,
        )

    def start_run(self, payload: TestExecutionStartRequest, test_case: TestCase) -> TestExecutionRunResponse:
        if not payload.device_ip:
            raise TestExecutionSshError("请选择执行设备")

        plan = self._build_plan(test_case)
        with self._lock:
            if self.get_status().available_sessions <= 0:
                raise TestExecutionLimitError("活跃 SSH 测试连接已达到上限")

            run = TestExecutionRunResponse(
                id=f"run_{uuid4().hex[:12]}",
                case_id=payload.case_id,
                case_name=test_case.name,
                command=test_case.command,
                device_ip=payload.device_ip,
                status="running",
                events=[
                    TestExecutionEvent(type="started", message=f"执行命令: {test_case.command}"),
                    TestExecutionEvent(type="ssh_connecting", message=f"连接设备: {payload.device_ip}"),
                ],
            )
            self._runs[run.id] = run
            self._plans[run.id] = plan
            self._prune_completed_runs_locked()

        worker = Thread(
            target=self._run_ssh_worker,
            args=(run.id, payload.device_ip, test_case.command, test_case.timeout_seconds),
            name=f"test-execution-{run.id}",
            daemon=True,
        )
        worker.start()
        return self.get_run(run.id)

    def set_current_node(self, run_id: str, node_id: str) -> TestExecutionRunResponse:
        with self._lock:
            run = self._get_run(run_id)
            self._mark_node_running(run, node_id)
            return run

    def wait_for_input(self, run_id: str, payload: TestExecutionWaitingInputRequest) -> TestExecutionRunResponse:
        with self._lock:
            run = self._get_run(run_id)
            run.status = "waiting_input"
            run.current_node_id = payload.node_id
            run.waiting_node_id = payload.node_id
            run.waiting_input_kind = payload.input_kind
            run.waiting_options = payload.input_options
            run.updated_at = utc_now()
            run.events.append(
                TestExecutionEvent(
                    type="waiting_input",
                    node_id=payload.node_id,
                    message=payload.expect,
                )
            )
            return run

    def submit_input(self, run_id: str, payload: TestExecutionInputRequest) -> TestExecutionRunResponse:
        with self._lock:
            run = self._get_run(run_id)
            if run.status != "waiting_input" or run.waiting_node_id != payload.node_id:
                raise TestExecutionStateError("当前运行不在该节点的等待输入状态")

            self._write_to_ssh_stdin(run_id, run, payload.value)
            run.events.append(
                TestExecutionEvent(
                    type="input_submitted",
                    node_id=payload.node_id,
                    value=payload.value,
                    message="用户输入已发送",
                )
            )
            next_node = self._next_node(self._plans[run_id], payload.node_id)
            if next_node is None:
                run.status = "running"
                run.current_node_id = payload.node_id
                run.waiting_node_id = None
                run.waiting_input_kind = None
                run.waiting_options = []
                run.updated_at = utc_now()
            else:
                self._mark_node_running(run, next_node.id)
                if next_node.kind == "end":
                    self._complete_run_locked(run_id, run, "passed", "流程执行完成")
            return run

    def complete_run(self, run_id: str, payload: TestExecutionCompleteRequest) -> TestExecutionRunResponse:
        with self._lock:
            run = self._get_run(run_id)
            self._complete_run_locked(run_id, run, payload.status, payload.message or payload.status)
            return run

    def stop_run(self, run_id: str) -> TestExecutionRunResponse:
        with self._lock:
            run = self._get_run(run_id)
            if run.status not in {"running", "waiting_input"}:
                return run

            session = self._sessions.get(run_id)
            if session is not None:
                try:
                    session.channel.send("\x03")
                except Exception:
                    pass

            run.events.append(TestExecutionEvent(type="ssh_session_stopped", message="SSH session 已停止"))
            self._complete_run_locked(run_id, run, "stopped", "用户停止测试")
            return run

    def get_run(self, run_id: str) -> TestExecutionRunResponse:
        with self._lock:
            return self._get_run(run_id)

    def _run_ssh_worker(self, run_id: str, device_ip: str, command: str, timeout_seconds: int) -> None:
        client: paramiko.SSHClient | None = None
        channel: paramiko.Channel | None = None
        stop_event = threading.Event()
        started_at = time.monotonic()

        try:
            client = self._connect_ssh(device_ip)
            transport = client.get_transport()
            if transport is None:
                raise TestExecutionSshError("SSH transport 未建立")

            channel = transport.open_session(timeout=self.SSH_CONNECT_TIMEOUT)
            channel.get_pty()
            remote_command = build_remote_test_command(
                command,
                setting.ROBOT_TEST_WORKING_DIRECTORY,
            )
            channel.exec_command(remote_command)

            session = SshRuntimeSession(
                client=client,
                channel=channel,
                stop_event=stop_event,
                worker=threading.current_thread(),
            )
            with self._lock:
                self._sessions[run_id] = session
                run = self._get_run(run_id)
                run.events.append(TestExecutionEvent(type="ssh_connected", message=f"SSH 已连接: {device_ip}"))
                run.events.append(TestExecutionEvent(type="command_started", message=command))
                self._mark_node_running(run, self._plans[run_id].nodes[0].id)
                output_buffer = self._advance_flow_from_output(run_id, run, "")

            while not stop_event.is_set():
                if timeout_seconds > 0 and time.monotonic() - started_at > timeout_seconds:
                    self._fail_run(run_id, "timeout", f"执行超时: {timeout_seconds}s")
                    break

                output_buffer = self._read_available_output(run_id, channel, output_buffer)

                with self._lock:
                    run = self._get_run(run_id)
                    if run.status not in {"running", "waiting_input"}:
                        break

                if channel.exit_status_ready():
                    output_buffer = self._read_available_output(run_id, channel, output_buffer)
                    exit_code = channel.recv_exit_status()
                    with self._lock:
                        run = self._get_run(run_id)
                        if run.status in {"running", "waiting_input"}:
                            plan = self._plans[run_id]
                            current = plan.node_map.get(run.current_node_id or "")
                            if current is not None and current.kind == "end":
                                status = "passed" if exit_code == 0 else "failed"
                                self._complete_run_locked(run_id, run, status, f"流程执行完成，退出码: {exit_code}")
                            else:
                                self._complete_run_locked(run_id, run, "failed", f"命令退出但流程未完成，退出码: {exit_code}")
                    break

                time.sleep(self.SSH_READ_SLEEP_SECONDS)
        except Exception as exc:
            self._fail_run(run_id, "error", str(exc) or exc.__class__.__name__)
        finally:
            self._close_session(run_id, close_client=False)
            try:
                if channel is not None:
                    channel.close()
            except Exception:
                pass
            try:
                if client is not None:
                    client.close()
            except Exception:
                pass

    def _connect_ssh(self, ip: str) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                ip,
                username="root",
                key_filename=setting.ROBOT_KEY_PATH,
                timeout=self.SSH_CONNECT_TIMEOUT,
                banner_timeout=self.SSH_CONNECT_TIMEOUT,
                auth_timeout=self.SSH_CONNECT_TIMEOUT,
            )
            return client
        except Exception as key_exc:
            try:
                client.connect(
                    ip,
                    username="root",
                    password="",
                    timeout=self.SSH_CONNECT_TIMEOUT,
                    banner_timeout=self.SSH_CONNECT_TIMEOUT,
                    auth_timeout=self.SSH_CONNECT_TIMEOUT,
                )
                return client
            except (paramiko.SSHException, socket.error, OSError) as exc:
                client.close()
                raise TestExecutionSshError(f"SSH 连接失败: {exc or key_exc}") from exc

    def _read_available_output(
        self,
        run_id: str,
        channel: paramiko.Channel,
        output_buffer: str,
    ) -> str:
        chunks: list[bytes] = []
        while channel.recv_ready():
            chunks.append(channel.recv(4096))
        while channel.recv_stderr_ready():
            chunks.append(channel.recv_stderr(4096))

        if not chunks:
            return output_buffer

        text = b"".join(chunks).decode("utf-8", errors="replace")
        if len(text) > self.MAX_SSH_OUTPUT_EVENT_CHARS:
            text = text[-self.MAX_SSH_OUTPUT_EVENT_CHARS:]
        with self._lock:
            run = self._get_run(run_id)
            run.events.append(TestExecutionEvent(type="ssh_output", message=text))
            self._trim_run_events(run)
            run.updated_at = utc_now()
            if run.status == "running":
                output_buffer = self._advance_flow_from_output(run_id, run, output_buffer + text)
        return output_buffer

    def _advance_flow_from_output(self, run_id: str, run: TestExecutionRunResponse, output_buffer: str) -> str:
        plan = self._plans[run_id]
        current = plan.node_map.get(run.current_node_id or "")
        if current is None:
            current = plan.nodes[0]
            self._mark_node_running(run, current.id)

        while run.status == "running":
            if current.kind == "start":
                next_node = self._next_node(plan, current.id)
                if next_node is None:
                    self._complete_run_locked(run_id, run, "failed", "开始节点没有后续节点")
                    break
                current = next_node
                self._mark_node_running(run, current.id)
                continue

            if current.kind == "end":
                self._complete_run_locked(run_id, run, "passed", "流程执行完成")
                break

            if current.kind != "expect":
                break

            expect = current.expect or ""
            match_end = self._expect_match_end(output_buffer, expect)
            if match_end is None:
                break
            output_buffer = output_buffer[match_end:]

            run.events.append(
                TestExecutionEvent(
                    type="expect_matched",
                    node_id=current.id,
                    message=expect or current.name,
                )
            )
            if current.input_kind != "none":
                run.status = "waiting_input"
                run.waiting_node_id = current.id
                run.waiting_input_kind = current.input_kind
                run.waiting_options = current.input_options
                run.updated_at = utc_now()
                run.events.append(
                    TestExecutionEvent(
                        type="waiting_input",
                        node_id=current.id,
                        message=expect or current.name,
                    )
                )
                break

            next_node = self._next_node(plan, current.id)
            if next_node is None:
                self._complete_run_locked(run_id, run, "failed", f"节点没有后续节点: {current.name}")
                break
            current = next_node
            self._mark_node_running(run, current.id)
            if current.kind == "end":
                self._complete_run_locked(run_id, run, "passed", "流程执行完成")
                break

        return output_buffer[-12000:]

    def _build_plan(self, test_case: TestCase) -> TestFlowPlan:
        nodes = test_case.nodes
        node_map = {node.id: node for node in nodes}
        start = next((node for node in nodes if node.kind == "start"), None)
        if start is None:
            raise TestExecutionSshError("测试用例缺少开始节点")

        next_node_by_source = {}
        for edge in test_case.edges:
            if edge.source not in next_node_by_source:
                next_node_by_source[edge.source] = edge.target

        ordered: list[TestCaseNode] = []
        visited: set[str] = set()
        current: TestCaseNode | None = start
        while current is not None and current.id not in visited:
            ordered.append(current)
            visited.add(current.id)
            next_id = next_node_by_source.get(current.id)
            current = node_map.get(next_id or "")

        if not ordered:
            ordered = [start]
        return TestFlowPlan(nodes=ordered, node_map=node_map, next_node_by_source=next_node_by_source)

    def _next_node(self, plan: TestFlowPlan, node_id: str) -> TestCaseNode | None:
        return plan.node_map.get(plan.next_node_by_source.get(node_id, ""))

    def _expect_match_end(self, output: str, expect: str) -> int | None:
        if not expect:
            return 0
        if expect.startswith("regex:"):
            pattern = expect.removeprefix("regex:")
            try:
                match = re.search(pattern, output, flags=re.MULTILINE)
                return match.end() if match else None
            except re.error:
                expect = pattern

        index = output.find(expect)
        if index < 0:
            return None
        return index + len(expect)

    def _mark_node_running(self, run: TestExecutionRunResponse, node_id: str) -> None:
        run.status = "running"
        run.current_node_id = node_id
        run.waiting_node_id = None
        run.waiting_input_kind = None
        run.waiting_options = []
        run.updated_at = utc_now()
        run.events.append(TestExecutionEvent(type="node_running", node_id=node_id))

    def _complete_run_locked(
        self,
        run_id: str,
        run: TestExecutionRunResponse,
        status: str,
        message: str,
    ) -> None:
        run.status = status  # type: ignore[assignment]
        run.waiting_node_id = None
        run.waiting_input_kind = None
        run.waiting_options = []
        run.updated_at = utc_now()
        event_type = "completed" if status == "passed" else status
        run.events.append(TestExecutionEvent(type=event_type, message=message))
        self._trim_run_events(run)
        self._close_session(run_id)
        self._prune_completed_runs_locked()

    def _fail_run(self, run_id: str, status: str, message: str) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None or run.status not in {"running", "waiting_input"}:
                return
            run.events.append(TestExecutionEvent(type="execution_error", message=message))
            self._complete_run_locked(run_id, run, status, message)

    def _write_to_ssh_stdin(self, run_id: str, run: TestExecutionRunResponse, value: str) -> None:
        session = self._sessions.get(run_id)
        if session is None:
            raise TestExecutionStateError("SSH session 尚未建立或已经结束")

        try:
            payload = value if value.endswith("\n") else f"{value}\n"
            session.channel.sendall(payload)
        except Exception as exc:
            raise TestExecutionStateError(f"SSH 输入发送失败: {exc}") from exc

        run.events.append(
            TestExecutionEvent(
                type="ssh_stdin_sent",
                node_id=run.current_node_id,
                value=value,
                message="输入已写入 SSH",
            )
        )

    def _close_session(self, run_id: str, *, close_client: bool = True) -> None:
        session = self._sessions.pop(run_id, None)
        if session is None:
            return

        session.stop_event.set()
        try:
            session.channel.close()
        except Exception:
            pass
        if close_client:
            try:
                session.client.close()
            except Exception:
                pass

    def _trim_run_events(self, run: TestExecutionRunResponse) -> None:
        if len(run.events) > self.MAX_EVENTS_PER_RUN:
            run.events = run.events[-self.MAX_EVENTS_PER_RUN:]

    def _prune_completed_runs_locked(self) -> None:
        completed_statuses = {"passed", "failed", "error", "timeout", "stopped"}
        cutoff = utc_now() - timedelta(hours=self.COMPLETED_RUN_RETENTION_HOURS)
        completed_runs = [
            run
            for run in self._runs.values()
            if run.status in completed_statuses
        ]
        remove_ids = {
            run.id
            for run in completed_runs
            if run.updated_at < cutoff
        }
        remaining_completed = [
            run for run in completed_runs
            if run.id not in remove_ids
        ]
        if len(remaining_completed) > self.MAX_COMPLETED_RUNS:
            remaining_completed.sort(key=lambda run: run.updated_at, reverse=True)
            remove_ids.update(run.id for run in remaining_completed[self.MAX_COMPLETED_RUNS:])
        for run_id in remove_ids:
            self._runs.pop(run_id, None)
            self._plans.pop(run_id, None)
            self._close_session(run_id)

    def _get_run(self, run_id: str) -> TestExecutionRunResponse:
        run = self._runs.get(run_id)
        if run is None:
            raise TestExecutionNotFoundError(run_id)
        return run


test_execution_manager = TestExecutionManager()
