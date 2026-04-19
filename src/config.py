from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # Database
    database_url: str = Field(default="postgresql://analyzer:password@localhost:5432/chat_analyzer")
    db_password: Optional[str] = Field(default=None, alias="DB_PASSWORD")

    # Ollama
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_llm_model: str = Field(default="gemma3:27b")
    ollama_embedding_model: str = Field(default="nomic-embed-text")

    # Telegram
    telegram_bot_token: str = Field(default="")

    # LLM Provider Settings
    llm_provider: str = Field(default="gemma3")  # 'ollama', 'gemma3', 'mock', 'openai'
    embedding_provider: str = Field(default="nomic")  # 'ollama', 'nomic', 'openai'
    llm_temperature: float = Field(default=0.1)
    gemma3_model_size: str = Field(default="27b")  # '2b', '12b', '27b'

    # Legacy (для обратной совместимости)
    embedding_model: str = Field(default="nomic-embed-text")
    llm_model: str = Field(default="gemma3:27b")

    # Application Settings
    debug: bool = Field(default=False) # Режим дебага для бд - позволяет смотреть sql запросы
    log_level: str = Field(default="INFO")
    monitor_interval: int = Field(default=300, alias="MONITOR_INTERVAL")
    llm_context_size: int = Field(default=4096)
    llm_max_tokens: int = Field(default=2048)

    # Context management
    max_context_messages: int = 50
    context_window_minutes: int = 60  # Keep context for last hour
    enable_conversation_memory: bool = True

    # Performance
    batch_size: int = 100

    class Config:
        env_file = ".env"
        extra = "ignore"  # Игнорировать лишние поля из .env
        populate_by_name = True  # Позволяет использовать как DB_PASSWORD, так и db_password


settings = Settings()