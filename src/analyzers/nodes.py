import logging
from datetime import datetime

from sqlalchemy import select

from src.config import settings
from src.analyzers.state import AgentState
from src.llm.base import BaseLLMProvider, BaseEmbeddingProvider
from src.llm.factory import LLMFactory
from src.llm import exceptions
from src.database.session import AsyncSessionLocal
from src.database.models import Message


logger = logging.getLogger(__name__)

llm_provider: BaseLLMProvider | None = None
embedding_provider: BaseEmbeddingProvider | None = None

def get_llm_provider() -> BaseLLMProvider | None:
    """Ленивая инициализация LLM провайдера"""
    global llm_provider
    if llm_provider is None:
        llm_provider = LLMFactory.create_llm_provider(
            provider_type=settings.llm_provider,
            model=getattr(settings, 'ollama_llm_model', 'gemma3:27b'),
            base_url=settings.ollama_base_url,
            temperature=settings.llm_temperature,
            model_size=getattr(settings, 'gemma3_model_size', '27b')
        )
        logger.info(f"LLM provider initialized: {settings.llm_provider}")
    return llm_provider

def get_embedding_provider() -> BaseEmbeddingProvider | None:
    """Ленивая инициализация эмбеддинг провайдера"""
    global embedding_provider
    if embedding_provider is None:
        embedding_provider = LLMFactory.create_embedding_provider(
            provider_type=settings.embedding_provider,
            model=settings.ollama_embedding_model,
            base_url=settings.ollama_base_url
        )
        logger.info(f"Embedding provider initialized: {settings.embedding_provider}")
    return embedding_provider

async def analyze_query_type(state: AgentState) -> AgentState:
    """Analyze the user's query to determine if it's a review or compliance check"""
    logger.info("Analyzing query type...")

    # This would be determined by the handler, so just return state
    return state


async def retrieve_chat_messages(state: AgentState) -> AgentState:
    """Retrieve chat messages from database based on date range"""
    logger.info(f"Retrieving messages for date range: {state.get('date_start')} to {state.get('date_end')}")


    async with AsyncSessionLocal() as db:
        stmt = select(Message)

        if state.get("chat_id"):
            stmt = stmt.where(Message.chat_id == state["chat_id"])
        if state.get("date_start"):
            stmt = stmt.filter(Message.timestamp >= datetime.fromisoformat(state["date_start"]))
        if state.get("date_end"):
            stmt = stmt.filter(Message.timestamp <= datetime.fromisoformat(state["date_end"]))

        stmt = stmt.order_by(Message.timestamp)
        result = await db.execute(stmt)
        results = result.scalars().all()

        messages = [
            {
                "sender_name": msg.sender_name,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in results
        ]

    state["chat_messages"] = messages
    return state


async def generate_review(state: AgentState) -> AgentState:
    """Generate a summary review of the chat messages"""
    logger.info("Generating chat review...")

    if not state.get("chat_messages"):
        state["analysis_result"] = "Нет сообщений для анализа в указанном диапазоне дат."
        return state

    messages_text = "\n".join([
        f"[{m['timestamp']}] {m['sender_name']}: {m['content']}"
        for m in state["chat_messages"]
    ])

    prompt = f"""Ты - эксперт по анализу чатов. Проанализируй следующие сообщения и предоставь краткое ревью.

Сообщения:
{messages_text[:8000]}

Пожалуйста, предоставь ревью в следующем формате:
1. Общая тематика переписки
2. Ключевые моменты и важные решения
3. Основные участники и их роли
4. Итог и рекомендации

Ревью должно быть кратким, информативным и на русском языке."""
    llm = get_llm_provider()
    if not llm:
        raise exceptions.AnalysisException("No LLM provider")
    response = await llm.generate(prompt)
    if hasattr(response, 'content'):
        state["analysis_result"] = response.content
    else:
        state["analysis_result"] = str(response)
    return state


async def check_compliance(state: AgentState) -> AgentState:
    """Check if chat messages comply with the given instruction"""
    logger.info("Checking compliance with instruction...")

    messages_text = "\n".join([
        f"[{m['timestamp']}] {m['sender_name']}: {m['content']}"
        for m in state["chat_messages"]
    ])

    instruction = state.get("instruction", "")

    prompt = f"""Ты - эксперт по анализу соответствия чатов заданным инструкциям.

Инструкция (требования к чату):
{instruction}

Сообщения для анализа:
{messages_text[:8000]}

Проанализируй, соответствует ли переписка заданной инструкции. Если есть отклонения, укажи их.

Ответь в формате:
1. Общая оценка соответствия (Соответствует / Частично соответствует / Не соответствует)
2. Отклонения (если есть):
   - Отклонение 1: описание и где именно это произошло
   - Отклонение 2: описание и где именно это произошло
3. Рекомендации по улучшению"""
    llm = get_llm_provider()
    if not llm:
        raise exceptions.AnalysisException("No LLM provider")
    response = await llm.generate(prompt)
    state["analysis_result"] = response.content
    return state


async def extract_deviations(state: AgentState) -> AgentState:
    """Extract specific deviations from the analysis for compliance check"""
    # This would parse the analysis result to extract structured deviations
    # For simplicity, we'll return the analysis as-is
    return state