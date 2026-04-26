import logging
from datetime import datetime
from aiogram import types
from aiogram.fsm.context import FSMContext
from src.interfaces.telegram import utils
from src.interfaces.telegram import chat_manager
from src.interfaces.telegram.states import ComplianceStates, ReviewStates
from src.interfaces.telegram import keyboards
from src.database import crud

logger = logging.getLogger(__name__)


@utils.private_chat_only
async def handle_start_command(message: types.Message, state: FSMContext):
    """Handle /start command"""
    await state.clear()  # Очищаем состояние при старте
    await message.answer(
        "👋 Привет! Я бот для анализа чатов.\n\n"
        "Я могу:\n"
        "📊 **Ревью чата** - сделать ревью переписки за указанный период\n"
        "✅ **Проверка соответствия** - проверить соответствие переписки инструкции\n"
        "❓ **Помощь** - показать инструкцию\n\n"
        "Добавь меня в чат, который хочешь анализировать!\n\n"
        "Используйте кнопки меню для навигации:",
        parse_mode="Markdown",
        reply_markup=keyboards.main_menu_keyboard
    )
    logger.info(f"Start command from {message.from_user.full_name}")


@utils.private_chat_only
async def handle_main_menu(message: types.Message, state: FSMContext):
    """Handle main menu button presses"""
    await state.clear()
    logger.info(f"Main menu button pressed: {message.text}")
    if message.text == "📊 Ревью чата":
        await handle_review_command(message, state)
    elif message.text == "✅ Проверка соответствия":
        await handle_compliance_command(message, state)
    elif message.text == "📋 Мои чаты":
        await chat_manager.show_chats_list(message, page=0, edit_message=False)
    elif message.text == "❓ Помощь":
        await handle_help_command(message)
    elif message.text == "🏠 Главное меню":
        await message.answer(
            "🏠 Главное меню",
            reply_markup=keyboards.main_menu_keyboard
        )


# handlers.py - добавьте эти функции

@utils.private_chat_only
async def handle_chats_command(message: types.Message):
    """Handle /chats command - show available chats"""
    await chat_manager.show_chats_list(message, page=0, edit_message=False)


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
    user_chats = await crud.get_user_chats(message.from_user.id)
    chat_exists = any(chat['chat_id'] == chat_id for chat in user_chats)

    if not chat_exists:
        await message.answer(
            f"❌ Чат с ID `{chat_id}` не найден или у вас нет к нему доступа.\n\n"
            f"Используйте `/chats` для просмотра доступных чатов.",
            parse_mode="Markdown"
        )
        return

    # Получаем название чата из user_chats
    chat_title = next((c['title'] for c in user_chats if c['chat_id'] == chat_id), "Unknown")

    await chat_manager.set_current_chat(message.from_user.id, chat_id)
    await message.answer(
        f"✅ Выбран чат для анализа: *{chat_title}*\n"
        f"ID: `{chat_id}`\n\n"
        f"Теперь используйте кнопки меню для анализа.",
        parse_mode="Markdown",
        reply_markup=keyboards.main_menu_keyboard
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

    # Получаем название чата из user_chats
    user_chats = await crud.get_user_chats(message.from_user.id)
    chat_title = next((c['title'] for c in user_chats if c['chat_id'] == current_chat_id), "Unknown")

    await message.answer(
        f"📌 *Текущий выбранный чат:*\n"
        f"Название: {chat_title}\n"
        f"ID: `{current_chat_id}`",
        parse_mode="Markdown"
    )

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
        "5. Используйте кнопки меню для анализа:\n"
        "   • 📊 Ревью чата - анализ переписки\n"
        "   • ✅ Проверка соответствия - проверка инструкции\n\n"
        "*Примеры инструкций:*\n"
        "• Чат по продаже автомобилей, деловой стиль, цель - продажа\n"
        "• Техническая поддержка, вежливость, решение проблем клиентов"
    )

    await message.answer(help_text, parse_mode="Markdown")


