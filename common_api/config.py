from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # Database Postgresql
    database_url: str = Field(default=f"postgresql://analyzer:password@localhost:5432/chat_analyzer",
                              alias="DATABASE_URL")
    db_password: Optional[str] = Field(default=None, alias="DB_PASSWORD")

    api_keys_raw: str = Field(default="", alias="API_KEYS")
    admin_api_key: str = Field(default="", alias="ADMIN_API_KEY")

    # CORS Settings
    cors_allowed_origins: str = Field(
        default="http://localhost:8000",
        alias="CORS_ALLOWED_ORIGINS"
    )
    cors_allow_credentials: bool = Field(default=True, alias="CORS_ALLOW_CREDENTIALS")

    # Server Settings
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_reload: bool = Field(default=False, alias="API_RELOAD")
    debug: bool = Field(default=False, alias="DEBUG")

    @property
    def api_tokens(self) -> List[str]:
        """Parse API tokens from comma-separated string"""
        if not self.api_keys_raw:
            return []
        return [token.strip() for token in self.api_keys_raw.split(",") if token.strip()]

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS allowed origins from comma-separated string"""
        return [origin.strip() for origin in self.cors_allowed_origins.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"  # Игнорировать лишние поля из .env
        populate_by_name = True  # Позволяет использовать как DB_PASSWORD, так и db_password


settings = Settings()
