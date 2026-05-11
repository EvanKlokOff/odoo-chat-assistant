from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
import uuid
import logging

from common_api.routers.utils import transform_result_for_odoo
from common_api.utils import verify_api_key
from common_api.schemas import (
    TaskStatusResponse, ComplianceByPeriodRequest, ReviewByPeriodRequest,
    ComplianceByPeriodResponse, ReviewByPeriodResponse, PeriodInfo,

)
from src.database.crud import (
    create_analysis_task,
    get_analysis_task
)
from src.database import enums

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/review/by-period", response_model=ReviewByPeriodResponse)
async def review_chat_by_period(
        request: ReviewByPeriodRequest,
        api_key: str = Depends(verify_api_key),
):
    """
    Get a review (overview) of chat conversation for a specific time period.

    Args:
        start_date: Start of analysis period
        end_date: End of analysis period

    Returns:
        A concise overview of the chat conversation
    """
    try:

        # Create async task
        task_id = str(uuid.uuid4())

        await create_analysis_task(
            user_id=request.user_id,
            chat_id=request.chat_id,
            task_type=enums.TaskType.REVIEW.value,
            task_id=task_id,
            date_start=request.start_date.isoformat(),
            date_end=request.end_date.isoformat()
        )

        from src.tasks.analysis_tasks import run_review_analysis
        # Run Celery task
        run_review_analysis.delay(
            user_id=request.user_id,
            chat_id=request.chat_id,
            date_start=request.start_date.isoformat(),
            date_end=request.end_date.isoformat(),
            task_id=task_id
        )

        period_info = PeriodInfo(
            task_id=task_id,
            status="processing",
            user_id=request.user_id,
            chat_id=request.chat_id,
            start_date=request.start_date,
            end_date=request.end_date,
            created_at=datetime.now(),
            check_status_url=f"/analysis/task/{task_id}"
        )

        return ReviewByPeriodResponse(
            success=True,
            message="Review analysis started successfully",
            task_id=task_id,
            period_info=period_info
        )

    except Exception as e:
        logger.error(f"Review by period failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== NEW: Period-based Compliance Check ==========

@router.post("/compliance/by-period", response_model=ComplianceByPeriodResponse)
async def check_compliance_by_period(
        request: ComplianceByPeriodRequest,
        api_key: str = Depends(verify_api_key),
):
    """
    Check if chat conversation complies with given instruction for a specific time period.

    Args:
        chat_id: ID of the chat to analyze
        instruction: Instruction/requirements to check compliance against
        start_date: Start of analysis period
        end_date: End of analysis period

    Returns:
        Compliance check result with explanation and violations
    """
    try:
        # Create async task
        task_id = str(uuid.uuid4())

        await create_analysis_task(
            user_id=request.user_id,
            chat_id=request.chat_id,
            task_type=enums.TaskType.COMPLIANCE.value,
            task_id=task_id,
            date_start=request.start_date.isoformat(),
            date_end=request.end_date.isoformat(),
            instruction=request.instruction
        )
        from src.tasks.analysis_tasks import run_compliance_analysis
        # Run Celery task
        run_compliance_analysis.delay(
            user_id=request.user_id,
            chat_id=request.chat_id,
            instruction=request.instruction,
            date_start=request.start_date.isoformat(),
            date_end=request.end_date.isoformat(),
            task_id=task_id
        )

        period_info = PeriodInfo(
            task_id=task_id,
            status="processing",
            user_id=request.user_id,
            chat_id=request.chat_id,
            start_date=request.start_date,
            end_date=request.end_date,
            created_at=datetime.now(),
            check_status_url=f"/analysis/task/{task_id}"
        )

        return ComplianceByPeriodResponse(
            success=True,
            message="Compliance analysis started successfully",
            task_id=task_id,
            period_info=period_info
        )

    except Exception as e:
        logger.error(f"Compliance by period failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
        task_id: str,
        api_key: str = Depends(verify_api_key),
):
    """Get analysis task status and result"""
    task = await get_analysis_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    logger.info(f"=== GET TASK STATUS ===")
    logger.info(f"Task ID: {task.task_id}")
    logger.info(f"Task type from DB: '{task.task_type}'")
    logger.info(f"Task type repr: {repr(task.task_type)}")
    logger.info(f"Task status: {task.status}")
    logger.info(f"Task result type: {type(task.result)}")

    result = transform_result_for_odoo(task.result, task.task_type)

    logger.info(f"Result: {result}")

    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status,
        progress=task.progress,
        result=result,
        error=task.error,
        created_at=task.created_at,
        completed_at=task.completed_at
    )


@router.get("/task/{task_id}/wait", response_model=TaskStatusResponse)
async def wait_for_task_completion(
        task_id: str,
        timeout: int = 300,
        api_key: str = Depends(verify_api_key),
):
    """
    Wait for task to complete (polling until done or timeout).
    """
    import asyncio

    start_time = datetime.now()

    while (datetime.now() - start_time).total_seconds() < timeout:
        task = await get_analysis_task(task_id)

        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        if task.status in ["completed", "failed"]:
            return TaskStatusResponse(
                task_id=task.task_id,
                status=task.status,
                progress=task.progress,
                result=task.result,
                error=task.error,
                created_at=task.created_at,
                completed_at=task.completed_at
            )

        await asyncio.sleep(2)

    # Timeout
    return TaskStatusResponse(
        task_id=task_id,
        status="timeout",
        progress=0,
        result=None,
        error="Task did not complete within timeout",
        created_at=task.created_at if task else datetime.now(),
        completed_at=None
    )