# ============= REVIEW FSM HANDLERS =============

@utils.private_chat_only
async def handle_review_command(message: types.Message, state: FSMContext):
    """Handle /review command - start FSM for date selection"""
    # Проверяем, выбран ли чат
    chat_id = await chat_manager.get_current_chat(message.from_user.id)
    if not chat_id:
        await message.answer(
            "❌ Сначала выберите чат для анализа.\n\n"
            "Используйте `/chats` для просмотра доступных чатов\n"
            "или `/select CHAT_ID` для выбора чата.",
            parse_mode="Markdown",
            reply_markup=keyboards.main_menu_keyboard
        )
        return

    # Сохраняем chat_id в состояние
    await state.update_data(chat_id=chat_id, command_type="review")
    await state.set_state(ReviewStates.waiting_for_date)

    await message.answer(
        "📅 *Выберите период для анализа переписки:*\n\n"
        "Используйте кнопки ниже для быстрого выбора периода:",
        parse_mode="Markdown",
        reply_markup=keyboards.get_date_selection_keyboard("review")
    )


async def handle_review_date_selection(callback: types.CallbackQuery, state: FSMContext):
    """Handle date selection for review"""
    await callback.answer()

    data = callback.data

    if data == "review_main_menu":
        await state.clear()
        await callback.message.edit_text(
            "🏠 Возврат в главное меню",
            reply_markup=None
        )
        await callback.message.answer(
            "Главное меню:",
            reply_markup=keyboards.main_menu_keyboard
        )
        return

    if data == "review_custom":
        await state.set_state(ReviewStates.waiting_for_date)
        await callback.message.edit_text(
            "📝 *Введите дату или период:*\n\n"
            "Форматы:\n"
            "• `01.01.2025` - с указанной даты\n"
            "• `01.01.2025 31.01.2025` - период\n\n"
            "Или выберите тип ввода:",
            parse_mode="Markdown",
            reply_markup=keyboards.get_custom_date_keyboard("review")
        )
        return

    if data == "review_back_to_periods":
        await callback.message.edit_text(
            "📅 *Выберите период для анализа переписки:*\n\n"
            "Используйте кнопки ниже для быстрого выбора периода.",
            parse_mode="Markdown",
            reply_markup=keyboards.get_date_selection_keyboard("review")
        )
        return

    user_data = await state.get_data()
    chat_id = user_data.get("chat_id")

    date_start, date_end, error = await utils.parse_date_from_callback(data, "review")

    if error:
        await callback.message.edit_text(
            f"❌ {error}\n\nПопробуйте снова:",
            reply_markup=keyboards.get_date_selection_keyboard("review")
        )
        return

    if date_start and date_end:
        # Даты уже выбраны, запускаем анализ
        await callback.message.edit_text(
            f"🔍 Анализирую переписку за период:\n"
            f"📅 с {datetime.fromisoformat(date_start).strftime('%d.%m.%Y %H:%M:%S')}\n"
            f"📅 по {datetime.fromisoformat(date_end).strftime('%d.%m.%Y %H:%M:%S')}\n\n"
            f"Это может занять несколько секунд..."
        )

        await state.clear()  # Очищаем состояние

        # Запускаем анализ
        await utils.run_review_analysis(callback.message, chat_id, date_start, date_end)
        return


