"""
Тестовый скрипт для OCR обработки PDF документов
Использует unstructured для извлечения только текста с Pydantic моделями
"""

from pathlib import Path
from typing import Dict, List, Any
from unstructured.partition.pdf import partition_pdf

from models import TextElement, PageData, DocumentData


def process_pdf_with_pydantic(pdf_path: str, max_pages: int = None) -> DocumentData:
    """
    Выполняет OCR обработку PDF документа с использованием Pydantic моделей
    
    Args:
        pdf_path (str): Путь к PDF файлу
        max_pages (int): Максимальное количество страниц для обработки
        
    Returns:
        DocumentData: Структурированные данные документа
    """
    
    print(f"Обрабатываю файл: {pdf_path}")
    
    # OCR обработка только для текста
    elements = partition_pdf(
        filename=pdf_path,
        strategy="hi_res",  # Высокое качество распознавания
        extract_image_block_to_payload=False,  # НЕ извлекаем изображения
        infer_table_structure=False,
        languages=["rus"]
    )
    
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
        if element.text.strip():
            text_element = TextElement(
                category=element.category,
                content=element.text.strip(),
                type="text"
            )
            pages_data[page_number].append(text_element)
    
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
    
    # Создаём объект DocumentData
    document = DocumentData(
        filename=Path(pdf_path).name,
        total_pages=len(pages),
        pages=pages
    )
    
    return document


def test_pdf_ocr():
    """
    Основная функция тестирования OCR
    """
    
    # УКАЖИТЕ ЗДЕСЬ ПУТЬ К ВАШЕМУ PDF ФАЙЛУ
    pdf_file_path = "tests/data/doc_demo_5_6.pdf"  # <-- Измените этот путь
    
    pdf_file = Path(pdf_file_path)
    
    # Проверяем существование файла
    if not pdf_file.exists():
        print(f"❌ Файл {pdf_file_path} не найден")
        print("Укажите правильный путь к PDF файлу в переменной pdf_file_path")
        return
    
    print(f"Обрабатываю файл: {pdf_file.name}")
    
    try:
        # Создаём папку для результатов тестирования
        result_folder = Path(__file__).parent / "test_results"
        result_folder.mkdir(exist_ok=True)
        
        # Обрабатываем документ с помощью Pydantic моделей
        document = process_pdf_with_pydantic(str(pdf_file), max_pages=3)
        
        print(f"✅ Успешно обработан документ: {document.filename}")
        print(f"📄 Всего страниц: {document.total_pages}")
        
        # Выводим краткий результат по страницам
        for page in document.pages:
            print(f"\nСтраница {page.page_number}: {page.total_elements} элементов")
            
            # Показываем полный текст страницы (первые 200 символов)
            text_preview = page.full_text[:200]
            if len(page.full_text) > 200:
                text_preview += "..."
            print(f"  Полный текст: {text_preview}")
            
            # Показываем первые несколько элементов
            print("  Элементы:")
            for i, element in enumerate(page.elements[:3]):
                content_preview = element.content[:80]
                if len(element.content) > 80:
                    content_preview += "..."
                print(f"    {i+1}. [{element.category}]: {content_preview}")
            
            if page.total_elements > 3:
                print(f"    ... и ещё {page.total_elements - 3} элементов")
        
        # Сохраняем результат в JSON через Pydantic в папку test_results
        output_file = result_folder / f"pydantic_result_{pdf_file.stem}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            # Используем встроенный метод model_dump_json() для сериализации
            f.write(document.model_dump_json(indent=2))
        
        print(f"📄 Pydantic результат сохранён в: {output_file}")
        
        # Демонстрация дополнительных возможностей Pydantic моделей
        print("\n🔍 Дополнительные возможности:")
        print(f"Элементов типа 'Title': {len(document.get_elements_by_category('Title'))}")
        print(f"Элементов типа 'ListItem': {len(document.get_elements_by_category('ListItem'))}")
        print(f"Элементов типа 'NarrativeText': {len(document.get_elements_by_category('NarrativeText'))}")
        
        # Сохраняем весь текст как строку в папку test_results
        text_output_file = result_folder / f"full_text_{pdf_file.stem}.txt"
        with open(text_output_file, "w", encoding="utf-8") as f:
            f.write(document.get_all_text())
        print(f"📝 Полный текст сохранён в: {text_output_file}")
        
    except Exception as e:
        print(f"❌ Ошибка при обработке {pdf_file.name}: {e}")


if __name__ == "__main__":
    print("🔍 Тестирование OCR обработки PDF документов")
    test_pdf_ocr()