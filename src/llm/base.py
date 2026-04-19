from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class Message:
    """Сообщение для диалога"""
    role: str  # 'system', 'user', 'assistant'
    content: str


class BaseLLMProvider(ABC):
    """Абстрактный класс для всех LLM провайдеров"""

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None):
        """Генерация текста по промпту"""
        pass

    @abstractmethod
    async def chat(self, messages: List[Message]):
        """Диалог с моделью"""
        pass

    @abstractmethod
    async def generate_with_template(self, template: str, **kwargs):
        """Генерация с использованием шаблона"""
        pass


class BaseEmbeddingProvider(ABC):
    """Абстрактный класс для эмбеддинг-провайдеров"""

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """Получение эмбеддинга для текста"""
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Получение эмбеддингов для нескольких текстов"""
        pass