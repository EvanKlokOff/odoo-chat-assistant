# common_api/tests/test_analysis.py
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from common_api.main import app

@pytest.mark.asyncio
async def test_review_by_period_success(sample_chat, mock_celery_tasks):
    """Test starting a review analysis for a period"""
    start_date = (datetime.now() - timedelta(days=1)).isoformat()
    end_date = datetime.now().isoformat()

    payload = {
        "user_id": 123456789,
        "chat_id": sample_chat["chat_id"],
        "start_date": start_date,
        "end_date": end_date
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/review/by-period",
            json=payload,
            headers={"Authorization": "Bearer odoo_api_key_1"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Review analysis started successfully" in data["message"]
    assert "task_id" in data
    assert data["task_id"] is not None
    assert "period_info" in data
    assert data["period_info"]["status"] == "processing"
    assert data["period_info"]["user_id"] == 123456789
    assert data["period_info"]["chat_id"] == sample_chat["chat_id"]

    # Проверяем, что Celery задача была вызвана
    mock_celery_tasks['review'].delay.assert_called_once()


@pytest.mark.asyncio
async def test_review_by_period_invalid_dates(sample_chat):
    """Test review with invalid date range (start_date after end_date)"""
    start_date = datetime.now().isoformat()
    end_date = (datetime.now() - timedelta(days=1)).isoformat()

    payload = {
        "user_id": 123456789,
        "chat_id": sample_chat["chat_id"],
        "start_date": start_date,
        "end_date": end_date
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/review/by-period",
            json=payload,
            headers={"Authorization": "Bearer odoo_api_key_1"}
        )

    assert response.status_code == 422

@pytest.mark.asyncio
async def test_review_by_period_missing_user_id(sample_chat):
    """Test review without user_id"""
    start_date = (datetime.now() - timedelta(days=1)).isoformat()
    end_date = datetime.now().isoformat()

    payload = {
        "chat_id": sample_chat["chat_id"],
        "start_date": start_date,
        "end_date": end_date
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/review/by-period",
            json=payload,
            headers={"Authorization": "Bearer odoo_api_key_1"}
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_review_by_period_missing_chat_id():
    """Test review without chat_id"""
    start_date = (datetime.now() - timedelta(days=1)).isoformat()
    end_date = datetime.now().isoformat()

    payload = {
        "user_id": 123456789,
        "start_date": start_date,
        "end_date": end_date
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/review/by-period",
            json=payload,
            headers={"Authorization": "Bearer odoo_api_key_1"}
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_compliance_by_period_success(sample_chat, mock_celery_tasks):
    """Test starting a compliance analysis for a period"""
    start_date = (datetime.now() - timedelta(days=1)).isoformat()
    end_date = datetime.now().isoformat()

    payload = {
        "user_id": 123456789,
        "chat_id": sample_chat["chat_id"],
        "instruction": "Check if the conversation follows business ethics rules",
        "start_date": start_date,
        "end_date": end_date
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/compliance/by-period",
            json=payload,
            headers={"Authorization": "Bearer odoo_api_key_1"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Compliance analysis started successfully" in data["message"]
    assert "task_id" in data
    assert data["task_id"] is not None
    assert "period_info" in data
    assert data["period_info"]["status"] == "processing"

    # Проверяем, что Celery задача была вызвана
    mock_celery_tasks['compliance'].delay.assert_called_once()

@pytest.mark.asyncio
async def test_compliance_by_period_missing_instruction(sample_chat):
    """Test compliance without instruction"""
    start_date = (datetime.now() - timedelta(days=1)).isoformat()
    end_date = datetime.now().isoformat()

    payload = {
        "user_id": 123456789,
        "chat_id": sample_chat["chat_id"],
        "start_date": start_date,
        "end_date": end_date
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/compliance/by-period",
            json=payload,
            headers={"Authorization": "Bearer odoo_api_key_1"}
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_compliance_by_period_invalid_instruction_too_short(sample_chat):
    """Test compliance with instruction too short"""
    start_date = (datetime.now() - timedelta(days=1)).isoformat()
    end_date = datetime.now().isoformat()

    payload = {
        "user_id": 123456789,
        "chat_id": sample_chat["chat_id"],
        "instruction": "short",
        "start_date": start_date,
        "end_date": end_date
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/compliance/by-period",
            json=payload,
            headers={"Authorization": "Bearer odoo_api_key_1"}
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_task_status_not_found():
    """Test getting status of non-existent task"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/analysis/task/non_existent_task_id_12345",
            headers={"Authorization": "Bearer odoo_api_key_1"}
        )

    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["error"]


@pytest.mark.asyncio
async def test_review_by_period_unauthorized(sample_chat):
    """Test review without API key"""
    start_date = (datetime.now() - timedelta(days=1)).isoformat()
    end_date = datetime.now().isoformat()

    payload = {
        "user_id": 123456789,
        "chat_id": sample_chat["chat_id"],
        "start_date": start_date,
        "end_date": end_date
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/review/by-period",
            json=payload
        )

    assert response.status_code == 401
    assert "Not authenticated" in response.json()["error"]


@pytest.mark.asyncio
async def test_review_by_period_invalid_api_key(sample_chat):
    """Test review with invalid API key"""
    start_date = (datetime.now() - timedelta(days=1)).isoformat()
    end_date = datetime.now().isoformat()

    payload = {
        "user_id": 123456789,
        "chat_id": sample_chat["chat_id"],
        "start_date": start_date,
        "end_date": end_date
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/review/by-period",
            json=payload,
            headers={"Authorization": "Bearer invalid_key"}
        )

    assert response.status_code == 403
    assert "Invalid API Key" in response.json()["error"]


@pytest.mark.asyncio
async def test_review_by_period_negative_user_id(sample_chat):
    """Test review with negative user_id"""
    start_date = (datetime.now() - timedelta(days=1)).isoformat()
    end_date = datetime.now().isoformat()

    payload = {
        "user_id": -1,
        "chat_id": sample_chat["chat_id"],
        "start_date": start_date,
        "end_date": end_date
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/review/by-period",
            json=payload,
            headers={"Authorization": "Bearer odoo_api_key_1"}
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_review_by_period_with_same_dates(sample_chat):
    """Test review with same start_date and end_date"""
    same_date = datetime.now().isoformat()

    payload = {
        "user_id": 123456789,
        "chat_id": sample_chat["chat_id"],
        "start_date": same_date,
        "end_date": same_date
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/review/by-period",
            json=payload,
            headers={"Authorization": "Bearer odoo_api_key_1"}
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_compliance_by_period_with_same_dates(sample_chat):
    """Test compliance with same start_date and end_date"""
    same_date = datetime.now().isoformat()

    payload = {
        "user_id": 123456789,
        "chat_id": sample_chat["chat_id"],
        "instruction": "Check if the conversation follows business ethics rules",
        "start_date": same_date,
        "end_date": same_date
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/compliance/by-period",
            json=payload,
            headers={"Authorization": "Bearer odoo_api_key_1"}
        )

    assert response.status_code == 422
