import logging
from typing import Dict, Optional
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.database import crud
logger = logging.getLogger(__name__)

# Хранилище выбранных чатов для пользователей (в памяти)
# В продакшене лучше использовать Redis или БД
user_selected_chat: Dict[int, str] = {}


async def get_user_available_chats(user_id: int) -> list[dict]:
    """Get all chats where user has interacted with bot"""
    return await crud.get_user_chats(user_id)

async def show_chats_list(message: types.Message):
    """Show list of available chats for user"""
    chats = await get_user_available_chats(message.from_user.id)

    if not chats:
        await message.answer(
            "❌ У вас пока нет доступных чатов.\n\n"
            "Добавьте бота в групповой чат и напишите там любое сообщение.\n"
            "После этого вернитесь сюда и нажмите /chats снова."
        )
        return

    current_chat = await get_current_chat(message.from_user.id)

    keyboard_buttons = []
    for chat in chats[:10]:  # Ограничим 10 чатами
        # Отмечаем текущий выбранный чат
        is_selected = (current_chat == chat['chat_id'])
        title = chat['title']
        if len(title) > 40:
            title = title[:37] + "..."

        button_text = f"{'✅ ' if is_selected else '📌 '}{title} (ID: {chat['chat_id']})"
        keyboard_buttons.append(
            [InlineKeyboardButton(
                text=button_text,
                callback_data=f"select_chat_{chat['chat_id']}"
            )]
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.answer(
        "📋 *Доступные чаты для анализа:*\n\n"
        "Нажмите на чат, чтобы выбрать его для анализа.\n\n"
        f"Текущий чат: {get_current_chat(message.from_user.id) or 'не выбран'}",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def set_current_chat(user_id: int, chat_id: str):
    """Set selected chat for user"""
    await crud.set_user_selected_chat(user_id, chat_id)
    logger.info(f"User {user_id} selected chat {chat_id}")


async def get_current_chat(user_id: int) -> Optional[str]:
    """Get currently selected chat for user from database"""
    return await crud.get_user_selected_chat(user_id)


async def select_chat_callback(callback_query: types.CallbackQuery):
    """Handle chat selection callback"""
    chat_id = callback_query.data.replace("select_chat_", "")

    # Проверяем, имеет ли пользователь доступ к этому чату
    user_chats = await get_user_available_chats(callback_query.from_user.id)
    chat_exists = any(chat['chat_id'] == chat_id for chat in user_chats)

    if not chat_exists:
        await callback_query.answer("❌ У вас нет доступа к этому чату!", show_alert=True)
        return

    await set_current_chat(callback_query.from_user.id, chat_id)

    # Обновляем сообщение с отмеченным чатом
    await show_chats_list(callback_query.message)
    await callback_query.answer(f"✅ Выбран чат для анализа!")