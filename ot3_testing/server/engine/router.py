from fastapi import Depends, FastAPI, HTTPException, APIRouter, status
from hardware_control.hardware_control import HardwareControl
from textwrap import dedent
from server.engine.models import *
from typing import Union
from ot_type import Point

engine_router = APIRouter()
api: Union[None, HardwareControl] = None


@engine_router.post(
    path="/init_hardware",
    summary="Initial device",
    description=dedent(
        """
        init a device and building api
        """
    ),
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_201_CREATED: {"message": "OK"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "message": "HTTP_422_UNPROCESSABLE_ENTITY"},
    },
)
async def init_hardware(device_name: DeviceName):
    global api
    api = HardwareControl(device_name.ip)


@engine_router.post(
    path="/home",
    summary="Hardware home",
    description=dedent(
        """
        home robot and pipette
        """
    ),
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"message": "OK"},
        status.HTTP_405_METHOD_NOT_ALLOWED: {
            "message": "HTTP_405_METHOD_NOT_ALLOWED"},
    },
)
async def home(axis: Axis):
    await api.home(target=axis.target, mount=axis.mount)


@engine_router.post(
    path="/move_to",
    summary="Hardware move to",
    description=dedent(
        """
        pipette move to
        """
    ),
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"message": "OK"},
        status.HTTP_405_METHOD_NOT_ALLOWED: {
            "message": "HTTP_405_METHOD_NOT_ALLOWED"},
    },
)
async def move_to(move_point: MovePoint):
    point = Point(move_point.point['x'], move_point.point['y'], move_point.point['z'])
    await api.move_to(move_point.mount, point)


@engine_router.post(
    path="/disengage",
    summary="Hardware disengage",
    description=dedent(
        """
        disengage axis: 
        X = "x"
        Y = "y"
        Z = "z"
        L_Z = "leftZ"
        R_Z = "rightZ"
        L_P = "leftPlunger"
        R_P = "rightPlunger"
        """
    ),
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"message": "OK"},
        status.HTTP_405_METHOD_NOT_ALLOWED: {
            "message": "HTTP_405_METHOD_NOT_ALLOWED"},
    },
)
async def dis_engage(axis: OTAxis):
    await api._post_disengaged_motor(axis.axis)
