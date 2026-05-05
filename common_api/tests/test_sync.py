# common_api/tests/test_sync.py
import pytest
from datetime import datetime, timedelta


class TestSyncAPI:
    """Tests for sync endpoints - через реальный HTTP сервер"""

    def test_get_sync_status_success(self, api_client, admin_key_headers, create_sample_messages):
        """Test getting sync status with admin key"""
        response = api_client("GET", "/api/v1/sync/status", headers=admin_key_headers)

        assert response.status_code == 200
        data = response.json()
        assert "users_count" in data
        assert "chats_count" in data
        assert "messages_count" in data
        assert "pending_tasks" in data
        # Проверяем, что значения корректные
        assert data["users_count"] >= 1
        assert data["chats_count"] >= 1
        assert data["messages_count"] >= 10
        assert data["pending_tasks"] >= 0

    def test_get_sync_status_unauthorized(self, api_client, api_key_headers):
        """Test getting sync status without admin key (regular user)"""
        response = api_client("GET", "/api/v1/sync/status", headers=api_key_headers)

        assert response.status_code == 403
        assert "Admin privileges required" in response.json()["error"]

    def test_get_sync_status_no_auth(self, api_client):
        """Test getting sync status without any authentication"""
        response = api_client("GET", "/api/v1/sync/status")

        assert response.status_code == 401
        assert "Not authenticated" in response.json()["error"]

    def test_refresh_data(self, api_client, admin_key_headers):
        """Test refresh data endpoint"""
        response = api_client("POST", "/api/v1/sync/refresh", headers=admin_key_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Refresh initiated" in data["message"]

    def test_refresh_data_unauthorized(self, api_client, api_key_headers):
        """Test refresh data without admin key"""
        response = api_client("POST", "/api/v1/sync/refresh", headers=api_key_headers)

        assert response.status_code == 403
        assert "Admin privileges required" in response.json()["error"]

    def test_get_changes(self, api_client, admin_key_headers, create_sample_messages):
        """Test getting changes since last sync"""
        since = (datetime.now() - timedelta(days=1)).isoformat()

        response = api_client("GET", f"/api/v1/sync/changes?since={since}", headers=admin_key_headers)

        assert response.status_code == 200
        data = response.json()
        assert "since" in data
        assert "new_messages_count" in data
        assert "new_messages" in data
        assert isinstance(data["new_messages"], list)
        assert data["new_messages_count"] >= 10

    def test_get_changes_with_limit(self, api_client, admin_key_headers, create_sample_messages):
        """Test getting changes with custom limit"""
        since = (datetime.now() - timedelta(days=1)).isoformat()
        limit = 5

        response = api_client("GET", f"/api/v1/sync/changes?since={since}&limit={limit}", headers=admin_key_headers)

        assert response.status_code == 200
        data = response.json()
        # Количество возвращённых сообщений не должно превышать limit
        assert len(data["new_messages"]) <= limit

    def test_get_changes_with_higher_limit(self, api_client, admin_key_headers, create_sample_messages):
        """Test getting changes with high limit"""
        since = (datetime.now() - timedelta(days=1)).isoformat()
        limit = 50

        response = api_client("GET", f"/api/v1/sync/changes?since={since}&limit={limit}", headers=admin_key_headers)

        assert response.status_code == 200
        data = response.json()
        # Так как всего 10 сообщений, должно вернуть 10
        assert len(data["new_messages"]) == 10

    def test_get_changes_old_date(self, api_client, admin_key_headers, create_sample_messages):
        """Test getting changes from old date (should return all messages)"""
        since = (datetime.now() - timedelta(days=30)).isoformat()

        response = api_client("GET", f"/api/v1/sync/changes?since={since}", headers=admin_key_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["new_messages_count"] >= 10

    def test_get_changes_future_date(self, api_client, admin_key_headers, create_sample_messages):
        """Test getting changes from future date (should return empty)"""
        since = (datetime.now() + timedelta(days=30)).isoformat()

        response = api_client("GET", f"/api/v1/sync/changes?since={since}", headers=admin_key_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["new_messages_count"] == 0
        assert data["new_messages"] == []

    def test_get_changes_missing_since(self, api_client, admin_key_headers):
        """Test getting changes without since parameter"""
        response = api_client("GET", "/api/v1/sync/changes", headers=admin_key_headers)

        assert response.status_code == 422

    def test_get_changes_invalid_date_format(self, api_client, admin_key_headers):
        """Test getting changes with invalid date format"""
        response = api_client("GET", "/api/v1/sync/changes?since=invalid-date", headers=admin_key_headers)

        assert response.status_code == 422

    def test_sync_endpoints_with_regular_user(self, api_client, api_key_headers):
        """Test all sync endpoints with regular user (should all fail with 403)"""
        response = api_client("GET", "/api/v1/sync/status", headers=api_key_headers)
        assert response.status_code == 403

        response = api_client("POST", "/api/v1/sync/refresh", headers=api_key_headers)
        assert response.status_code == 403

        since = (datetime.now() - timedelta(days=1)).isoformat()
        response = api_client("GET", f"/api/v1/sync/changes?since={since}", headers=api_key_headers)
        assert response.status_code == 403