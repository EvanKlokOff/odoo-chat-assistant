import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from src.config import settings
from src.interfaces.telegram.handlers import (
    handle_review_command,
    handle_compliance_command,
    handle_start_command,
    handle_help_command,
    handle_chats_command,
    handle_select_command,
    handle_current_command,
)
from src.interfaces.telegram.message_handler import handle_new_message, handle_chat_member_update
from src.interfaces.telegram.chat_manager import select_chat_callback

logger = logging.getLogger(__name__)

bot = Bot(token=settings.telegram_bot_token)
dp = Dispatcher()


def register_handlers():
    """Register all bot handlers"""
    dp.message.register(handle_start_command, Command("start"))
    dp.message.register(handle_help_command, Command("help"))

    dp.message.register(handle_chats_command, Command("chats"))
    dp.message.register(handle_select_command, Command("select"))
    dp.message.register(handle_current_command, Command("current"))

    dp.message.register(handle_review_command, Command("review"))
    dp.message.register(handle_compliance_command, Command("compliance"))

    dp.message.register(handle_new_message)
    dp.my_chat_member.register(handle_chat_member_update)

    dp.callback_query.register(select_chat_callback, lambda c: c.data and c.data.startswith("select_chat_"))

async def start_bot():
    """Start the Telegram bot"""
    register_handlers()
    logger.info("Starting Telegram bot...")
    await dp.start_polling(bot)


async def stop_bot():
    """Stop the Telegram bot"""
    logger.info("Stopping Telegram bot...")
    await bot.session.close()
