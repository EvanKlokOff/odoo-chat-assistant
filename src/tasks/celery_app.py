# src/tasks/celery_app.py
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready, worker_shutdown
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

# Остальные настройки остаются без изменений
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_send_sent_event=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,
    task_max_retries=3,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    result_expires=3600,
    result_compression="gzip",
    result_extended=True,
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
    task_default_exchange="default",
    task_default_routing_key="default",
    worker_redirect_stdouts_level="INFO",
    worker_hijack_root_logger=False,
    task_protocol=2,
    result_accept_content=["json"],
)

celery_app.conf.beat_schedule = {
    "generate-missing-embeddings": {
        "task": "generate_missing_embeddings",
        "schedule": 300.0,
        "options": {"queue": "embeddings"}
    },
    "cleanup-old-results": {
        "task": "celery.backend_cleanup",
        "schedule": crontab(minute=0, hour="*/1"),
    },
}


@worker_ready.connect
def on_worker_ready(**kwargs):
    """Инициализация при старте worker'а"""
    from src.tasks.worker_startup import on_worker_start
    on_worker_start()


@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    """Очистка при остановке worker'а"""
    from src.tasks.worker_startup import on_worker_shutdown
    on_worker_shutdown()


logger.info(f"✅ Celery app configured with broker: {celery_app.conf.broker_url}")
logger.info(f"   Queues: {list(celery_app.conf.task_queues.keys())}")