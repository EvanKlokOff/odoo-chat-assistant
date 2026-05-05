from datetime import datetime, timedelta
import json


def generate_test_messages(chat_id: str, user_id: str, count: int = 50):
    """Generate test messages for testing"""
    messages = []
    base_time = datetime.now()

    for i in range(count):
        messages.append({
            "message_id": f"msg_{i}",
            "chat_id": chat_id,
            "chat_title": f"Test Chat {chat_id}",
            "sender_id": user_id,
            "sender_name": f"Test User {user_id}",
            "content": f"Test message content number {i}. This is a sample message for testing.",
            "timestamp": (base_time - timedelta(hours=count - i)).isoformat(),
            "platform": "telegram",
            "reply_to_message_id": None if i == 0 else f"msg_{i - 1}"
        })

    return messages


def generate_test_compliance_scenarios():
    """Generate different compliance test scenarios"""
    return {
        "compliant": {
            "description": "Friendly customer support conversation about product return",
            "messages": [
                "Hello! I need to return a product I purchased.",
                "Of course! I'll be happy to help you with the return.",
                "Thank you for your assistance!",
                "You're welcome! Your return has been processed."
            ]
        },
        "non_compliant": {
            "description": "Professional and polite conversation",
            "messages": [
                "Hey! Return my money now!",
                "You're so slow! Why can't you just do it?",
                "This is ridiculous! I want to speak to a manager!",
                "I'll never use your service again!"
            ]
        },
        "partially_compliant": {
            "description": "Proper greeting and closing in conversation",
            "messages": [
                "Hi! I have a question about my order.",
                "What's your order number?",
                "I don't know. Just help me.",
                "Ok. Bye."
            ]
        }
    }


def generate_test_review_scenarios():
    """Generate different review test scenarios"""
    return {
        "deal_closed": {
            "chat_title": "Sales Chat",
            "messages": [
                "Hi! I'm interested in your premium plan.",
                "Great choice! The premium plan costs $99/month.",
                "I'll take it. Can I pay with credit card?",
                "Yes, absolutely! I'll send you the payment link.",
                "Payment done! Thank you for your business!"
            ],
            "expected": {
                "status": "closed",
                "participants_count": 2,
                "has_price": True
            }
        },
        "discussion": {
            "chat_title": "Support Chat",
            "messages": [
                "I'm having issues with the software.",
                "Sorry to hear that. Can you describe the problem?",
                "It crashes when I try to export data.",
                "Let me check. We'll fix this in the next update."
            ],
            "expected": {
                "status": "discussing",
                "participants_count": 2,
                "has_price": False
            }
        }
    }


# Test data for API responses
EXPECTED_SCHEMAS = {
    "user_response": ["user_id", "user_name", "telegram_id"],
    "user_detail_response": ["user_id", "user_name", "telegram_id", "chat_count", "message_count", "last_active"],
    "chat_response": ["chat_id", "title", "selected", "last_used", "message_count"],
    "message_response": ["id", "message_id", "sender_id", "sender_name", "content", "timestamp"],
    "review_response": ["chat_id", "target_datetime", "time_window", "summary", "key_points", "sentiment",
                        "participant_count", "message_count", "message_count_before", "message_count_after"],
    "compliance_response": ["chat_id", "target_datetime", "compliant", "confidence", "explanation",
                            "violations", "suggestions"],
    "task_status_response": ["task_id", "status", "progress", "created_at"],
    "sync_status_response": ["last_sync", "users_count", "chats_count", "messages_count", "pending_tasks"]
}