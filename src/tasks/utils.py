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
            # Проверяем, нет ли цикла событий в текущем потоке
            try:
                loop = asyncio.get_running_loop()
                # Если цикл уже запущен, создаем новый в отдельном потоке
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        lambda: asyncio.run(func(task_self, *args, **kwargs))
                    )
                    return future.result()
            except RuntimeError:
                # Нет запущенного цикла - создаем новый
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(func(task_self, *args, **kwargs))
                finally:
                    loop.close()

        # Сохраняем оригинальную асинхронную функцию для прямого вызова
        wrapper._async_func = func
        wrapper._is_async = True

        return wrapper

    return decorator
