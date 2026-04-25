import logging
from datetime import datetime
from aiogram import types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from src.analyzers.graph import create_analysis_graph
from src.analyzers.state import AgentState
from src.interfaces.telegram import utils
from src.interfaces.telegram import chat_manager
from src.database import crud

logger = logging.getLogger(__name__)

# Create keyboard
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/review")],
        [KeyboardButton(text="/compliance")],
        [KeyboardButton(text="/help")]
    ],
    resize_keyboard=True
)

@utils.private_chat_only
async def handle_start_command(message: types.Message):
    """Handle /start command"""
    await message.answer(
        "👋 Привет! Я бот для анализа чатов.\n\n"
        "Я могу:\n"
        "📊 **/review** - сделать ревью переписки за указанный период\n"
        "✅ **/compliance** - проверить соответствие переписки инструкции\n"
        "❓ **/help** - показать это сообщение\n\n"
        "Добавь меня в чат, который хочешь анализировать!\n\n"
        "*Форматы /review:*\n"
        "• `/review to_day` - переписка за текущий день\n"
        "• `/review to_hour` - за последний час\n"
        "• `/review to_5_hour` - за последние 5 часов (max 24)\n"
        "• `/review 01.01.2025 31.01.2025` - за период",
        parse_mode="Markdown",
        reply_markup=main_keyboard
    )
    logger.info(f"Ручка handle_start_command была активирована пользователем {message.from_user.full_name}")

@utils.private_chat_only
async def handle_help_command(message: types.Message):
    """Handle /help command"""
    help_text = (
        "📖 *Инструкция по использованию:*\n\n"
        "*Важно:* Все команды анализа работают только в личном диалоге с ботом!\n\n"
        "1. Добавьте бота в групповой чат\n"
        "2. Напишите любое сообщение в группе (бот начнет сохранять историю)\n"
        "3. Перейдите в личный диалог с ботом\n"
        "4. Выберите чат для анализа:\n"
        "   • `/chats` - показать доступные чаты\n"
        "   • `/select CHAT_ID` - выбрать чат\n"
        "   • `/current` - показать текущий чат\n"
        "5. Используйте команды анализа:\n"
        "   • `/review to_day` - анализ за текущий день\n"
        "   • `/review to_hour` - анализ за последний час\n"
        "   • `/review to_N_hour` - анализ за последние N часов (N ≤ 24)\n"
        "   • `/review DD.MM.YYYY` - анализ с указанной даты\n"
        "   • `/review DD.MM.YYYY DD.MM.YYYY` - анализ за период\n"
        "   • `/compliance инструкция` - проверить соответствие инструкции\n\n"
        "*Примеры:*\n"
        "`/review to_day`\n"
        "`/review to_6_hour`\n"
        "`/review 01.01.2025 31.01.2025`\n"
        "`/compliance Чат по продаже недвижимости, деловой стиль`"
    )

    await message.answer(help_text, parse_mode="Markdown")
    logger.info(f"Help command from {message.from_user.full_name}")

async def _send_long_message(message: types.Message, text: str, prefix: str = "",
                             parse_mode: str | None = None):
    """Split long message into multiple parts"""
    max_length = 4000

    if len(text) <= max_length:
        safe_result = utils.escape_markdown(text)
        await message.answer(f"{prefix}\n\n{safe_result}", parse_mode=parse_mode)
        return

    # Разбиваем на части
    parts = []
    current_part = ""

    for line in text.split('\n'):
        safe_line = utils.escape_markdown(line)
        if len(current_part) + len(safe_line) + 1 > max_length:
            parts.append(current_part)
            current_part = safe_line
        else:
            current_part += '\n' + safe_line if current_part else safe_line

    if current_part:
        parts.append(current_part)

    # Отправляем первую часть с префиксом
    await message.answer(f"{prefix}\n\n{parts[0]}", parse_mode=parse_mode)

    # Остальные части без префикса
    for part in parts[1:]:
        await message.answer(part, parse_mode=parse_mode)

