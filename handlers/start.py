from aiogram import types
# from aiogram.filters import CommandStart
from keyboards.main import main_keyboard

async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! 👋 Я бот, который скоро станет умным. Для начала вы можете загрузить документ.",
        reply_markup=main_keyboard
    )