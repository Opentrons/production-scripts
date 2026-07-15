from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response

import settings as setting
from api.models import (
    CollectionDataResponse,
    CollectionFilterOptionsResponse,
    DataAnalysisPathRequest,
    DataAnalysisOnlineRequest,
    DataAnalysisResponse,
    CollectionListResponse,
    DataLinksResponse,
    FileResourceDeleteResponse,
    FileResourceProjectsResponse,
    FileResourceVersionResponse,
    FileResourceVersionUpdateRequest,
    HealthResponse,
    DataAnalysisSpecRequest,
    DataAnalysisSpecResponse,
    MarkMessageReadResponse,
    MessageListResponse,
    PullFolderResponse,
    ProductManagementFilterOptionsResponse,
    ProductManagementListResponse,
    ProductManagementManualAddRequest,
    ProductManagementManualAddResponse,
    ProductManagementSyncResponse,
    RobotBatchCommandResponse,
    RobotCommandRequest,
    RobotActionResponse,
    RobotControlSummaryResponse,
    RobotFileContentResponse,
    RobotFileListResponse,
    RobotFileWriteRequest,
    RobotHomeRequest,
    RobotInfo,
    RobotMoveRequest,
    RobotProtocolAnalyzeRequest,
    RobotProtocolListResponse,
    RobotResetRequest,
    RobotRunActionRequest,
    RobotRunCreateRequest,
    RobotRunListResponse,
    RobotScanGateway,
    RobotScanGatewayCreateRequest,
    RobotScanGatewaysResponse,
    RobotsScanResponse,
    TestDataResponse,
    ProductStatusUpdateRequest,
    ProductStatusUpdateResponse,
    UploadDataRequest,
    UploadDataResponse,
    UploadFinishSettingResponse,
    UploadFinishSettingUpdateRequest,
    UploadRecordFilterOptionsResponse,
    UploadRecordListResponse,
    UploadRecordStatsResponse,
    UnitTrackerRowsResponse,
    UnitTrackerSyncResponse,
)
from api.services import data as data_service
from api.services import data_analysis as data_analysis_service
from api.services import data_links as data_links_service
from api.services import file_transfer as file_transfer_service
from api.services import file_resources as file_resource_service
from api.services import health as health_service
from api.services import messages as message_service
from api.services import opentrons_control as opentrons_control_service
from api.services import opentrons_protocols as opentrons_protocols_service
from api.services import product_management as product_management_service
from api.services import robots as robot_service
from api.services import upload as upload_service
from api.services import upload_records as upload_record_service
from api.services import upload_settings as upload_settings_service
from api.services import unit_tracker as unit_tracker_service
from api.services.logging import logger
from test_case.execution import test_execution_manager
from test_case.execution.manager import (
    TestExecutionLimitError,
    TestExecutionNotFoundError,
    TestExecutionSshError,
    TestExecutionStateError,
)
from test_case.models import (
    ExecutionStatusResponse,
    TestCase,
    TestCaseCreate,
    TestCaseListResponse,
    TestCaseTreeResponse,
    TestCaseUpdate,
    TestExecutionCompleteRequest,
    TestExecutionInputRequest,
    TestExecutionNodeRequest,
    TestExecutionRunResponse,
    TestExecutionStartRequest,
    TestExecutionWaitingInputRequest,
    TestProduct,
    TestProductCreate,
    TestType,
    TestTypeCreate,
)
from test_case.services.test_case_service import TestCaseValidationError, test_case_service
from opentrons.opentrons_files.ssh_client import OpentronsSshError

router = APIRouter()


@router.get("/file-resources/projects", response_model=FileResourceProjectsResponse)
async def list_file_resource_projects():
    try:
        return await run_in_threadpool(file_resource_service.list_projects)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/file-resources/versions", response_model=FileResourceVersionResponse)
