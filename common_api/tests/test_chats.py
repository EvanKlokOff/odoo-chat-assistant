# common_api/tests/test_chats.py
import pytest
from datetime import datetime, timedelta


class TestChatsAPI:
    """Tests for chats endpoints - через реальный HTTP сервер"""

    def test_get_all_chats(self, api_client, api_key_headers, create_sample_messages, sample_chat):
        """Test getting all chats"""
        response = api_client("GET", "/api/v1/chats", headers=api_key_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Проверяем структуру ответа
        first_chat = data[0]
        assert "chat_id" in first_chat
        assert "title" in first_chat
        assert "last_used" in first_chat
        assert "message_count" in first_chat

    def test_get_chats_with_pagination(self, api_client, api_key_headers, create_sample_messages):
        """Test getting chats with pagination"""
        response = api_client("GET", "/api/v1/chats?limit=2&offset=0", headers=api_key_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 2

    def test_get_chat_detail_success(self, api_client, api_key_headers, create_sample_messages, sample_chat):
        """Test getting chat detail"""
        response = api_client("GET", f"/api/v1/chats/{sample_chat['chat_id']}", headers=api_key_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["chat_id"] == sample_chat["chat_id"]
        assert "title" in data
        assert "message_count" in data
        assert "participants" in data
        assert "first_message_date" in data
        assert "last_message_date" in data
        assert data["message_count"] >= 10

    def test_get_chat_detail_not_found(self, api_client, api_key_headers):
        """Test getting non-existent chat"""
        response = api_client("GET", "/api/v1/chats/non_existent_chat", headers=api_key_headers)

        assert response.status_code == 404
        assert "not found" in response.json()["error"]

    def test_get_chat_messages(self, api_client, api_key_headers, create_sample_messages, sample_chat):
        """Test getting chat messages with pagination"""
        response = api_client(
            "GET",
            f"/api/v1/chats/{sample_chat['chat_id']}/messages?page=1&per_page=5",
            headers=api_key_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
        assert len(data["items"]) <= 5

    def test_get_chat_messages_ordering(self, api_client, api_key_headers, create_sample_messages, sample_chat):
        """Test chat messages ordering"""
        # Descending order
        response_desc = api_client(
            "GET",
            f"/api/v1/chats/{sample_chat['chat_id']}/messages?order_desc=true&per_page=5",
            headers=api_key_headers
        )
        assert response_desc.status_code == 200
        data_desc = response_desc.json()

        # Ascending order - ИСПРАВЛЕНО: убрана лишняя '=' после GET
        response_asc = api_client(
            "GET",
            f"/api/v1/chats/{sample_chat['chat_id']}/messages?order_desc=false&per_page=5",
            headers=api_key_headers
        )
        assert response_asc.status_code == 200
        data_asc = response_asc.json()

        # Проверяем, что порядок разный (если есть сообщения)
        if data_desc["items"] and data_asc["items"]:
            # Первое сообщение в DESC должно быть последним в ASC
            # Или просто проверяем, что ID не совпадают
            assert data_desc["items"][0]["id"] != data_asc["items"][0]["id"]

    def test_get_chat_messages_with_date_filter(self, api_client, api_key_headers, sample_chat, create_sample_messages):
        """Test getting chat messages with date filter"""
        start_date = (datetime.now() - timedelta(days=1)).isoformat()
        end_date = datetime.now().isoformat()

        response = api_client(
            "GET",
            f"/api/v1/chats/{sample_chat['chat_id']}/messages?start_date={start_date}&end_date={end_date}",
            headers=api_key_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_get_chat_messages_without_date_filter(self, api_client, api_key_headers, sample_chat, create_sample_messages):
        """Test getting chat messages without date filter"""
        response = api_client(
            "GET",
            f"/api/v1/chats/{sample_chat['chat_id']}/messages?page=1&per_page=10",
            headers=api_key_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] >= 10

    def test_unauthorized_access(self, api_client):
        """Test accessing endpoint without API key"""
        response = api_client("GET", "/api/v1/chats")

        assert response.status_code == 401
        assert "Not authenticated" in response.json()["error"]

    def test_invalid_chat_id(self, api_client, api_key_headers):
        """Test getting chat with invalid ID format"""
        response = api_client("GET", "/api/v1/chats/invalid_chat_id_!!@#", headers=api_key_headers)

        # Должен вернуть 404, так как чат не существует
        assert response.status_code == 404

    def test_chat_messages_empty_result(self, api_client, api_key_headers):
        """Test getting messages from non-existent chat"""
        response = api_client(
            "GET",
            "/api/v1/chats/non_existent_chat_123/messages?page=1&per_page=10",
            headers=api_key_headers
        )

        # Должен вернуть пустой результат с 200
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0