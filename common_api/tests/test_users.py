# common_api/tests/test_users.py
import pytest


class TestUsersAPI:
    """Tests for users endpoints - через реальный HTTP сервер"""

    def test_get_users_success(self, api_client, api_key_headers, create_sample_messages):
        response = api_client("GET", "/api/v1/users", headers=api_key_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "user_id" in data[0]
        assert "user_name" in data[0]

    def test_get_users_with_search(self, api_client, api_key_headers, create_sample_messages):
        response = api_client("GET", "/api/v1/users?search=Test", headers=api_key_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        for user in data:
            if user.get("user_name"):
                assert "Test" in user["user_name"] or "Test" in user["user_id"]

    def test_get_user_detail_success(self, api_client, api_key_headers, create_sample_messages, sample_user):
        response = api_client("GET", f"/api/v1/users/{sample_user['user_id']}", headers=api_key_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == sample_user["user_id"]
        assert "user_name" in data
        assert "chat_count" in data
        assert "message_count" in data
        assert data["message_count"] >= 10

    def test_get_user_detail_not_found(self, api_client, api_key_headers):
        response = api_client("GET", "/api/v1/users/non_existent_user", headers=api_key_headers)
        assert response.status_code == 404
        assert "not found" in response.json()["error"]

    def test_get_user_chats(self, api_client, api_key_headers, create_sample_messages, sample_user):
        response = api_client("GET", f"/api/v1/users/{sample_user['user_id']}/chats", headers=api_key_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if data:
            assert "chat_id" in data[0]
            assert "title" in data[0]

    def test_get_user_messages(self, api_client, api_key_headers, create_sample_messages, sample_user):
        response = api_client("GET", f"/api/v1/users/{sample_user['user_id']}/messages?page=1&per_page=10", headers=api_key_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
        assert len(data["items"]) <= 10

    def test_get_user_messages_pagination(self, api_client, api_key_headers, create_sample_messages, sample_user):
        response1 = api_client("GET", f"/api/v1/users/{sample_user['user_id']}/messages?page=1&per_page=3", headers=api_key_headers)
        data1 = response1.json()
        assert response1.status_code == 200
        assert len(data1["items"]) <= 3

        response2 = api_client("GET", f"/api/v1/users/{sample_user['user_id']}/messages?page=2&per_page=3", headers=api_key_headers)
        data2 = response2.json()
        assert response2.status_code == 200

        if data1["items"] and data2["items"]:
            assert data1["items"][0]["id"] != data2["items"][0]["id"]

    def test_unauthorized_access(self, api_client):
        response = api_client("GET", "/api/v1/users")
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["error"]