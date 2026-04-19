from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from src.config import settings
from src.database.models import Base
from contextlib import asynccontextmanager

# Convert postgresql:// to postgresql+asyncpg://
async_db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")

# Настройки пула соединений
engine = create_async_engine(
    async_db_url,
    echo=settings.debug,  # Лучше использовать отдельную настройку
    pool_size=20,  # Размер пула
    max_overflow=10,  # Максимум дополнительных соединений
    pool_pre_ping=True,  # Проверять соединения перед использованием
    pool_recycle=3600,  # Пересоздавать соединения каждый час
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)


async def get_db() -> AsyncGenerator[AsyncSession, Any]:
    """Dependency для FastAPI endpoints"""
    async with AsyncSessionLocal() as session:
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
    async with AsyncSessionLocal() as session:
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
    async with engine.begin() as conn:
        # Включить pgvector extension если нужно
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Закрытие соединений"""
    await engine.dispose()
