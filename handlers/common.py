from aiogram import types
from keyboards.main import main_keyboard

async def fallback(message: types.Message):
    await message.answer(
        "**В РАЗРАБОТКЕ:** Бот находится в процессе разработки. Скоро здесь появится новая функциональность.",
        reply_markup=main_keyboard
    )