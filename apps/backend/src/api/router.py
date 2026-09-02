from fastapi import APIRouter, Depends

from modules.agent.routes import odd_stream_router, router as agent_router
from modules.auth.dependencies import require_platform_access
from modules.auth.routes import router as auth_router
from modules.bridge_tokens.routes import router as bridge_tokens_router
from modules.protocol_monitor.routes import router as protocol_monitor_router

from api.routers import (
    data,
    file_transfer,
    integrations,
    products,
    resources,
    robot_control,
    robot_files,
    robot_logs,
    robot_protocols,
    robots,
    supplies,
    system,
    test_management,
    uploads,
    versions,
)


router = APIRouter()
protected_router = APIRouter(dependencies=[Depends(require_platform_access)])

router.include_router(auth_router)
router.include_router(odd_stream_router)
router.include_router(system.data_center_client_router)
router.include_router(uploads.data_center_client_router)
router.include_router(file_transfer.router)
router.include_router(integrations.router)
protected_router.include_router(agent_router)
protected_router.include_router(bridge_tokens_router)
protected_router.include_router(protocol_monitor_router)
protected_router.include_router(resources.router)
protected_router.include_router(test_management.router)
protected_router.include_router(system.router)
protected_router.include_router(data.router)
protected_router.include_router(uploads.router)
protected_router.include_router(products.router)
protected_router.include_router(robots.router)
protected_router.include_router(robot_logs.router)
protected_router.include_router(robot_control.router)
protected_router.include_router(robot_files.router)
protected_router.include_router(robot_protocols.router)
protected_router.include_router(supplies.router)
protected_router.include_router(versions.router)
router.include_router(protected_router)
