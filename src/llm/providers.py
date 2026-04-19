import logging
from dataclasses import dataclass
from typing import List, Optional, Dict
from langchain_ollama import ChatOllama, OllamaEmbeddings
from src.llm.base import BaseLLMProvider, BaseEmbeddingProvider, Message
from src.llm import utils
logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Провайдер для локального Ollama с оптимизациями для Gemma 3"""

    def __init__(
            self,
            model: str,
            base_url: str,
            temperature: float = 0.1,
            num_ctx: int = 4096,  # Размер контекста
            num_predict: int = 2048,  # Максимальная длина ответа
            top_k: int = 40,
            top_p: float = 0.9,
            repeat_penalty: float = 1.1,
            # Специальные оптимизации для Mac
            flash_attention: bool = True,
            kv_cache_type: str = "q8_0"
    ):
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        self.top_k = top_k
        self.top_p = top_p
        self.repeat_penalty = repeat_penalty
        self.flash_attention = flash_attention
        self.kv_cache_type = kv_cache_type
        self._llm = None

    def _get_llm(self):
        if self._llm is None:
            # Базовые параметры
            llm_kwargs = {
                "model": self.model,
                "base_url": self.base_url,
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
                "top_k": self.top_k,
                "top_p": self.top_p,
                "repeat_penalty": self.repeat_penalty,
            }

            # Добавляем оптимизации для Mac (если поддерживаются)
            if self.flash_attention:
                llm_kwargs["num_gpu"] = -1  # Использовать все GPU
                # Flash Attention включается через переменные окружения
                # OLLAMA_FLASH_ATTENTION=1

            logger.info(f"Initializing Ollama model: {self.model} with context size: {self.num_ctx}")
            self._llm = ChatOllama(**llm_kwargs)

        return self._llm

    async def generate(self, prompt: str, system_prompt: Optional[str] = None):
        """Генерация текста с поддержкой system prompt для Gemma 3"""
        messages = []

        # Gemma 3 поддерживает system prompt через специальный формат
        if system_prompt:
            # Для Gemma 3 можно использовать стандартный формат
            messages.append(("system", system_prompt))

        messages.append(("user", prompt))

        try:
            response = await self._get_llm().ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            # Fallback: пробуем без system prompt
            if system_prompt:
                logger.info("Retrying without system prompt...")
                return await self.generate(prompt)
            raise

    async def chat(self, messages: List[Message]):
        """Диалог с моделью"""
        langchain_messages = [(m.role, m.content) for m in messages]
        response = await self._get_llm().ainvoke(langchain_messages)
        return response.content

    async def generate_with_template(self, template: str, **kwargs):
        """Генерация с использованием шаблона"""
        prompt = template.format(**kwargs)
        return await self.generate(prompt)

    async def stream_generate(self, prompt: str, system_prompt: Optional[str] = None):
        """Стриминговая генерация (для длинных ответов)"""
        messages = []
        if system_prompt:
            messages.append(("system", system_prompt))
        messages.append(("user", prompt))

        async for chunk in self._get_llm().astream(messages):
            yield chunk.content


class Gemma3OptimizedProvider(OllamaProvider):
    """Специально оптимизированный провайдер для Gemma 3 на Mac"""

    def __init__(
            self,
            base_url: str = "http://localhost:11434",
            model_size: str = "27b",  # 2b, 9b, 27b
            temperature: float = 0.1,
            **kwargs
    ):
        model_name = f"gemma3:{model_size}"

        # Оптимальные настройки для разных размеров модели
        if model_size == "27b":
            num_ctx = 4096  # 4K контекста для 27B
            num_predict = 2048
        elif model_size == "12b":
            num_ctx = 8192  # 8K контекста для 12B
            num_predict = 4096
        else:  # 2b
            num_ctx = 16384  # 16K контекста для 2B
            num_predict = 8192

        super().__init__(
            model=model_name,
            base_url=base_url,
            temperature=temperature,
            num_ctx=num_ctx,
            num_predict=num_predict,
            flash_attention=True,
            kv_cache_type="q8_0",
            **kwargs
        )
        logger.info(f"Initialized Gemma 3 {model_size} with optimized settings (ctx={num_ctx})")

@dataclass
class MockResponse:
    """Mock ответ для совместимости с LangChain"""
    content: str

class MockProvider(BaseLLMProvider):
    """Mock-провайдер для тестирования"""

    def __init__(self, mock_responses: Optional[Dict[str, str]] = None):
        self.mock_responses = mock_responses or {}

    async def generate(self, prompt: str, system_prompt: Optional[str] = None):
        content = "Ошибка"
        if "ревью" in prompt.lower():
            content = "Это тестовое ревью переписки. Все сообщения соответствуют деловому стилю."
        elif "соответствие" in prompt.lower() or "инструкция" in prompt.lower():
            content = """1. Общая оценка: Соответствует
