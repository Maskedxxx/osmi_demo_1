import os
import tempfile
from aiogram import types, Bot

from services.ocr_service import process_pdf_ocr, save_ocr_result
from config import logger


async def handle_upload_document(message: types.Message):
    """Обработчик кнопки 'Загрузить документ'"""
    await message.answer(
        "Пожалуйста, отправьте мне документ (файл) в формате PDF."
    )


async def handle_pdf_document(message: types.Message, bot: Bot):
    """Обработчик загруженного PDF документа"""
    
    if not message.document:
        await message.answer("❌ Ошибка: файл не найден.")
        return
    
    # Проверяем что это PDF файл
    if not message.document.file_name.lower().endswith('.pdf'):
        await message.answer("❌ Пожалуйста, отправьте файл в формате PDF.")
        return
    
    logger.info(f"Получен PDF файл: {message.document.file_name} от пользователя {message.from_user.id}")
    
    # Сообщаем пользователю что начинаем обработку
    processing_message = await message.answer("🔄 Начинаю OCR обработку документа...")
    
    try:
        # Скачиваем файл во временную папку
        file_info = await bot.get_file(message.document.file_id)
        
        # Создаём временный файл
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_path = temp_file.name
            await bot.download_file(file_info.file_path, temp_file)
        
        logger.info(f"PDF файл сохранён во временную папку: {temp_path}")
        
        # Обновляем сообщение
        await processing_message.edit_text("📄 Извлекаю текст из PDF документа...")
        
        # Выполняем OCR обработку
        document_data, processing_time = await process_pdf_ocr(temp_path, message.document.file_name)
        
        # Сохраняем результат в папку result/
        json_file, txt_file = await save_ocr_result(document_data)
        
        # Удаляем временный файл
        os.unlink(temp_path)
        logger.info(f"Временный файл удалён: {temp_path}")
        
        # Показываем статистику по элементам (только в логах)
        total_elements = sum(page.total_elements for page in document_data.pages)
        logger.info(f"📊 Статистика OCR - Всего элементов: {total_elements}")
        logger.info(f"📝 Заголовков: {len(document_data.get_elements_by_category('Title'))}")
        logger.info(f"📝 Списков: {len(document_data.get_elements_by_category('ListItem'))}")
        logger.info(f"📝 Текстовых блоков: {len(document_data.get_elements_by_category('NarrativeText'))}")
        
        # Отправляем результат пользователю (без подробной статистики)
        result_text = "✅ OCR обработка завершена!\n\n"
        result_text += f"📄 Документ: {document_data.filename}\n"
        result_text += f"📖 Страниц обработано: {document_data.total_pages}\n"
        result_text += f"⏱️ Время обработки: {processing_time:.1f} сек\n"
        result_text += f"💾 JSON результат: {json_file}\n"
        result_text += f"📝 Текстовый файл: {txt_file}"
        
        await processing_message.edit_text(result_text)
        
        logger.info(f"✅ Успешно завершена обработка файла {message.document.file_name}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке PDF: {e}")
        
        # Удаляем временный файл в случае ошибки
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)
        
        await processing_message.edit_text(
            f"❌ Произошла ошибка при обработке документа:\n{str(e)}"
        )