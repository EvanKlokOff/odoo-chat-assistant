# src/sanitizer/config.py
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import json
import re
import logging

logger = logging.getLogger(__name__)


class ForbiddenCategory:
    """Класс для категории запрещенных фраз"""

    def __init__(self, category_data: Dict[str, Any]):
        self.name = category_data.get("category", "Unknown")
        self.text_phrases = [p.lower() for p in category_data.get("text", [])]
        self.re_templates = category_data.get("re_templates", [])
        self.compiled_patterns = []

        # Компилируем регулярные выражения
        for pattern in self.re_templates:
            try:
                self.compiled_patterns.append(re.compile(pattern, re.IGNORECASE | re.UNICODE))
            except re.error as e:
                logger.error(f"Invalid regex pattern '{pattern}' in category '{self.name}': {e}")

    def check_text(self, text: str) -> Optional[Tuple[str, str]]:
        """
        Проверяет текст на соответствие категории

        Returns:
            Tuple(category_name, matched_phrase) если найдено, иначе None
        """
        text_lower = text.lower()

        # Проверяем точные фразы
        for phrase in self.text_phrases:
            if phrase in text_lower:
                return (self.name, phrase)

        # Проверяем регулярные выражения
        for pattern in self.compiled_patterns:
            match = pattern.search(text)
            if match:
                matched_text = match.group(0)
                return (self.name, matched_text)

        return None


