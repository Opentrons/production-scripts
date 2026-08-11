from fastapi import APIRouter, Depends

from modules.agent.routes import router as agent_router
from modules.auth.dependencies import require_authenticated_user
from modules.auth.routes import router as auth_router
from modules.protocol_monitor.routes import router as protocol_monitor_router

from api.routers import (
    data,
    file_transfer,
    products,
    resources,
    robot_control,
    robot_files,
    robot_logs,
    robot_protocols,
    robots,
    system,
    test_management,
    uploads,
    versions,
)


router = APIRouter()
protected_router = APIRouter(dependencies=[Depends(require_authenticated_user)])

router.include_router(auth_router)
protected_router.include_router(agent_router)
protected_router.include_router(protocol_monitor_router)
protected_router.include_router(resources.router)
protected_router.include_router(test_management.router)
protected_router.include_router(system.router)
protected_router.include_router(data.router)
protected_router.include_router(uploads.router)
protected_router.include_router(products.router)
protected_router.include_router(file_transfer.router)
protected_router.include_router(robots.router)
protected_router.include_router(robot_logs.router)
protected_router.include_router(robot_control.router)
protected_router.include_router(robot_files.router)
protected_router.include_router(robot_protocols.router)
protected_router.include_router(versions.router)
router.include_router(protected_router)
