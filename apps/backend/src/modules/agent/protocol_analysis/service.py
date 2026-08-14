from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiofiles
from fastapi import UploadFile

from core import config
from modules.agent.protocol_analysis.models import (
    OpentronsEnvironmentResponse,
    ProtocolAnalysisError,
    ProtocolAnalysisResponse,
)
from modules.agent.protocol_analysis.opentrons_path import resolve_opentrons_environment
from modules.agent.protocol_analysis.versions import (
    ensure_opentrons_version,
    list_opentrons_versions,
    resolve_default_version,
)


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_PROTOCOL_BYTES = 8 * 1024 * 1024
_MAX_CSV_BYTES = 5 * 1024 * 1024
_ANALYZE_TIMEOUT_SECONDS = 180


class ProtocolAnalysisErrorExc(RuntimeError):
    pass


def _analysis_pythonpath(root: Path) -> str:
    """Include common Opentrons monorepo packages needed by production protocols."""
    extras = [
        root / "api" / "src",
        root / "shared-data" / "python",
        root / "hardware-testing",
        root / "hardware" / "src",
        root / "server-utils" / "src",
        root / "robot-server",
    ]
    existing = [str(path) for path in extras if path.exists()]
    current = os.environ.get("PYTHONPATH", "").strip()
    if current:
        existing.append(current)
    seen: set[str] = set()
    ordered: list[str] = []
    for item in existing:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return os.pathsep.join(ordered)


