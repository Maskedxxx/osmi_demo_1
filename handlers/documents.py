import os
import tempfile
import aiohttp
import re
from datetime import datetime
from aiogram import types, Bot

from services.ocr_service import process_pdf_ocr, save_ocr_result
from services.semantic_page_filter import analyze_document_from_json
from services.vlm_page_cleaner import VLMPageCleaner
from services.defect_analyzer import analyze_vlm_cleaned_pages_with_excel
from config import logger, DEFECT_SEARCH_UTTERANCES, DEFECT_ANALYSIS_SCORE_THRESHOLD, DEFECT_ANALYSIS_TOP_PAGES


async def handle_upload_document(message: types.Message):
    """Обработчик кнопки 'Загрузить документ'"""
    await message.answer(
        "🔍 **Анализ дефектов строительных работ**\n\n"
        "Отправьте мне PDF документ экспертизы или технического отчета, "
        "и я выполню полный анализ:\n\n"
        "📄 **1. OCR обработка** - извлечение текста\n"
        "🎯 **2. Семантический поиск** - поиск страниц с дефектами\n"
        "🖼️ **3. VLM очистка** - улучшение качества текста\n"
        "🤖 **4. LLM анализ** - структурирование информации\n"
        "📊 **5. Excel отчет** - готовая таблица дефектов\n\n"
        "💡 **Поддерживаются:**\n"
        "• PDF файлы (до 20 МБ)\n"
        "• Ссылки на файлы из облачных хранилищ:\n"
        "  - Google Drive\n"
        "  - Dropbox\n"
        "  - Яндекс.Диск",
        parse_mode="Markdown"
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


async def handle_analyze_defects_command(message: types.Message):
    """Обработчик команды /analyze_defects"""
    await message.answer(
        "🔍 **Анализ дефектов строительных работ**\n\n"
        "Отправьте мне PDF документ экспертизы или технического отчета, "
        "и я выполню полный анализ:\n\n"
        "📄 **1. OCR обработка** - извлечение текста\n"
        "🎯 **2. Семантический поиск** - поиск страниц с дефектами\n"
        "🖼️ **3. VLM очистка** - улучшение качества текста\n"
        "🤖 **4. LLM анализ** - структурирование информации\n"
        "📊 **5. Excel отчет** - готовая таблица дефектов\n\n"
        "💡 Поддерживаются:\n"
        "• PDF файлы (до 20 МБ)\n"
        "• Ссылки на файлы из облачных хранилищ",
        parse_mode="Markdown"
    )


async def handle_full_defect_analysis(message: types.Message, bot: Bot):
    """
    Полный пайплайн анализа дефектов:
    1. OCR обработка PDF
    2. Семантический поиск релевантных страниц
    3. VLM очистка и улучшение текста страниц
    4. LLM анализ дефектов
    5. Создание Excel отчета
    """
    
    # Определяем тип входных данных (файл или ссылка)
    is_file = bool(message.document)
    is_url = bool(message.text and ("http" in message.text or "drive.google.com" in message.text))
    
    if not (is_file or is_url):
        await message.answer(
            "❌ Для анализа дефектов отправьте PDF файл или ссылку на документ.\n"
            "Используйте команду /analyze_defects для получения инструкций."
        )
        return
    
    # Проверка типа файла для загруженных документов
    if is_file and not message.document.file_name.lower().endswith('.pdf'):
        await message.answer("❌ Пожалуйста, отправьте файл в формате PDF.")
        return
    
    logger.info(f"Начинаю полный анализ дефектов для пользователя {message.from_user.id}")
    
    # Сообщение о начале процесса
    progress_message = await message.answer("🚀 **Запускаю полный анализ дефектов...**", parse_mode="Markdown")
    
    temp_path = None
    
    try:
        # ========== ЭТАП 1: Загрузка и OCR обработка ==========
        await progress_message.edit_text("📄 **Этап 1/5:** Загрузка и OCR обработка документа...", parse_mode="Markdown")
        
        if is_file:
            # Скачиваем загруженный файл
            file_info = await bot.get_file(message.document.file_id)
            
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_path = temp_file.name
                await bot.download_file(file_info.file_path, temp_file)
            
            original_filename = message.document.file_name
            logger.info(f"Загружен файл: {original_filename}")
            
        else:  # is_url
            # Скачиваем файл по ссылке
            temp_path = await download_file_from_url(message.text.strip())
            original_filename = f"document_from_url_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            logger.info(f"Скачан файл по ссылке: {message.text.strip()}")
        
        # Выполняем OCR обработку
        document_data, processing_time = await process_pdf_ocr(temp_path, original_filename)
        
        # Сохраняем OCR результат
        json_file, txt_file = await save_ocr_result(document_data)
        
        logger.info(f"OCR завершен: {document_data.total_pages} страниц за {processing_time:.1f}с")
        
        # ========== ЭТАП 2: Семантический поиск релевантных страниц ==========
        await progress_message.edit_text("🎯 **Этап 2/5:** Поиск страниц с описанием дефектов...", parse_mode="Markdown")
        
        relevant_pages = await analyze_document_from_json(
            json_path=json_file,
            utterances=DEFECT_SEARCH_UTTERANCES,
            score_threshold=DEFECT_ANALYSIS_SCORE_THRESHOLD,
            top_limit=DEFECT_ANALYSIS_TOP_PAGES
        )

        # Сортируем и убираем дубликаты, чтобы сохранить порядок страниц в документе
        sorted_relevant_pages = sorted(set(relevant_pages))

        if not sorted_relevant_pages:
            await progress_message.edit_text(
                "⚠️ **Анализ завершен с предупреждением**\n\n"
                "В документе не найдены страницы с описанием дефектов строительных работ.\n"
                f"📄 Обработано страниц: {document_data.total_pages}\n"
                f"🔍 Порог схожести: {DEFECT_ANALYSIS_SCORE_THRESHOLD}\n\n"
                "💡 Возможно, документ не содержит технических описаний дефектов или "
                "использует нестандартную терминологию.",
                parse_mode="Markdown"
            )
            return
        
        logger.info(
            "Найдено релевантных страниц: %d (после сортировки: %d) - %s (отсортировано: %s)",
            len(relevant_pages),
            len(sorted_relevant_pages),
            relevant_pages,
            sorted_relevant_pages,
        )

        # ========== ЭТАП 3: VLM обработка релевантных страниц ==========
        await progress_message.edit_text("🖼️ **Этап 3/5:** VLM обработка и очистка страниц...", parse_mode="Markdown")

        # Инициализируем VLM очиститель
        vlm_cleaner = VLMPageCleaner()

        # Обрабатываем релевантные страницы через VLM
        from pathlib import Path
        vlm_result = vlm_cleaner.process_pages(Path(temp_path), sorted_relevant_pages)
        
        logger.info(f"VLM обработка завершена: {vlm_result.processed_pages} страниц")
        
        # ========== ЭТАП 4: LLM анализ и создание Excel ==========
        await progress_message.edit_text("🤖 **Этап 4/5:** Анализ дефектов через LLM и создание Excel...", parse_mode="Markdown")
        
        excel_path = await analyze_vlm_cleaned_pages_with_excel(
            vlm_result=vlm_result,
            output_path=None  # Автоматическое имя файла
        )
        
        logger.info(f"Excel отчет создан: {excel_path}")
        
        # ========== ЭТАП 5: Отправка результата пользователю ==========
        await progress_message.edit_text("📊 **Этап 5/5:** Подготовка результата...", parse_mode="Markdown")
        
        # Отправляем Excel файл пользователю
        with open(excel_path, 'rb') as excel_file:
            excel_document = types.BufferedInputFile(
                excel_file.read(),
                filename=f"defect_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            
            await message.answer_document(
                excel_document,
                caption=(
                    f"✅ **Анализ дефектов завершен!**\n\n"
                    f"📄 **Документ:** {document_data.filename}\n"
                    f"📖 **Страниц обработано:** {document_data.total_pages}\n"
                    f"🎯 **Найдено релевантных:** {len(sorted_relevant_pages)} страниц\n"
                    f"⏱️ **Время OCR:** {processing_time:.1f} сек\n\n"
                    f"📋 **Результат:** Excel таблица с структурированными данными о дефектах"
                ),
                parse_mode="Markdown"
            )
        
        # Удаляем сообщение о прогрессе
        await progress_message.delete()
        
        logger.info(f"✅ Полный анализ дефектов завершен для {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в полном анализе дефектов: {e}")
        
        await progress_message.edit_text(
            f"❌ **Ошибка при анализе дефектов**\n\n"
            f"Произошла ошибка: {str(e)}\n\n"
            f"Попробуйте еще раз или обратитесь в поддержку.",
            parse_mode="Markdown"
        )
        
    finally:
        # Очистка временных файлов
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
            logger.info(f"Временный файл удален: {temp_path}")
