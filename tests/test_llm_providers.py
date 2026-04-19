import pytest
import asyncio
import time
from src.llm.base import Message

# Создаём event loop для синхронных тестов
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)


def test_generate_response(ollama_llm):
    """Тест генерации ответа"""
    response = _loop.run_until_complete(
        ollama_llm.generate("Привет! Напиши 'OK' в ответ")
    )

    assert response is not None
    assert isinstance(response, str)
    assert len(response) > 0


def test_generate_with_system_prompt(ollama_llm):
    """Тест генерации с system prompt"""
    response = _loop.run_until_complete(
        ollama_llm.generate(
            "Что ты умеешь?",
            system_prompt="Ты полезный ассистент. Отвечай кратко, максимум 3 предложения."
        )
    )

    assert response is not None
    assert isinstance(response, str)
    assert len(response) < 500


def test_chat(ollama_llm):
    """Тест диалога"""
    messages = [
        Message(role="user", content="Как тебя зовут?"),
        Message(role="assistant", content="Меня зовут Gemma 3!"),
        Message(role="user", content="Какой сегодня день?")
    ]

    response = _loop.run_until_complete(ollama_llm.chat(messages))

    assert response is not None
    assert isinstance(response, str)


def test_generate_with_template(ollama_llm):
    """Тест генерации по шаблону"""
    template = "Проанализируй сообщение: {message}. Дай оценку тональности: позитивная/негативная/нейтральная."
    response = _loop.run_until_complete(
        ollama_llm.generate_with_template(
            template,
            message="Спасибо за отличную работу!"
        )
    )

    assert response is not None
    assert any(word in response.lower() for word in ["позитив", "хорош", "отличн"])


def test_gemma3_response(gemma3_llm):
    """Тест работы Gemma 3"""
    response = _loop.run_until_complete(
        gemma3_llm.generate("Напиши приветствие для чат-бота на русском. Ограничься 1 предложением")
    )

    assert response is not None
    assert isinstance(response, str)
    assert len(response) > 10


def test_gemma3_analysis(gemma3_llm, sample_messages):
    """Тест анализа сообщений Gemma 3"""
    messages_text = "\n".join([
        f"{m['sender_name']}: {m['content']}"
        for m in sample_messages[:3]
    ])

    prompt = f"Проанализируй этот диалог:\n{messages_text}\n\nКакова основная тема разговора?"
    response = _loop.run_until_complete(gemma3_llm.generate(prompt))

    assert response is not None
    assert any(word in response.lower() for word in ["квартир", "недвижим", "покупк"])
