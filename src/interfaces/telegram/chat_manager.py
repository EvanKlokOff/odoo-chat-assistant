import logging
import re
from typing import Dict, Optional
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from interfaces.telegram import keyboards
from src.database import crud
from src.config import settings

logger = logging.getLogger(__name__)

# Хранилище выбранных чатов для пользователей (в памяти)
# В продакшене лучше использовать Redis или БД
user_selected_chat: Dict[int, str] = {}


async def get_user_available_chats(user_id: int) -> list[dict]:
    """Get all chats where user has interacted with bot"""
    chats = await crud.get_user_chats(user_id)
    logger.info(f"get_user_available_chats for user {user_id}: {len(chats)} chats found")
    for chat in chats:
        logger.info(f"  Chat: {chat['chat_id']} - {chat['title']}")
    return chats


async def show_chats_list(message: types.Message, page: int = 0, edit_message: bool = False):
    """Show list of available chats for user"""
    logger.info(f"show_chats_list called for user {message.from_user.id}, page={page}, edit={edit_message}")
    chats = await get_user_available_chats(message.from_user.id)

    if not chats:
        text = (
            "❌ У вас пока нет доступных чатов.\n\n"
            "Добавьте бота в групповой чат и напишите там любое сообщение.\n"
            "После этого вернитесь сюда и нажмите /chats снова."
        )
        if edit_message:
            await message.edit_text(text, reply_markup=None)
        else:
            await message.answer(text, reply_markup=keyboards.main_menu_keyboard)
        return
    logger.info(f"Found {len(chats)} chats for user {message.from_user.id}")
    current_chat = await get_current_chat(message.from_user.id)
    total_pages = (len(chats) + settings.chat_per_page - 1) // settings.chat_per_page

    page = max(0, min(page, total_pages - 1))

    start_idx = page * settings.chat_per_page
    end_idx = start_idx + settings.chat_per_page
    chats_page = chats[start_idx:end_idx]

    keyboard_buttons = []
    for chat in chats_page:
        is_selected = (current_chat == chat['chat_id'])
        title = chat['title']
        if len(title) > 35:
            title = title[:32] + "..."

        button_text = f"{'✅ ' if is_selected else '📌 '}{title}"
        keyboard_buttons.append(
            [InlineKeyboardButton(
                text=button_text,
                callback_data=f"select_chat_{chat['chat_id']}"
            )]
        )

    pagination_buttons = []
    if page > 0:
        pagination_buttons.append(
            InlineKeyboardButton(text="◀️ Пред.", callback_data=f"chats_page_{page - 1}")
        )
    if page < total_pages - 1:
        pagination_buttons.append(
            InlineKeyboardButton(text="След. ▶️", callback_data=f"chats_page_{page + 1}")
        )

    if pagination_buttons:
        keyboard_buttons.append(pagination_buttons)

    # Добавляем кнопку обновления
    keyboard_buttons.append(
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"chats_page_{page}")]
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    selected_info = ""
    if current_chat:
        current_title = next((c['title'] for c in chats if c['chat_id'] == current_chat), "Unknown")
        if len(current_title) > 30:
            current_title = current_title[:27] + "..."
        selected_info = f"\n✅ *Текущий:* {current_title}"

    message_text = (
        f"📋 *Мои чаты* (стр. {page + 1}/{total_pages})\n\n"
        f"Всего чатов: {len(chats)}{selected_info}\n\n"
        f"Нажмите на чат, чтобы выбрать его для анализа."
    )

    if edit_message:
        await message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            message_text,
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
    callback_data = callback_query.data

    if callback_data.startswith("chats_page_"):
        page = int(callback_data.replace("chats_page_", ""))
        await show_chats_list(callback_query.message, page, edit_message=True)
        await callback_query.answer()
        return

    chat_id = callback_query.data.replace("select_chat_", "")

    # Проверяем, имеет ли пользователь доступ к этому чату
    user_chats = await get_user_available_chats(callback_query.from_user.id)
    chat_exists = any(chat['chat_id'] == chat_id for chat in user_chats)

    if not chat_exists:
        await callback_query.answer("❌ У вас нет доступа к этому чату!", show_alert=True)
        return

    await set_current_chat(callback_query.from_user.id, chat_id)

    selected_chat = next((c for c in user_chats if c['chat_id'] == chat_id), None)
    chat_title = selected_chat['title'] if selected_chat else "Unknown"

    # Обновляем сообщение с отмеченным чатом
    text = callback_query.message.text
    match = re.search(r'стр\. (\d+)/(\d+)', text)
    if match:
        current_page = int(match.group(1)) - 1
        await show_chats_list(callback_query.message, current_page, edit_message=True)
    else:
        await show_chats_list(callback_query.message, 0, edit_message=True)

    await callback_query.answer(f"✅ Выбран чат: {chat_title}")
