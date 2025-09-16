"""
Сервис для OCR обработки PDF документов
"""

import asyncio
import time
from pathlib import Path
from typing import Optional, Tuple
from unstructured.partition.pdf import partition_pdf

from models import TextElement, PageData, DocumentData
from config import logger


async def process_pdf_ocr(pdf_path: str, original_filename: str, max_pages: Optional[int] = None) -> Tuple[DocumentData, float]:
    """
    Выполняет OCR обработку PDF документа
    
    Args:
        pdf_path (str): Путь к PDF файлу
        original_filename (str): Оригинальное имя файла
        max_pages (int): Максимальное количество страниц для обработки
        
    Returns:
        Tuple[DocumentData, float]: Структурированные данные документа и время обработки
    """
    
    logger.info(f"Начинаю OCR обработку файла: {original_filename}")
    start_time = time.time()
    
    try:
        # OCR обработка только для текста
        logger.info("Запускаю unstructured для извлечения текста")
        elements = await asyncio.to_thread(
            partition_pdf,
            filename=pdf_path,
            strategy="hi_res",  # Высокое качество распознавания
            extract_image_block_to_payload=False,  # НЕ извлекаем изображения
            infer_table_structure=False,  # НЕ обрабатываем таблицы
            languages=["rus"],  # Русский язык
        )
        
        logger.info(f"Извлечено элементов: {len(elements)}")
        
        # Группируем данные по страницам для создания Pydantic моделей
        pages_data = {}
        
        for element in elements:
            # Получаем номер страницы
            page_number = getattr(element.metadata, "page_number", 1)
            
            # Ограничиваем количество страниц если задано
            if max_pages and page_number > max_pages:
                continue
                
            # Инициализируем страницу если её ещё нет
            if page_number not in pages_data:
                pages_data[page_number] = []
            
            # Создаём TextElement для каждого непустого элемента
            if element.text and element.text.strip():
                text_element = TextElement(
                    category=element.category,
                    content=element.text.strip(),
                    type="text"
                )
                pages_data[page_number].append(text_element)
        
        logger.info(f"Обработано страниц: {len(pages_data)}")
        
        # Создаём список объектов PageData
        pages = []
        for page_num in sorted(pages_data.keys()):
            # Создаём полный текст страницы
            full_page_text = " ".join([element.content for element in pages_data[page_num]])
            
            page_data = PageData(
                page_number=page_num,
                full_text=full_page_text,
                elements=pages_data[page_num],
                total_elements=len(pages_data[page_num])
            )
            pages.append(page_data)
            logger.info(f"Страница {page_num}: {len(pages_data[page_num])} элементов")
        
        # Создаём объект DocumentData с оригинальным именем
        document = DocumentData(
            filename=original_filename,
            total_pages=len(pages),
            pages=pages
        )
        
        # Вычисляем время обработки
        processing_time = time.time() - start_time
        
        logger.info(f"Успешно завершена OCR обработка документа: {document.filename}")
        logger.info(f"Время обработки: {processing_time:.2f} секунд")
        return document, processing_time
        
    except Exception as e:
        logger.error(f"Ошибка при OCR обработке файла {pdf_path}: {e}")
        raise


async def save_ocr_result(document: DocumentData, result_folder: str = "result") -> Tuple[str, str]:
    """
    Сохраняет результат OCR в JSON и TXT файлы
    
    Args:
        document (DocumentData): Данные документа
        result_folder (str): Папка для сохранения результата
        
    Returns:
        Tuple[str, str]: Пути к сохранённым JSON и TXT файлам
    """
    
    # Создаём папку если её нет
    result_path = Path(result_folder)
    result_path.mkdir(exist_ok=True)
    
    # Генерируем имена файлов
    file_stem = Path(document.filename).stem
    json_file = result_path / f"ocr_result_{file_stem}.json"
    txt_file = result_path / f"full_text_{file_stem}.txt"
    
    logger.info(f"Сохраняю результат OCR в файлы: {json_file} и {txt_file}")
    
    try:
        # Сохраняем JSON
        with open(json_file, "w", encoding="utf-8") as f:
            f.write(document.model_dump_json(indent=2))
        
        # Сохраняем полный текст
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write(document.get_all_text())
        
        logger.info(f"Результаты OCR сохранены: {json_file} и {txt_file}")
        return str(json_file), str(txt_file)
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении результата OCR: {e}")
        raise
