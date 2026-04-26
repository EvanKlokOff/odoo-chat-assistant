from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)

# Главное меню
main_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Ревью чата"), KeyboardButton(text="✅ Проверка соответствия")],
        [KeyboardButton(text="📋 Мои чаты"), KeyboardButton(text="❓ Помощь")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# Клавиатура для выбора периода (для review и compliance)
def get_date_selection_keyboard(command_type: str = "review") -> InlineKeyboardMarkup:
    """
    Создает клавиатуру выбора периода

    Args:
        command_type: "review" или "compliance"
    """
    prefix = command_type

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 За весь период", callback_data=f"{prefix}_date_all"),
            InlineKeyboardButton(text="📆 За сегодня", callback_data=f"{prefix}_date_today")
        ],
        [
            InlineKeyboardButton(text="🕐 За последний час", callback_data=f"{prefix}_date_hour"),
            InlineKeyboardButton(text="🕓 За 5 часов", callback_data=f"{prefix}_date_5hour")
        ],
        [
            InlineKeyboardButton(text="🕙 За 12 часов", callback_data=f"{prefix}_date_12hour"),
            InlineKeyboardButton(text="📅 За 24 часа", callback_data=f"{prefix}_date_24hour")
        ],
        [
            InlineKeyboardButton(text="📆 Выбрать дату", callback_data=f"{prefix}_date_custom")
        ],
        [
            InlineKeyboardButton(text="🏠 Главное меню", callback_data=f"{prefix}_main_menu")
        ]
    ])

    return keyboard


# Клавиатура для выбора формата ввода даты
def get_custom_date_keyboard(command_type: str = "review") -> InlineKeyboardMarkup:
    """Клавиатура для выбора формата ввода даты"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Одна дата", callback_data=f"{command_type}_custom_single"),
            InlineKeyboardButton(text="📅📅 Период", callback_data=f"{command_type}_custom_range")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад к периодам", callback_data=f"{command_type}_back_to_periods"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data=f"{command_type}_main_menu")
        ]
    ])


# Клавиатура для подтверждения отмены
cancel_confirmation_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="✅ Да, отменить", callback_data="cancel_confirm"),
        InlineKeyboardButton(text="❌ Нет, продолжить", callback_data="cancel_continue")
    ]
])

# Клавиатура для возврата в главное меню
back_to_menu_reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🏠 Главное меню")]],
    resize_keyboard=True
)

back_to_menu_inline = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
])

remove_keyboard = ReplyKeyboardRemove()