class SanitizerConfig:
    """Конфигурация для санитайзера"""

    def __init__(self):
        # Загружаем запрещенные категории ТОЛЬКО из JSON
        self.forbidden_categories = self._load_forbidden_categories()

        # Загружаем паттерны промпт-инъекций из отдельного файла
        self.prompt_injection_patterns = self._load_prompt_injection_patterns()

        # Загружаем сообщения предупреждений
        self.warning_messages = self._load_warning_messages()

        # Логируем статистику загрузки
        self._log_stats()

    def _load_forbidden_categories(self) -> List[ForbiddenCategory]:
        """Загружает запрещенные категории ТОЛЬКО из JSON файла"""
        json_file = Path(__file__).parent / "forbidden_categories.json"
        categories = []

        # Обязательно проверяем существование файла
        if not json_file.exists():
            logger.error(f"Forbidden categories file not found: {json_file}")
            logger.info("Please create forbidden_categories.json file with categories")
            return categories

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                categories_data = json.load(f)

            for category_data in categories_data:
                category = ForbiddenCategory(category_data)
                categories.append(category)

            logger.info(f"✅ Loaded {len(categories)} forbidden categories from {json_file}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {json_file}: {e}")
        except Exception as e:
            logger.error(f"Error loading forbidden categories: {e}")

        return categories

    def _load_prompt_injection_patterns(self) -> List[re.Pattern]:
        """Загружает паттерны промпт-инъекций из отдельного файла"""
        patterns_file = Path(__file__).parent / "injection_patterns.txt"
        patterns = []

        default_patterns = [
            r"ignore\s+(?:previous|above|all)\s+(?:instructions|commands|prompts)",
            r"forget\s+(?:previous|above|all)\s+(?:instructions|commands|prompts)",
            r"pretend\s+you\s+are\s+",
            r"you\s+are\s+now\s+",
            r"show\s+(?:me\s+)?(?:your|the)\s+(?:system|internal)\s+prompt",
            r"what\s+are\s+your\s+instructions",
            r"покажи\s+свой\s+промпт",
            r"игнорируй\s+предыдущие\s+инструкции",
            r"забудь\s+все\s+инструкции",
            r"ты\s+теперь\s+",
            r"отныне\s+ты\s+",
        ]

        try:
            if patterns_file.exists():
                with open(patterns_file, 'r', encoding='utf-8') as f:
                    pattern_strings = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                logger.info(f"✅ Loaded {len(pattern_strings)} injection patterns from {patterns_file}")
            else:
                logger.warning(f"Injection patterns file not found: {patterns_file}")
                logger.info(f"Creating default patterns file: {patterns_file}")
                self._create_default_patterns_file(patterns_file, default_patterns)
                pattern_strings = default_patterns

            for pattern_str in pattern_strings:
                try:
                    patterns.append(re.compile(pattern_str, re.IGNORECASE | re.UNICODE))
                except re.error as e:
                    logger.error(f"Invalid injection pattern '{pattern_str}': {e}")

        except Exception as e:
            logger.error(f"Error loading injection patterns: {e}")
            # Добавляем дефолтные паттерны как fallback
            for pattern_str in default_patterns:
                try:
                    patterns.append(re.compile(pattern_str, re.IGNORECASE | re.UNICODE))
                except re.error:
                    pass

        return patterns

    def _create_default_patterns_file(self, file_path: Path, default_patterns: List[str]):
        """Создает файл с паттернами по умолчанию"""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("# Паттерны для обнаружения промпт-инъекций (регулярные выражения)\n")
                f.write("# Каждая строка - один паттерн\n")
                f.write("# Строки, начинающиеся с #, игнорируются\n\n")
                for pattern in default_patterns:
                    f.write(f"{pattern}\n")
            logger.info(f"✅ Created default injection patterns file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to create default patterns file: {e}")

    def _load_warning_messages(self) -> dict:
        """Загружает сообщения предупреждений"""
        messages_file = Path(__file__).parent / "warning_messages.json"

        default_messages = {
            "prompt_injection": "🔒 *Обнаружена попытка взлома!*\n\nВаше сообщение содержит попытку промпт-инъекции - это попытка взломать систему.\n\n*Действие:* Сообщение заблокировано и не будет обработано.\n\n*Предупреждение:* Повторные попытки могут привести к блокировке.",

            "multiple_violations": "🚫 *КРИТИЧЕСКОЕ НАРУШЕНИЕ!*\n\nВы совершили {count} нарушений за последние {minutes} минут.\n\nВаш аккаунт временно заблокирован на {block_minutes} минут.\n\nДата и время блокировки: {timestamp}",

            "block_expired": "✅ *Блокировка снята*\n\nВы снова можете использовать бота.\n\nПожалуйста, соблюдайте правила использования.",

            "default_category": "⚠️ *Нарушение правил!*\n\nВаше сообщение относится к категории *{category}* и содержит запрещенные высказывания.\n\n*Запрещенная фраза:* `{phrase}`\n\nТакие темы обсуждать нельзя. Пожалуйста, соблюдайте правила общения."
        }

        try:
            if messages_file.exists():
                with open(messages_file, 'r', encoding='utf-8') as f:
                    messages = json.load(f)
                logger.info(f"✅ Loaded warning messages from {messages_file}")
                # Объединяем с дефолтными (дефолтные добавляем если нет в файле)
                return {**default_messages, **messages}
            else:
                logger.warning(f"Warning messages file not found: {messages_file}, using defaults")
                return default_messages
        except Exception as e:
            logger.error(f"Error loading warning messages: {e}")
            return default_messages

    def _log_stats(self):
        """Логирует статистику загрузки"""
        logger.info("=" * 50)
        logger.info("📋 Sanitizer Configuration Loaded:")
        logger.info(f"  - Forbidden categories: {len(self.forbidden_categories)}")
        for cat in self.forbidden_categories:
            logger.info(f"    • {cat.name}: {len(cat.text_phrases)} phrases, {len(cat.re_templates)} patterns")
        logger.info(f"  - Prompt injection patterns: {len(self.prompt_injection_patterns)}")
        logger.info("=" * 50)

    def check_forbidden(self, text: str) -> Optional[Tuple[str, str, str]]:
        """
        Проверяет текст на наличие запрещенных фраз из любой категории

        Returns:
            Tuple(category_name, matched_phrase, warning_message) если найдено, иначе None
        """
        for category in self.forbidden_categories:
            result = category.check_text(text)
            if result:
                category_name, matched_phrase = result
                warning = self.warning_messages.get(
                    f"category_{category_name.lower().replace(' ', '_')}",
                    self.warning_messages.get("default_category",
                                              f"⚠️ *Нарушение правил!*\n\nВаше сообщение относится к категории *{category_name}* и содержит запрещенные высказывания.\n\n*Запрещенная фраза:* `{matched_phrase}`\n\nТакие темы обсуждать нельзя. Пожалуйста, соблюдайте правила общения."
                                              )
                ).format(
                    category=category_name,
                    phrase=matched_phrase
                )
                return (category_name, matched_phrase, warning)

        return None

    def check_prompt_injection(self, text: str) -> Optional[str]:
        """
        Проверяет текст на наличие промпт-инъекций

        Returns:
            Matched pattern если найдено, иначе None
        """
        for pattern in self.prompt_injection_patterns:
            if pattern.search(text):
                return pattern.pattern
        return None


config = SanitizerConfig()