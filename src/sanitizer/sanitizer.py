# src/sanitizer/sanitizer.py
import logging
from typing import Tuple, Optional
from src.sanitizer.config import config

logger = logging.getLogger(__name__)


class MessageSanitizer:
    """Класс для санитайзинга сообщений и защиты от промпт-инъекций"""

    def __init__(self):
        self.injection_patterns = config.prompt_injection_patterns

    def check_message(self, text: str, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Проверяет сообщение на наличие запрещенного контента

        Returns:
            Tuple[is_safe, warning_message]
            is_safe: True - сообщение безопасно, False - обнаружено нарушение
            warning_message: сообщение для отправки пользователю (если есть нарушение)
        """
        if not text:
            return True, None

        # Проверка на запрещенные категории
        forbidden_result = config.check_forbidden(text)
        if forbidden_result:
            category, phrase, warning = forbidden_result
            logger.warning(f"User {user_id} used forbidden content: category={category}, phrase={phrase}")
            return False, warning

        # Проверка на промпт-инъекции
        injection_match = config.check_prompt_injection(text)
        if injection_match:
            logger.warning(f"User {user_id} attempted prompt injection: {injection_match}")
            warning = config.warning_messages.get("prompt_injection", "Обнаружена попытка взлома!")
            return False, warning

        return True, None

    def is_safe(self, text: str) -> bool:
        """Быстрая проверка на безопасность без логирования"""
        if not text:
            return True

        # Проверка на запрещенные категории
        if config.check_forbidden(text):
            return False

        # Проверка на промпт-инъекции
        if config.check_prompt_injection(text):
            return False

        return True


# Глобальный экземпляр санитайзера
sanitizer = MessageSanitizer()