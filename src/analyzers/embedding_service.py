# src/analyzers/embedding_service.py
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select, func, desc, delete
from src.database.session import get_db_context
from src.database.models import Message, MessageChunk
from src.llm.factory import LLMFactory
from src.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        self.embedding_provider = None
        self.chunk_size = 1000  # символов на чанк
        self.chunk_overlap = 100

    async def _get_provider(self):
        if self.embedding_provider is None:
            self.embedding_provider = LLMFactory.create_embedding_provider(
                provider_type=settings.embedding_provider,
                model=settings.ollama_embedding_model,
                base_url=settings.ollama_base_url
            )
        return self.embedding_provider

    def split_text(self, text: str, message_id: int, chat_id: str, timestamp: datetime) -> List[MessageChunk]:
        """Разбивает текст на чанки"""
        chunks = []
        text_len = len(text)

        for i in range(0, text_len, self.chunk_size - self.chunk_overlap):
            chunk_text = text[i:i + self.chunk_size]
            if len(chunk_text.strip()) < 50:  # Пропускаем короткие
                continue

            chunk = MessageChunk(
                chat_id=chat_id,
                message_id=message_id,
                chunk_index=i // (self.chunk_size - self.chunk_overlap),
                chunk_text=chunk_text,
                timestamp=timestamp
            )
            chunks.append(chunk)

        return chunks

    async def generate_embeddings_for_messages(self, messages: List[Message]) -> int:
        """Генерирует эмбеддинги для сообщений"""
        provider = await self._get_provider()

        # Создаем чанки
        all_chunks = []
        for msg in messages:
            if msg.content and len(msg.content) > 100:
                chunks = self.split_text(msg.content, msg.id, msg.chat_id, msg.timestamp)
                all_chunks.extend(chunks)

        if not all_chunks:
            return 0

        # Параллельная генерация эмбеддингов
        texts = [chunk.chunk_text for chunk in all_chunks]
        embeddings = await provider.embed_batch(texts)

        # Присваиваем эмбеддинги
        for chunk, embedding in zip(all_chunks, embeddings):
            chunk.embedding = embedding

        # Сохраняем в БД
        async with get_db_context() as db:
            # Удаляем старые чанки для этих сообщений
            message_ids = [msg.id for msg in messages]
            stmt = delete(MessageChunk).where(MessageChunk.message_id.in_(message_ids))
            await db.execute(stmt)

            db.add_all(all_chunks)
            await db.commit()

        logger.info(f"Generated {len(all_chunks)} embeddings for {len(messages)} messages")
        return len(all_chunks)

    async def retrieve_relevant_messages(
            self,
            chat_id: str,
            query: str,
            date_start: Optional[str] = None,
            date_end: Optional[str] = None,
            limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Поиск релевантных сообщений через векторное сходство"""
        provider = await self._get_provider()

        # Эмбеддинг запроса
        query_embedding = await provider.embed(query)

        async with get_db_context() as db:
            # Базовый запрос
            chunk_subq = (
                select(
                    MessageChunk.message_id,
                    MessageChunk.chunk_text,
                    MessageChunk.timestamp,
                    Message.sender_name,
                    MessageChunk.cosine_similarity(query_embedding).label("similarity")
                )
                .join(Message, MessageChunk.message_id == Message.id)
                .where(MessageChunk.chat_id == chat_id)
                .where(MessageChunk.embedding.isnot(None))
            )

            # Фильтр по датам
            if date_start:
                chunk_subq = chunk_subq.where(Message.timestamp >= datetime.fromisoformat(date_start))
            if date_end:
                chunk_subq = chunk_subq.where(Message.timestamp <= datetime.fromisoformat(date_end))

            chunk_subq = chunk_subq.subquery()

            stmt = (
                select(
                    chunk_subq.c.message_id,
                    func.string_agg(chunk_subq.c.chunk_text, ' ').label("content"),
                    func.max(chunk_subq.c.timestamp).label("timestamp"),
                    func.max(chunk_subq.c.sender_name).label("sender_name"),
                    func.max(chunk_subq.c.similarity).label("max_similarity"),
                    func.count(chunk_subq.c.message_id).label("chunks_count")
                )
                .group_by(chunk_subq.c.message_id)
                .having(func.max(chunk_subq.c.similarity) > 0.3)
                .order_by(desc("max_similarity"))
                .limit(limit)
            )

            result = await db.execute(stmt)
            rows = result.fetchall()

            if not rows:
                logger.warning("No results from vector search, using fallback")
                return await self._fallback_retrieval(chat_id, date_start, date_end, limit)

            result_list = []
            for row in rows:
                result_list.append({
                    "content": row.content[:1000] if row.content else "",
                    "timestamp": row.timestamp.isoformat(),
                    "sender_name": row.sender_name,
                    "similarity": float(row.max_similarity) if row.max_similarity else 0,
                    "chunks_count": row.chunks_count
                })

            logger.info(f"Vector search (optimized) found {len(result_list)} relevant messages")
            return result_list


    async def _fallback_retrieval(
            self,
            chat_id: str,
            date_start: Optional[str] = None,
            date_end: Optional[str] = None,
            limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Fallback: берем последние сообщения если векторный поиск не нашел ничего"""
        from src.database import crud

        messages = await crud.get_chat_messages(
            chat_id=chat_id,
            limit=limit,
            date_start=datetime.fromisoformat(date_start) if date_start else None,
            date_end=datetime.fromisoformat(date_end) if date_end else None,
            order_desc=True
        )

        return [
            {
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "sender_name": msg.sender_name,
                "similarity": 0
            }
            for msg in messages
        ]
# Глобальный экземпляр
embedding_service = EmbeddingService()