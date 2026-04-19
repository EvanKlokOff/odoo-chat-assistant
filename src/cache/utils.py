# src/context/redis_context_manager.py
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from src.cache.redis_client import redis_client
from src.llm.base import Message

logger = logging.getLogger(__name__)


class ContextType(str, Enum):
    """Типы контекста"""
    GENERAL = "general"
    REVIEW = "review"
    COMPLIANCE = "compliance"
    CHAT_ANALYSIS = "chat_analysis"


@dataclass
class ContextMessage:
    """Сообщение в контексте"""
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: datetime
    metadata: Optional[Dict] = None

    def to_dict(self):
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata or {}
        }

    @classmethod
    def from_dict(cls, data: Dict):
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {})
        )


class RedisContextManager:
    """
    Асинхронный менеджер контекста с использованием Redis
    Использует Redis Lists и Hashes для эффективного хранения
    """

    def __init__(
            self,
            default_ttl: int = 3600,  # 1 час по умолчанию
            max_context_messages: int = 100,
            context_window_minutes: int = 60
    ):
        self.default_ttl = default_ttl
        self.max_context_messages = max_context_messages
        self.context_window = timedelta(minutes=context_window_minutes)

    def _get_context_key(self, chat_id: str, user_id: str, context_type: ContextType) -> str:
        """Сгенерировать ключ для контекста"""
        return f"context:{chat_id}:{user_id}:{context_type.value}"

    def _get_metadata_key(self, chat_id: str, user_id: str, context_type: ContextType) -> str:
        """Сгенерировать ключ для метаданных контекста"""
        return f"context:meta:{chat_id}:{user_id}:{context_type.value}"

    def _get_session_key(self, session_id: str) -> str:
        """Сгенерировать ключ для сессии"""
        return f"session:{session_id}"

    async def add_message(
            self,
            chat_id: str,
            user_id: str,
            context_type: ContextType,
            message: ContextMessage,
            ttl: Optional[int] = None
    ) -> bool:
        """
        Добавить сообщение в контекст (асинхронно)
        Использует Redis List для хранения сообщений в порядке добавления
        """
        try:
            key = self._get_context_key(chat_id, user_id, context_type)
            ttl = ttl or self.default_ttl

            # Добавляем сообщение в список
            message_dict = message.to_dict()
            await redis_client.lpush(key, message_dict)

            # Обрезаем список до максимального размера
            await redis_client.ltrim(key, 0, self.max_context_messages - 1)

            # Устанавливаем TTL
            await redis_client.expire(key, ttl)

            # Обновляем метаданные
            await self._update_metadata(chat_id, user_id, context_type, ttl)

            logger.debug(f"Added message to context for user {user_id} in chat {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add message to Redis context: {e}")
            return False

    async def get_context(
            self,
            chat_id: str,
            user_id: str,
            context_type: ContextType,
            limit: Optional[int] = None,
            include_old: bool = False
    ) -> List[ContextMessage]:
        """
        Получить контекст (асинхронно)
        Возвращает сообщения в хронологическом порядке
        """
        try:
            key = self._get_context_key(chat_id, user_id, context_type)
            limit = limit or self.max_context_messages

            # Получаем сообщения из Redis List (в обратном порядке)
            raw_messages = await redis_client.lrange(key, 0, limit - 1)

            # Преобразуем в объекты ContextMessage
            messages = []
            cutoff_time = datetime.now() - self.context_window

            for msg_dict in raw_messages:
                message = ContextMessage.from_dict(msg_dict)

                # Фильтруем по времени если нужно
                if include_old or message.timestamp >= cutoff_time:
                    messages.append(message)

            # Возвращаем в хронологическом порядке
            return list(reversed(messages))

        except Exception as e:
            logger.error(f"Failed to get context from Redis: {e}")
            return []

    async def get_context_for_llm(
            self,
            chat_id: str,
            user_id: str,
            context_type: ContextType,
            max_tokens: int = 2000
    ) -> List[Message]:
        """
        Получить контекст в формате для LLM (асинхронно)
        С учетом ограничения по токенам
        """
        messages = await self.get_context(chat_id, user_id, context_type)

        llm_messages = []
        total_chars = 0

        # Идем с конца (самые свежие сообщения)
        for msg in reversed(messages):
            msg_text = f"{msg.role}: {msg.content}"

            if total_chars + len(msg_text) > max_tokens:
                break

            llm_messages.append(Message(
                role=msg.role,
                content=msg.content
            ))
            total_chars += len(msg_text)

        # Возвращаем в правильном порядке
        return list(reversed(llm_messages))

    async def clear_context(
            self,
            chat_id: str,
            user_id: str,
            context_type: ContextType
    ) -> bool:
        """Очистить контекст (асинхронно)"""
        try:
            key = self._get_context_key(chat_id, user_id, context_type)
            meta_key = self._get_metadata_key(chat_id, user_id, context_type)

            await redis_client.delete(key)
            await redis_client.delete(meta_key)

            logger.info(f"Cleared context for user {user_id} in chat {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to clear context: {e}")
            return False

    async def _update_metadata(
            self,
            chat_id: str,
            user_id: str,
            context_type: ContextType,
            ttl: int
    ) -> None:
        """Обновить метаданные контекста"""
        try:
            meta_key = self._get_metadata_key(chat_id, user_id, context_type)

            metadata = {
                "last_updated": datetime.now().isoformat(),
                "context_type": context_type.value,
                "chat_id": chat_id,
                "user_id": user_id,
                "message_count": await self._get_message_count(chat_id, user_id, context_type)
            }

            await redis_client.hset(meta_key, "metadata", metadata)
            await redis_client.expire(meta_key, ttl)

        except Exception as e:
            logger.error(f"Failed to update metadata: {e}")

    async def _get_message_count(
            self,
            chat_id: str,
            user_id: str,
            context_type: ContextType
    ) -> int:
        """Получить количество сообщений в контексте"""
        try:
            key = self._get_context_key(chat_id, user_id, context_type)
            return await redis_client.redis.llen(key)
        except Exception as e:
            logger.error(f"Failed to get message count: {e}")
            return 0

    async def get_context_summary(
            self,
            chat_id: str,
            user_id: str,
            context_type: ContextType
    ) -> Dict[str, Any]:
        """Получить сводку по контексту"""
        try:
            meta_key = self._get_metadata_key(chat_id, user_id, context_type)
            metadata = await redis_client.hgetall(meta_key)

            if not metadata:
                return {"exists": False}

            messages = await self.get_context(chat_id, user_id, context_type, limit=10)

            return {
                "exists": True,
                "metadata": metadata.get("metadata", {}),
                "recent_messages": [msg.to_dict() for msg in messages[-5:]],
                "total_messages": len(messages)
            }

        except Exception as e:
            logger.error(f"Failed to get context summary: {e}")
            return {"exists": False, "error": str(e)}


