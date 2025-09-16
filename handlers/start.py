from aiogram import types
# from aiogram.filters import CommandStart
from keyboards.main import main_keyboard

async def cmd_start(message: types.Message):
    await message.answer(
        "**ПРИВЕТ!** Я бот для анализа технических документов. Для начала вы можете загрузить документ.",
        reply_markup=main_keyboard
    )