from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from typing import List, Optional
from datetime import datetime
import logging

from common_api.utils import get_db, verify_api_key, get_pagination
from common_api.schemas import (
    ChatResponse, ChatDetailResponse, MessageResponse, PaginatedResponse, UserResponse
)
from src.database import models
from src.database.crud import get_chunks_count_by_chat

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chats", tags=["chats"])


@router.get("/", response_model=List[ChatResponse])
async def get_all_chats(
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_api_key),
        search: Optional[str] = Query(None, description="Search by chat title"),
        limit: int = Query(100, le=500),
        offset: int = Query(0, ge=0),
):
    """Get all chats from messages"""
    stmt = select(
        models.Message.chat_id,
        models.Message.chat_title,
        func.max(models.Message.timestamp).label('last_used')
    ).group_by(models.Message.chat_id, models.Message.chat_title)

    if search:
        stmt = stmt.where(models.Message.chat_title.ilike(f"%{search}%"))

    stmt = stmt.order_by(func.max(models.Message.timestamp).desc())
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)

    chats = []
    for chat_id, chat_title, last_used in result.all():
        if chat_id:
            message_count = await get_chunks_count_by_chat(chat_id)
            chats.append(ChatResponse(
                chat_id=chat_id,
                title=chat_title or f"Chat_{chat_id}",
                last_used=last_used,
                message_count=message_count
            ))

    return chats


@router.get("/{chat_id}", response_model=ChatDetailResponse)
async def get_chat_detail(
        chat_id: str,
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_api_key),
):
    """Get detailed chat information"""
    # Get chat info
    stmt = select(
        models.Message.chat_title,
        func.count(models.Message.id).label('message_count'),
        func.min(models.Message.timestamp).label('first_message'),
        func.max(models.Message.timestamp).label('last_message'),
        func.count(distinct(models.Message.sender_id)).label('user_count')
    ).where(models.Message.chat_id == chat_id).group_by(models.Message.chat_title)

    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail=f"Chat {chat_id} not found")

    chat_title, message_count, first_message, last_message, user_count = row

    # Get participants
    participants_stmt = select(
        distinct(models.Message.sender_id),
        models.Message.sender_name
    ).where(models.Message.chat_id == chat_id).limit(20)

    participants_result = await db.execute(participants_stmt)

    participants = [
        UserResponse(
            user_id=p[0],
            user_name=p[1] or f"User_{p[0]}"
        )
        for p in participants_result.all() if p[0]
    ]

    return ChatDetailResponse(
        chat_id=chat_id,
        title=chat_title or f"Chat_{chat_id}",
        message_count=message_count,
        first_message_date=first_message,
        last_message_date=last_message,
        user_count=user_count,
        participants=participants
    )


@router.get("/{chat_id}/messages", response_model=PaginatedResponse)
async def get_chat_messages_endpoint(
        chat_id: str,
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_api_key),
        start_date: Optional[datetime] = Query(None),
        end_date: Optional[datetime] = Query(None),
        page: int = Query(1, ge=1),
        per_page: int = Query(50, ge=1, le=200),
        order_desc: bool = Query(True, description="Order by timestamp descending"),
):
    """Get messages from a specific chat with pagination"""
    pagination = await get_pagination(page, per_page)

    # Build query
    stmt = select(models.Message).where(models.Message.chat_id == chat_id)

    if start_date:
        stmt = stmt.where(models.Message.timestamp >= start_date)
    if end_date:
        stmt = stmt.where(models.Message.timestamp <= end_date)

    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Order
    if order_desc:
        stmt = stmt.order_by(models.Message.timestamp.desc())
    else:
        stmt = stmt.order_by(models.Message.timestamp.asc())

    stmt = stmt.offset(pagination["offset"]).limit(pagination["limit"])

    result = await db.execute(stmt)
    messages = result.scalars().all()

    items = [
        MessageResponse(
            id=msg.id,
            message_id=msg.message_id,
            sender_id=msg.sender_id,
            sender_name=msg.sender_name,
            content=msg.content[:1000] if len(msg.content) > 1000 else msg.content,
            timestamp=msg.timestamp,
            reply_to_message_id=msg.reply_to_message_id
        )
        for msg in messages
    ]

    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination["page"],
        per_page=pagination["per_page"],
        total_pages=(total + pagination["per_page"] - 1) // pagination["per_page"]
    )
