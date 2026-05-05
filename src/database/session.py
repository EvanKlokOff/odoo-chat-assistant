from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text, NullPool
from src.config import settings
from src.database.models import Base
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)

# Convert postgresql:// to postgresql+asyncpg://
async_db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")

# Настройки пула соединений
engine = create_async_engine(
    async_db_url,
    echo=settings.debug,  # Лучше использовать отдельную настройку
    # pool=NullPool,
    pool_size=5,  # Размер пула
    max_overflow=10,  # Максимум дополнительных соединений
    pool_pre_ping=False,  # Проверять соединения перед использованием
    pool_recycle=300,  # Пересоздавать соединения каждый час
    pool_use_lifo=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)


def get_engine():
    """
    Получить engine для текущего контекста.
    В worker процессах использует process-local engine из worker_startup.
    В основном процессе создает отдельный engine.
    """
    # Пытаемся получить worker-specific engine
    try:
        from src.tasks.worker_startup import get_worker_engine
        return get_worker_engine()
    except (ImportError, AttributeError):
        # Вне worker контекста (например, в FastAPI) создаем свой engine
        from sqlalchemy.ext.asyncio import create_async_engine

        async_db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")

        return create_async_engine(
            async_db_url,
            echo=settings.debug,
            pool_size=10,  # Больше соединений для API
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_use_lifo=True,
            pool_timeout=30,
        )


def get_session_local():
    """Получить sessionmaker для текущего контекста"""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlalchemy.ext.asyncio import AsyncSession

    return async_sessionmaker(
        get_engine(),
        expire_on_commit=False,
        class_=AsyncSession
    )


async def get_db() -> AsyncGenerator[AsyncSession, Any]:
    """Dependency для FastAPI endpoints"""
    # async with AsyncSessionLocal() as session:
    async with get_session_local()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, Any]:
    """Context manager для использования вне FastAPI"""
    # async with AsyncSessionLocal() as session:
    async with get_session_local()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Создание всех таблиц"""
    engine = get_engine()
    async with engine.begin() as conn:
        # Включить pgvector extension если нужно
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Закрытие соединений"""
    engine = get_engine()
    await engine.dispose()


async def check_database_connection() -> bool:
    """
    Проверяет соединение с базой данных.

    Returns:
        True если соединение успешно, False в противном случае
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            logger.debug("Database connection check successful")
            return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False
