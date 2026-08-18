from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from api.models import PullFolderResponse
from core.logging import get_logger
from modules.robots import file_transfer as file_transfer_service


logger = get_logger(__name__)
router = APIRouter()


def _client_ip(request: Request) -> str:
    forwarded_ip = request.headers.get("X-Real-IP", "").strip()
    if forwarded_ip:
        return forwarded_ip
    return request.client.host if request.client else "unknown"


@router.post("/pull-folder", response_model=PullFolderResponse)
async def pull_folder(
    request: Request,
    csv_file: UploadFile = File(...),
    folder_name: str = Form(...),
    pull_method: str = Form("sftp", description="Pull method: sftp or scp"),
):
    try:
        robot_ip = _client_ip(request)
        logger.info(f"Received pull-folder request from {robot_ip}")
        return await file_transfer_service.pull_folder(
            robot_ip=robot_ip,
            csv_file=csv_file,
            folder_name=folder_name,
            pull_method=pull_method,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal server error",
                "error": str(exc),
            },
        )
