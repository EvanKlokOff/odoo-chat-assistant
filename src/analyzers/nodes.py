import logging
from datetime import datetime

from src.config import settings
from src.analyzers.state import AgentState
from src.llm.base import BaseLLMProvider, BaseEmbeddingProvider
from src.llm.factory import LLMFactory
from src.llm import exceptions
from src.analyzers.embedding_service import embedding_service
from src.database import crud

logger = logging.getLogger(__name__)

llm_provider: BaseLLMProvider | None = None
embedding_provider: BaseEmbeddingProvider | None = None

def get_llm_provider() -> BaseLLMProvider | None:
    """Ленивая инициализация LLM провайдера"""
    global llm_provider
    if llm_provider is None:
        llm_provider = LLMFactory.create_llm_provider(
            provider_type=settings.llm_provider,
            model=getattr(settings, 'ollama_llm_model'),
            base_url=settings.ollama_base_url,
            temperature=settings.llm_temperature,
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

    # Формируем поисковый запрос
    if state["query_type"] == "review":
        query = "ключевые темы обсуждения основные решения важные моменты"
    else:  # compliance
        instruction = state.get("instruction", "")
        query = f"проверка соответствия инструкции: {instruction}"

    relevant_messages = await embedding_service.retrieve_relevant_messages(
        chat_id=state["chat_id"],
        query=query,
        date_start=state.get("date_start"),
        date_end=state.get("date_end"),
        limit=10  # Берем только 10 самых релевантных
    )
    if not relevant_messages:
        # Fallback: берем последние сообщения если RAG не нашел
        logger.warning("No relevant messages found, falling back to recent messages")
        messages = await crud.get_chat_messages(
            chat_id=state["chat_id"],
            date_start=datetime.fromisoformat(state["date_start"]) if state.get("date_start") else None,
            date_end=datetime.fromisoformat(state["date_end"]) if state.get("date_end") else None,
            limit=20,
            order_desc=True
        )
        relevant_messages = [
            {
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "sender_name": msg.sender_name
            }
            for msg in messages
        ]
    state["chat_messages"] = relevant_messages
    logger.info(f"Retrieved {len(relevant_messages)} relevant messages")

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

    prompt = f"""Ты - эксперт по анализу деловой переписки. Проанализируй диалог и извлеки структурированную информацию.

## Правила анализа:
1. Имена участников: используй ТОЛЬКО те имена, которые указаны в сообщениях (username, full name, first name)
2. Не додумывай и не путай участников - если имя не указано, используй "Участник 1", "Участник 2"
3. Все суммы, даты, условия фиксируй ТОЧНО как в тексте

Анализируемые сообщения:
{messages_text[:8000]}

## Требуемый формат ответа:

### 1. ИНФОРМАЦИЯ О СДЕЛКЕ (если есть):
- Статус сделки: [ЗАКЛЮЧЕНА / НЕ ЗАКЛЮЧЕНА / ОБСУЖДАЕТСЯ / НЕ УПОМИНАЕТСЯ]
- Предмет сделки: [что именно обсуждается? товар, услуга, работа]
- Ключевые условия: [перечисли цифрами]
- Сумма и валюта: [если есть, точная цифра]
- Сроки: [дедлайны, даты, периоды]

### 2. УЧАСТНИКИ И РОЛИ:
- Покупатель/Заказчик: [имя участника]
- Продавец/Исполнитель: [имя участника]
- Другие участники: [имя и роль]

### 3. ПРИНЯТЫЕ РЕШЕНИЯ:
- Решение 1: [что решили, кто предложил]
- Решение 2: [если есть]

### 4. НЕ РЕШЕННЫЕ ВОПРОСЫ (если есть):
- Вопрос 1: [что осталось не согласовано]

### 5. ИТОГ И РЕКОМЕНДАЦИИ:
[2-3 предложения с выводами]

## Важно:
- Если информация отсутствует, пиши "НЕ УКАЗАНО"
- Не добавляй предположения от себя
- Пиши на русском языке, кратко и по делу"""
    llm = get_llm_provider()
    if not llm:
        raise exceptions.AnalysisException("No LLM provider")

    response = await llm.generate(prompt)
    state["analysis_result"] = response.content if hasattr(response, 'content') else str(response)

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
    state["analysis_result"] = response.content if hasattr(response, 'content') else str(response)
    return state


async def extract_deviations(state: AgentState) -> AgentState:
    """Extract specific deviations from the analysis for compliance check"""
    # This would parse the analysis result to extract structured deviations
    # For simplicity, we'll return the analysis as-is
    return state