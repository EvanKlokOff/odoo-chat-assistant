# common_api/routers/messages.py (исправленный)
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from common_api.utils import get_db, verify_api_key, get_pagination
from common_api.schemas import (
    MessageResponse, MessageWithChunksResponse, PaginatedResponse
)
from src.database import models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/", response_model=PaginatedResponse)
async def get_all_messages(
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_api_key),
        chat_id: Optional[str] = Query(None, description="Filter by chat ID"),
        sender_id: Optional[str] = Query(None, description="Filter by sender ID"),
        start_date: Optional[datetime] = Query(None, description="Start date filter"),
        end_date: Optional[datetime] = Query(None, description="End date filter"),
        search: Optional[str] = Query(None, description="Search in content"),
        page: int = Query(1, ge=1),
        per_page: int = Query(50, ge=1, le=200),
        order_desc: bool = Query(True, description="Order by timestamp descending"),
):
    """Get all messages with optional filters."""
    pagination = await get_pagination(page, per_page)

    stmt = select(models.Message)

    if chat_id:
        stmt = stmt.where(models.Message.chat_id == chat_id)
    if sender_id:
        stmt = stmt.where(models.Message.sender_id == sender_id)
    if start_date:
        stmt = stmt.where(models.Message.timestamp >= start_date)
    if end_date:
        stmt = stmt.where(models.Message.timestamp <= end_date)
    if search:
        stmt = stmt.where(models.Message.content.ilike(f"%{search}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

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
            sender_id=msg.sender_id or "",
            sender_name=msg.sender_name,
            content=msg.content[:500] if len(msg.content) > 500 else msg.content,
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


@router.get("/search", response_model=PaginatedResponse)
async def search_messages(
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_api_key),
        query: str = Query(..., min_length=1, description="Search query"),
        chat_id: Optional[str] = Query(None, description="Limit search to specific chat"),
        sender_id: Optional[str] = Query(None, description="Limit search to specific sender"),
        start_date: Optional[datetime] = Query(None),
        end_date: Optional[datetime] = Query(None),
        page: int = Query(1, ge=1),
        per_page: int = Query(50, ge=1, le=100),
):
    """Search messages by content using full-text search."""
    pagination = await get_pagination(page, per_page)

    stmt = select(models.Message).where(
        models.Message.content.ilike(f"%{query}%")
    )

    if chat_id:
        stmt = stmt.where(models.Message.chat_id == chat_id)
    if sender_id:
        stmt = stmt.where(models.Message.sender_id == sender_id)
    if start_date:
        stmt = stmt.where(models.Message.timestamp >= start_date)
    if end_date:
        stmt = stmt.where(models.Message.timestamp <= end_date)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(models.Message.timestamp.desc())
    stmt = stmt.offset(pagination["offset"]).limit(pagination["limit"])

    result = await db.execute(stmt)
    messages = result.scalars().all()

    items = [
        MessageResponse(
            id=msg.id,
            message_id=msg.message_id,
            sender_id=msg.sender_id or "",
            sender_name=msg.sender_name,
            content=highlight_content(msg.content, query)[:500] if len(msg.content) > 500 else highlight_content(
                msg.content, query),
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


@router.get("/{message_id}", response_model=MessageWithChunksResponse)
async def get_message_by_id(
        message_id: int,
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_api_key),
        include_chunks: bool = Query(False, description="Include message chunks"),
):
    """Get a specific message by its database ID."""
    stmt = select(models.Message).where(models.Message.id == message_id)
    result = await db.execute(stmt)
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail=f"Message {message_id} not found")

    chunks = None
    if include_chunks:
        chunks_stmt = select(models.MessageChunk).where(
            models.MessageChunk.message_id == message_id
        ).order_by(models.MessageChunk.chunk_index)
        chunks_result = await db.execute(chunks_stmt)
        chunks = [chunk.chunk_text for chunk in chunks_result.scalars().all()]

    return MessageWithChunksResponse(
        id=message.id,
        message_id=message.message_id,
        sender_id=message.sender_id or "",
        sender_name=message.sender_name,
        content=message.content,
        timestamp=message.timestamp,
        reply_to_message_id=message.reply_to_message_id,
        chunks=chunks
    )


@router.get("/external/{external_message_id}", response_model=MessageResponse)
async def get_message_by_external_id(
        external_message_id: str,
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_api_key),
):
    """Get a message by its external ID (Telegram message ID)."""
    stmt = select(models.Message).where(models.Message.message_id == external_message_id)
    result = await db.execute(stmt)
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(
            status_code=404,
            detail=f"Message with external ID {external_message_id} not found"
        )

    return MessageResponse(
        id=message.id,
        message_id=message.message_id,
        sender_id=message.sender_id or "",
        sender_name=message.sender_name,
        content=message.content[:500] if len(message.content) > 500 else message.content,
        timestamp=message.timestamp,
        reply_to_message_id=message.reply_to_message_id
    )


