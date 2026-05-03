# src/tasks/worker_startup.py
import asyncio
import logging
import os
from src.config import settings

logger = logging.getLogger(__name__)

# Процесс-локальные переменные
_worker_loop = None
_worker_engine = None
_worker_session_local = None

def get_or_create_event_loop():
    """Получить или создать event loop для текущего процесса"""
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        try:
            _worker_loop = asyncio.get_event_loop()
        except RuntimeError:
            _worker_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_worker_loop)
    return _worker_loop

def get_worker_engine():
    """Получить engine для текущего worker процесса"""
    global _worker_engine
    if _worker_engine is None:
        from sqlalchemy.ext.asyncio import create_async_engine

        async_db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")

        loop = get_or_create_event_loop()

        _worker_engine = create_async_engine(
            async_db_url,
            echo=settings.debug,
            # Настройки пула для одного процесса
            pool_size=2,  # 2 соединения на процесс
            max_overflow=3,  # +3 дополнительных при нужде
            pool_pre_ping=True,  # Проверять соединения перед использованием
            pool_recycle=3600,  # Пересоздавать каждый час
            pool_use_lifo=True,  # LIFO для лучшей производительности
            pool_timeout=30,  # Таймаут получения соединения
        )
        logger.info(f"✅ Created DB engine for process {os.getpid()} in loop {id(loop)}")

    return _worker_engine


def get_worker_session_local():
    """Получить sessionmaker для текущего worker процесса"""
    global _worker_session_local
    if _worker_session_local is None:
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from sqlalchemy.ext.asyncio import AsyncSession

        _worker_session_local = async_sessionmaker(
            get_worker_engine(),
            expire_on_commit=False,
            class_=AsyncSession
        )
    return _worker_session_local


def on_worker_start():
    """Callback при старте worker процесса"""
    global _worker_loop
    logger.info(f"🚀 Worker process {os.getpid()} starting...")

    # Создаем event loop для этого процесса
    try:
        _worker_loop = asyncio.get_running_loop()
    except RuntimeError:
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)

    # Инициализируем engine в этом процессе
    engine = get_worker_engine()

    logger.info(f"✅ Worker {os.getpid()} initialized with loop {id(_worker_loop)}")


def on_worker_shutdown():
    """Callback при остановке worker процесса"""
    global _worker_loop, _worker_engine, _worker_session_local
    logger.info(f"🛑 Worker process {os.getpid()} shutting down...")

    async def cleanup():
        if _worker_engine:
            await _worker_engine.dispose()
            logger.info(f"✅ DB engine disposed for process {os.getpid()}")

    if _worker_loop and not _worker_loop.is_closed():
        try:
            if _worker_loop.is_running():
                asyncio.create_task(cleanup())
            else:
                _worker_loop.run_until_complete(cleanup())
        except Exception as e:
            logger.error(f"Error during cleanup in process {os.getpid()}: {e}")

    _worker_engine = None
    _worker_session_local = None
    _worker_loop = None