from typing import Optional
from src.llm.base import BaseLLMProvider, BaseEmbeddingProvider
from src.llm.providers import (
    OllamaProvider, MockProvider,
    OllamaEmbeddingProvider, Gemma3OptimizedProvider,
    NomicEmbedTextProvider
)


class LLMFactory:
    """Фабрика для создания LLM провайдеров"""

    @staticmethod
    def create_llm_provider(
            provider_type: str,
            model: Optional[str] = None,
            api_key: Optional[str] = None,
            base_url: Optional[str] = None,
            temperature: float = 0.1,
            **kwargs
    ) -> BaseLLMProvider:
        """Создание LLM провайдера"""
        provider_type = provider_type.lower()

        if provider_type == 'ollama':
            return OllamaProvider(
                model=model or "gemma3:27b",
                base_url=base_url or "http://localhost:11434",
                temperature=temperature,
                **kwargs
            )
        elif provider_type == 'gemma3':
            model_size = kwargs.pop('model_size', '27b')
            return Gemma3OptimizedProvider(
                base_url=base_url or "http://localhost:11434",
                model_size=model_size,
                temperature=temperature,
                **kwargs
            )
        elif provider_type == 'mock':
            return MockProvider(kwargs.get('mock_responses'))
        else:
            raise ValueError(f"Неизвестный тип провайдера: {provider_type}")

    @staticmethod
    def create_embedding_provider(
            provider_type: str,
            model: Optional[str] = None,
            api_key: Optional[str] = None,
            base_url: Optional[str] = None,
            **kwargs
    ) -> BaseEmbeddingProvider:
        """Создание эмбеддинг провайдера"""
        provider_type = provider_type.lower()

        if provider_type == 'nomic':
            return NomicEmbedTextProvider(
                base_url=base_url or "http://localhost:11434",
                model=model or "nomic-embed-text",
                **kwargs
            )
        else:
            raise ValueError(f"Неизвестный тип провайдера для эмбеддингов: {provider_type}")