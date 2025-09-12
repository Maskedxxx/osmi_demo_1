from aiogram import types
from aiogram.fsm.context import FSMContext
from datetime import datetime
from models import DocumentFile
from states import DocumentUpload
from keyboards.main import main_keyboard
from config import logger

async def handle_upload_document(message: types.Message, state: FSMContext):
    """Обработчик кнопки 'Загрузить документ'"""
    await message.answer(
        "Пожалуйста, отправьте мне документ (файл) в формате DOCX."
    )
    await state.set_state(DocumentUpload.waiting_file)

async def handle_document_file(message: types.Message, state: FSMContext):
    """Обработчик загруженного документа"""
    if not message.document:
        await message.answer("Пожалуйста, отправьте документ как файл.")
        return
    
    document = message.document
    
    # Проверяем тип файла
    if not document.file_name.lower().endswith('.docx'):
        await message.answer(
            "Поддерживаются только файлы формата DOCX. Попробуйте еще раз.",
            reply_markup=main_keyboard
        )
        await state.clear()
        return
    
    try:
        # Создаем объект документа с метаданными
        doc_file = DocumentFile(
            filename=document.file_name,
            file_id=document.file_id,
            file_size=document.file_size,
            upload_date=datetime.now(),
            user_id=message.from_user.id
        )
        
        # Логируем загрузку
        logger.info(f"Загружен документ: {doc_file.filename} от пользователя {doc_file.user_id}")
        
        # Отправляем метаданные пользователю
        await message.answer(
            doc_file.get_metadata_text(),
            reply_markup=main_keyboard
        )
        
        # Очищаем состояние
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке документа: {e}")
        await message.answer(
            "Произошла ошибка при обработке документа. Попробуйте еще раз.",
            reply_markup=main_keyboard
        )
        await state.clear()