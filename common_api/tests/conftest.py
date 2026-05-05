# common_api/tests/conftest.py
import pytest
import asyncio
import os
import requests
from typing import Generator

# Устанавливаем переменные окружения для тестов
os.environ.setdefault("API_KEYS", "odoo_api_key_1,odoo_api_key_2,backup_api_key")
os.environ.setdefault("ADMIN_API_KEY", "your_admin_api_key")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:8000,http://localhost:8069")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://analyzer:secure_password@localhost:5432/chat_analyzer")

# URL тестового сервера (должен быть запущен вручную на порту 8001)
TEST_SERVER_URL = "http://127.0.0.1:8001"



@pytest.fixture(scope="session")
def test_server_url():
    """Возвращает URL тестового сервера."""
    # Проверяем, что сервер запущен
    try:
        response = requests.get(f"{TEST_SERVER_URL}/health", timeout=2)
        if response.status_code != 200:
            raise RuntimeError(f"Test server not healthy at {TEST_SERVER_URL}")
    except requests.RequestException as e:
        raise RuntimeError(
            f"Test server is not running at {TEST_SERVER_URL}. "
            f"Please start it manually with: python -m common_api.main\n"
            f"Error: {e}"
        )

    return TEST_SERVER_URL


@pytest.fixture
def api_client(test_server_url):
    """Возвращает функцию для выполнения запросов к API."""

    def request(method, path, **kwargs):
        url = f"{test_server_url}{path}"
        return requests.request(method, url, **kwargs)

    return request


@pytest.fixture
def api_key_headers():
    return {"Authorization": "Bearer odoo_api_key_1"}


@pytest.fixture
def admin_key_headers():
    return {"Authorization": "Bearer your_admin_api_key"}


@pytest.fixture
def sample_user():
    return {
        "user_id": "123456789",
        "user_name": "Test User",
        "telegram_id": "123456789"
    }


@pytest.fixture
def sample_chat():
    return {
        "chat_id": "-1001234567890",
        "chat_title": "Test Chat",
        "selected": False
    }


@pytest.fixture(scope="session")
def setup_database():
    """Однократная настройка базы данных с тестовыми данными."""
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    from src.database.models import Base, Message, UserChat
    from src.database.crud import save_message, add_user_chat
    from datetime import datetime

    async def _setup():
        # Создаём engine напрямую для тестов
        engine = create_async_engine(
            os.environ["DATABASE_URL"],
            echo=False
        )

        async with engine.begin() as conn:
            # Создаём все таблицы
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

            # Очищаем старые данные
            await conn.execute(text("DELETE FROM messages"))
            await conn.execute(text("DELETE FROM user_chats"))

            # Создаём тестовые данные с помощью прямых SQL запросов (быстрее и надёжнее)
            for i in range(10):
                await conn.execute(
                    text("""
                         INSERT INTO messages (message_id, chat_id, chat_title, sender_id, sender_name, content,
                                               timestamp, platform)
                         VALUES (:message_id, :chat_id, :chat_title, :sender_id, :sender_name, :content, :timestamp,
                                 :platform)
                         """),
                    {
                        "message_id": f"msg_{i}_{datetime.now().timestamp()}",
                        "chat_id": "-1001234567890",
                        "chat_title": "Test Chat",
                        "sender_id": "123456789",
                        "sender_name": "Test User",
                        "content": f"Test message content {i}",
                        "timestamp": datetime.now(),
                        "platform": "telegram"
                    }
                )

            # Добавляем связь пользователя с чатом
            await conn.execute(
                text("""
                     INSERT INTO user_chats (user_id, chat_id, chat_title, selected)
                     VALUES (:user_id, :chat_id, :chat_title, :selected)
                     """),
                {
                    "user_id": "123456789",
                    "chat_id": "-1001234567890",
                    "chat_title": "Test Chat",
                    "selected": 0
                }
            )

        await engine.dispose()

    asyncio.run(_setup())
    return True


@pytest.fixture
def create_sample_messages(setup_database):
    """Возвращает уже созданные тестовые сообщения."""
    return setup_database