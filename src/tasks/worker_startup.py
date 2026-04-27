# src/tasks/worker_startup.py
import asyncio
import logging
from src.database.session import engine

logger = logging.getLogger(__name__)


def on_worker_start():
    """Callback при старте worker'а - инициализируем event loop"""
    logger.info("🚀 Worker starting, initializing event loop...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    logger.info("✅ Event loop created and set")


def on_worker_shutdown():
    """Callback при остановке worker'а - чистим ресурсы"""
    logger.info("🛑 Worker shutting down, cleaning up...")
    loop = asyncio.get_event_loop()

    # Закрываем соединения в пуле
    async def cleanup():
        await engine.dispose()

    if loop.is_running():
        asyncio.create_task(cleanup())
    else:
        loop.run_until_complete(cleanup())

    loop.close()
    logger.info("✅ Cleanup completed")