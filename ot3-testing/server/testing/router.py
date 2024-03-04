from fastapi import Depends, FastAPI, HTTPException, APIRouter, status
from tests.lifetime_test import LifeTime
from textwrap import dedent
from server.testing.models import *
from typing import Union
from ot_type import Point

testing_router = APIRouter()



@testing_router.post(
    path="/lifetime/z_stage",
    summary="Test z_stage lifetime",
    description=dedent(
        """
        z-stage lifetime test, start a series of robots
        """
    ),
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {"message": "OK"},
        status.HTTP_405_METHOD_NOT_ALLOWED: {
            "message": "HTTP_405_METHOD_NOT_ALLOWED"},
    },
)
async def start_z_stage_lifetime_test(cfg: List[LifetimeCfg]):
    lifetime = LifeTime()
    lifetime.test_z_stage_lifetime_robots(cfg)

