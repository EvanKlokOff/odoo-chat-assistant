# src/tasks/celery_app.py
from celery import Celery
from celery.schedules import crontab
from src.config import settings
import logging

logger = logging.getLogger(__name__)

# Создаем Celery приложение
celery_app = Celery(
    "chat_assistant",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "src.tasks.embedding_tasks",
    ]
)

# Оптимальные настройки для Celery
celery_app.conf.update(
    # Сериализация
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Временные зоны
    timezone="UTC",
    enable_utc=True,

    # Отслеживание задач
    task_track_started=True,
    task_send_sent_event=True,

    # Таймауты (30 минут на задачу)
    task_time_limit=30 * 60,  # 30 минут максимум
    task_soft_time_limit=25 * 60,  # 25 минут до мягкого таймаута

    # Retry настройки
    task_acks_late=True,  # Подтверждение после выполнения
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,  # 60 секунд до ретрая
    task_max_retries=3,

    # Производительность воркера
    worker_prefetch_multiplier=1,  # Не перегружаем воркеры
    worker_max_tasks_per_child=100,  # Перезапуск воркера после 100 задач
    worker_cancel_long_running_tasks_on_connection_loss=True,

    # Результаты
    result_expires=3600,  # Результаты живут 1 час
    result_compression="gzip",
    result_extended=True,

    # Очереди
    task_default_queue="default",
    task_queues={
        "default": {
            "exchange": "default",
            "routing_key": "default",
        },
        "embeddings": {
            "exchange": "embeddings",
            "routing_key": "embeddings",
        },
        "high_priority": {
            "exchange": "high_priority",
            "routing_key": "high_priority",
        },
    },

    # Маршрутизация по умолчанию
    task_default_exchange="default",
    task_default_routing_key="default",

    # Логирование
    worker_redirect_stdouts_level="INFO",
    worker_hijack_root_logger=False,

    # Безопасность
    task_protocol=2,
    result_accept_content=["json"],
)

# Периодические задачи (для Celery Beat - опционально)
celery_app.conf.beat_schedule = {
    # Каждые 5 минут проверяем пропущенные эмбеддинги
    "generate-missing-embeddings": {
        "task": "generate_missing_embeddings",
        "schedule": 300.0,  # 5 минут
        "options": {"queue": "embeddings"}
    },
    # Каждый час очищаем старые результаты
    "cleanup-old-results": {
        "task": "celery.backend_cleanup",
        "schedule": crontab(minute=0, hour="*/1"),
    },
}

logger.info(f"✅ Celery app configured with broker: {celery_app.conf.broker_url}")
logger.info(f"   Queues: {list(celery_app.conf.task_queues.keys())}")