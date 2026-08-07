from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.models import TestDataResponse
from modules.data_analysis import data as data_service
from modules.test_management.domain.execution import test_execution_manager
from modules.test_management.domain.execution.manager import (
    TestExecutionLimitError,
    TestExecutionNotFoundError,
    TestExecutionSshError,
    TestExecutionStateError,
)
from modules.test_management.domain.models import (
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
from modules.test_management.domain.services.test_case_service import (
    TestCaseValidationError,
    test_case_service,
)


router = APIRouter()

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
