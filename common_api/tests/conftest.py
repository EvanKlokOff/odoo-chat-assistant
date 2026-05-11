# common_api/tests/conftest.py
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

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

# Используем порт 8000 (как в Docker)
TEST_SERVER_URL = "http://127.0.0.1:8000"


@pytest.fixture(scope="session")
def test_server_url():
    """Возвращает URL тестового сервера."""
    try:
        response = requests.get(f"{TEST_SERVER_URL}/health", timeout=5)
        if response.status_code != 200:
            raise RuntimeError(f"Test server not healthy at {TEST_SERVER_URL}")
    except requests.RequestException as e:
        raise RuntimeError(
            f"Test server is not running at {TEST_SERVER_URL}. "
            f"Make sure Docker container is running: docker-compose up -d chat_api\n"
            f"Error: {e}"
        )
    return TEST_SERVER_URL


# Фикстура для мока Celery задач
@pytest.fixture(autouse=True)
def mock_celery_tasks():
    """Автоматически мокаем все Celery задачи для всех тестов"""
    with patch('src.tasks.analysis_tasks.run_review_analysis') as mock_review, \
            patch('src.tasks.analysis_tasks.run_compliance_analysis') as mock_compliance:
        # Настраиваем моки для delay
        mock_review.delay = MagicMock(return_value=None)
        mock_compliance.delay = MagicMock(return_value=None)

        yield {
            'review': mock_review,
            'compliance': mock_compliance
        }


# Фикстура для мока БД операций
@pytest.fixture(autouse=True)
def mock_database_operations():
    """Мокаем операции с БД для всех тестов"""
    with patch('src.database.crud.get_analysis_task', new_callable=AsyncMock) as mock_get_task, \
            patch('src.database.crud.create_analysis_task', new_callable=AsyncMock) as mock_create_task:
        # Настраиваем мок для get_analysis_task - возвращаем None для несуществующих задач
        async def mock_get_side_effect(task_id):
            if task_id == "non_existent_task_id_12345":
                return None
            # Для существующей задачи возвращаем мок
            mock_task = AsyncMock()
            mock_task.task_id = task_id
            mock_task.status = "completed"
            mock_task.progress = 100
            mock_task.result = {"summary": "Test result"}
            mock_task.error = None
            mock_task.created_at = datetime.now()
            mock_task.completed_at = datetime.now()
            return mock_task

        mock_get_task.side_effect = mock_get_side_effect
        mock_create_task.return_value = AsyncMock()

        yield {
            'get_task': mock_get_task,
            'create_task': mock_create_task
        }


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


@pytest.fixture
def create_sample_messages(setup_database):
    """Возвращает уже созданные тестовые сообщения."""
    return setup_database