async def handle_review_custom_date(callback: types.CallbackQuery, state: FSMContext):
    """Handle custom date input for review"""
    await callback.answer()

    data = callback.data

    if data == "review_custom_single":
        await state.update_data(date_type="single")
        await callback.message.edit_text(
            "📅 *Введите одну дату в формате ДД.ММ.ГГГГ*\n\n"
            "Пример: `25.12.2025`\n\n"
            "Анализ будет выполнен с указанной даты по текущий момент.",
            parse_mode="Markdown",
            reply_markup=keyboards.back_to_menu_keyboard
        )
    elif data == "review_custom_range":
        await state.update_data(date_type="range")
        await callback.message.edit_text(
            "📅📅 *Введите период в формате ДД.ММ.ГГГГ ДД.ММ.ГГГГ*\n\n"
            "Пример: `01.01.2025 31.01.2025`\n\n"
            "Анализ будет выполнен за указанный период.",
            parse_mode="Markdown",
            reply_markup=keyboards.back_to_menu_keyboard
        )
    elif data in ["review_back_to_periods", "review_main_menu"]:
        # Эти кнопки обрабатываются в handle_review_date_selection
        pass

# ============= COMPLIANCE FSM HANDLERS =============

@utils.private_chat_only
async def handle_compliance_command(message: types.Message, state: FSMContext):
    """Handle /compliance command - start FSM for date selection"""
    # Проверяем, выбран ли чат
    chat_id = await chat_manager.get_current_chat(message.from_user.id)
    if not chat_id:
        await message.answer(
            "❌ Сначала выберите чат для анализа.\n\n"
            "Используйте `/chats` для просмотра доступных чатов\n"
            "или `/select CHAT_ID` для выбора чата.",
            parse_mode="Markdown",
            reply_markup=keyboards.main_menu_keyboard
        )
        return

    # Сохраняем chat_id в состояние
    await state.update_data(chat_id=chat_id, command_type="compliance")
    await state.set_state(ComplianceStates.waiting_for_date)

    await message.answer(
        "📅 *Выберите период для проверки соответствия:*\n\n"
        "Сначала выберите период переписки для анализа,\n"
        "затем введите инструкцию для проверки.",
        parse_mode="Markdown",
        reply_markup=keyboards.get_date_selection_keyboard("compliance")
    )


async def handle_compliance_date_selection(callback: types.CallbackQuery, state: FSMContext):
    """Handle date selection for compliance"""
    await callback.answer()

    data = callback.data
    if data == "compliance_main_menu":
        await state.clear()
        await callback.message.edit_text(
            "🏠 Возврат в главное меню",
            reply_markup=None
        )
        await callback.message.answer(
            "Главное меню:",
            reply_markup=keyboards.main_menu_keyboard
        )
        return
    if data == "compliance_custom":
        await state.set_state(ComplianceStates.waiting_for_date)
        await callback.message.edit_text(
            "📝 *Введите дату или период:*\n\n"
            "Форматы:\n"
            "• `01.01.2025` - с указанной даты\n"
            "• `01.01.2025 31.01.2025` - период\n\n"
            "Или выберите тип ввода:",
            parse_mode="Markdown",
            reply_markup=keyboards.get_custom_date_keyboard("compliance")
        )
        return
    if data == "compliance_back_to_periods":
        await callback.message.edit_text(
            "📅 *Выберите период для проверки соответствия:*\n\n"
            "Сначала выберите период переписки для анализа,\n"
            "затем введите инструкцию для проверки.",
            parse_mode="Markdown",
            reply_markup=keyboards.get_date_selection_keyboard("compliance")
        )
        return

    date_start, date_end, error = await utils.parse_date_from_callback(data, "compliance")

    if error:
        await callback.message.edit_text(
            f"❌ {error}\n\nПопробуйте снова:",
            reply_markup=keyboards.get_date_selection_keyboard("compliance")
        )
        return

    # Сохраняем даты в состояние
    await state.update_data(date_start=date_start, date_end=date_end)

    if date_start and date_end:
        # Переходим к вводу инструкции
        await state.set_state(ComplianceStates.waiting_for_instruction)

        period_text = "за весь доступный период" if not date_start else \
            f"за период с {datetime.fromisoformat(date_start).strftime('%d.%m.%Y %H:%M:%S')} " \
            f"по {datetime.fromisoformat(date_end).strftime('%d.%m.%Y %H:%M:%S')}"

        await callback.message.edit_text(
            f"✅ *Период выбран:* {period_text}\n\n"
            f"📝 *Теперь введите инструкцию для проверки*\n\n"
            f"Инструкция должна описывать правила, стиль общения, цели чата.\n"
            f"Пример: *Чат по продаже автомобилей, деловой стиль, цель - продажа*\n\n"
            f"Или нажмите /cancel для отмены.",
            parse_mode="Markdown",
            reply_markup=keyboards.back_to_menu_keyboard
        )
    else:
        # Обработка кастомной даты
        await state.set_state(ComplianceStates.waiting_for_date)
        await callback.message.edit_text(
            "📝 *Введите дату или период:*\n\n"
            "Форматы:\n"
            "• `01.01.2025` - с указанной даты\n"
            "• `01.01.2025 31.01.2025` - период\n\n"
            "Или выберите тип ввода:",
            parse_mode="Markdown",
            reply_markup=keyboards.get_custom_date_keyboard("compliance")
        )