@router.get("/by-chat/{chat_id}/recent", response_model=List[MessageResponse])
async def get_recent_messages(
        chat_id: str,
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_api_key),
        limit: int = Query(50, ge=1, le=200),
        before_timestamp: Optional[datetime] = Query(None, description="Get messages before this timestamp"),
):
    """Get recent messages from a specific chat."""
    stmt = select(models.Message).where(models.Message.chat_id == chat_id)

    if before_timestamp:
        stmt = stmt.where(models.Message.timestamp < before_timestamp)

    stmt = stmt.order_by(models.Message.timestamp.desc()).limit(limit)

    result = await db.execute(stmt)
    messages = result.scalars().all()
    messages = list(reversed(messages))

    return [
        MessageResponse(
            id=msg.id,
            message_id=msg.message_id,
            sender_id=msg.sender_id or "",
            sender_name=msg.sender_name,
            content=msg.content[:500] if len(msg.content) > 500 else msg.content,
            timestamp=msg.timestamp,
            reply_to_message_id=msg.reply_to_message_id
        )
        for msg in messages
    ]


@router.get("/conversation/{chat_id}", response_model=List[MessageResponse])
async def get_conversation_thread(
        chat_id: str,
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_api_key),
        start_message_id: Optional[int] = Query(None, description="Start from this message ID"),
        limit: int = Query(100, ge=1, le=500),
):
    """Get conversation thread from a chat."""
    stmt = select(models.Message).where(models.Message.chat_id == chat_id)

    if start_message_id:
        stmt = stmt.where(models.Message.id >= start_message_id)
        stmt = stmt.order_by(models.Message.timestamp.asc())
    else:
        stmt = stmt.order_by(models.Message.timestamp.desc())

    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    messages = result.scalars().all()

    if not start_message_id:
        messages = list(reversed(messages))

    return [
        MessageResponse(
            id=msg.id,
            message_id=msg.message_id,
            sender_id=msg.sender_id or "",
            sender_name=msg.sender_name,
            content=msg.content[:500] if len(msg.content) > 500 else msg.content,
            timestamp=msg.timestamp,
            reply_to_message_id=msg.reply_to_message_id
        )
        for msg in messages
    ]


def highlight_content(content: str, query: str) -> str:
    """Highlight search terms in content."""
    if query in content:
        return content.replace(query, f"**{query}**")
    return content


@router.delete("/{message_id}", response_model=dict)
async def delete_message(
        message_id: int,
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_api_key),
):
    """Delete a message and its associated chunks."""
    stmt = select(models.Message).where(models.Message.id == message_id)
    result = await db.execute(stmt)
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail=f"Message {message_id} not found")

    chunks_stmt = select(models.MessageChunk).where(
        models.MessageChunk.message_id == message_id
    )
    chunks_result = await db.execute(chunks_stmt)
    chunks = chunks_result.scalars().all()

    for chunk in chunks:
        await db.delete(chunk)

    await db.delete(message)
    await db.commit()

    return {
        "success": True,
        "deleted_message_id": message_id,
        "deleted_chunks_count": len(chunks)
    }


@router.get("/export/{chat_id}", response_model=dict)
async def export_chat_messages(
        chat_id: str,
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_api_key),
        format: str = Query("json", pattern="^(json|csv)$"),
        start_date: Optional[datetime] = Query(None),
        end_date: Optional[datetime] = Query(None),
):
    """Export chat messages in JSON or CSV format."""
    stmt = select(models.Message).where(models.Message.chat_id == chat_id)

    if start_date:
        stmt = stmt.where(models.Message.timestamp >= start_date)
    if end_date:
        stmt = stmt.where(models.Message.timestamp <= end_date)

    stmt = stmt.order_by(models.Message.timestamp.asc())

    result = await db.execute(stmt)
    messages = result.scalars().all()

    data = []
    for msg in messages:
        data.append({
            "id": msg.id,
            "message_id": msg.message_id,
            "sender_id": msg.sender_id,
            "sender_name": msg.sender_name,
            "content": msg.content,
            "timestamp": msg.timestamp.isoformat(),
            "reply_to_message_id": msg.reply_to_message_id
        })

    return {
        "chat_id": chat_id,
        "export_format": format,
        "total_messages": len(data),
        "date_range": {
            "start": start_date.isoformat() if start_date else None,
            "end": end_date.isoformat() if end_date else None
        },
        "data": data
    }
