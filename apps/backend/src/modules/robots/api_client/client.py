from __future__ import annotations

from typing import Any

import requests

from modules.robots.api_client.spec import (
    DEFAULT_OPENTRONS_VERSION,
    DEFAULT_PORT,
    PATH_COMMANDS,
    PATH_DATA_FILES,
    PATH_HEALTH,
    PATH_INSTRUMENTS,
    PATH_MAINTENANCE_RUNS,
    PATH_MODULES,
    PATH_PIPETTES,
    PATH_PROTOCOLS,
    PATH_ROBOT_HOME,
    PATH_ROBOT_MOVE,
    PATH_ROBOT_POSITIONS,
    PATH_RUNS,
    PATH_SETTINGS_RESET,
    PATH_SETTINGS_RESET_OPTIONS,
    PATH_SETTINGS_ROBOT,
    PATH_UPDATE_SERVER_HEALTH,
)


class OpentronsApiError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, response: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class OpentronsHttpClient:
    """HTTP client for Opentrons robot server (OpenAPI port 31950)."""

    def __init__(
        self,
        ip: str,
        port: int = DEFAULT_PORT,
        *,
        opentrons_version: str = DEFAULT_OPENTRONS_VERSION,
        timeout: int = 10,
    ):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{ip}:{port}"
        self.headers = {
            "Content-Type": "application/json",
            "Opentrons-Version": opentrons_version,
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> Any:
        normalized_path = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}{normalized_path}"
        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=self.headers,
                json=json_body,
                timeout=timeout or self.timeout,
            )
        except requests.RequestException as exc:
            raise OpentronsApiError(str(exc)) from exc

        payload: Any
        try:
            payload = response.json()
        except ValueError:
            payload = response.text

        if response.status_code >= 400:
            message = payload if isinstance(payload, str) else payload
            raise OpentronsApiError(
                f"HTTP {response.status_code}: {message}",
                status_code=response.status_code,
                response=payload,
            )
        return payload

    def request_raw(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
        timeout: int | None = None,
    ) -> requests.Response:
        normalized_path = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}{normalized_path}"
        headers = {"Opentrons-Version": self.headers["Opentrons-Version"]}
        if files:
            headers.pop("Content-Type", None)
        else:
            headers["Content-Type"] = "application/json"
        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=json_body if not files else None,
                data=data,
                files=files,
                timeout=timeout or self.timeout,
            )
        except requests.RequestException as exc:
            raise OpentronsApiError(str(exc)) from exc
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            message = payload if isinstance(payload, str) else payload
            raise OpentronsApiError(
                f"HTTP {response.status_code}: {message}",
                status_code=response.status_code,
                response=payload,
            )
        return response

    @staticmethod
    def unwrap_data(payload: Any) -> Any:
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    def get_health(self) -> dict[str, Any]:
        return self.request("GET", PATH_HEALTH)

    def get_update_server_health(self) -> dict[str, Any]:
        return self.request("GET", PATH_UPDATE_SERVER_HEALTH)

    def get_instruments(self) -> dict[str, Any]:
        return self.request("GET", PATH_INSTRUMENTS)

    def get_pipettes(self) -> dict[str, Any]:
        return self.request("GET", PATH_PIPETTES)

    def get_modules(self) -> dict[str, Any]:
        return self.request("GET", PATH_MODULES)

    def get_robot_positions(self) -> dict[str, Any]:
        return self.request("GET", PATH_ROBOT_POSITIONS)

    def get_robot_settings(self) -> dict[str, Any]:
        return self.request("GET", PATH_SETTINGS_ROBOT)

    def get_reset_options(self) -> dict[str, Any]:
        return self.request("GET", PATH_SETTINGS_RESET_OPTIONS)

    def home_robot(self, *, target: str = "robot", mount: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"target": target}
        if mount:
            body["mount"] = mount
        return self.request("POST", PATH_ROBOT_HOME, json_body=body)

    def home_axes(self, *, axes: list[str]) -> dict[str, Any]:
        normalized_axes = list(dict.fromkeys(axis.strip() for axis in axes if axis.strip()))
        if not normalized_axes:
            raise ValueError("At least one motor axis is required")
        payload = self.request(
            "POST",
            f"{PATH_COMMANDS}?waitUntilComplete=true&timeout=120000",
            json_body={
                "data": {
                    "commandType": "home",
                    "params": {"axes": normalized_axes},
                }
            },
            timeout=130,
        )
        command = self.unwrap_data(payload)
        if isinstance(command, dict) and command.get("status") == "failed":
            error = command.get("error") or "Motor axis home failed"
            if isinstance(error, dict):
                error = error.get("detail") or error.get("message") or str(error)
            raise OpentronsApiError(str(error), response=payload)
        return payload

    def create_maintenance_run(self) -> str:
        payload = self.request(
            "POST",
            PATH_MAINTENANCE_RUNS,
            json_body={"data": {}},
        )
        run = self.unwrap_data(payload)
        run_id = run.get("id") if isinstance(run, dict) else None
        if not run_id:
            raise OpentronsApiError("Maintenance run response did not include an id", response=payload)
        return str(run_id)

    def execute_maintenance_command(
        self,
        *,
        run_id: str,
        command_type: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self.request(
            "POST",
            f"{PATH_MAINTENANCE_RUNS}/{run_id}/commands?waitUntilComplete=true&timeout=120000",
            json_body={
                "data": {
                    "commandType": command_type,
                    "params": params,
                }
            },
            timeout=130,
        )
        command = self.unwrap_data(payload)
        if isinstance(command, dict) and command.get("status") == "failed":
            error = command.get("error") or f"Maintenance command {command_type} failed"
            if isinstance(error, dict):
                error = error.get("detail") or error.get("message") or str(error)
            raise OpentronsApiError(str(error), response=payload)
        return payload

    def move_axes_relative(self, *, run_id: str, axis_map: dict[str, float]) -> dict[str, Any]:
        normalized_axis_map = {
            axis.strip(): float(distance)
            for axis, distance in axis_map.items()
            if axis.strip() and float(distance) != 0
        }
        if not normalized_axis_map:
            raise ValueError("At least one non-zero axis movement is required")
        return self.execute_maintenance_command(
            run_id=run_id,
            command_type="robot/moveAxesRelative",
            params={"axis_map": normalized_axis_map},
        )

    def close_gripper_jaw(self, *, run_id: str) -> dict[str, Any]:
        return self.execute_maintenance_command(
            run_id=run_id,
            command_type="robot/closeGripperJaw",
            params={},
        )

    def open_gripper_jaw(self, *, run_id: str) -> dict[str, Any]:
        return self.execute_maintenance_command(
            run_id=run_id,
            command_type="robot/openGripperJaw",
            params={},
        )

    def load_pipette(
        self,
        *,
        run_id: str,
        pipette_name: str,
        mount: str,
        pipette_id: str,
    ) -> dict[str, Any]:
        return self.execute_maintenance_command(
            run_id=run_id,
            command_type="loadPipette",
            params={
                "pipetteName": pipette_name,
                "mount": mount,
                "pipetteId": pipette_id,
            },
        )

    def drop_tip_in_place(
        self,
        *,
        run_id: str,
        pipette_id: str,
        home_after: bool | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"pipetteId": pipette_id}
        if home_after is not None:
            params["homeAfter"] = home_after
        return self.execute_maintenance_command(
            run_id=run_id,
            command_type="unsafe/dropTipInPlace",
            params=params,
        )

    def delete_maintenance_run(self, run_id: str) -> dict[str, Any]:
        return self.request("DELETE", f"{PATH_MAINTENANCE_RUNS}/{run_id}")

    def move_robot(
        self,
        *,
        target: str,
        point: list[float],
        mount: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "target": target,
            "point": point,
            "mount": mount,
        }
        if model:
            body["model"] = model
        return self.request("POST", PATH_ROBOT_MOVE, json_body=body)

    def reset_settings(self, *, options: dict[str, bool]) -> dict[str, Any]:
        return self.request("POST", PATH_SETTINGS_RESET, json_body=options)

    def list_protocols(self) -> list[dict[str, Any]]:
        payload = self.request("GET", PATH_PROTOCOLS)
        data = self.unwrap_data(payload)
        return data if isinstance(data, list) else []

    def get_protocol(self, protocol_id: str) -> dict[str, Any]:
        payload = self.request("GET", f"{PATH_PROTOCOLS}/{protocol_id}")
        return self.unwrap_data(payload)

    def upload_protocol(
        self,
        files: list[tuple[str, bytes]],
        *,
        key: str | None = None,
        protocol_kind: str | None = None,
    ) -> dict[str, Any]:
        multipart_files = [
            ("files", (filename, content, "application/octet-stream"))
            for filename, content in files
        ]
        form_data: dict[str, str] = {}
        if key:
            form_data["key"] = key
        if protocol_kind:
            form_data["protocol_kind"] = protocol_kind
        response = self.request_raw(
            "POST",
            PATH_PROTOCOLS,
            data=form_data,
            files=multipart_files,
            timeout=max(self.timeout, 120),
        )
        return self.unwrap_data(response.json())

    def analyze_protocol(
        self,
        protocol_id: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        request_body = body or {}
        if "data" not in request_body:
            request_body = {"data": request_body}
        payload = self.request(
            "POST",
            f"{PATH_PROTOCOLS}/{protocol_id}/analyses",
            json_body=request_body,
            timeout=max(self.timeout, 120),
        )
        data = self.unwrap_data(payload)
        return data if isinstance(data, list) else [data] if data else []

    def list_protocol_analyses(self, protocol_id: str) -> list[dict[str, Any]]:
        payload = self.request("GET", f"{PATH_PROTOCOLS}/{protocol_id}/analyses")
        data = self.unwrap_data(payload)
        return data if isinstance(data, list) else []

    def list_data_files(self) -> list[dict[str, Any]]:
        payload = self.request("GET", PATH_DATA_FILES)
        data = self.unwrap_data(payload)
        return data if isinstance(data, list) else []

    def list_protocol_data_files(self, protocol_id: str) -> list[dict[str, Any]]:
        payload = self.request("GET", f"{PATH_PROTOCOLS}/{protocol_id}/dataFiles")
        data = self.unwrap_data(payload)
        return data if isinstance(data, list) else []

    def upload_data_file(self, filename: str, content: bytes) -> dict[str, Any]:
        response = self.request_raw(
            "POST",
            PATH_DATA_FILES,
            files=[("file", (filename, content, "text/csv"))],
            timeout=max(self.timeout, 60),
        )
        return self.unwrap_data(response.json())

    def list_runs(self) -> list[dict[str, Any]]:
        payload = self.request("GET", PATH_RUNS)
        data = self.unwrap_data(payload)
        return data if isinstance(data, list) else []

    def create_run(self, *, protocol_id: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"data": {}}
        if protocol_id:
            body["data"]["protocolId"] = protocol_id
        payload = self.request("POST", PATH_RUNS, json_body=body)
        return self.unwrap_data(payload)

    def run_action(self, run_id: str, action_type: str) -> dict[str, Any]:
        payload = self.request(
            "POST",
            f"{PATH_RUNS}/{run_id}/actions",
            json_body={"data": {"actionType": action_type}},
        )
        return self.unwrap_data(payload)
