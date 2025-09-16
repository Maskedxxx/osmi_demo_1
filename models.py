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
    source_text: str = Field(..., description="Текст из документа экспертизы или АПО, на основе которого выявлен дефект, коротко определение дефекта в несколько точных слов.")
    room: Literal[
        "Коридор", "Комната", "Санузел"
    ] = Field(..., description="Верхнеуровневый тип помещения в котором обнаружен дефект")
    location: Literal[
        "Пол", "Потолок", "Стена", "Межкомнатная дверь", "Входная дверь", "Оконный блок"
    ] = Field(..., description="Локализация дефекта. (Точное определение локации в помещении согласно исходному тексту)")
    defect: str = Field(..., description="Техническое описание дефекта")
    work_type: Literal[
        "Отделочные работы", "Сантехнические работы", "Электромонтажные работы",
        "Плиточные работы", "Малярные работы", "Штукатурные работы",
        "Демонтажные работы"
    ] = Field(..., description="Наименование работ которые проводились при возникновении дефекта")


class CleanedPageData(BaseModel):
    """
    Данные страницы после обработки VLM
    """
    page_number: int = Field(..., description="Номер страницы")
    cleaned_text: str = Field(..., description="Очищенный и структурированный текст страницы")


class VLMCleaningResult(BaseModel):
    """
    Результат VLM обработки страниц
    """
    source_pdf: str = Field(..., description="Путь к исходному PDF файлу")
    processed_pages: int = Field(..., description="Количество обработанных страниц")
    cleaned_pages: List[CleanedPageData] = Field(default=[], description="Список очищенных страниц")


class DefectAnalysisListResult(BaseModel):
    """
    Список результатов анализа дефектов
    """
    defects: List[DefectAnalysisResult] = Field(
        ..., 
        description="Список найденных дефектов",
        min_items=0
    )