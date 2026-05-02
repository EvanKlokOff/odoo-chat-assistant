# src/tasks/worker_startup.py
import asyncio
import logging
from src.database.session import engine

logger = logging.getLogger(__name__)

# Global event loop for the worker
_worker_loop = None


def on_worker_start():
    """Callback при старте worker'а - инициализируем один event loop"""
    global _worker_loop
    logger.info("🚀 Worker starting, initializing event loop...")

    try:
        _worker_loop = asyncio.get_running_loop()
    except RuntimeError:
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)

    logger.info(f"✅ Event loop created: {id(_worker_loop)}")


def on_worker_shutdown():
    """Callback при остановке worker'а"""
    global _worker_loop
    logger.info("🛑 Worker shutting down, cleaning up...")

    async def cleanup():
        await engine.dispose()

    if _worker_loop and not _worker_loop.is_closed():
        if _worker_loop.is_running():
            asyncio.create_task(cleanup())
        else:
            _worker_loop.run_until_complete(cleanup())

    logger.info("✅ Cleanup completed")