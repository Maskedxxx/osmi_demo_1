"""
Pydantic модели для структурирования данных OCR
"""

from typing import List, Literal
from pydantic import BaseModel, Field


class TextElement(BaseModel):
    """
    Элемент текста на странице
    """
    category: str = Field(..., description="Категория элемента: Title, NarrativeText, ListItem, etc.")
    content: str = Field(..., description="Текстовое содержимое элемента")
    type: Literal["text"] = Field(default="text", description="Тип элемента (всегда text)")


class PageData(BaseModel):
    """
    Данные одной страницы документа
    """
    page_number: int = Field(..., description="Номер страницы")
    full_text: str = Field(..., description="Весь текст страницы в одной строке")
    elements: List[TextElement] = Field(default=[], description="Список текстовых элементов на странице")
    total_elements: int = Field(..., description="Общее количество элементов на странице")
    
    def __init__(self, **data):
        super().__init__(**data)
        # Автоматически подсчитываем количество элементов
        self.total_elements = len(self.elements)
        # Если full_text не передан, создаём его из элементов
        if 'full_text' not in data:
            self.full_text = " ".join([element.content for element in self.elements])


class DocumentData(BaseModel):
    """
    Данные всего документа
    """
    filename: str = Field(..., description="Имя файла документа")
    total_pages: int = Field(..., description="Общее количество страниц")
    pages: List[PageData] = Field(default=[], description="Список страниц документа")
    
    def __init__(self, **data):
        super().__init__(**data)
        # Автоматически подсчитываем количество страниц
        self.total_pages = len(self.pages)
    
    def get_page(self, page_number: int) -> PageData:
        """Получить данные конкретной страницы"""
        for page in self.pages:
            if page.page_number == page_number:
                return page
        raise ValueError(f"Страница {page_number} не найдена")
    
    def get_all_text(self) -> str:
        """Получить весь текст документа как строку"""
        all_text = []
        for page in self.pages:
            page_text = []
            for element in page.elements:
                page_text.append(element.content)
            all_text.append(f"=== Страница {page.page_number} ===\n" + "\n".join(page_text))
        return "\n\n".join(all_text)
    
    def get_elements_by_category(self, category: str) -> List[TextElement]:
        """Получить все элементы определенной категории"""
        elements = []
        for page in self.pages:
            for element in page.elements:
                if element.category == category:
                    elements.append(element)
        return elements


class DefectAnalysisResult(BaseModel):
    """
    Результат LLM анализа дефекта для заполнения формы
    """
    source_text: str = Field(..., description="Исходный текст из АПО/экспертизы")
    room: str = Field(..., description="Помещение (например: Коридор, Кухня, Ванная)")  
    location: str = Field(..., description="Локализация (например: Пол, Потолок, Стена)")
    defect: str = Field(..., description="Описание дефекта")
    work_type: str = Field(..., description="Наименование работы (например: Отделочные работы)")