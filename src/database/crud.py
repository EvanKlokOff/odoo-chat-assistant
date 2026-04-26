import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy import func
from src.database import models
from src.database.session import get_db_context


logger = logging.getLogger(__name__)


# src/database/crud.py - добавьте эти ДВА метода в конец файла

async def delete_chunks_by_chat(chat_id: str) -> int:
    """
    Удаляет все чанки сообщений чата

    Args:
        chat_id: ID чата

    Returns:
        Количество удаленных чанков
    """
    from src.database.models import MessageChunk

    async with get_db_context() as db:
        # Получаем все чанки чата
        stmt = select(MessageChunk).where(MessageChunk.chat_id == chat_id)
        result = await db.execute(stmt)
        chunks = result.scalars().all()

        count = len(chunks)
        for chunk in chunks:
            await db.delete(chunk)

        await db.commit()
        return count


async def get_chunks_count_by_chat(chat_id: str) -> int:
    """
    Получает количество чанков в чате

    Args:
        chat_id: ID чата

    Returns:
        Количество чанков
    """
    from src.database.models import MessageChunk

    async with get_db_context() as db:
        stmt = select(func.count()).select_from(MessageChunk).where(
            MessageChunk.chat_id == chat_id
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

async def get_message_by_db_id(db_id: int) -> models.Message|None:
    """Get message by internal database ID"""
    from src.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        stmt = select(models.Message).where(models.Message.id == db_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


async def get_messages_without_embeddings(chat_id: str|None = None, limit: int = 100) -> list[models.Message]:
    """Получает сообщения без эмбеддингов"""
    from src.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        # LEFT JOIN для поиска сообщений без чанков
        stmt = select(models.Message).outerjoin(
            models.MessageChunk, models.Message.id == models.MessageChunk.message_id
        ).where(models.MessageChunk.id == None)

        if chat_id:
            stmt = stmt.where(models.Message.chat_id == chat_id)

        stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        return result.scalars().all()

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
) -> models.Message:
    """Save a single message to database"""
    async with get_db_context() as db:
        message = models.Message(
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
        date_end: datetime | None = None,
        limit: int | None = None,
        offset: int = 0,
        order_desc: bool = False
) -> list[models.Message]:
    """
    Get messages from a specific chat with optional filters

    Args:
        chat_id: ID чата
        date_start: Начальная дата (включительно)
        date_end: Конечная дата (включительно)
        limit: Максимальное количество сообщений (None - все)
        offset: Смещение для пагинации
        order_desc: Если True - сортировка от новых к старым, иначе от старых к новым

    Returns:
        Список сообщений
    """
    async with get_db_context() as db:
        stmt = select(models.Message).where(models.Message.chat_id == chat_id)

        # Фильтры по датам
        if date_start:
            stmt = stmt.where(models.Message.timestamp >= date_start)
        if date_end:
            stmt = stmt.where(models.Message.timestamp <= date_end)

        # Сортировка
        if order_desc:
            stmt = stmt.order_by(models.Message.timestamp.desc())
        else:
            stmt = stmt.order_by(models.Message.timestamp.asc())

        # Пагинация
        if offset > 0:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        messages = result.scalars().all()

        # Если сортировка была от новых к старым, возвращаем в хронологическом порядке
        if order_desc and limit is not None:
            messages = list(reversed(messages))

        return messages


# Добавьте эти функции в crud.py

async def get_chats_by_user(user_id: int) -> list[dict]:
    """Get all chats where user has messages"""

    async with get_db_context() as db:
        # Находим все chat_id, где есть сообщения от этого пользователя
        stmt = select(models.Message.chat_id, models.Message.chat_title).where(
            models.Message.sender_id == str(user_id)
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
        stmt = select(models.Message.chat_title).where(models.Message.chat_id == chat_id).limit(1)
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
        stmt = select(models.Message).where(models.Message.chat_id == chat_id)

        if date_start:
            stmt = stmt.where(models.Message.timestamp >= date_start)
        if date_end:
            stmt = stmt.where(models.Message.timestamp <= date_end)

        stmt = stmt.order_by(models.Message.timestamp)
        result = await db.execute(stmt)
        return result.scalars().all()


# Добавьте в crud.py после существующих импортов
from sqlalchemy import and_, update
from src.database.models import UserChat, UserSettings


async def add_user_chat(user_id: int, chat_id: str, chat_title: str | None = None):
    """Add or update user-chat relationship"""
    async with get_db_context() as db:
        logger.info(f"add_user_chat: user={user_id}, chat={chat_id}, title={chat_title}")
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
            logger.info(f"Created new user_chat record for user {user_id}, chat {chat_id}")
        else:
            logger.info(f"UserChat already exists for user {user_id}, chat {chat_id}")
            # Обновляем название чата если нужно
            if user_chat.chat_title != chat_title and chat_title:
                user_chat.chat_title = chat_title
                await db.flush()
                logger.info(f"Updated chat title to {chat_title}")
        return user_chat


async def get_user_chats(user_id: int) -> list[dict]:
    """Get all chats for a user"""
    async with get_db_context() as db:
        stmt = select(UserChat).where(
            UserChat.user_id == str(user_id)
        ).order_by(UserChat.last_used.desc())

        result = await db.execute(stmt)
        user_chats = result.scalars().all()
        logger.info(f"Found {len(user_chats)} chats for user {user_id}")
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
        stmt = select(models.Message.chat_title).where(
            models.Message.chat_id == chat_id
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