class RedisSessionManager:
    """Управление сессиями в Redis"""

    def __init__(self, session_ttl: int = 7200):  # 2 часа по умолчанию
        self.session_ttl = session_ttl

    def _get_session_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def create_session(
            self,
            chat_id: str,
            user_id: str,
            session_type: ContextType,
            metadata: Optional[Dict] = None
    ) -> str:
        """Создать новую сессию"""
        import uuid
        session_id = str(uuid.uuid4())

        session_data = {
            "session_id": session_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "session_type": session_type.value,
            "created_at": datetime.now().isoformat(),
            "metadata": metadata or {},
            "message_count": 0
        }

        key = self._get_session_key(session_id)
        await redis_client.set(key, session_data, self.session_ttl)

        logger.info(f"Created session {session_id} for user {user_id}")
        return session_id

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Получить данные сессии"""
        key = self._get_session_key(session_id)
        return await redis_client.get(key)

    async def update_session(
            self,
            session_id: str,
            update_data: Dict[str, Any]
    ) -> bool:
        """Обновить сессию"""
        key = self._get_session_key(session_id)
        session = await redis_client.get(key)

        if not session:
            return False

        session.update(update_data)
        session["updated_at"] = datetime.now().isoformat()

        # Увеличиваем счетчик сообщений
        if "message_count" in update_data:
            session["message_count"] = update_data["message_count"]
        else:
            session["message_count"] = session.get("message_count", 0) + 1

        await redis_client.set(key, session, self.session_ttl)
        return True

    async def end_session(self, session_id: str) -> bool:
        """Завершить сессию"""
        key = self._get_session_key(session_id)
        session = await redis_client.get(key)

        if session:
            session["ended_at"] = datetime.now().isoformat()
            session["is_active"] = False
            # Сохраняем с коротким TTL для истории
            await redis_client.set(key, session, 300)  # 5 минут
            logger.info(f"Ended session {session_id}")

        return True

    async def get_active_sessions(
            self,
            chat_id: str,
            user_id: str
    ) -> List[Dict]:
        """Получить активные сессии пользователя"""
        # Используем паттерн для поиска сессий
        pattern = f"session:*"
        keys = await redis_client.redis.keys(pattern)

        sessions = []
        for key in keys:
            session = await redis_client.get(key)
            if (session and
                    session.get("chat_id") == chat_id and
                    session.get("user_id") == user_id and
                    not session.get("ended_at")):
                sessions.append(session)

        return sessions


# Глобальные экземпляры
redis_context_manager = RedisContextManager()
redis_session_manager = RedisSessionManager()