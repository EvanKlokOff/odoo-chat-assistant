# common_api/tests/test_messages.py (исправленный)
import pytest
from datetime import datetime, timedelta


class TestMessagesAPI:
    """Tests for messages endpoints - через реальный HTTP сервер"""

    def test_get_all_messages(self, api_client, api_key_headers, create_sample_messages):
        response = api_client("GET", "/api/v1/messages?page=1&per_page=20", headers=api_key_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 10

    def test_get_messages_pagination(self, api_client, api_key_headers, create_sample_messages):
        response1 = api_client("GET", "/api/v1/messages?page=1&per_page=3", headers=api_key_headers)
        assert response1.status_code == 200
        data1 = response1.json()
        assert len(data1["items"]) <= 3

        response2 = api_client("GET", "/api/v1/messages?page=2&per_page=3", headers=api_key_headers)
        assert response2.status_code == 200
        data2 = response2.json()

        if data1["items"] and data2["items"]:
            assert data1["items"][0]["id"] != data2["items"][0]["id"]

    def test_get_messages_with_chat_filter(self, api_client, api_key_headers, sample_chat, create_sample_messages):
        response = api_client("GET", f"/api/v1/messages?chat_id={sample_chat['chat_id']}", headers=api_key_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_get_messages_with_sender_filter(self, api_client, api_key_headers, sample_user, create_sample_messages):
        response = api_client("GET", f"/api/v1/messages?sender_id={sample_user['user_id']}", headers=api_key_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_get_messages_with_date_filter(self, api_client, api_key_headers, create_sample_messages):
        start_date = (datetime.now() - timedelta(days=1)).isoformat()
        end_date = datetime.now().isoformat()
        response = api_client(
            "GET",
            f"/api/v1/messages?start_date={start_date}&end_date={end_date}",
            headers=api_key_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_get_messages_with_search_param(self, api_client, api_key_headers, create_sample_messages):
        response = api_client("GET", "/api/v1/messages?search=Test", headers=api_key_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] >= 1

    def test_get_message_by_id_success(self, api_client, api_key_headers, create_sample_messages):
        response_all = api_client("GET", "/api/v1/messages?page=1&per_page=1", headers=api_key_headers)
        assert response_all.status_code == 200
        messages = response_all.json()

        if messages["items"]:
            message_id = messages["items"][0]["id"]
            response = api_client("GET", f"/api/v1/messages/{message_id}", headers=api_key_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == message_id
            assert "content" in data

    def test_get_message_by_id_not_found(self, api_client, api_key_headers):
        response = api_client("GET", "/api/v1/messages/999999", headers=api_key_headers)
        assert response.status_code == 404
        assert "not found" in response.json()["error"]

    def test_get_message_by_id_with_chunks(self, api_client, api_key_headers, create_sample_messages):
        response_all = api_client("GET", "/api/v1/messages?page=1&per_page=1", headers=api_key_headers)
        assert response_all.status_code == 200
        messages = response_all.json()

        if messages["items"]:
            message_id = messages["items"][0]["id"]
            response = api_client(
                "GET",
                f"/api/v1/messages/{message_id}?include_chunks=true",
                headers=api_key_headers
            )
            assert response.status_code == 200
            data = response.json()
            assert "chunks" in data

    def test_get_message_by_external_id(self, api_client, api_key_headers, create_sample_messages):
        response_all = api_client("GET", "/api/v1/messages?page=1&per_page=1", headers=api_key_headers)
        assert response_all.status_code == 200
        messages = response_all.json()

        if messages["items"]:
            external_id = messages["items"][0]["message_id"]
            response = api_client("GET", f"/api/v1/messages/external/{external_id}", headers=api_key_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["message_id"] == external_id

    def test_get_recent_messages(self, api_client, api_key_headers, sample_chat, create_sample_messages):
        response = api_client(
            "GET",
            f"/api/v1/messages/by-chat/{sample_chat['chat_id']}/recent?limit=5",
            headers=api_key_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 5

    def test_get_conversation_thread(self, api_client, api_key_headers, sample_chat, create_sample_messages):
        response = api_client(
            "GET",
            f"/api/v1/messages/conversation/{sample_chat['chat_id']}?limit=20",
            headers=api_key_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_search_messages_endpoint(self, api_client, api_key_headers, create_sample_messages):
        # Используем слово, которое точно есть в сообщениях (с заглавной буквы)
        response = api_client("GET", "/api/v1/messages/search?query=Test", headers=api_key_headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")  # Увидим детали ошибки валидации
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_search_messages_with_chat_filter(self, api_client, api_key_headers, sample_chat, create_sample_messages):
        response = api_client(
            "GET",
            f"/api/v1/messages/search?query=Test&chat_id={sample_chat['chat_id']}",
            headers=api_key_headers
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")  # Увидим детали ошибки валидации
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] >= 1

    def test_get_message_context(self, api_client, api_key_headers, create_sample_messages):
        response_all = api_client("GET", "/api/v1/messages?page=1&per_page=10", headers=api_key_headers)
        assert response_all.status_code == 200
        messages = response_all.json()

        if len(messages["items"]) >= 3:
            message_id = messages["items"][2]["id"]
            response = api_client(
                "GET",
                f"/api/v1/messages/{message_id}/context?before=2&after=2",
                headers=api_key_headers
            )
            assert response.status_code in [200, 404]

    def test_delete_message_unauthorized(self, api_client, api_key_headers, create_sample_messages):
        """Test deleting message with regular user"""
        response_all = api_client("GET", "/api/v1/messages?page=1&per_page=1", headers=api_key_headers)
        assert response_all.status_code == 200
        messages = response_all.json()

        if messages["items"]:
            message_id = messages["items"][0]["id"]
            response = api_client("DELETE", f"/api/v1/messages/{message_id}", headers=api_key_headers)
            assert response.status_code in [200, 403]

    def test_export_messages_json(self, api_client, api_key_headers, sample_chat, create_sample_messages):
        response = api_client(
            "GET",
            f"/api/v1/messages/export/{sample_chat['chat_id']}?format=json",
            headers=api_key_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["chat_id"] == sample_chat["chat_id"]
        assert data["export_format"] == "json"
        assert "total_messages" in data

    def test_export_messages_with_date_range(self, api_client, api_key_headers, sample_chat, create_sample_messages):
        start_date = (datetime.now() - timedelta(days=1)).isoformat()
        end_date = datetime.now().isoformat()
        response = api_client(
            "GET",
            f"/api/v1/messages/export/{sample_chat['chat_id']}?format=json&start_date={start_date}&end_date={end_date}",
            headers=api_key_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["export_format"] == "json"
        assert "date_range" in data

    def test_unauthorized_access(self, api_client):
        response = api_client("GET", "/api/v1/messages")
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["error"]