async def handle_compliance_custom_date(callback: types.CallbackQuery, state: FSMContext):
    """Handle custom date input for compliance"""
    await callback.answer()

    data = callback.data

    if data == "compliance_custom_single":
        await state.update_data(date_type="single")
        await callback.message.edit_text(
            "📅 *Введите одну дату в формате ДД.ММ.ГГГГ*\n\n"
            "Пример: `25.12.2025`\n\n"
            "Анализ будет выполнен с указанной даты по текущий момент.\n\n"
            "После ввода даты вы сможете ввести инструкцию.",
            parse_mode="Markdown",
            reply_markup=keyboards.back_to_menu_keyboard
        )
    elif data == "compliance_custom_range":
        await state.update_data(date_type="range")
        await callback.message.edit_text(
            "📅📅 *Введите период в формате ДД.ММ.ГГГГ ДД.ММ.ГГГГ*\n\n"
            "Пример: `01.01.2025 31.01.2025`\n\n"
            "После ввода периода вы сможете ввести инструкцию.",
            parse_mode="Markdown",
            reply_markup=keyboards.back_to_menu_keyboard
        )
    elif data in ["compliance_back_to_periods", "compliance_main_menu"]:
        # Эти кнопки обрабатываются в handle_compliance_date_selection
        pass


async def handle_compliance_instruction(message: types.Message, state: FSMContext):
    """Handle instruction input for compliance"""
    if message.text == "🏠 Главное меню":
        await state.clear()
        await message.answer("🏠 Возврат в главное меню", reply_markup=keyboards.main_menu_keyboard)
        return

    user_data = await state.get_data()
    chat_id = user_data.get("chat_id")
    date_start = user_data.get("date_start")
    date_end = user_data.get("date_end")
    instruction = message.text.strip()

    if not instruction:
        await message.answer(
            "❌ Инструкция не может быть пустой.\n\n"
            "Пожалуйста, введите инструкцию для проверки:",
            reply_markup=keyboards.back_to_menu_keyboard
        )
        return

    # Показываем, что начали анализ
    period_text = "за всю доступную переписку" if not date_start else \
        f"за период с {datetime.fromisoformat(date_start).strftime('%d.%m.%Y %H:%M:%S')} " \
        f"по {datetime.fromisoformat(date_end).strftime('%d.%m.%Y %H:%M:%S')}"

    await message.answer(
        f"✅ *Проверяю соответствие переписки инструкции*\n"
        f"📅 {period_text}\n\n"
        f"📝 *Инструкция:* {instruction[:200]}{'...' if len(instruction) > 200 else ''}\n\n"
        f"Это может занять несколько секунд...",
        parse_mode="Markdown",
        reply_markup=keyboards.remove_keyboard
    )

    # Очищаем состояние
    await state.clear()

    # Запускаем анализ
    await utils.run_compliance_analysis(message, chat_id, instruction, date_start, date_end)


