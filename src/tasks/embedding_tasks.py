# src/tasks/embedding_tasks.py
import logging
from typing import List, Optional
from src.tasks.celery_app import celery_app
from src.analyzers.embedding_service import embedding_service
from src.database import crud
from src.tasks.utils import async_celery_task, async_celery_task_bind

logger = logging.getLogger(__name__)


@celery_app.task(
    name="generate_message_embeddings",
    queue="embeddings",
    bind=True,
)
@async_celery_task_bind(max_retries=3, default_retry_delay=60)
async def generate_message_embeddings(self, message_db_id: int) -> dict:
    """
    Генерация эмбеддингов для одного сообщения

    Args:
        message_db_id: ID сообщения в БД
    """
    """Генерация эмбеддингов для одного сообщения"""

    message = await crud.get_message_by_db_id(message_db_id)

    if not message:
        logger.error(f"Message {message_db_id} not found")
        return {"status": "error", "error": "Message not found", "message_id": message_db_id}

    # Генерируем эмбеддинги
    chunks_count = await embedding_service.generate_embeddings_for_messages([message])

    logger.info(f"✅ Generated {chunks_count} embeddings for message {message_db_id}")

    return {
        "status": "success",
        "message_id": message_db_id,
        "chunks_generated": chunks_count
    }


@celery_app.task(
    name="generate_batch_embeddings",
    queue="embeddings",
    rate_limit="10/m",  # Не более 10 задач в минуту
    bind=True
)
def generate_batch_embeddings(self, message_ids: List[int]) -> dict:
    """
    Массовая генерация эмбеддингов для нескольких сообщений
    (синхронная обертка, так как просто вызывает другие задачи)
    """
    results = []
    for msg_id in message_ids:
        result = generate_message_embeddings.delay(msg_id)
        results.append({
            "message_id": msg_id,
            "task_id": result.id
        })

    logger.info(f"📦 Scheduled {len(results)} embedding tasks")
    return {
        "status": "success",
        "scheduled": len(results),
        "tasks": results
    }


@celery_app.task(
    name="generate_missing_embeddings",
    queue="embeddings",
    rate_limit="30/m",
)
@async_celery_task(max_retries=2)
async def generate_missing_embeddings(chat_id: Optional[str] = None, limit: int = 100):
    """
    Генерация эмбеддингов для всех сообщений без эмбеддингов

    Args:
        chat_id: ID чата (опционально)
        limit: Максимум сообщений за раз
    """
    messages = await crud.get_messages_without_embeddings(chat_id=chat_id, limit=limit)

    if not messages:
        logger.info("No messages without embeddings found")
        return {"status": "success", "processed": 0}

    # Генерируем эмбеддинги для всех найденных сообщений
    chunks_count = await embedding_service.generate_embeddings_for_messages(messages)

    logger.info(f"📦 Generated embeddings for {len(messages)} missing messages, chunks={chunks_count}")

    return {
        "status": "success",
        "processed": len(messages),
        "chunks_generated": chunks_count
    }


@celery_app.task(
    name="reindex_chat_embeddings",
    queue="embeddings",
    bind=True
)
@async_celery_task_bind(max_retries=3, default_retry_delay=60)
async def reindex_chat_embeddings(self, chat_id: str) -> dict:
    """
    Переиндексация всех сообщений часта (удаляет старые и создает новые эмбеддинги)

    Args:
        chat_id: ID чата
    """
    logger.info(f"🔄 Starting reindex for chat {chat_id}")

    # Получаем все сообщения чата через CRUD
    messages = await crud.get_chat_messages(chat_id=chat_id)

    if not messages:
        logger.warning(f"No messages found for chat {chat_id}")
        return {"status": "error", "error": "No messages found", "chat_id": chat_id}

    # 2. Получаем количество старых чанков (НУЖНО ДОБАВИТЬ)
    old_chunks_count = await crud.get_chunks_count_by_chat(chat_id)
    logger.info(f"Found {old_chunks_count} existing chunks")
    # 3. Удаляем старые чанки (НУЖНО ДОБАВИТЬ)
    deleted_count = await crud.delete_chunks_by_chat(chat_id)
    logger.info(f"Deleted {deleted_count} old chunks")

    # 4. Генерируем новые эмбеддинги
    chunks_count = await embedding_service.generate_embeddings_for_messages(messages)

    result = {
        "status": "success",
        "chat_id": chat_id,
        "messages_processed": len(messages),
        "chunks_generated": chunks_count,
        "old_chunks_deleted": deleted_count
    }

    logger.info(f"✅ Reindex completed: {result}")
    return result
