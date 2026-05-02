import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, StateFilter, ChatMemberUpdatedFilter, JOIN_TRANSITION
from src.redis_db.session import redis_client
from src.config import settings
from aiogram.fsm.storage.redis import RedisStorage
from src.interfaces.telegram import handlers
from src.interfaces.telegram import states
from src.interfaces.telegram import chat_manager
from src.interfaces.telegram import message_handler

logger = logging.getLogger(__name__)

bot = Bot(token=settings.telegram_bot_token)
redis_storage = RedisStorage(redis=redis_client)
dp = Dispatcher(storage=redis_storage)


def register_handlers():
    """Register all bot handlers"""
    dp.message.register(handlers.handle_start_command, Command("start"))
    dp.message.register(handlers.handle_help_command, Command("help"))

    # FSM handlers для review
    # FSM handlers - Review
    dp.message.register(handlers.handle_review_command, Command("review"))
    dp.callback_query.register(handlers.handle_review_date_selection,
                               lambda c: c.data and (c.data.startswith("review_date_") or
                                                     c.data in ["review_custom", "review_main_menu",
                                                                "review_back_to_periods"]))
    dp.callback_query.register(handlers.handle_review_custom_date,
                               lambda c: c.data and c.data.startswith("review_custom_"))
    dp.message.register(handlers.process_review_custom_date_text, StateFilter(states.ReviewStates.waiting_for_date))

    # Выбор чатов
    dp.message.register(handlers.handle_chats_command, Command("chats"))
    dp.message.register(handlers.handle_select_command, Command("select"))
    dp.message.register(handlers.handle_current_command, Command("current"))

    # Callback для выбора чата из списка
    dp.callback_query.register(chat_manager.select_chat_callback,
                               lambda c: c.data and c.data.startswith("select_chat_") or c.data.startswith(
                                   "chats_page_"))

    # FSM handlers - Compliance
    dp.message.register(handlers.handle_compliance_command, Command("compliance"))
    dp.callback_query.register(handlers.handle_compliance_date_selection,
                               lambda c: c.data and (c.data.startswith("compliance_date_") or
                                                     c.data in ["compliance_custom", "compliance_main_menu",
                                                                "compliance_back_to_periods"]))
    dp.callback_query.register(handlers.handle_compliance_custom_date,
                               lambda c: c.data and c.data.startswith("compliance_custom_"))
    dp.message.register(handlers.process_compliance_custom_date_text,
                        StateFilter(states.ComplianceStates.waiting_for_date))
    dp.message.register(handlers.handle_compliance_instruction,
                        StateFilter(states.ComplianceStates.waiting_for_instruction))

    # # Добавьте в register_handlers():
    # dp.callback_query.register(handlers.handle_cancel_callback,
    #                            lambda c: c.data and "cancel" in c.data)

    # Menu handlers
    dp.message.register(handlers.handle_main_menu,
                        lambda m: m.text in ["📊 Ревью чата", "✅ Проверка соответствия",
                                             "📋 Мои чаты", "❓ Помощь", "🏠 Главное меню"])

    # Сбор переписок
    dp.message.register(
        message_handler.handle_new_message,
        lambda m: m.chat.type != "private" and not m.text.startswith('/')
    )
    dp.my_chat_member.register(message_handler.handle_chat_member_update,
                               ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))


async def start_bot():
    """Start the Telegram bot"""
    register_handlers()
    logger.info("Starting Telegram bot...")
    await dp.start_polling(bot)


async def stop_bot():
    """Stop the Telegram bot"""
    logger.info("Stopping Telegram bot...")
    await bot.session.close()
    await redis_client.close()