2. Отклонения: не обнаружены
3. Рекомендации: продолжать в том же духе"""
        return MockResponse(content)

    async def chat(self, messages: List[Message]):
        return MockResponse("Тестовый ответ от чат-модели")

    async def generate_with_template(self, template: str, **kwargs):
        return MockResponse("Тестовый ответ на шаблон")


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """Провайдер эмбеддингов для Ollama"""

    def __init__(self, model: str, base_url: str):
        self.model = model
        self.base_url = base_url
        self._embeddings = None
        logger.info(f"Initializing Ollama embedding provider with model: {model}")

    def _get_embeddings(self):
        if self._embeddings is None:
            self._embeddings = OllamaEmbeddings(
                model=self.model,
                base_url=self.base_url,
            )
            logger.info(f"Ollama embeddings initialized: {self.model}")
        return self._embeddings

    async def embed(self, text: str) -> List[float]:
        """Получение эмбеддинга для одного текста"""
        try:
            embedding = await self._get_embeddings().aembed_query(text)
            return embedding
        except Exception as e:
            logger.error(f"Error embedding text: {e}")
            # Возвращаем нулевой вектор в случае ошибки
            return [0.0] * 768

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Получение эмбеддингов для нескольких текстов"""
        try:
            embeddings = await self._get_embeddings().aembed_documents(texts)
            return embeddings
        except Exception as e:
            logger.error(f"Error embedding batch: {e}")
            # Возвращаем список нулевых векторов
            return [[0.0] * 768 for _ in texts]


class NomicEmbedTextProvider(OllamaEmbeddingProvider):
    """Специализированный провайдер для nomic-embed-text с оптимизациями"""

    def __init__(
            self,
            base_url: str = "http://localhost:11434",
            model: str = "nomic-embed-text",
            truncation: bool = True,
            max_length: int = 8192
    ):
        super().__init__(model=model, base_url=base_url)
        self.truncation = truncation
        self.max_length = max_length
        logger.info(f"Initialized Nomic Embed Text provider (max_length={max_length})")

    async def embed(self, text: str) -> List[float]:
        """Получение эмбеддинга с поддержкой длинных текстов"""
        # Обрезаем слишком длинные тексты если нужно
        if self.truncation and len(text) > self.max_length:
            logger.warning(f"Truncating text from {len(text)} to {self.max_length} chars")
            text = text[:self.max_length]

        return await super().embed(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Пакетное получение эмбеддингов"""
        results = []
        total = len(texts)

        for i, text in enumerate(texts):
            if i % 10 == 0:
                logger.debug(f"Embedding batch progress: {i}/{total}")
            results.append(await self.embed(text))

        logger.info(f"Completed embedding {total} texts")
        return results

    async def semantic_search(self, query: str, documents: List[str]) -> List[tuple]:
        """Семантический поиск: эмбеддинг запроса и сравнение с документами"""
        query_embedding = await self.embed(query)
        doc_embeddings = await self.embed_batch(documents)

        # Вычисляем косинусное сходство
        import math

        similarities = []
        for i, doc_emb in enumerate(doc_embeddings):
            similarity = utils.cosine_similarity_np(query_embedding, doc_emb)
            similarities.append((i, similarity))

        return sorted(similarities, key=lambda x: x[1], reverse=True)