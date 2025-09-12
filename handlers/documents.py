from aiogram import types

async def handle_upload_document(message: types.Message):
    """Обработчик кнопки 'Загрузить документ'"""
    await message.answer(
        "Пожалуйста, отправьте мне документ (файл) в формате PDF."
    )