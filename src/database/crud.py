import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy import func

from database.session import get_db_context
from src.database.models import Message


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


# Добавьте эти функции в crud.py

async def get_chats_by_user(user_id: int) -> list[dict]:
    """Get all chats where user has messages"""
    from sqlalchemy import distinct
    from src.database.session import get_db_context

    async with get_db_context() as db:
        # Находим все chat_id, где есть сообщения от этого пользователя
        stmt = select(Message.chat_id, Message.chat_title).where(
            Message.sender_id == str(user_id)
        ).distinct()

        result = await db.execute(stmt)
        chats = []
        seen = set()

        for chat_id, chat_title in result.all():
            if chat_id not in seen:
                chats.append({
                    "chat_id": chat_id,
                    "title": chat_title or f"Chat_{chat_id}"
                })
                seen.add(chat_id)

        return chats


async def get_chat_by_id(chat_id: str) -> dict | None:
    """Get chat info by ID"""
    from src.database.session import get_db_context

    async with get_db_context() as db:
        stmt = select(Message.chat_title).where(Message.chat_id == chat_id).limit(1)
        result = await db.execute(stmt)
        title = result.scalar_one_or_none()

        if title:
            return {"chat_id": chat_id, "title": title}
        return None


async def get_chat_messages_by_chat_id(
        chat_id: str,
        date_start: datetime | None = None,
        date_end: datetime | None = None
):
    """Get messages from specific chat with date filter"""
    async with get_db_context() as db:
        stmt = select(Message).where(Message.chat_id == chat_id)

        if date_start:
            stmt = stmt.where(Message.timestamp >= date_start)
        if date_end:
            stmt = stmt.where(Message.timestamp <= date_end)

        stmt = stmt.order_by(Message.timestamp)
        result = await db.execute(stmt)
        return result.scalars().all()


# Добавьте в crud.py после существующих импортов
from sqlalchemy import and_, update
from src.database.models import UserChat, UserSettings


async def add_user_chat(user_id: int, chat_id: str, chat_title: str | None = None):
    """Add or update user-chat relationship"""
    async with get_db_context() as db:
        # Проверяем, существует ли связь
        stmt = select(UserChat).where(
            and_(
                UserChat.user_id == str(user_id),
                UserChat.chat_id == chat_id
            )
        )
        result = await db.execute(stmt)
        user_chat = result.scalar_one_or_none()

        if not user_chat:
            # Создаем новую связь
            user_chat = UserChat(
                user_id=str(user_id),
                chat_id=chat_id,
                chat_title=chat_title or f"Chat_{chat_id}",
                selected=0
            )
            db.add(user_chat)
            await db.flush()

        return user_chat


async def get_user_chats(user_id: int) -> list[dict]:
    """Get all chats for a user"""
    async with get_db_context() as db:
        stmt = select(UserChat).where(
            UserChat.user_id == str(user_id)
        ).order_by(UserChat.last_used.desc())

        result = await db.execute(stmt)
        user_chats = result.scalars().all()

        return [
            {
                "chat_id": uc.chat_id,
                "title": uc.chat_title or f"Chat_{uc.chat_id}",
                "selected": uc.selected,
                "last_used": uc.last_used
            }
            for uc in user_chats
        ]


async def get_user_selected_chat(user_id: int) -> str | None:
    """Get currently selected chat for user"""
    async with get_db_context() as db:
        # Сначала проверяем в настройках пользователя
        stmt = select(UserSettings).where(UserSettings.user_id == str(user_id))
        result = await db.execute(stmt)
        settings = result.scalar_one_or_none()

        if settings and settings.selected_chat_id:
            # Проверяем, что чат все еще существует для пользователя
            chat_stmt = select(UserChat).where(
                and_(
                    UserChat.user_id == str(user_id),
                    UserChat.chat_id == settings.selected_chat_id
                )
            )
            chat_result = await db.execute(chat_stmt)
            if chat_result.scalar_one_or_none():
                return settings.selected_chat_id

        # Если нет выбранного чата, берем последний использованный
        stmt = select(UserChat).where(
            UserChat.user_id == str(user_id)
        ).order_by(UserChat.last_used.desc()).limit(1)

        result = await db.execute(stmt)
        last_chat = result.scalar_one_or_none()

        return last_chat.chat_id if last_chat else None


async def set_user_selected_chat(user_id: int, chat_id: str):
    """Set selected chat for user"""
    async with get_db_context() as db:
        # Обновляем или создаем настройки пользователя
        stmt = select(UserSettings).where(UserSettings.user_id == str(user_id))
        result = await db.execute(stmt)
        settings = result.scalar_one_or_none()

        if settings:
            settings.selected_chat_id = chat_id
        else:
            settings = UserSettings(
                user_id=str(user_id),
                selected_chat_id=chat_id
            )
            db.add(settings)

        # Обновляем флаг selected в UserChat
        # Сначала сбрасываем все selected для этого пользователя
        await db.execute(
            update(UserChat).where(
                UserChat.user_id == str(user_id)
            ).values(selected=0)
        )

        # Устанавливаем selected для выбранного чата
        await db.execute(
            update(UserChat).where(
                and_(
                    UserChat.user_id == str(user_id),
                    UserChat.chat_id == chat_id
                )
            ).values(selected=1, last_used=func.now())
        )

        await db.flush()


async def update_chat_last_used(user_id: int, chat_id: str):
    """Update last_used timestamp for a chat"""
    async with get_db_context() as db:
        stmt = select(UserChat).where(
            and_(
                UserChat.user_id == str(user_id),
                UserChat.chat_id == chat_id
            )
        )
        result = await db.execute(stmt)
        user_chat = result.scalar_one_or_none()

        if user_chat:
            user_chat.last_used = func.now()
            await db.flush()


async def get_chat_info_by_id(chat_id: str) -> dict | None:
    """Get chat info by ID from messages"""
    async with get_db_context() as db:
        stmt = select(Message.chat_title).where(
            Message.chat_id == chat_id
        ).limit(1)
        result = await db.execute(stmt)
        title = result.scalar_one_or_none()

        if title:
            return {"chat_id": chat_id, "title": title}

        # Если нет сообщений, пробуем получить из UserChat
        stmt = select(UserChat.chat_title).where(
            UserChat.chat_id == chat_id
        ).limit(1)
        result = await db.execute(stmt)
        title = result.scalar_one_or_none()

        return {"chat_id": chat_id, "title": title} if title else None