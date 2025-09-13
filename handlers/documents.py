import os
import tempfile
import aiohttp
import re
from datetime import datetime
from aiogram import types, Bot

from services.ocr_service import process_pdf_ocr, save_ocr_result
from config import logger


async def handle_upload_document(message: types.Message):
    """Обработчик кнопки 'Загрузить документ'"""
    await message.answer(
        "Пожалуйста, отправьте мне документ (файл) в формате PDF.\n\n"
        "📎 Вы можете:\n"
        "• Загрузить файл напрямую (до 20 МБ)\n"
        "• Отправить ссылку на файл из облака:\n"
        "  - Google Drive\n"
        "  - Dropbox\n"
        "  - Яндекс.Диск"
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


async def download_file_from_url(url: str) -> str:
    """Скачивает файл по URL и возвращает путь к временному файлу"""
    
    # Определяем прямую ссылку для скачивания
    direct_url = get_direct_download_url(url)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(direct_url) as response:
                if response.status != 200:
                    raise Exception(f"Ошибка загрузки: HTTP {response.status}")
                
                # Создаём временный файл
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                    temp_path = temp_file.name
                    async for chunk in response.content.iter_chunked(8192):
                        temp_file.write(chunk)
                
                logger.info(f"Файл скачан из URL в: {temp_path}")
                return temp_path
                
    except Exception as e:
        logger.error(f"Ошибка при скачивании файла: {e}")
        raise


def get_direct_download_url(url: str) -> str:
    """Преобразует ссылки облачных хранилищ в прямые ссылки"""
    
    # Google Drive
    if "drive.google.com" in url:
        # Извлекаем ID файла из ссылки
        file_id_match = re.search(r'/file/d/([a-zA-Z0-9-_]+)', url)
        if file_id_match:
            file_id = file_id_match.group(1)
            return f"https://drive.google.com/uc?export=download&id={file_id}"
    
    # Dropbox
    elif "dropbox.com" in url:
        # Заменяем dl=0 на dl=1 для прямого скачивания
        return url.replace("dl=0", "dl=1")
    
    # Yandex Disk
    elif "disk.yandex" in url:
        # Для Яндекс.Диска нужно использовать API, пока возвращаем как есть
        return url
    
    # Обычная ссылка
    return url


async def handle_url_document(message: types.Message, bot: Bot):
    """Обработчик PDF документа по ссылке"""
    
    url = message.text.strip()
    logger.info(f"Получена ссылка на документ: {url} от пользователя {message.from_user.id}")
    
    # Сообщаем пользователю что начинаем обработку
    processing_message = await message.answer("🔄 Скачиваю документ по ссылке...")
    
    try:
        # Скачиваем файл по ссылке
        temp_path = await download_file_from_url(url)
        
        # Обновляем сообщение
        await processing_message.edit_text("📄 Извлекаю текст из PDF документа...")
        
        # Генерируем имя файла с датой
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"document_{timestamp}.pdf"
        
        # Выполняем OCR обработку
        document_data, processing_time = await process_pdf_ocr(temp_path, filename)
        
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
        
        # Отправляем результат пользователю
        result_text = "✅ OCR обработка завершена!\n\n"
        result_text += f"📄 Документ: {document_data.filename}\n"
        result_text += f"📖 Страниц обработано: {document_data.total_pages}\n"
        result_text += f"⏱️ Время обработки: {processing_time:.1f} сек\n"
        result_text += f"💾 JSON результат: {json_file}\n"
        result_text += f"📝 Текстовый файл: {txt_file}"
        
        await processing_message.edit_text(result_text)
        
        logger.info(f"✅ Успешно завершена обработка файла из URL: {url}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке PDF по ссылке: {e}")
        
        # Удаляем временный файл в случае ошибки
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)
        
        await processing_message.edit_text(
            f"❌ Произошла ошибка при обработке документа по ссылке:\n{str(e)}"
        )