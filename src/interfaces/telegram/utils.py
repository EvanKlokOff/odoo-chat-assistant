import uuid
from datetime import datetime, timedelta
import re
from functools import wraps
from aiogram import types

from src.database import crud
from src.interfaces.telegram import keyboards
import logging
from src.tasks.analysis_tasks import run_review_analysis, run_compliance_analysis

logger = logging.getLogger(__name__)


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


def get_date_hours(hours: int):
    """Возращает диапозон дат, длинной в hours часов"""
    now = datetime.now()
    date_start = (now - timedelta(hours=hours)).isoformat()
    date_end = now.isoformat()
    return date_start, date_end, None


async def parse_date_from_callback(callback_data: str, command_type: str) -> tuple:
    """Parse date from callback data"""
    now = datetime.now()

    if callback_data == f"{command_type}_date_all":
        return None, None, None  # Весь период

    elif callback_data == f"{command_type}_date_today":
        date_start = datetime(now.year, now.month, now.day).isoformat()
        date_end = now.isoformat()
        return date_start, date_end, None

    elif callback_data == f"{command_type}_date_hour":
        return get_date_hours(1)

    elif callback_data == f"{command_type}_date_5hour":
        return get_date_hours(5)

    elif callback_data == f"{command_type}_date_12hour":
        return get_date_hours(12)

    elif callback_data == f"{command_type}_date_24hour":
        return get_date_hours(24)


    elif callback_data == f"{command_type}_custom":
        return None, None, None

    elif callback_data == f"{command_type}_date_cancel":
        return None, None, "cancel"

    return None, None, "Неизвестный выбор"


async def run_review_analysis_async(
        message: types.Message,
        user_id: int,
        chat_id: str,
        date_start: str,
        date_end: str
):
    """Асинхронный запуск анализа ревью через Celery"""
    logger.info(f"🔍 Creating task for user_id: {message.from_user.id}, username: {message.from_user.username}")
    task_id = str(uuid.uuid4())

    # Создаем запись в БД
    await crud.create_analysis_task(
        user_id=user_id,
        chat_id=chat_id,
        task_type="review",
        task_id=task_id,
        date_start=date_start,
        date_end=date_end
    )

    # Отправляем задачу в Celery
    run_review_analysis.delay(
        user_id=user_id,
        chat_id=chat_id,
        date_start=date_start,
        date_end=date_end,
        task_id=task_id
    )

    # Сообщаем пользователю
    await message.answer(
        "🔄 *Анализ запущен в фоновом режиме*\n\n"
        f"ID задачи: `{task_id[:8]}...`\n\n"
        "Я уведомлю вас, когда анализ будет готов.\n"
        "Обычно это занимает до 30 секунд.\n\n",
        parse_mode="Markdown",
        reply_markup=keyboards.main_menu_keyboard
    )


async def run_compliance_analysis_async(
        message: types.Message,
        user_id: int,
        chat_id: str,
        instruction: str,
        date_start: str | None,
        date_end: str | None
):
    """Асинхронный запуск проверки соответствия через Celery"""
    logger.info(f"🔍 Creating task for user_id: {user_id}, username: {message.from_user.username}")

    logger.info(f"🔍 DEBUG: message.from_user.id = {message.from_user.id}")
    logger.info(f"🔍 DEBUG: message.from_user.username = {message.from_user.username}")
    logger.info(f"🔍 DEBUG: message.chat.id = {message.chat.id}")
    logger.info(f"🔍 DEBUG: message.chat.type = {message.chat.type}")

    task_id = str(uuid.uuid4())

    # Создаем запись в БД
    await crud.create_analysis_task(
        user_id=user_id,
        chat_id=chat_id,
        task_type="compliance",
        task_id=task_id,
        instruction=instruction,
        date_start=date_start,
        date_end=date_end
    )

    # Отправляем задачу в Celery
    run_compliance_analysis.delay(
        user_id=user_id,
        chat_id=chat_id,
        instruction=instruction,
        date_start=date_start,
        date_end=date_end,
        task_id=task_id
    )

    # Сообщаем пользователю
    instruction_preview = instruction[:100] + "..." if len(instruction) > 100 else instruction
    await message.answer(
        f"🔄 *Проверка соответствия запущена*\n\n"
        f"📝 Инструкция: {instruction_preview}\n\n"
        f"ID задачи: `{task_id[:8]}...`\n\n"
        "Я уведомлю вас, когда проверка будет завершена.\n"
        "Обычно это занимает до 30 секунд.",
        parse_mode="Markdown",
        reply_markup=keyboards.main_menu_keyboard
    )


# def escape_markdown(text: str) -> str:
#     """Escape special characters for Telegram MarkdownV2"""
#     special_chars = r'_*[]()~`>#+-=|{}.!'
#     return re.sub(f'([{re.escape(special_chars)}])', r'\\\1', text)
#
#
# async def send_long_message(message: types.Message, text: str, prefix: str = "",
#                             parse_mode: str = "Markdown"):
#     """Split long message into multiple parts"""
#     max_length = 4000
#
#     safe_text = escape_markdown(text)
#     full_message = f"{prefix}\n\n{safe_text}" if prefix else safe_text
#
#     if len(full_message) <= max_length:
#         await message.answer(full_message, parse_mode=parse_mode)
#         return
#
#     # Если сообщение слишком длинное, разбиваем на части
#     if prefix:
#         first_part = f"{prefix}\n\n"
#         remaining = safe_text
#     else:
#         first_part = ""
#         remaining = safe_text
#
#     parts = []
#     current_part = first_part
#
#     for line in remaining.split('\n'):
#         if len(current_part) + len(line) + 1 > max_length:
#             parts.append(current_part)
#             current_part = line
#         else:
#             current_part += '\n' + line if current_part else line
#
#     if current_part:
#         parts.append(current_part)
#
#     # Отправляем все части
#     for i, part in enumerate(parts):
#         if i == 0 and prefix:
#             await message.answer(part, parse_mode=parse_mode)
#         else:
#             await message.answer(part, parse_mode=parse_mode)

