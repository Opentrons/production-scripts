from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

import core.config as setting
from api.models import (
    RobotActionResponse,
    RobotBatchCommandResponse,
    RobotCommandRequest,
    RobotInfo,
    RobotScanGateway,
    RobotScanGatewayCreateRequest,
    RobotScanGatewaysResponse,
    RobotSshCommandBatchExecuteRequest,
    RobotSshCommandCreateRequest,
    RobotSshCommandExecuteRequest,
    RobotSshCommandUpdateRequest,
    RobotVersionCaptureRequest,
    RobotsScanResponse,
)
from modules.robots import robots as robot_service
from modules.robots import ssh_commands as ssh_command_service
from modules.robots import version_records as version_record_service


router = APIRouter()



async def _load_cached_robots(port: int, network: str | None) -> dict:
    try:
        result = await run_in_threadpool(robot_service.load_robot_scan_cache, port, network)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    result["refreshing"] = robot_service.is_robot_scan_refreshing(port, network)
    return result


async def _trigger_robot_scan(port: int, network: str | None) -> dict:
    try:
        robot_service.trigger_robot_scan_refresh(port=port, network=network)
        return await _load_cached_robots(port, network)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/robots/scan", response_model=RobotsScanResponse)
async def scan_robots(port: int = setting.ROBOT_HEALTH_PORT, network: str | None = None):
    """Compatibility endpoint: start an asynchronous refresh and return cached data."""
    return await _trigger_robot_scan(port, network)


@router.post("/robots/scan", response_model=RobotsScanResponse, status_code=202)
async def refresh_robots(port: int = setting.ROBOT_HEALTH_PORT, network: str | None = None):
    return await _trigger_robot_scan(port, network)


@router.get("/robots/scan-gateways", response_model=RobotScanGatewaysResponse)
async def list_robot_scan_gateways():
    try:
        return await run_in_threadpool(robot_service.list_scan_gateways)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/robots/scan-gateways", response_model=RobotScanGateway)
async def add_robot_scan_gateway(request: RobotScanGatewayCreateRequest):
    try:
        return await run_in_threadpool(robot_service.add_scan_gateway, request.gateway)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/robots/scan-gateways/{gateway}", response_model=RobotActionResponse)
async def delete_robot_scan_gateway(gateway: str):
    try:
        result = await run_in_threadpool(robot_service.delete_scan_gateway, gateway)
        return RobotActionResponse(
            success=bool(result["deleted"]),
            message="Deleted" if result["deleted"] else "Gateway not found",
            data=result,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/robots", response_model=RobotsScanResponse)
async def get_robots(port: int = setting.ROBOT_HEALTH_PORT, network: str | None = None):
    return await _load_cached_robots(port, network)


@router.get("/robot/{ip}", response_model=RobotInfo)
async def get_robot_detail(ip: str, port: int = setting.ROBOT_HEALTH_PORT):
    return await run_in_threadpool(robot_service.get_robot_detail, ip, port)


@router.get("/robots/version-products")
async def list_robot_version_products():
    return version_record_service.list_products()


@router.get("/robots/{ip}/versions/current")
async def get_current_robot_versions(ip: str, port: int = setting.ROBOT_HEALTH_PORT):
    try:
        return await run_in_threadpool(
            version_record_service.get_current_robot_versions,
            ip,
            port,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={"message": f"读取设备版本失败: {exc}"},
        ) from exc


@router.post("/robots/version-records")
async def capture_robot_version(request: RobotVersionCaptureRequest):
    try:
        return await run_in_threadpool(
            version_record_service.capture_version,
            ip=request.ip,
            port=request.port,
            product_type=request.product_type,
            test_name=request.test_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    except RuntimeError as exc:
        status_code = 503 if "MongoDB" in str(exc) else 502
        raise HTTPException(status_code=status_code, detail={"message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={"message": f"读取或保存版本失败: {exc}"},
        ) from exc


@router.get("/robots/version-history")
async def list_robot_version_history(page: int = 1, page_size: int = 100):
    try:
        return await run_in_threadpool(
            version_record_service.list_history,
            page=page,
            page_size=page_size,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc


@router.post("/robots/commands", response_model=RobotBatchCommandResponse)
async def execute_robot_commands(request: RobotCommandRequest):
    results = await robot_service.execute_robot_commands_batch(
        ips=request.ips,
        port=request.port,
        method=request.method,
        path=request.path,
        body=request.body,
        timeout=request.timeout,
    )
    return {"results": results}


@router.get("/robots/ssh-commands")
async def list_robot_ssh_commands():
    return await run_in_threadpool(ssh_command_service.list_commands)


@router.post("/robots/ssh-commands/execute")
async def execute_robot_ssh_command(request: RobotSshCommandExecuteRequest):
    try:
        return await run_in_threadpool(
            ssh_command_service.execute_command,
            ip=request.ip,
            command=request.command,
            timeout=request.timeout,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"message": f"SSH 命令执行失败: {exc}"}) from exc


@router.post("/robots/ssh-commands/batch-execute")
async def execute_robot_ssh_commands_batch(request: RobotSshCommandBatchExecuteRequest):
    try:
        return await run_in_threadpool(
            ssh_command_service.execute_commands_batch,
            ips=request.ips,
            command=request.command,
            timeout=request.timeout,
            concurrency=request.concurrency,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"message": f"批量 SSH 命令执行失败: {exc}"}) from exc


@router.post("/robots/ssh-commands")
async def create_robot_ssh_command(request: RobotSshCommandCreateRequest):
    try:
        return await run_in_threadpool(
            ssh_command_service.create_command,
            name=request.name,
            command=request.command,
            description=request.description,
            tag=request.tag,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"message": f"保存 SSH 自定义命令失败: {exc}"}) from exc


@router.put("/robots/ssh-commands/{command_id}")
async def update_robot_ssh_command(command_id: str, request: RobotSshCommandUpdateRequest):
    try:
        return await run_in_threadpool(
            ssh_command_service.update_command,
            command_id,
            name=request.name,
            command=request.command,
            description=request.description,
            tag=request.tag,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"message": f"更新 SSH 自定义命令失败: {exc}"}) from exc


@router.delete("/robots/ssh-commands/{command_id}")
async def delete_robot_ssh_command(command_id: str):
    try:
        return await run_in_threadpool(ssh_command_service.delete_command, command_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"message": str(exc)}) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"message": f"删除 SSH 自定义命令失败: {exc}"}) from exc
