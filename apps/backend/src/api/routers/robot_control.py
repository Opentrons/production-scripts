from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

import core.config as setting
from api.models import (
    RobotActionResponse,
    RobotBarcodeProvisionRequest,
    RobotBarcodeTargetsResponse,
    RobotControlSummaryResponse,
    RobotHomeRequest,
    RobotJogDropTipRequest,
    RobotJogGripperRequest,
    RobotJogMoveRequest,
    RobotJogRunRequest,
    RobotMoveRequest,
    RobotResetRequest,
)
from modules.robots import barcode_provision as barcode_provision_service
from modules.robots import opentrons_control as opentrons_control_service
from modules.robots.api_client.client import OpentronsApiError


router = APIRouter()

@router.get("/robots/{ip}/control/summary", response_model=RobotControlSummaryResponse)
async def get_robot_control_summary(ip: str, port: int = setting.ROBOT_HEALTH_PORT):
    return await run_in_threadpool(opentrons_control_service.get_device_control_summary, ip, port)


@router.post("/robots/{ip}/control/home", response_model=RobotActionResponse)
async def home_robot(ip: str, request: RobotHomeRequest):
    data = await run_in_threadpool(
        opentrons_control_service.home_robot,
        ip,
        target=request.target,
        mount=request.mount,
        port=request.port,
    )
    return RobotActionResponse(success=True, message="Home command sent", data=data)


@router.post("/robots/{ip}/control/move", response_model=RobotActionResponse)
async def move_robot(ip: str, request: RobotMoveRequest):
    data = await run_in_threadpool(
        opentrons_control_service.move_robot,
        ip,
        target=request.target,
        point=request.point,
        mount=request.mount,
        model=request.model,
        port=request.port,
    )
    return RobotActionResponse(success=True, message="Move command sent", data=data)


@router.post("/robots/{ip}/control/reset", response_model=RobotActionResponse)
async def reset_robot(ip: str, request: RobotResetRequest):
    try:
        data = await run_in_threadpool(
            opentrons_control_service.reset_robot,
            ip,
            axes=request.axes,
            port=request.port,
        )
    except OpentronsApiError as exc:
        raise HTTPException(status_code=502, detail={"message": f"设备轴复位失败: {exc}"}) from exc
    return RobotActionResponse(success=True, message="Axis home command completed", data=data)


@router.post("/robots/{ip}/control/jog/runs", response_model=RobotActionResponse)
async def create_jog_run(ip: str, request: RobotJogRunRequest):
    try:
        data = await run_in_threadpool(
            opentrons_control_service.create_jog_run,
            ip,
            port=request.port,
        )
    except OpentronsApiError as exc:
        raise HTTPException(status_code=502, detail={"message": f"创建 Jog Run 失败: {exc}"}) from exc
    return RobotActionResponse(success=True, message="Jog run created", data=data)


@router.post("/robots/{ip}/control/jog/runs/{run_id}/move", response_model=RobotActionResponse)
async def move_jog_robot(ip: str, run_id: str, request: RobotJogMoveRequest):
    try:
        data = await run_in_threadpool(
            opentrons_control_service.move_jog_robot,
            ip,
            run_id=run_id,
            direction=request.direction,
            step_mm=request.step_mm,
            mount=request.mount,
            port=request.port,
        )
    except (ValueError, OpentronsApiError) as exc:
        status_code = 400 if isinstance(exc, ValueError) else 502
        raise HTTPException(status_code=status_code, detail={"message": f"Jog 移动失败: {exc}"}) from exc
    return RobotActionResponse(success=True, message="Jog movement completed", data=data)


@router.post("/robots/{ip}/control/jog/runs/{run_id}/gripper", response_model=RobotActionResponse)
async def control_jog_gripper(ip: str, run_id: str, request: RobotJogGripperRequest):
    try:
        data = await run_in_threadpool(
            opentrons_control_service.control_jog_gripper,
            ip,
            run_id=run_id,
            action=request.action,
            port=request.port,
        )
    except (ValueError, OpentronsApiError) as exc:
        status_code = 400 if isinstance(exc, ValueError) else 502
        raise HTTPException(status_code=status_code, detail={"message": f"Gripper 操作失败: {exc}"}) from exc
    return RobotActionResponse(success=True, message="Gripper action completed", data=data)


@router.post("/robots/{ip}/control/jog/runs/{run_id}/drop-tip", response_model=RobotActionResponse)
async def drop_jog_tip(ip: str, run_id: str, request: RobotJogDropTipRequest):
    try:
        data = await run_in_threadpool(
            opentrons_control_service.drop_jog_tip,
            ip,
            run_id=run_id,
            pipette_id=request.pipette_id,
            home_after=request.home_after,
            port=request.port,
        )
    except OpentronsApiError as exc:
        raise HTTPException(status_code=502, detail={"message": f"Drop Tip 失败: {exc}"}) from exc
    return RobotActionResponse(success=True, message="Drop tip completed", data=data)


@router.delete("/robots/{ip}/control/jog/runs/{run_id}", response_model=RobotActionResponse)
async def delete_jog_run(ip: str, run_id: str, port: int = setting.ROBOT_HEALTH_PORT):
    try:
        data = await run_in_threadpool(
            opentrons_control_service.delete_jog_run,
            ip,
            run_id=run_id,
            port=port,
        )
    except OpentronsApiError as exc:
        raise HTTPException(status_code=502, detail={"message": f"释放 Jog Run 失败: {exc}"}) from exc
    return RobotActionResponse(success=True, message="Jog run released", data=data)


@router.post("/robots/{ip}/control/reboot", response_model=RobotActionResponse)
async def reboot_robot(ip: str):
    result = await run_in_threadpool(opentrons_control_service.reboot_robot, ip)
    return RobotActionResponse(success=True, message=result.get("message"))


@router.get("/robots/{ip}/barcode/targets", response_model=RobotBarcodeTargetsResponse)
async def get_barcode_targets(ip: str, port: int = setting.ROBOT_HEALTH_PORT):
    data = await run_in_threadpool(barcode_provision_service.list_provision_targets, ip, port)
    return RobotBarcodeTargetsResponse(**data)


@router.post("/robots/{ip}/barcode/provision", response_model=RobotActionResponse)
async def provision_barcode(ip: str, request: RobotBarcodeProvisionRequest):
    try:
        data = await run_in_threadpool(
            barcode_provision_service.provision_barcode,
            ip,
            kind=request.kind,
            serial=request.serial,
            mount=request.mount,
            target_id=request.target_id,
            port=request.port,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail={"message": str(exc)}) from exc

    return RobotActionResponse(
        success=bool(data.get("success")),
        message=data.get("message"),
        data=data,
    )