class ProtocolAnalysisService:
    async def environment(self) -> OpentronsEnvironmentResponse:
        env = resolve_opentrons_environment()
        versions = await list_opentrons_versions() if env.root else []
        default_version = versions[0] if versions else None
        return OpentronsEnvironmentResponse(
            available=env.available,
            root=str(env.root) if env.root else None,
            python=str(env.python) if env.python else None,
            detail=env.detail,
            candidates=env.candidates,
            versions=versions,
            default_version=default_version,
            selected_version=default_version,
        )

    def _workspace_root(self) -> Path:
        root = Path(config.DOWNLOAD_DIR) / "protocol_analysis"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _safe_filename(self, name: str | None, fallback: str) -> str:
        raw = Path(str(name or fallback).replace("\\", "/")).name.strip() or fallback
        cleaned = _SAFE_NAME.sub("_", raw).strip("._") or fallback
        return cleaned[:180]

    async def _save_upload(self, upload: UploadFile, target: Path, max_bytes: int) -> int:
        size = 0
        async with aiofiles.open(target, "wb") as handle:
            while True:
                chunk = await upload.read(256 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise ProtocolAnalysisErrorExc(f"{target.name} 超过大小限制")
                await handle.write(chunk)
        return size

    def _summarize(self, analysis: dict[str, Any]) -> tuple[str, list[ProtocolAnalysisError]]:
        result = str(analysis.get("result") or "error")
        errors: list[ProtocolAnalysisError] = []
        for item in analysis.get("errors") or []:
            if not isinstance(item, dict):
                continue
            detail = str(
                item.get("detail")
                or item.get("errorCode")
                or item.get("errorType")
                or "Unknown analysis error"
            )
            errors.append(
                ProtocolAnalysisError(
                    id=str(item.get("id") or "") or None,
                    errorType=str(item.get("errorType") or "") or None,
                    detail=detail,
                    errorCode=str(item.get("errorCode") or "") or None,
                )
            )
        return result, errors

    async def analyze(
        self,
        protocol_files: list[UploadFile],
        labware_files: list[UploadFile] | None = None,
        rtp_values_json: str = "{}",
        csv_variable_names: list[str] | None = None,
        csv_files: list[UploadFile] | None = None,
        opentrons_version: str = "",
    ) -> ProtocolAnalysisResponse:
        env = resolve_opentrons_environment()
        if not env.available or env.root is None or env.python is None:
            raise ProtocolAnalysisErrorExc(env.detail)

        if not protocol_files:
            raise ProtocolAnalysisErrorExc("请至少上传一个 protocol 文件")

        try:
            rtp_values = json.loads(rtp_values_json or "{}")
            if not isinstance(rtp_values, dict):
                raise ValueError("rtp_values 必须是 JSON 对象")
        except Exception as exc:  # noqa: BLE001
            raise ProtocolAnalysisErrorExc(f"rtp_values 无效: {exc}") from exc

        csv_variable_names = csv_variable_names or []
        csv_files = csv_files or []
        labware_files = labware_files or []
        if len(csv_variable_names) != len(csv_files):
            raise ProtocolAnalysisErrorExc("CSV 参数名与文件数量不一致")

        selected_version = (opentrons_version or "").strip() or await resolve_default_version() or ""
        try:
            source_root = await ensure_opentrons_version(selected_version)
        except Exception as exc:  # noqa: BLE001
            raise ProtocolAnalysisErrorExc(str(exc)) from exc

        session_id = uuid4().hex
        work_dir = self._workspace_root() / session_id
        protocol_dir = work_dir / "protocol"
        csv_dir = work_dir / "csv"
        protocol_dir.mkdir(parents=True, exist_ok=True)
        csv_dir.mkdir(parents=True, exist_ok=True)
        output_path = work_dir / "analysis.json"

        saved_protocol_names: list[str] = []
        rtp_files: dict[str, str] = {}
        try:
            for index, upload in enumerate(protocol_files[:12]):
                filename = self._safe_filename(upload.filename, f"protocol_{index + 1}.py")
                target = protocol_dir / filename
                await self._save_upload(upload, target, _MAX_PROTOCOL_BYTES)
                saved_protocol_names.append(filename)

            for index, upload in enumerate(labware_files[:40]):
                filename = self._safe_filename(upload.filename, f"customer_labware_{index + 1}.json")
                if not filename.lower().endswith(".json"):
                    filename = f"{filename}.json"
                target = protocol_dir / filename
                await self._save_upload(upload, target, _MAX_PROTOCOL_BYTES)
                saved_protocol_names.append(filename)

            for variable_name, upload in zip(csv_variable_names, csv_files, strict=True):
                name = str(variable_name or "").strip()
                if not name:
                    raise ProtocolAnalysisErrorExc("CSV 参数名不能为空")
                filename = self._safe_filename(upload.filename, f"{name}.csv")
                target = csv_dir / filename
                await self._save_upload(upload, target, _MAX_CSV_BYTES)
                rtp_files[name] = str(target.resolve())

            command = [
                str(env.python),
                "-m",
                "opentrons.cli",
                "analyze",
                "--json-output",
                str(output_path),
                "--rtp-values",
                json.dumps(rtp_values, ensure_ascii=False),
                "--rtp-files",
                json.dumps(rtp_files, ensure_ascii=False),
                *[str(protocol_dir / name) for name in saved_protocol_names],
            ]
            child_env = os.environ.copy()
            # Prefer the selected tag sources on PYTHONPATH; keep shared api/.venv interpreter.
            child_env["PYTHONPATH"] = _analysis_pythonpath(source_root)
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(source_root),
                env=child_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=_ANALYZE_TIMEOUT_SECONDS,
                )
            except TimeoutError as exc:
                process.kill()
                await process.communicate()
                raise ProtocolAnalysisErrorExc("协议分析超时") from exc

            stderr_text = (stderr or b"").decode("utf-8", errors="replace").strip()
            stdout_text = (stdout or b"").decode("utf-8", errors="replace").strip()
            if process.returncode not in (0, None) and not output_path.exists():
                detail = stderr_text or stdout_text or f"analyze 退出码 {process.returncode}"
                raise ProtocolAnalysisErrorExc(detail[:2000])

            if not output_path.exists():
                detail = stderr_text or stdout_text or "分析未生成 JSON 结果"
                raise ProtocolAnalysisErrorExc(detail[:2000])

            analysis = json.loads(output_path.read_text(encoding="utf-8"))
            result, errors = self._summarize(analysis)
            metadata = analysis.get("metadata") if isinstance(analysis.get("metadata"), dict) else {}
            protocol_name = str(
                metadata.get("protocolName")
                or metadata.get("protocol_name")
                or (saved_protocol_names[0] if saved_protocol_names else "protocol")
            )
            return ProtocolAnalysisResponse(
                session_id=session_id,
                protocol_name=protocol_name,
                filenames=saved_protocol_names,
                result=result,
                robot_type=str(analysis.get("robotType") or "") or None,
                metadata=metadata,
                run_time_parameters=list(analysis.get("runTimeParameters") or []),
                errors=errors,
                command_count=len(analysis.get("commands") or []),
                labware_count=len(analysis.get("labware") or []),
                pipette_count=len(analysis.get("pipettes") or []),
                module_count=len(analysis.get("modules") or []),
                liquid_count=len(analysis.get("liquids") or []),
                analysis=analysis,
                opentrons_root=str(source_root),
                opentrons_version=selected_version,
                stderr=stderr_text[:4000] if stderr_text else None,
            )
        except ProtocolAnalysisErrorExc:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise
        except Exception as exc:  # noqa: BLE001
            shutil.rmtree(work_dir, ignore_errors=True)
            raise ProtocolAnalysisErrorExc(str(exc)) from exc


protocol_analysis_service = ProtocolAnalysisService()