async def handle_cancel_callback(callback: types.CallbackQuery, state: FSMContext):
    """Handle cancel callbacks"""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "❌ Действие отменено",
        reply_markup=keyboards.main_menu_keyboard
    )


# Обработчик текстовых сообщений для кастомных дат
async def process_review_custom_date_text(message: types.Message, state: FSMContext):
    """Process custom date text input for review"""
    if message.text == "🏠 Главное меню":
        await state.clear()
        await message.answer(
            "🏠 Возврат в главное меню",
            reply_markup=keyboards.main_menu_keyboard
        )
        return
    user_data = await state.get_data()
    date_type = user_data.get("date_type", "single")
    chat_id = user_data.get("chat_id")

    try:
        if date_type == "single":
            # Парсим одну дату
            date_start = datetime.strptime(message.text.strip(), "%d.%m.%Y").isoformat()
            date_end = datetime.now().isoformat()
        else:
            # Парсим две даты
            parts = message.text.strip().split()
            if len(parts) != 2:
                await message.answer(
                    "❌ Неверный формат. Введите две даты через пробел: ДД.ММ.ГГГГ ДД.ММ.ГГГГ"
                )
                return
            date_start = datetime.strptime(parts[0], "%d.%m.%Y").isoformat()
            date_end = datetime.strptime(parts[1], "%d.%m.%Y").isoformat()

        await message.answer(
            f"🔍 Анализирую переписку за период:\n"
            f"📅 с {datetime.fromisoformat(date_start).strftime('%d.%m.%Y %H:%M:%S')}\n"
            f"📅 по {datetime.fromisoformat(date_end).strftime('%d.%m.%Y %H:%M:%S')}\n\n"
            f"Это может занять несколько секунд..."
        )

        await state.clear()
        await utils.run_review_analysis(message, chat_id, date_start, date_end)

    except ValueError:
        await message.answer(
            "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ\n"
            "Пример: 25.12.2025"
        )


async def process_compliance_custom_date_text(message: types.Message, state: FSMContext):
    """Process custom date text input for compliance"""
    if message.text == "🏠 Главное меню":
        await state.clear()
        await message.answer(
            "🏠 Возврат в главное меню",
            reply_markup=keyboards.main_menu_keyboard
        )
        return
    user_data = await state.get_data()
    date_type = user_data.get("date_type", "single")

    try:
        if date_type == "single":
            # Парсим одну дату
            date_start = datetime.strptime(message.text.strip(), "%d.%m.%Y").isoformat()
            date_end = datetime.now().isoformat()
        else:
            # Парсим две даты
            parts = message.text.strip().split()
            if len(parts) != 2:
                await message.answer(
                    "❌ Неверный формат. Введите две даты через пробел: ДД.ММ.ГГГГ ДД.ММ.ГГГГ"
                )
                return
            date_start = datetime.strptime(parts[0], "%d.%m.%Y").isoformat()
            date_end = datetime.strptime(parts[1], "%d.%m.%Y").isoformat()

        # Сохраняем даты и переходим к вводу инструкции
        await state.update_data(date_start=date_start, date_end=date_end)
        await state.set_state(ComplianceStates.waiting_for_instruction)

        period_text = f"за период с {datetime.fromisoformat(date_start).strftime('%d.%m.%Y %H:%M:%S')} " \
                      f"по {datetime.fromisoformat(date_end).strftime('%d.%m.%Y %H:%M:%S')}"

        await message.answer(
            f"✅ *Период выбран:* {period_text}\n\n"
            f"📝 *Теперь введите инструкцию для проверки*\n\n"
            f"Инструкция должна описывать правила, стиль общения, цели чата.\n"
            f"Пример: *Чат по продаже автомобилей, деловой стиль, цель - продажа*",
            parse_mode="Markdown",
            reply_markup=keyboards.back_to_menu_keyboard
        )

    except ValueError:
        await message.answer(
            "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ\n"
            "Пример: 25.12.2025"
        )
