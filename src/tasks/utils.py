# src/tasks/utils.py
import asyncio
import functools
from typing import Callable
import logging

logger = logging.getLogger(__name__)

# Store event loop per thread/process
_loop_cache = {}


def get_or_create_loop():
    """Get or create event loop for current thread/process"""
    import threading
    thread_id = threading.get_ident()

    if thread_id not in _loop_cache or _loop_cache[thread_id].is_closed():
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        _loop_cache[thread_id] = loop

    return _loop_cache[thread_id]


def async_celery_task(max_retries: int = 3, default_retry_delay: int = 60):
    """Декоратор для асинхронных Celery задач БЕЗ bind=True"""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Use persistent loop per thread
            loop = get_or_create_loop()

            try:
                # Ensure we're not calling run_until_complete on a running loop
                if loop.is_running():
                    # Create new loop if current is running
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    return new_loop.run_until_complete(func(*args, **kwargs))
                else:
                    return loop.run_until_complete(func(*args, **kwargs))
            except Exception as e:
                logger.error(f"Async task failed: {e}", exc_info=True)
                raise
            # DON'T close the loop - keep it for reuse

        return wrapper

    return decorator


def async_celery_task_bind(max_retries: int = 3, default_retry_delay: int = 60):
    """Декоратор для асинхронных Celery задач С bind=True"""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            loop = get_or_create_loop()

            try:
                if loop.is_running():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    return new_loop.run_until_complete(func(self, *args, **kwargs))
                else:
                    return loop.run_until_complete(func(self, *args, **kwargs))
            except Exception as e:
                logger.error(f"Async task failed: {e}", exc_info=True)

                if hasattr(self, 'retry'):
                    current_retries = getattr(self.request, 'retries', 0)
                    if current_retries < max_retries:
                        raise self.retry(exc=e, countdown=default_retry_delay)
                raise
            # DON'T close the loop

        return wrapper

    return decorator