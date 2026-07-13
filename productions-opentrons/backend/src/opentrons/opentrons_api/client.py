from __future__ import annotations

from typing import Any

import requests

from opentrons.opentrons_api.spec import (
    DEFAULT_OPENTRONS_VERSION,
    DEFAULT_PORT,
    PATH_HEALTH,
    PATH_INSTRUMENTS,
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
        payload = self.request(
            "POST",
            f"{PATH_PROTOCOLS}/{protocol_id}/analyses",
            json_body=body or {},
            timeout=max(self.timeout, 120),
        )
        data = self.unwrap_data(payload)
        return data if isinstance(data, list) else [data] if data else []

    def list_protocol_analyses(self, protocol_id: str) -> list[dict[str, Any]]:
        payload = self.request("GET", f"{PATH_PROTOCOLS}/{protocol_id}/analyses")
        data = self.unwrap_data(payload)
        return data if isinstance(data, list) else []

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
