from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Загрузить документ")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)