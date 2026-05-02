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


def escape_markdown(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2"""
    special_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(special_chars)}])', r'\\\1', text)


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


# async def run_review_analysis(message: types.Message, chat_id: str, date_start: str, date_end: str):
#     """Run review analysis"""
#     try:
#         # Prepare state for graph
#         state: AgentState = {
#             "query_type": "review",
#             "chat_id": chat_id,
#             "messages": [],
#             "date_start": date_start,
#             "date_end": date_end,
#             "instruction": None,
#             "chat_messages": [],
#             "analysis_result": None,
#             "deviations": None,
#             "current_step": "start",
#             "error": None
#         }
#
#         # Run the graph
#         graph = create_analysis_graph()
#         final_state = await graph.ainvoke(state)
#
#         # Send result
#         result = final_state.get("analysis_result", "Не удалось выполнить анализ.")
#
#         await _send_long_message(message, result, "📊 Результат анализа", "Markdown")
#         await message.answer("🏠 Главное меню", reply_markup=keyboards.main_menu_keyboard)
#
#     except Exception as e:
#         logger.error(f"Review analysis failed: {e}", exc_info=True)
#         await message.answer(
#             f"❌ Ошибка при анализе: {str(e)}\n\n"
#             "Пожалуйста, попробуйте позже.",
#             reply_markup=keyboards.main_menu_keyboard
#         )


async def run_review_analysis_async(
        message: types.Message,
        chat_id: str,
        date_start: str,
        date_end: str
):
    """Асинхронный запуск анализа ревью через Celery"""
    logger.info(f"🔍 Creating task for user_id: {message.from_user.id}, username: {message.from_user.username}")
    task_id = str(uuid.uuid4())

    # Создаем запись в БД
    await crud.create_analysis_task(
        user_id=message.from_user.id,
        chat_id=chat_id,
        task_type="review",
        task_id=task_id,
        date_start=date_start,
        date_end=date_end
    )

    # Отправляем задачу в Celery
    run_review_analysis.delay(
        user_id=message.from_user.id,
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
        chat_id: str,
        instruction: str,
        date_start: str | None,
        date_end: str | None
):
    """Асинхронный запуск проверки соответствия через Celery"""
    logger.info(f"🔍 Creating task for user_id: {message.from_user.id}, username: {message.from_user.username}")

    logger.info(f"🔍 DEBUG: message.from_user.id = {message.from_user.id}")
    logger.info(f"🔍 DEBUG: message.from_user.username = {message.from_user.username}")
    logger.info(f"🔍 DEBUG: message.chat.id = {message.chat.id}")
    logger.info(f"🔍 DEBUG: message.chat.type = {message.chat.type}")

    task_id = str(uuid.uuid4())

    # Создаем запись в БД
    await crud.create_analysis_task(
        user_id=message.from_user.id,
        chat_id=chat_id,
        task_type="compliance",
        task_id=task_id,
        instruction=instruction,
        date_start=date_start,
        date_end=date_end
    )

    # Отправляем задачу в Celery
    run_compliance_analysis.delay(
        user_id=message.from_user.id,
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

# async def run_compliance_analysis(
#         message: types.Message,
#         chat_id: str,
#         instruction: str,
#         date_start: str | None,
#         date_end: str | None
# ):
#     """Run compliance analysis"""
#     try:
#         # Prepare state for graph
#         state: AgentState = {
#             "query_type": "compliance",
#             "chat_id": chat_id,
#             "messages": [],
#             "date_start": date_start,
#             "date_end": date_end,
#             "instruction": instruction,
#             "chat_messages": [],
#             "analysis_result": None,
#             "deviations": None,
#             "current_step": "start",
#             "error": None
#         }
#
#         # Run the graph
#         graph = create_analysis_graph()
#         final_state = await graph.ainvoke(state)
#
#         # Send result
#         result = final_state.get("analysis_result", "Не удалось выполнить анализ.")
#
#         header = "✅ *Результат проверки соответствия инструкции*"
#         if date_start and date_end:
#             header += f"\n📅 *Период:* {datetime.fromisoformat(date_start).strftime('%d.%m.%Y %H:%M:%S')} - {datetime.fromisoformat(date_end).strftime('%d.%m.%Y %H:%M:%S')}"
#         else:
#             header += "\n📅 *Период:* вся доступная переписка"
#
#         await _send_long_message(message, result, header, "Markdown")
#         await message.answer("🏠 Главное меню", reply_markup=keyboards.main_menu_keyboard)
#
#     except Exception as e:
#         logger.error(f"Compliance analysis failed: {e}", exc_info=True)
#         await message.answer(
#             f"❌ Ошибка при анализе: {str(e)}\n\n"
#             "Пожалуйста, попробуйте позже.",
#             reply_markup=keyboards.main_menu_keyboard
#         )


async def _send_long_message(message: types.Message, text: str, prefix: str = "",
                             parse_mode: str | None = None):
    """Split long message into multiple parts"""
    max_length = 4000

    safe_text = escape_markdown(text)
    full_message = f"{prefix}\n\n{safe_text}" if prefix else safe_text

    if len(full_message) <= max_length:
        await message.answer(full_message, parse_mode=parse_mode)
        return

    # Если сообщение слишком длинное, разбиваем на части
    if prefix:
        first_part = f"{prefix}\n\n"
        remaining = safe_text
    else:
        first_part = ""
        remaining = safe_text

    parts = []
    current_part = first_part

    for line in remaining.split('\n'):
        if len(current_part) + len(line) + 1 > max_length:
            parts.append(current_part)
            current_part = line
        else:
            current_part += '\n' + line if current_part else line

    if current_part:
        parts.append(current_part)

    # Отправляем все части
    for i, part in enumerate(parts):
        if i == 0 and prefix:
            await message.answer(part, parse_mode=parse_mode)
        else:
            await message.answer(part, parse_mode=parse_mode)
