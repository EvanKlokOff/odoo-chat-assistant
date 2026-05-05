# common_api/tests/test_analysis.py
import pytest
from datetime import datetime, timedelta


class TestAnalysisAPI:
    """Tests for analysis endpoints - через реальный HTTP сервер"""

    def test_review_chat_success(self, api_client, api_key_headers, create_sample_messages, sample_chat):
        """Test review chat endpoint"""
        target_datetime = datetime.now().isoformat()

        response = api_client(
            "POST",
            "/api/v1/analysis/review",
            json={
                "chat_id": sample_chat["chat_id"],
                "target_datetime": target_datetime,
                "lookback_minutes": 60,
                "lookforward_minutes": 60
            },
            headers=api_key_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["chat_id"] == sample_chat["chat_id"]
        assert "summary" in data
        assert "key_points" in data
        assert "sentiment" in data
        assert "participant_count" in data
        assert "message_count" in data
        assert data["participant_count"] >= 1

    def test_review_chat_no_messages(self, api_client, api_key_headers):
        """Test review chat with no messages in time window"""
        target_datetime = datetime.now().isoformat()

        response = api_client(
            "POST",
            "/api/v1/analysis/review",
            json={
                "chat_id": "non_existent_chat",
                "target_datetime": target_datetime,
                "lookback_minutes": 60,
                "lookforward_minutes": 60
            },
            headers=api_key_headers
        )

        assert response.status_code == 404
        assert "No messages found" in response.json()["error"]

    def test_review_chat_async(self, api_client, api_key_headers, sample_chat):
        """Test async review chat endpoint"""
        target_datetime = datetime.now().isoformat()

        response = api_client(
            "POST",
            "/api/v1/analysis/review/async",
            json={
                "chat_id": sample_chat["chat_id"],
                "target_datetime": target_datetime,
                "lookback_minutes": 60,
                "lookforward_minutes": 60
            },
            headers=api_key_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert "status" in data
        assert data["status"] == "pending"

    def test_get_analysis_task(self, api_client, api_key_headers, sample_chat):
        """Test getting analysis task status"""
        # Сначала создаём задачу через async эндпоинт
        target_datetime = datetime.now().isoformat()

        create_response = api_client(
            "POST",
            "/api/v1/analysis/review/async",
            json={
                "chat_id": sample_chat["chat_id"],
                "target_datetime": target_datetime,
                "lookback_minutes": 60,
                "lookforward_minutes": 60
            },
            headers=api_key_headers
        )

        assert create_response.status_code == 200
        task_data = create_response.json()
        task_id = task_data["task_id"]

        # Получаем статус задачи
        response = api_client(
            "GET",
            f"/api/v1/analysis/task/{task_id}",
            headers=api_key_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert "status" in data
        assert "progress" in data
        assert "created_at" in data

    def test_compliance_check_success(self, api_client, api_key_headers, create_sample_messages, sample_chat):
        """Test compliance check endpoint"""
        target_datetime = datetime.now().isoformat()

        response = api_client(
            "POST",
            "/api/v1/analysis/compliance",
            json={
                "chat_id": sample_chat["chat_id"],
                "target_datetime": target_datetime,
                "description": "Test conversation about testing messages content",
                "lookback_minutes": 60,
                "lookforward_minutes": 60
            },
            headers=api_key_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["chat_id"] == sample_chat["chat_id"]
        assert "compliant" in data
        assert "confidence" in data
        assert "explanation" in data
        assert "violations" in data
        assert "suggestions" in data

    def test_compliance_check_no_messages(self, api_client, api_key_headers):
        """Test compliance check with no messages"""
        target_datetime = datetime.now().isoformat()

        response = api_client(
            "POST",
            "/api/v1/analysis/compliance",
            json={
                "chat_id": "non_existent_chat",
                "target_datetime": target_datetime,
                "description": "Test description",
                "lookback_minutes": 60,
                "lookforward_minutes": 60
            },
            headers=api_key_headers
        )

        assert response.status_code == 404
        assert "No messages found" in response.json()["error"]

    def test_compliance_check_async(self, api_client, api_key_headers, sample_chat):
        """Test async compliance check endpoint"""
        target_datetime = datetime.now().isoformat()

        response = api_client(
            "POST",
            "/api/v1/analysis/compliance/async",
            json={
                "chat_id": sample_chat["chat_id"],
                "target_datetime": target_datetime,
                "description": "Test description",
                "lookback_minutes": 60,
                "lookforward_minutes": 60
            },
            headers=api_key_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert "status" in data

    def test_get_task_status_not_found(self, api_client, api_key_headers):
        """Test getting non-existent task"""
        response = api_client(
            "GET",
            "/api/v1/analysis/task/non_existent_task_id",
            headers=api_key_headers
        )

        assert response.status_code == 404
        assert "not found" in response.json()["error"]

    def test_review_chat_invalid_date_range(self, api_client, api_key_headers, sample_chat):
        """Test review chat with invalid date range"""
        response = api_client(
            "POST",
            "/api/v1/analysis/review",
            json={
                "chat_id": sample_chat["chat_id"],
                "target_datetime": "invalid_date",
                "lookback_minutes": 60,
                "lookforward_minutes": 60
            },
            headers=api_key_headers
        )

        assert response.status_code == 422

    def test_review_chat_missing_required_fields(self, api_client, api_key_headers, sample_chat):
        """Test review chat with missing required fields"""
        response = api_client(
            "POST",
            "/api/v1/analysis/review",
            json={
                "chat_id": sample_chat["chat_id"]
                # missing target_datetime, lookback_minutes, lookforward_minutes
            },
            headers=api_key_headers
        )

        assert response.status_code == 422

    def test_compliance_check_missing_description(self, api_client, api_key_headers, sample_chat):
        """Test compliance check with missing description"""
        target_datetime = datetime.now().isoformat()

        response = api_client(
            "POST",
            "/api/v1/analysis/compliance",
            json={
                "chat_id": sample_chat["chat_id"],
                "target_datetime": target_datetime
                # missing description
            },
            headers=api_key_headers
        )

        assert response.status_code == 422

    def test_unauthorized_access(self, api_client):
        """Test accessing endpoint without API key"""
        response = api_client("POST", "/api/v1/analysis/review", json={})
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["error"]