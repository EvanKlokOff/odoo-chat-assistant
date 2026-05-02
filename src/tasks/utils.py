# src/tasks/utils.py
import asyncio
import functools
from typing import Callable
import logging

logger = logging.getLogger(__name__)


def async_celery_task(max_retries: int = 3, default_retry_delay: int = 60):
    """
    Декоратор для асинхронных Celery задач БЕЗ bind=True

    Для prefork pool: каждый процесс создает свой event loop
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Создаем НОВЫЙ event loop для каждой задачи
            # Это важно для prefork pool
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(func(*args, **kwargs))
            except Exception as e:
                logger.error(f"Async task failed: {e}", exc_info=True)
                raise
            finally:
                # Обязательно закрываем loop
                loop.close()

        return wrapper

    return decorator


def async_celery_task_bind(max_retries: int = 3, default_retry_delay: int = 60):
    """
    Декоратор для асинхронных Celery задач С bind=True
    Поддерживает self и retry

    Для prefork pool: каждый процесс создает свой event loop
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(func(self, *args, **kwargs))
            except Exception as e:
                logger.error(f"Async task failed: {e}", exc_info=True)

                # Retry если нужно
                if hasattr(self, 'retry'):
                    current_retries = getattr(self.request, 'retries', 0)
                    if current_retries < max_retries:
                        raise self.retry(exc=e, countdown=default_retry_delay)
                raise
            finally:
                loop.close()

        return wrapper

    return decorator