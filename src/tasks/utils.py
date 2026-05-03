# src/tasks/utils.py
import asyncio
import functools
from typing import Callable
import logging

logger = logging.getLogger(__name__)


def async_celery_task(max_retries: int = 3, default_retry_delay: int = 60):
    """Декоратор для асинхронных Celery задач БЕЗ bind=True"""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Пытаемся получить существующий loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Loop уже запущен, создаем task
                    return asyncio.create_task(func(*args, **kwargs))
                else:
                    # Loop существует но не запущен
                    return loop.run_until_complete(func(*args, **kwargs))
            except RuntimeError:
                # Нет event loop, создаем новый
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(func(*args, **kwargs))
                finally:
                    loop.close()

        return wrapper

    return decorator


def async_celery_task_bind(max_retries: int = 3, default_retry_delay: int = 60):
    """Декоратор для асинхронных Celery задач С bind=True"""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Пытаемся получить существующий loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Loop уже запущен, создаем task
                    return asyncio.create_task(func(self, *args, **kwargs))
                else:
                    # Loop существует но не запущен
                    return loop.run_until_complete(func(self, *args, **kwargs))
            except RuntimeError:
                # Нет event loop, создаем новый
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(func(self, *args, **kwargs))
                except Exception as e:
                    logger.error(f"Async task failed: {e}", exc_info=True)
                    if hasattr(self, 'retry') and hasattr(self, 'request'):
                        current_retries = getattr(self.request, 'retries', 0)
                        if current_retries < max_retries:
                            raise self.retry(exc=e, countdown=default_retry_delay)
                    raise
                finally:
                    # Не закрываем loop, если он не был создан здесь
                    pass

        return wrapper

    return decorator