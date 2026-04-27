# src/tasks/utils.py
import asyncio
import functools
from typing import Callable, Any
from celery import Task
import logging

logger = logging.getLogger(__name__)

# Глобальный event loop для всех Celery задач
_global_loop = None


def get_or_create_event_loop():
    """Получить или создать глобальный event loop"""
    global _global_loop
    if _global_loop is None or _global_loop.is_closed():
        _global_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_global_loop)
    return _global_loop


def async_celery_task(max_retries: int = 3, default_retry_delay: int = 60):
    """
    Декоратор для запуска асинхронных функций в Celery задачах
    Использует глобальный event loop для переиспользования соединений
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(task_self: Task, *args, **kwargs):
            loop = get_or_create_event_loop()

            try:
                # Запускаем асинхронную функцию в глобальном loop'е
                return loop.run_until_complete(func(task_self, *args, **kwargs))
            except Exception as e:
                logger.error(f"Async task failed: {e}", exc_info=True)
                if hasattr(task_self, 'retry'):
                    raise task_self.retry(exc=e, max_retries=max_retries, countdown=default_retry_delay)
                raise

        wrapper._async_func = func
        wrapper._is_async = True
        return wrapper

    return decorator