import logging
from datetime import datetime
from aiogram import types
from aiogram.types import ChatMemberUpdated
from src.database.crud import add_user_chat
from src.database.crud import save_message
from src.analyzers.embedding_service import embedding_service
from src.tasks import embedding_tasks
logger = logging.getLogger(__name__)


async def handle_new_message(message: types.Message):
    """Handle all new messages and save them to database"""
    # Skip if message is from bot itself
    if message.from_user.is_bot:
        logger.debug(f"Skipping bot's own message in chat {message.chat.id}")
        return

    if message.chat.type == "private":
        logger.debug(f"Skipping private message with bot's in chat {message.chat.id}")
        return

    try:
        # Extract sender name
        sender_name = message.from_user.full_name
        if message.from_user.username:
            sender_name = f"{sender_name} (@{message.from_user.username})"

        logger.info(f"Processing message from user {message.from_user.id} in chat {message.chat.id}")

        result = await add_user_chat(
            user_id=message.from_user.id,
            chat_id=str(message.chat.id),
            chat_title=message.chat.title or "Без названия"
        )

        if result:
            logger.info(f"Successfully added/updated user_chat for user {message.from_user.id}")
        else:
            logger.error(f"Failed to add user_chat for user {message.from_user.id}")

        # Save to database
        saved_message = await save_message(
            chat_id=str(message.chat.id),
            chat_title=message.chat.title,
            sender_id=str(message.from_user.id),
            sender_name=sender_name,
            content=message.text or message.caption or "[Non-text message]",
            timestamp=datetime.fromtimestamp(message.date.timestamp()),
            message_id=str(message.message_id),
            reply_to_message_id=str(message.reply_to_message.message_id) if message.reply_to_message else None
        )

        logger.info(f"Saved message from {sender_name} in chat {message.chat.id}")

        if saved_message:
            # Run embedding generation in background
            embedding_tasks.generate_message_embeddings.delay(saved_message.id)
            logger.debug(f"Scheduled embedding generation for message {saved_message}")
        else:
            logger.warning(f"save_message returned no message {message.message_id}")
        logger.info(f"Saved message from {sender_name} in chat {message.chat.id}")
    except Exception as e:
        logger.error(f"Failed to save message: {e}", exc_info=True)


async def handle_chat_member_update(event: ChatMemberUpdated):
    """Handle when bot is added to a chat"""
    # Check if bot was added to chat
    if event.new_chat_member.user.id == event.bot.id and event.new_chat_member.status == "member":
        # Check if it's a new addition (not just an update)
        if event.old_chat_member.status in ["left", "kicked"]:
            logger.info(f"Bot was added to chat: {event.chat.id} - {event.chat.title}")

            # Send welcome message
            try:
                # Создаем запись о чате через системного пользователя (бот)
                from src.database.crud import add_chat_only
                await add_chat_only(
                    chat_id=str(event.chat.id),
                    chat_title=event.chat.title or "Без названия"
                )
                logger.info(f"Added chat {event.chat.id} to database")
            except Exception as e:
                logger.error(f"Failed to add chat to database: {e}")

            from src.interfaces.telegram.bot import bot

            await bot.send_message(
                chat_id=event.chat.id,
                text="👋 Привет! Я буду сохранять все сообщения в этом чате для последующего анализа.\n\n"
                     "Команды для анализа:\n"
                     "/review - анализ переписки\n"
                     "/compliance - проверка соответствия инструкции\n"
                     "/help - помощь"
            )
