from datetime import datetime, timedelta
import re
from html import escape
from functools import wraps
from aiogram import types

import logging

logger = logging.getLogger(__name__)

async def handle_unknown_command(message: types.Message):
    """Обработчик неизвестных команд"""
    command = message.text.split()[0] if message.text else "unknown"

    if message.chat.type == "private":
        # В ЛС - показываем help
        from src.interfaces.telegram.handlers import main_keyboard, get_help_text

        await message.answer(
            f"❓ Неизвестная команда: `{command}`\n\n"
            f"{get_help_text()}",
            parse_mode="Markdown",
            reply_markup=main_keyboard
        )
    else:
        # В группе - просто логируем
        user_info = f"{message.from_user.full_name} (ID: {message.from_user.id})"
        logger.info(f"⚠️ Unknown command '{command}' from {user_info} in chat {message.chat.id} ({message.chat.title})")

def private_chat_only(func):
    """Декоратор для команд, которые работают только в ЛС"""
    @wraps(func)
    async def wrapper(message: types.Message, *args, **kwargs):
        if message.chat.type != "private":
            await message.answer(
                "⚠️ Эта команда доступна только в личном диалоге с ботом.\n\n"
                "Пожалуйста, перейдите в ЛС: https://t.me/" + (await message.bot.get_me()).username
            )
            return
        return await func(message, *args, **kwargs)
    return wrapper

def escape_markdown(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2"""
    special_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(special_chars)}])', r'\\\1', text)

def escape_html(text: str) -> str:
    """Escape special characters for HTML"""
    return escape(text)

def parse_review_parameters(text: str|None)-> tuple[str|None, str|None, str|None]:
    """
    Parse review command parameters.
    Returns tuple (date_start, date_end, error_message)
    """
    parts = text.split()

    if len(parts) < 2:
        return None, None, "Укажите параметры: даты или ключевые слова (to_day, to_hour, to_N_hour)"

    param = parts[1].lower()
    now = datetime.now()

    # Check for to_day keyword
    if param == "to_day":
        date_start = datetime(now.year, now.month, now.day).isoformat()
        date_end = now.isoformat()
        return date_start, date_end, None

    # Check for to_hour keyword
    if param == "to_hour":
        date_start = (now - timedelta(hours=1)).isoformat()
        date_end = now.isoformat()
        return date_start, date_end, None

    # Check for to_N_hour pattern
    if param.startswith("to_") and param.endswith("_hour"):
        try:
            # Extract N from to_N_hour
            n_str = param.replace("to_", "").replace("_hour", "")
            try:
                n = int(n_str)
            except ValueError:
                return None, None, "Требуется ввести кол-во часов в формате to_N_hour, где N от 1 до 24"
            # Validate N (max 24 hours)
            if n <= 0:
                return None, None, "Количество часов должно быть положительным числом"

            if n > 24:
                return None, None, "Максимальное количество часов - 24. Укажите значение от 1 до 24"

            date_start = (now - timedelta(hours=n)).isoformat()
            date_end = now.isoformat()
            return date_start, date_end, None

        except ValueError:
            return None, None, f"Неверный формат: '{param}'. Используйте: to_ЧИСЛО_hour (например, to_5_hour)"

    # Try to parse as dates
    try:
        date_start = datetime.strptime(parts[1], "%d.%m.%Y").isoformat()

        if len(parts) >= 3:
            date_end = datetime.strptime(parts[2], "%d.%m.%Y").isoformat()
        else:
            date_end = datetime.now().isoformat()

        return date_start, date_end, None

    except ValueError as e:
        return None, None, f"Неверный формат даты. Используйте ДД.ММ.ГГГГ или ключевые слова: to_day, to_hour, to_N_hour"
