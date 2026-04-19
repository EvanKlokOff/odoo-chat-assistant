import pytest
import asyncio
from src.analyzers import nodes
from src.analyzers.graph import should_do_compliance
from src.analyzers.state import AgentState
from langgraph.graph import StateGraph, END

import tests.utils as test_utils


def test_full_review_pipeline(mock_llm, sample_messages, monkeypatch):
    """Тест полного пайплайна ревью"""
    monkeypatch.setattr(nodes, 'get_llm_provider', lambda: mock_llm)

    async def mock_retrieve_chat_messages(state):
        state["chat_messages"] = sample_messages
        return state

    monkeypatch.setattr(nodes, 'retrieve_chat_messages', mock_retrieve_chat_messages)

    workflow = StateGraph(AgentState)

    workflow.add_node("analyze_type", test_utils.sync_analyze_query_type)
    workflow.add_node("retrieve", test_utils.sync_retrieve_chat_messages)
    workflow.add_node("generate_review", test_utils.sync_generate_review)
    workflow.add_node("check_compliance", test_utils.sync_check_compliance)
    workflow.add_node("extract_deviations", test_utils.sync_extract_deviations)

    workflow.set_entry_point("analyze_type")
    workflow.add_edge("analyze_type", "retrieve")

    workflow.add_conditional_edges(
        "retrieve",
        should_do_compliance,
        {
            "compliance": "check_compliance",
            "review": "generate_review",
        }
    )

    workflow.add_edge("generate_review", END)
    workflow.add_edge("check_compliance", "extract_deviations")
    workflow.add_edge("extract_deviations", END)

    graph = workflow.compile()

    initial_state: AgentState = {
        "query_type": "review",
        "messages": [],
        "date_start": "2025-04-01T00:00:00",
        "date_end": "2025-04-02T23:59:59",
        "instruction": None,
        "chat_messages": sample_messages,
        "analysis_result": None,
        "deviations": None,
        "current_step": "start",
        "error": None
    }

    final_state = graph.invoke(initial_state)

    assert final_state["analysis_result"] is not None
    assert isinstance(final_state["analysis_result"], str)


def test_full_compliance_pipeline(mock_llm, sample_messages, sample_instruction, monkeypatch):
    """Тест полного пайплайна проверки соответствия"""
    from src.analyzers import nodes
    monkeypatch.setattr(nodes, 'get_llm_provider', lambda: mock_llm)

    async def mock_retrieve_chat_messages(state):
        state["chat_messages"] = sample_messages
        return state

    monkeypatch.setattr(nodes, 'retrieve_chat_messages', mock_retrieve_chat_messages)


    workflow = StateGraph(AgentState)

    workflow.add_node("analyze_type", test_utils.sync_analyze_query_type)
    workflow.add_node("retrieve", test_utils.sync_retrieve_chat_messages)
    workflow.add_node("generate_review", test_utils.sync_generate_review)
    workflow.add_node("check_compliance", test_utils.sync_check_compliance)
    workflow.add_node("extract_deviations", test_utils.sync_extract_deviations)

    workflow.set_entry_point("analyze_type")
    workflow.add_edge("analyze_type", "retrieve")

    workflow.add_conditional_edges(
        "retrieve",
        should_do_compliance,
        {
            "compliance": "check_compliance",
            "review": "generate_review",
        }
    )

    workflow.add_edge("generate_review", END)
    workflow.add_edge("check_compliance", "extract_deviations")
    workflow.add_edge("extract_deviations", END)

    graph = workflow.compile()


    initial_state: AgentState = {
        "query_type": "compliance",
        "messages": [],
        "date_start": None,
        "date_end": None,
        "instruction": sample_instruction,
        "chat_messages": sample_messages,
        "analysis_result": None,
        "deviations": None,
        "current_step": "start",
        "error": None
    }

    final_state = graph.invoke(initial_state)

    assert final_state["analysis_result"] is not None
    print(f"\n✅ Full compliance pipeline test passed")


@pytest.mark.slow
def test_real_llm_review(gemma3_llm, sample_messages):
    """Тест с реальной Gemma 3 моделью"""
    messages_text = "\n".join([
        f"[{m['timestamp']}] {m['sender_name']}: {m['content']}"
        for m in sample_messages
    ])

    prompt = f"""Проанализируй этот диалог и напиши краткое ревью:
    {messages_text}

    Ревью должно включать:
    1. Тему разговора
    2. Участников
    3. Итог
    """

    response = asyncio.run(gemma3_llm.generate(prompt))

    assert response is not None
    assert len(response) > 50
    print(f"\n✅ Real LLM review test passed:\n{response[:200]}...")


@pytest.mark.slow
def test_real_embeddings_search(nomic_embedding):
    """Тест с реальной эмбеддинг моделью"""
    documents = [
        "Продается квартира в центре, 3 комнаты, 120 кв.м.",
        "Срочно продаю автомобиль Toyota Camry 2020",
        "Сдам офис в бизнес-центре, 50 кв.м."
    ]

    query = "недвижимость квартира"
    results = asyncio.run(nomic_embedding.semantic_search(query, documents))

    assert results is not None
    assert "квартир" in documents[results[0][0]].lower()
    print(f"\n✅ Real embeddings search test passed: best match = '{documents[results[0][0]]}'")