@utils.private_chat_only
async def handle_review_command(message: types.Message):
    """Handle /review command for chat analysis"""
    logger.info(f"Ручка handle_review_command была активирована пользователем {message.from_user.full_name}")
    logger.info(f"Command text: {message.text}")

    chat_id = await chat_manager.get_current_chat(message.from_user.id)
    if not chat_id:
        await message.answer(
            "❌ Сначала выберите чат для анализа.\n\n"
            "Используйте `/chats` для просмотра доступных чатов\n"
            "или `/select CHAT_ID` для выбора чата.",
            parse_mode="Markdown"
        )
        return

    try:
        date_start, date_end, error = utils.parse_review_parameters(message.text)

        if error:
            await message.answer(
                f"❌ {error}\n\n"
                "📝 *Примеры правильного использования:*\n"
                "• `/review to_day` - за сегодня\n"
                "• `/review to_hour` - за последний час\n"
                "• `/review to_5_hour` - за последние 5 часов\n"
                "• `/review 01.01.2025` - с указанной даты\n"
                "• `/review 01.01.2025 31.01.2025` - за период",
                parse_mode="Markdown"
            )
            return

        start_display = datetime.fromisoformat(date_start).strftime("%d.%m.%Y %H:%M:%S")
        end_display = datetime.fromisoformat(date_end).strftime("%d.%m.%Y %H:%M:%S")

        await message.answer(
            f"🔍 Анализирую переписку за период:\n"
            f"📅 с {start_display}\n"
            f"📅 по {end_display}\n\n"
            f"Это может занять несколько секунд..."
        )

        # Prepare state for graph
        state: AgentState = {
            "query_type": "review",
            "chat_id": chat_id,
            "messages": [],
            "date_start": date_start,
            "date_end": date_end,
            "instruction": None,
            "chat_messages": [],
            "analysis_result": None,
            "deviations": None,
            "current_step": "start",
            "error": None
        }

        # Run the graph
        graph = create_analysis_graph()
        final_state = await graph.ainvoke(state)

        # Send result
        result = final_state.get("analysis_result", "Не удалось выполнить анализ.")

        await _send_long_message(message, result, "📊 Результат анализа", "Markdown")
    except Exception as e:
        logger.error(f"Review command failed: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка: {str(e)}\n\n"
            "Пожалуйста, проверьте формат команды:\n"
            "• `/review to_day`\n"
            "• `/review to_hour`\n"
            "• `/review to_N_hour` (N ≤ 24)\n"
            "• `/review ДД.ММ.ГГГГ ДД.ММ.ГГГГ`",
            parse_mode="Markdown"
        )

@utils.private_chat_only
async def handle_compliance_command(message: types.Message):
    """Handle /compliance command for instruction compliance check"""
    logger.info(f"Ручка handle_compliance_command была активирована пользователем {message.from_user.full_name}")
    try:
        # Extract instruction from command
        instruction = message.text.replace("/compliance", "").strip()

        if not instruction:
            await message.answer(
                "📝 *Пожалуйста, укажите инструкцию для проверки.*\n\n"
                "Пример:\n"
                "`/compliance Чат по продаже автомобилей, деловой стиль, цель - продажа`",
                parse_mode="Markdown"
            )
            return

        await message.answer("✅ Проверяю соответствие переписки инструкции...")

        # Prepare state for graph
        state: AgentState = {
            "query_type": "compliance",
            "messages": [],
            "date_start": None,
            "date_end": None,
            "instruction": instruction,
            "chat_messages": [],
            "analysis_result": None,
            "deviations": None,
            "current_step": "start",
            "error": None
        }

        # Run the graph
        graph = create_analysis_graph()
        final_state = await graph.ainvoke(state)

        # Send result
        result = final_state.get("analysis_result", "Не удалось выполнить анализ.")

        await message.answer(
            f"✅ *Результат проверки соответствия:*\n\n{result}",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Compliance command failed: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")

@utils.private_chat_only
async def handle_chats_command(message: types.Message):
    """Handle /chats command - show available chats"""
    # Проверяем, что команда в ЛС

    await chat_manager.show_chats_list(message)

@utils.private_chat_only
async def handle_select_command(message: types.Message):
    """Handle /select CHAT_ID command"""
    parts = message.text.split()
    if len(parts) < 2:
        # Показываем список чатов
        await chat_manager.show_chats_list(message)
        return

    chat_id = parts[1]

    # Проверяем, существует ли чат и имеет ли пользователь к нему доступ
    chat = await crud.get_chat_by_id(chat_id)

    if not chat:
        await message.answer(
            f"❌ Чат с ID `{chat_id}` не найден или у вас нет к нему доступа.\n\n"
            f"Используйте `/chats` для просмотра доступных чатов.",
            parse_mode="Markdown"
        )
        return

    await chat_manager.set_current_chat(message.from_user.id, chat_id)
    await message.answer(
        f"✅ Выбран чат для анализа: *{chat['title']}*\n"
        f"ID: `{chat_id}`\n\n"
        f"Теперь используйте `/review` или `/compliance` для анализа.",
        parse_mode="Markdown"
    )

@utils.private_chat_only
async def handle_current_command(message: types.Message):
    """Handle /current command - show current selected chat"""

    current_chat_id = await chat_manager.get_current_chat(message.from_user.id)

    if not current_chat_id:
        await message.answer(
            "❌ Чат не выбран.\n\n"
            "Используйте `/chats` для просмотра доступных чатов\n"
            "или `/select CHAT_ID` для выбора чата."
        )
        return

    chat = await crud.get_chat_by_id(current_chat_id)

    await message.answer(
        f"📌 *Текущий выбранный чат:*\n"
        f"Название: {chat['title'] if chat else 'Unknown'}\n"
        f"ID: `{current_chat_id}`",
        parse_mode="Markdown"
    )