import re
from typing import Tuple, Optional, List


def escape_markdown(text: str) -> str:
    """
    Экранирует специальные символы для Telegram Markdown (старая версия)

    Спецсимволы: _ * [ ] ( ) ~ ` > # + - = | { } . !
    Для старого Markdown нужно экранировать:
    - _ * [ ] ( ) ~ ` > # + - = | { } . !
    - Обратные кавычки для кода экранируем, но осторожно
    """
    if not text:
        return text

    # Специальные символы Markdown
    special_chars = r'_*[]()~`>#+\-=|{}.!'

    # Экранируем все спецсимволы
    escaped = re.sub(f'([{re.escape(special_chars)}])', r'\\\1', text)

    # Возвращаем обратно экранирование для обратных кавычек внутри кода
    # (это упрощенная версия, для сложных случаев лучше использовать preserve_code_blocks)
    return escaped


def escape_markdown_preserve_code(text: str) -> str:
    """
    Экранирует Markdown, сохраняя кодовые блоки ```code``` и `code`
    """
    if not text:
        return text

    special_chars = r'_*[]()~>#+\-=|{}.!'
    result = []
    pos = 0
    length = len(text)

    while pos < length:
        # Проверяем многострочный кодовый блок
        if pos + 2 < length and text[pos:pos + 3] == '```':
            end_pos = text.find('```', pos + 3)
            if end_pos != -1:
                # Копируем блок без экранирования
                result.append(text[pos:end_pos + 3])
                pos = end_pos + 3
                continue

        # Проверяем инлайн-код
        elif text[pos] == '`':
            end_pos = text.find('`', pos + 1)
            if end_pos != -1:
                # Проверяем, что это не начало ``````
                if end_pos + 1 < length and text[end_pos + 1] == '`':
                    result.append(re.sub(f'([{re.escape(special_chars)}])', r'\\\1', text[pos]))
                    pos += 1
                    continue

                # Инлайн-код: копируем без экранирования
                result.append(text[pos:end_pos + 1])
                pos = end_pos + 1
                continue

        # Обычный текст - экранируем спецсимволы
        result.append(re.sub(f'([{re.escape(special_chars)}])', r'\\\1', text[pos]))
        pos += 1

    return ''.join(result)


def split_long_message(text: str, max_length: int = 4096) -> List[str]:
    """
    Разбивает длинное сообщение на части, сохраняя целостность строк

    Args:
        text: Текст для разбиения
        max_length: Максимальная длина одной части (Telegram: 4096)

    Returns:
        Список частей сообщения
    """
    if len(text) <= max_length:
        return [text]

    parts = []
    lines = text.split('\n')
    current_part = ""

    for line in lines:
        # Если одна строка длиннее лимита, разбиваем её
        if len(line) > max_length:
            if current_part:
                parts.append(current_part)
                current_part = ""

            # Разбиваем длинную строку
            for i in range(0, len(line), max_length):
                parts.append(line[i:i + max_length])
            continue

        # Проверяем, влезет ли строка в текущую часть
        if len(current_part) + len(line) + 1 > max_length:
            parts.append(current_part)
            current_part = line
        else:
            if current_part:
                current_part += "\n" + line
            else:
                current_part = line

    if current_part:
        parts.append(current_part)

    return parts


def prepare_markdown_message(
        text: str,
        preserve_code_blocks: bool = True,
        max_length: int = 4096
) -> Tuple[List[str], str]:
    """
    Подготавливает сообщение с Markdown форматированием

    Args:
        text: Исходный текст
        preserve_code_blocks: Сохранять ли кодовые блоки
        max_length: Максимальная длина сообщения

    Returns:
        (parts, parse_mode) - части сообщения и режим парсинга
    """
    # Экранируем текст
    if preserve_code_blocks:
        safe_text = escape_markdown_preserve_code(text)
    else:
        safe_text = escape_markdown(text)

    # Разбиваем на части
    parts = split_long_message(safe_text, max_length)

    return parts, "Markdown"


def clean_llm_response(text: str, task_id: str = "", task_type: str = "review") -> Tuple[List[str], str]:
    """
    Подготавливает ответ LLM к отправке в Telegram

    Args:
        text: Результат от LLM
        task_id: ID задачи (опционально)
        task_type: Тип задачи (review или compliance)

    Returns:
        (message_parts, parse_mode)
    """
    # Ограничиваем длину текста
    if len(text) > 3500:
        text = text[:3500] + "\n\n...(результат сокращен)"

    # Выбираем заголовок
    if task_type == "review":
        header = "📊 *Ревью чата завершено!*"
    else:
        header = "✅ *Проверка соответствия завершена!*"

    # Формируем полное сообщение
    if task_id:
        full_message = (
            f"{header}\n\n"
            f"📝 *Результат:*\n{text}\n\n"
            f"🆔 ID задачи: `{task_id[:8]}...`"
        )
    else:
        full_message = (
            f"{header}\n\n"
            f"📝 *Результат:*\n{text}"
        )

    # Подготавливаем с сохранением кодовых блоков
    return prepare_markdown_message(full_message, preserve_code_blocks=True)
