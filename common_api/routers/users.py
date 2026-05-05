from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from typing import List, Optional
import logging

from common_api.utils import get_db, verify_api_key, get_pagination
from common_api.schemas import (
    UserResponse, UserDetailResponse, PaginatedResponse, MessageResponse, ChatResponse
)
from src.database import models
from src.database.crud import get_user_chats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=List[UserResponse])
async def get_users(
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_api_key),
        search: Optional[str] = Query(None, description="Search by user name"),
        limit: int = Query(100, le=500),
        offset: int = Query(0, ge=0),
):
    """
    Get all users from messages.
    Returns unique users who have sent messages.
    """
    # Get unique users from messages
    stmt = select(
        distinct(models.Message.sender_id),
        models.Message.sender_name
    )

    if search:
        stmt = stmt.where(models.Message.sender_name.ilike(f"%{search}%"))

    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    users = []

    for user_id, user_name in result.all():
        if user_id:
            users.append(UserResponse(
                user_id=user_id,
                user_name=user_name or f"User_{user_id}",
                telegram_id=user_id
            ))

    return users


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user_detail(
        user_id: str,
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_api_key),
):
    """Get detailed user information"""
    # Get user info
    stmt = select(
        models.Message.sender_name,
        func.count(models.Message.id).label('message_count')
    ).where(
        models.Message.sender_id == user_id
    ).group_by(models.Message.sender_name)

    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    user_name, message_count = row

    # Get last active date
    last_active_stmt = select(
        func.max(models.Message.timestamp)
    ).where(models.Message.sender_id == user_id)

    last_active_result = await db.execute(last_active_stmt)
    last_active = last_active_result.scalar()

    # Get user chats
    user_chats = await get_user_chats(int(user_id))

    return UserDetailResponse(
        user_id=user_id,
        user_name=user_name or f"User_{user_id}",
        telegram_id=user_id,
        chat_count=len(user_chats),
        message_count=message_count,
        last_active=last_active
    )


@router.get("/{user_id}/chats", response_model=List[ChatResponse])
async def get_user_chats_list(
        user_id: str,
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_api_key),
):
    """Get all chats for a specific user"""
    from src.database.crud import get_user_chats, get_chunks_count_by_chat

    chats = await get_user_chats(int(user_id))

    result = []
    for chat in chats:
        message_count = await get_chunks_count_by_chat(chat["chat_id"])
        result.append(ChatResponse(
            chat_id=chat["chat_id"],
            title=chat["title"],
            selected=chat.get("selected", False),
            last_used=chat.get("last_used"),
            message_count=message_count
        ))

    return result


@router.get("/{user_id}/messages", response_model=PaginatedResponse)
async def get_user_messages(
        user_id: str,
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_api_key),
        start_date: Optional[datetime] = Query(None),
        end_date: Optional[datetime] = Query(None),
        page: int = Query(1, ge=1),
        per_page: int = Query(50, ge=1, le=200),
):
    """Get all messages from a specific user with pagination"""

    pagination = await get_pagination(page, per_page)

    # Build query
    stmt = select(models.Message).where(
        models.Message.sender_id == user_id
    )

    if start_date:
        stmt = stmt.where(models.Message.timestamp >= start_date)
    if end_date:
        stmt = stmt.where(models.Message.timestamp <= end_date)

    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Get messages
    stmt = stmt.order_by(models.Message.timestamp.desc())
    stmt = stmt.offset(pagination["offset"]).limit(pagination["limit"])

    result = await db.execute(stmt)
    messages = result.scalars().all()

    items = [
        MessageResponse(
            id=msg.id,
            message_id=msg.message_id,
            sender_id=msg.sender_id,
            sender_name=msg.sender_name,
            content=msg.content[:500],
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