async def create_file_resource_version(
    project_id: str | None = Form(None),
    project_name: str = Form(""),
    project_description: str = Form(""),
    version: str = Form(...),
    version_notes: str = Form(""),
    file: UploadFile = File(...),
):
    try:
        created_version = await file_resource_service.create_version(
            project_id=project_id,
            project_name=project_name,
            project_description=project_description,
            version=version,
            version_notes=version_notes,
            upload=file,
        )
        return {"success": True, "version": created_version}
    except file_resource_service.FileResourceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except file_resource_service.FileResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("File resource upload failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="文件上传失败") from exc


@router.put("/file-resources/versions/{version_id}", response_model=FileResourceVersionResponse)
async def update_file_resource_version(version_id: str, request: FileResourceVersionUpdateRequest):
    try:
        updates = request.model_dump(exclude_unset=True) if hasattr(request, "model_dump") else request.dict(exclude_unset=True)
        version = await run_in_threadpool(file_resource_service.update_version, version_id, updates)
        return {"success": True, "version": version}
    except file_resource_service.FileResourceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except file_resource_service.FileResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/file-resources/versions/{version_id}/download")
async def download_file_resource_version(version_id: str):
    try:
        file_path, filename, content_type = await run_in_threadpool(
            file_resource_service.resolve_download,
            version_id,
        )
        return FileResponse(file_path, media_type=content_type, filename=filename)
    except file_resource_service.FileResourceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except file_resource_service.FileResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/file-resources/versions/{version_id}", response_model=FileResourceDeleteResponse)
async def delete_file_resource_version(version_id: str):
    try:
        return await run_in_threadpool(file_resource_service.delete_version, version_id)
    except file_resource_service.FileResourceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except file_resource_service.FileResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/test-cases/tree", response_model=TestCaseTreeResponse)
async def get_test_case_tree():
    return test_case_service.get_tree()


@router.post("/test-products", response_model=TestProduct)
async def create_test_product(payload: TestProductCreate):
    try:
        return test_case_service.create_product(payload)
    except TestCaseValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/test-products/{product_id}/types", response_model=TestType)
async def create_test_type(product_id: str, payload: TestTypeCreate):
    try:
        test_type = test_case_service.create_type(product_id, payload)
    except TestCaseValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if test_type is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return test_type


@router.get("/test-cases", response_model=TestCaseListResponse)
async def get_test_cases(
    product_id: str | None = None,
    test_type: str | None = None,
    include_archived: bool = False,
):
    return test_case_service.list_cases(
        product_id=product_id,
        test_type=test_type,
        include_archived=include_archived,
    )


@router.post("/test-cases", response_model=TestCase)
async def create_test_case(payload: TestCaseCreate):
    try:
        return test_case_service.create_case(payload)
    except TestCaseValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/test-cases/{case_id}", response_model=TestCase)
async def get_test_case(case_id: str):
    test_case = test_case_service.get_case(case_id)
    if test_case is None:
        raise HTTPException(status_code=404, detail="Test case not found")
    return test_case


@router.put("/test-cases/{case_id}", response_model=TestCase)
async def update_test_case(case_id: str, payload: TestCaseUpdate):
    try:
        test_case = test_case_service.update_case(case_id, payload)
    except TestCaseValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if test_case is None:
        raise HTTPException(status_code=404, detail="Test case not found")
    return test_case


@router.delete("/test-cases/{case_id}", response_model=TestCase)
async def archive_test_case(case_id: str):
    test_case = test_case_service.archive_case(case_id)
    if test_case is None:
        raise HTTPException(status_code=404, detail="Test case not found")
    return test_case


@router.get("/test-execution/status", response_model=ExecutionStatusResponse)
async def get_test_execution_status():
    return test_execution_manager.get_status()


@router.post("/test-execution/runs", response_model=TestExecutionRunResponse)
async def start_test_execution(payload: TestExecutionStartRequest):
    test_case = test_case_service.get_case(payload.case_id)
    if test_case is None:
        raise HTTPException(status_code=404, detail="Test case not found")
    try:
        return test_execution_manager.start_run(payload, test_case)
    except TestExecutionLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except TestExecutionSshError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/test-execution/runs/{run_id}", response_model=TestExecutionRunResponse)
async def get_test_execution_run(run_id: str):
    try:
        return test_execution_manager.get_run(run_id)
    except TestExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test execution run not found") from exc


@router.post("/test-execution/runs/{run_id}/current-node", response_model=TestExecutionRunResponse)
async def set_test_execution_current_node(run_id: str, payload: TestExecutionNodeRequest):
    try:
        return test_execution_manager.set_current_node(run_id, payload.node_id)
    except TestExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test execution run not found") from exc


@router.post("/test-execution/runs/{run_id}/wait-input", response_model=TestExecutionRunResponse)
async def wait_test_execution_input(run_id: str, payload: TestExecutionWaitingInputRequest):
    try:
        return test_execution_manager.wait_for_input(run_id, payload)
    except TestExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test execution run not found") from exc


@router.post("/test-execution/runs/{run_id}/input", response_model=TestExecutionRunResponse)
async def submit_test_execution_input(run_id: str, payload: TestExecutionInputRequest):
    try:
        return test_execution_manager.submit_input(run_id, payload)
    except TestExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test execution run not found") from exc
    except TestExecutionStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/test-execution/runs/{run_id}/complete", response_model=TestExecutionRunResponse)
async def complete_test_execution(run_id: str, payload: TestExecutionCompleteRequest):
    try:
        return test_execution_manager.complete_run(run_id, payload)
    except TestExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test execution run not found") from exc


@router.post("/test-execution/runs/{run_id}/stop", response_model=TestExecutionRunResponse)
async def stop_test_execution(run_id: str):
    try:
        return test_execution_manager.stop_run(run_id)
    except TestExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Test execution run not found") from exc


@router.get("/test-data", response_model=TestDataResponse)
async def get_test_data(
    page: int = 1,
    page_size: int = 20,
    test_type: str | None = None,
):
    return data_service.get_test_data(page=page, page_size=page_size, test_type=test_type)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return await run_in_threadpool(health_service.get_health_status)


@router.get("/messages", response_model=MessageListResponse)
async def get_messages():
    return await run_in_threadpool(message_service.get_messages)


@router.put("/messages/read-all", response_model=MarkMessageReadResponse)
async def mark_all_messages_read():
    return await run_in_threadpool(message_service.mark_all_messages_read)


@router.put("/messages/{message_id}/read", response_model=MarkMessageReadResponse)
async def mark_message_read(message_id: str):
    return await run_in_threadpool(message_service.mark_message_read, message_id)


@router.get("/collections", response_model=CollectionListResponse)
async def get_collections():
    return await run_in_threadpool(data_service.get_collections)


@router.get("/collection-data", response_model=CollectionDataResponse)
async def get_collection_data(
    collection_name: str,
    page: int = 1,
    page_size: int = 20,
    model: str | None = None,
    type: str | None = None,
    total_result: str | None = None,
    barcode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    return await run_in_threadpool(
        data_service.get_collection_data,
        collection_name=collection_name,
        page=page,
        page_size=page_size,
        model=model,
        production_type=type,
        total_result=total_result,
        barcode=barcode,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/collection-filter-options", response_model=CollectionFilterOptionsResponse)
async def get_collection_filter_options(collection_name: str):
    return await run_in_threadpool(data_service.get_collection_filter_options, collection_name)


@router.get("/data-links", response_model=DataLinksResponse)
async def get_data_links():
    return data_links_service.get_data_links()


@router.post("/data-analysis/analyze", response_model=DataAnalysisResponse)
async def analyze_data_files(files: list[UploadFile] = File(...)):
    try:
        logger.info(
            "Received data analysis upload request: files=%s",
            [file.filename for file in files],
        )
        return await data_analysis_service.analyze_uploaded_files(files)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error in data-analysis/analyze: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/data-analysis/analyze-paths", response_model=DataAnalysisResponse)
async def analyze_data_paths(payload: DataAnalysisPathRequest):
    try:
        logger.info("Received data analysis path request: file_paths=%s", payload.file_paths)
        return await run_in_threadpool(data_analysis_service.analyze_paths, payload.file_paths)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error in data-analysis/analyze-paths: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/data-analysis/analyze-online", response_model=DataAnalysisResponse)
async def analyze_online_data(payload: DataAnalysisOnlineRequest):
    try:
        return await run_in_threadpool(
            data_analysis_service.analyze_online,
            payload.model_dump() if hasattr(payload, "model_dump") else payload.dict(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error in data-analysis/analyze-online: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/data-analysis/specs", response_model=DataAnalysisSpecResponse)
async def get_data_analysis_specs():
    return await run_in_threadpool(data_analysis_service.get_specs)


@router.put("/data-analysis/specs/gravimetric", response_model=dict)
async def update_data_analysis_gravimetric_spec(payload: DataAnalysisSpecRequest):
    return await run_in_threadpool(
        data_analysis_service.update_gravimetric_spec,
        payload.model_dump() if hasattr(payload, "model_dump") else payload.dict(),
    )


@router.get("/settings/upload/finish", response_model=UploadFinishSettingResponse)
async def get_upload_finish_settings():
    return await run_in_threadpool(upload_settings_service.get_upload_finish_settings)


@router.put("/settings/upload/finish", response_model=dict)
async def update_upload_finish_setting(payload: UploadFinishSettingUpdateRequest):
    payload_dict = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    try:
        return await run_in_threadpool(upload_settings_service.update_upload_finish_setting, payload_dict)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": str(exc),
                "success": False,
            },
        ) from exc


@router.post("/upload-data", response_model=UploadDataResponse)
async def upload_data(payload: UploadDataRequest):
    record_id = upload_record_service.create_upload_record(
        payload.csv_file_path,
        payload.zip_file_path,
        source="api",
    )
    try:
        return await run_in_threadpool(
            upload_service.upload_data,
            csv_path=payload.csv_file_path,
            zip_path=payload.zip_file_path,
            upload_record_id=record_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error in upload-data: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal server error",
                "error": str(exc),
            },
        )


@router.post("/upload-data/manual", response_model=UploadDataResponse)
async def upload_manual_data(
    csv_file: UploadFile = File(...),
    include_source_zip: bool = Form(False),
    all_files: bool = Form(False),
    meta: str | None = Form(None),
    source_files: list[UploadFile] | None = File(None),
):
    try:
        return await upload_service.upload_manual_data(
            csv_file=csv_file,
            include_source_zip=include_source_zip,
            all_files=all_files,
            meta=meta,
            source_files=source_files,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error in upload-data/manual: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal server error",
                "error": str(exc),
            },
        )


@router.get("/upload-records", response_model=UploadRecordListResponse)
async def get_upload_records(
    page: int = 1,
    page_size: int = 20,
    record_id: str | None = None,
    status: str | None = None,
    model: str | None = None,
    barcode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    return await run_in_threadpool(
        upload_record_service.get_upload_records,
        page=page,
        page_size=page_size,
        record_id=record_id,
        status=status,
        model=model,
        barcode=barcode,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/upload-record-stats", response_model=UploadRecordStatsResponse)
async def get_upload_record_stats(
    record_id: str | None = None,
    status: str | None = None,
    model: str | None = None,
    barcode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    return await run_in_threadpool(
        upload_record_service.get_upload_record_stats,
        record_id=record_id,
        status=status,
        model=model,
        barcode=barcode,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/upload-record-filter-options", response_model=UploadRecordFilterOptionsResponse)
async def get_upload_record_filter_options():
    return await run_in_threadpool(upload_record_service.get_upload_record_filter_options)


@router.get("/unit-tracker/rows", response_model=UnitTrackerRowsResponse)
async def get_unit_tracker_rows(
    page: int = 1,
    page_size: int = 100,
    product: str | None = None,
    test_type: str | None = None,
    barcode: str | None = None,
):
    return await run_in_threadpool(
        unit_tracker_service.list_rows,
        page=page,
        page_size=page_size,
        product=product,
        test_type=test_type,
        barcode=barcode,
    )


@router.post("/unit-tracker/sync", response_model=UnitTrackerSyncResponse)
async def sync_unit_tracker_rows(limit: int | None = Query(default=None, ge=1)):
    result = await run_in_threadpool(unit_tracker_service.sync_all_rows, limit=limit)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error") or "Unit tracker sync failed")
    return result


@router.get("/product-management/products", response_model=ProductManagementListResponse)
async def get_product_management_products(
    page: int = 1,
    page_size: int = 100,
    barcode: str | None = None,
    model: str | None = None,
    test_type: str | None = None,
    status: str | None = None,
):
    return await run_in_threadpool(
        product_management_service.get_products,
        page=page,
        page_size=page_size,
        barcode=barcode,
        model=model,
        test_type=test_type,
        status=status,
    )


@router.get("/product-management/filter-options", response_model=ProductManagementFilterOptionsResponse)
async def get_product_management_filter_options():
    return await run_in_threadpool(product_management_service.get_filter_options)


@router.post("/product-management/sync", response_model=ProductManagementSyncResponse)
async def sync_product_management_products():
    result = await run_in_threadpool(product_management_service.sync_products_from_upload_records)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error") or "Product sync failed")
    return result


@router.post("/product-management/manual-add", response_model=ProductManagementManualAddResponse)
async def add_manual_product_or_test(request: ProductManagementManualAddRequest):
    result = await run_in_threadpool(
        product_management_service.add_manual_product_or_test,
        request.model_dump() if hasattr(request, "model_dump") else request.dict(),
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error") or "Manual product add failed")
    return result


@router.put("/product-management/product-status", response_model=ProductStatusUpdateResponse)
async def update_product_status(request: ProductStatusUpdateRequest):
    result = await run_in_threadpool(
        product_management_service.update_product_status,
        barcode=request.barcode,
        status=request.status,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error") or "Product status update failed")
    return result


@router.post("/pull-folder", response_model=PullFolderResponse)
async def pull_folder(
    request: Request,
    csv_file: UploadFile = File(...),
    folder_name: str = Form(...),
    pull_method: str = Form("sftp", description="Pull method: sftp or scp"),
):
    try:
        robot_ip = request.client.host
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
    data = await run_in_threadpool(
        opentrons_control_service.reset_robot,
        ip,
        options=request.options,
        port=request.port,
    )
    return RobotActionResponse(success=True, message="Reset command sent", data=data)


@router.post("/robots/{ip}/control/reboot", response_model=RobotActionResponse)
async def reboot_robot(ip: str):
    result = await run_in_threadpool(opentrons_control_service.reboot_robot, ip)
    return RobotActionResponse(success=True, message=result.get("message"))


@router.get("/robots/{ip}/files", response_model=RobotFileListResponse)
async def list_robot_files(ip: str, path: str = "/"):
    try:
        return await run_in_threadpool(opentrons_control_service.list_robot_files, ip, path)
    except OpentronsSshError as exc:
        logger.warning("SSH file list failed for robot %s path %s: %s", ip, path, exc)
        raise HTTPException(status_code=502, detail={"message": f"SSH 目录读取失败: {exc}"}) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"message": f"目录不存在: {path}"}) from exc


@router.get("/robots/{ip}/files/content", response_model=RobotFileContentResponse)
async def read_robot_file(ip: str, path: str):
    try:
        return await run_in_threadpool(opentrons_control_service.read_robot_file, ip, path)
    except OpentronsSshError as exc:
        raise HTTPException(status_code=502, detail={"message": f"SSH 文件读取失败: {exc}"}) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"message": f"文件不存在: {path}"}) from exc


@router.put("/robots/{ip}/files/content", response_model=RobotActionResponse)
async def write_robot_file(ip: str, request: RobotFileWriteRequest):
    data = await run_in_threadpool(
        opentrons_control_service.write_robot_file,
        ip,
        request.path,
        request.content,
        create_if_missing=request.create_if_missing,
    )
    message = "File saved" if data.get("success") else "File skipped"
    return RobotActionResponse(success=bool(data.get("success")), message=message, data=data)


@router.post("/robots/{ip}/files/upload", response_model=RobotActionResponse)
async def upload_robot_file(
    ip: str,
    path: str = Form(...),
    file: UploadFile = File(...),
):
    content = await file.read()
    data = await run_in_threadpool(opentrons_control_service.upload_robot_file, ip, path, content)
    return RobotActionResponse(success=True, message="File uploaded", data=data)


@router.delete("/robots/{ip}/files", response_model=RobotActionResponse)
async def delete_robot_file(ip: str, path: str):
    await run_in_threadpool(opentrons_control_service.delete_robot_file, ip, path)
    return RobotActionResponse(success=True, message="Deleted")


@router.get("/robots/{ip}/files/download")
async def download_robot_file(ip: str, path: str):
    try:
        filename, content, media_type = await run_in_threadpool(
            opentrons_control_service.download_robot_file,
            ip,
            path,
        )
    except OpentronsSshError as exc:
        raise HTTPException(status_code=502, detail={"message": f"SSH 文件下载失败: {exc}"}) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"message": f"文件不存在: {path}"}) from exc
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/robots/{ip}/protocols", response_model=RobotProtocolListResponse)
async def list_robot_protocols(ip: str, port: int = setting.ROBOT_HEALTH_PORT):
    protocols = await run_in_threadpool(opentrons_protocols_service.list_protocols, ip, port)
    return RobotProtocolListResponse(protocols=protocols)


@router.get("/robots/{ip}/protocols/{protocol_id}/download")
async def download_robot_protocol(
    ip: str,
    protocol_id: str,
    format: str = Query("json", pattern="^(json|source)$"),
    port: int = setting.ROBOT_HEALTH_PORT,
):
    if format == "source":
        filename, content, media_type = await run_in_threadpool(
            opentrons_protocols_service.download_protocol_source,
            ip,
            protocol_id,
        )
    else:
        filename, content = await run_in_threadpool(
            opentrons_protocols_service.download_protocol_bundle,
            ip,
            protocol_id,
            port,
        )
        media_type = "application/json"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/robots/{ip}/protocols/upload", response_model=RobotActionResponse)
async def upload_robot_protocol(
    ip: str,
    files: list[UploadFile] = File(...),
    key: str | None = Form(None),
    protocol_kind: str | None = Form(None),
    port: int = setting.ROBOT_HEALTH_PORT,
):
    file_payloads: list[tuple[str, bytes]] = []
    for upload in files:
        content = await upload.read()
        file_payloads.append((upload.filename or "protocol.py", content))
    data = await run_in_threadpool(
        opentrons_protocols_service.upload_protocol,
        ip,
        file_payloads,
        key=key,
        protocol_kind=protocol_kind,
        port=port,
    )
    return RobotActionResponse(success=True, message="Protocol uploaded", data=data)


@router.post("/robots/{ip}/protocols/{protocol_id}/analyze", response_model=RobotActionResponse)
async def analyze_robot_protocol(ip: str, protocol_id: str, request: RobotProtocolAnalyzeRequest):
    analyses = await run_in_threadpool(
        opentrons_protocols_service.analyze_protocol,
        ip,
        protocol_id,
        body=request.body,
        port=request.port,
    )
    return RobotActionResponse(success=True, message="Analysis started", data={"analyses": analyses})


@router.get("/robots/{ip}/protocols/{protocol_id}/analyses", response_model=RobotActionResponse)
async def get_robot_protocol_analyses(ip: str, protocol_id: str, port: int = setting.ROBOT_HEALTH_PORT):
    analyses = await run_in_threadpool(
        opentrons_protocols_service.list_protocol_analyses,
        ip,
        protocol_id,
        port,
    )
    return RobotActionResponse(success=True, data={"analyses": analyses})


@router.get("/robots/{ip}/runs", response_model=RobotRunListResponse)
async def list_robot_runs(ip: str, port: int = setting.ROBOT_HEALTH_PORT):
    runs = await run_in_threadpool(opentrons_protocols_service.list_runs, ip, port)
    return RobotRunListResponse(runs=runs)


@router.post("/robots/{ip}/runs", response_model=RobotActionResponse)
async def create_robot_run(ip: str, request: RobotRunCreateRequest):
    result = await run_in_threadpool(
        opentrons_protocols_service.create_and_play_run,
        ip,
        request.protocol_id,
        request.port,
    )
    return RobotActionResponse(success=True, message="Run created and started", data=result)


@router.post("/robots/{ip}/runs/{run_id}/actions", response_model=RobotActionResponse)
async def control_robot_run(ip: str, run_id: str, request: RobotRunActionRequest):
    action = await run_in_threadpool(
        opentrons_protocols_service.run_control_action,
        ip,
        run_id,
        request.action_type,
        request.port,
    )
    return RobotActionResponse(success=True, message="Run action sent", data=action)
