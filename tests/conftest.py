import pytest
from src.config import settings
from src.llm.factory import LLMFactory
from src.llm.base import BaseLLMProvider, BaseEmbeddingProvider


@pytest.fixture(scope="function")
def mock_llm() -> BaseLLMProvider:
    """Create mock provider for testing"""
    provider = LLMFactory.create_llm_provider(
        provider_type="mock",
        model="mock"
    )
    return provider


@pytest.fixture(scope="function")
def ollama_llm() -> BaseLLMProvider:
    """Create Ollama LLM provider for testing"""
    provider = LLMFactory.create_llm_provider(
        provider_type="ollama",
        model="gemma3:27b",
        base_url=settings.ollama_base_url,
        temperature=0.1
    )
    return provider


@pytest.fixture(scope="function")
def gemma3_llm() -> BaseLLMProvider:
    """Create optimized Gemma 3 provider for testing"""
    provider = LLMFactory.create_llm_provider(
        provider_type="gemma3",
        base_url=settings.ollama_base_url,
        model_size="27b",
        temperature=0.1
    )
    return provider


@pytest.fixture(scope="function")
def nomic_embedding() -> BaseEmbeddingProvider:
    """Create Nomic embedding provider for testing"""
    provider = LLMFactory.create_embedding_provider(
        provider_type="nomic",
        model="nomic-embed-text",
        base_url=settings.ollama_base_url
    )
    return provider


@pytest.fixture(scope="function")
def sample_messages() -> list:
    """Sample messages for testing"""
    return [
        {
            "sender_name": "Алексей",
            "content": "Здравствуйте! Хочу приобрести квартиру в центре города.",
            "timestamp": "2025-04-01T10:00:00"
        },
        {
            "sender_name": "Менеджер",
            "content": "Добрый день! Какие требования по квартире?",
            "timestamp": "2025-04-01T10:05:00"
        },
        {
            "sender_name": "Алексей",
            "content": "Нужна 2-комнатная, с ремонтом, до 15 млн рублей.",
            "timestamp": "2025-04-01T10:10:00"
        },
        {
            "sender_name": "Менеджер",
            "content": "Отлично! У нас есть несколько вариантов. Пришлите удобное время для просмотра.",
            "timestamp": "2025-04-01T10:15:00"
        }
    ]


@pytest.fixture(scope="function")
def sample_instruction() -> str:
    """Sample instruction for compliance testing"""
    return """
    Чат по продаже недвижимости.
    Характер переписки: деловой, профессиональный.
    Цель: продажа квартир клиентам.
    Требования: вежливое общение, предоставление полной информации по объектам,
    оперативные ответы на вопросы клиентов.
    """