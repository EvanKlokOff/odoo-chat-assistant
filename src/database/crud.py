import logging
from datetime import datetime
from sqlalchemy import select

from database.session import get_db_context
from src.database.models import Message
from src.database.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def save_message(
        chat_id: str,
        chat_title: str | None,
        sender_id: str,
        sender_name: str,
        content: str,
        timestamp: datetime,
        reply_to_message_id: str,
        message_id: str | None = None,
        platform: str = "telegram"
) -> Message:
    """Save a single message to database"""
    async with get_db_context() as db:
        message = Message(
            message_id=message_id or str(timestamp.timestamp()),  # fallback if no message_id
            chat_id=chat_id,
            chat_title=chat_title or f"Chat_{chat_id}",
            sender_id=sender_id,
            sender_name=sender_name,
            content=content,
            timestamp=timestamp,
            platform=platform,
            reply_to_message_id=reply_to_message_id  # нужно добавить это поле в модель
        )
        db.add(message)
        await db.flush()  # Отправляем в БД, получаем ID
        await db.refresh(message)
        return message


async def get_chat_messages(
        chat_id: str,
        date_start: datetime | None = None,
        date_end: datetime | None = None
):
    """Get messages from a specific chat with optional date filter"""
    async with get_db_context() as db:
        stmt = select(Message).filter_by(chat_id = chat_id)

        if date_start:
            stmt = stmt.where(Message.timestamp >= date_start)
        if date_end:
            stmt = stmt.where(Message.timestamp <= date_end)

        stmt = stmt.order_by(Message.timestamp)
        result = await db.execute(stmt)
        return result.scalars().all()