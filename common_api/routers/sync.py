from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.sql import distinct
from datetime import datetime
import logging

from common_api.utils import get_db, verify_admin_key
from common_api.schemas import SyncStatusResponse
from src.database import models

router = APIRouter(prefix="/sync", tags=["sync"])
logger = logging.getLogger(__name__)


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status(
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_admin_key),
):
    """Get synchronization status"""
    # Get counts
    users_stmt = select(func.count(distinct(models.Message.sender_id)))
    users_result = await db.execute(users_stmt)
    users_count = users_result.scalar() or 0

    chats_stmt = select(func.count(distinct(models.Message.chat_id)))
    chats_result = await db.execute(chats_stmt)
    chats_count = chats_result.scalar() or 0

    messages_stmt = select(func.count(models.Message.id))
    messages_result = await db.execute(messages_stmt)
    messages_count = messages_result.scalar() or 0

    # Get pending tasks
    tasks_stmt = select(func.count(models.AnalysisTask.id)).where(
        models.AnalysisTask.status.in_(['pending', 'running'])
    )
    tasks_result = await db.execute(tasks_stmt)
    pending_tasks = tasks_result.scalar() or 0

    return SyncStatusResponse(
        last_sync=datetime.utcnow(),
        users_count=users_count,
        chats_count=chats_count,
        messages_count=messages_count,
        pending_tasks=pending_tasks
    )


@router.post("/refresh")
async def refresh_data(
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_admin_key),
):
    """Force refresh cache/data"""
    # Clear cache logic here
    return {"success": True, "message": "Refresh initiated"}


@router.get("/changes")
async def get_changes(
        since: datetime = Query(...),
        limit: int = Query(100, ge=1, le=1000),
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_admin_key),
):
    """Get changes since last sync"""
    new_messages_stmt = select(models.Message).where(
        models.Message.timestamp > since
    ).order_by(models.Message.timestamp.desc()).limit(limit)

    result = await db.execute(new_messages_stmt)
    messages = result.scalars().all()

    return {
        "since": since.isoformat(),
        "new_messages_count": len(messages),
        "new_messages": [
            {
                "id": msg.id,
                "chat_id": msg.chat_id,
                "content": msg.content[:200],
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in messages[:100]
        ]
    }
