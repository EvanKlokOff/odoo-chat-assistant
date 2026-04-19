import logging
from datetime import datetime
from aiogram import types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from src.analyzers.graph import create_analysis_graph
from src.analyzers.state import AgentState
from src.interfaces.telegram import utils

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


async def handle_help_command(message: types.Message):
    """Handle /help command"""
    await message.answer(
        "📖 *Инструкция по использованию:*\n\n"
        "1. Добавьте бота в чат для анализа\n"
        "2. Используйте команды:\n"
        "   • `/review to_day` - анализ переписки за текущий день\n"
        "   • `/review to_hour` - анализ за последний час\n"
        "   • `/review to_N_hour` - анализ за последние N часов (N ≤ 24)\n"
        "   • `/review DD.MM.YYYY DD.MM.YYYY` - анализ за период\n"
        "   • `/review DD.MM.YYYY` - анализ с указанной даты до сегодня\n"
        "   • `/compliance` - проверить соответствие инструкции\n\n"
        "*Примеры:*\n"
        "`/review to_day`\n"
        "`/review to_6_hour`\n"
        "`/review 01.01.2025 31.01.2025`\n"
        "`/compliance Чат по продаже недвижимости, деловой стиль`",
        parse_mode="Markdown"
    )

    logger.info(f"Ручка handle_help_command была активирована пользователем {message.from_user.full_name}")


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


async def handle_review_command(message: types.Message):
    """Handle /review command for chat analysis"""
    logger.info(f"Ручка handle_review_command была активирована пользователем {message.from_user.full_name}")
    logger.info(f"Command text: {message.text}")
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

        await message.answer(
            f"🔍 Анализирую переписку за период:\n"
            f"📅 с {start_display}\n"
            f"📅 по {end_display}\n\n"
            f"Это может занять несколько секунд..."
        )

        # Prepare state for graph
        state: AgentState = {
            "query_type": "review",
            "chat_id": str(message.chat.id),
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
