# src/tasks/utils.py
import asyncio
import functools
from typing import Callable, Any
from celery import Task


def async_celery_task(max_retries: int = 3, default_retry_delay: int = 60):
    """
    Декоратор для запуска асинхронных функций в Celery задачах

    Usage:
        @celery_app.task
        @async_celery_task(max_retries=3)
        async def my_async_task(param: str) -> dict:
            # асинхронный код
            return {"status": "success"}
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(task_self: Task, *args, **kwargs):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                result = loop.run_until_complete(func(*args, **kwargs))
                return result
            except Exception as e:
                # Retry logic
                if task_self.request.retries < max_retries:
                    raise task_self.retry(
                        exc=e,
                        countdown=default_retry_delay * (task_self.request.retries + 1)
                    )
                return {"status": "error", "error": str(e)}
            finally:
                loop.close()

        return wrapper

    return decorator