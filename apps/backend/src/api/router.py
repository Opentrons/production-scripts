from fastapi import APIRouter

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

router.include_router(resources.router)
router.include_router(test_management.router)
router.include_router(system.router)
router.include_router(data.router)
router.include_router(uploads.router)
router.include_router(products.router)
router.include_router(file_transfer.router)
router.include_router(robots.router)
router.include_router(robot_logs.router)
router.include_router(robot_control.router)
router.include_router(robot_files.router)
router.include_router(robot_protocols.router)
router.include_router(versions.router)
