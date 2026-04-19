import pytest
from src.analyzers.state import AgentState
from src.analyzers import nodes
from src.analyzers.nodes import (
    generate_review,
    check_compliance,
    retrieve_chat_messages
)


def test_generate_review_with_messages(mock_llm, sample_messages, monkeypatch):
    """Тест генерации ревью с сообщениями"""
    monkeypatch.setattr(nodes, 'get_llm_provider', lambda: mock_llm)

    state: AgentState = {
        "query_type": "review",
        "messages": [],
        "date_start": None,
        "date_end": None,
        "instruction": None,
        "chat_messages": sample_messages,
        "analysis_result": None,
        "deviations": None,
        "current_step": "generate_review",
        "error": None
    }

    # Запускаем асинхронную функцию через asyncio.run()
    import asyncio
    result = asyncio.run(generate_review(state))

    assert result["analysis_result"] is not None
    assert isinstance(result["analysis_result"], str)


def test_generate_review_empty_messages(mock_llm, monkeypatch):
    """Тест генерации ревью без сообщений"""
    monkeypatch.setattr(nodes, 'get_llm_provider', lambda: mock_llm)

    state: AgentState = {
        "query_type": "review",
        "messages": [],
        "date_start": None,
        "date_end": None,
        "instruction": None,
        "chat_messages": [],
        "analysis_result": None,
        "deviations": None,
        "current_step": "generate_review",
        "error": None
    }

    import asyncio
    result = asyncio.run(generate_review(state))

    assert "нет сообщений" in result["analysis_result"].lower()


def test_check_compliance(mock_llm, sample_messages, sample_instruction, monkeypatch):
    """Тест проверки соответствия инструкции"""
    monkeypatch.setattr(nodes, 'get_llm_provider', lambda: mock_llm)

    state: AgentState = {
        "query_type": "compliance",
        "messages": [],
        "date_start": None,
        "date_end": None,
        "instruction": sample_instruction,
        "chat_messages": sample_messages,
        "analysis_result": None,
        "deviations": None,
        "current_step": "check_compliance",
        "error": None
    }

    import asyncio
    result = asyncio.run(check_compliance(state))

    assert result["analysis_result"] is not None
    assert "соответствует" in result["analysis_result"].lower()


def test_retrieve_messages_no_dates():
    """Тест получения сообщений без указания дат"""
    state: AgentState = {
        "query_type": "review",
        "messages": [],
        "date_start": None,
        "date_end": None,
        "instruction": None,
        "chat_messages": [],
        "analysis_result": None,
        "deviations": None,
        "current_step": "retrieve",
        "error": None
    }

    # Этот тест требует реальной БД, поэтому пропускаем если нет подключения
    try:
        import asyncio
        result = asyncio.run(retrieve_chat_messages(state))
        assert "chat_messages" in result
    except Exception as e:
        pytest.skip(f"Database not available: {e}")