"""
Pydantic модели для структурирования данных OCR
"""

from typing import List, Literal
from pydantic import BaseModel, Field


# Enum для дефектов из справочника
DefectKey = Literal[
    "ventilation_system_malfunction", "ventilation_project_mismatch", "ventilation_wall_ceiling_gap", "ventilation_surface_defects",
    "heating_pipes_joint_overlap", "heating_pipes_surface_defects", "heating_pipes_sewerage", "heating_pipes_gaps", 
    "heating_pipes_fire_protection", "heating_pipes_water_supply", "heating_pipes_cold_supply",
    "wallpaper_paint_uniformity", "wallpaper_surface_chalking", "wallpaper_surface_defects",
    "window_mounting_seam_mismatch", "window_trim_cracks_gaps", "window_adjustment_missing", "window_glazing_beads_missing",
    "window_trim_incorrect_mounting", "window_hardware_missing",
    "interior_door_adjustment_missing", "interior_door_surface_defects", "interior_door_hardware_adjustment",
    "balcony_tile_steps_chips", "balcony_paint_drips_stains", "balcony_tile_grout_issues",
    "wallpaper_joints", "wallpaper_peeling", "wallpaper_gluing_surface_defects", "wallpaper_glue_stains", "wallpaper_overlap",
    "entrance_door_reinstall_needed", "entrance_door_adjustment_missing", "entrance_door_trim_missing", 
    "entrance_door_hardware_damage", "entrance_door_cleanliness", "entrance_door_surface_defects", 
    "entrance_door_opening_filling", "entrance_door_locking_devices",
    "baseboards_surface_defects", "threshold_steps", "baseboards_floor_gaps", "baseboards_connecting_elements",
    "baseboards_joint_overlap", "baseboards_insufficient_fasteners",
    "bath_screen_not_fixed",
    "ceiling_paint_uniformity", "ceiling_surface_defects",
    "inspection_hatch_door_adjustment", "inspection_hatch_vertical_deviation", "inspection_hatch_surface_defects", "inspection_hatch_wall_gap",
    "floor_tile_voids", "floor_tile_layout_mismatch", "floor_tile_grout", "floor_tile_unevenness", 
    "floor_tile_joint_displacement", "floor_tile_cracks_chips", "floor_tile_joint_placement", "floor_tile_steps", 
    "floor_tile_joint_width", "floor_level_deviation",
    "stretch_ceiling_embedded_parts", "stretch_ceiling_contamination", "stretch_ceiling_baseboard_gap", 
    "stretch_ceiling_pipe_gap", "stretch_ceiling_sagging",
    "plumbing_leaks_malfunction", "plumbing_joint_sealing", "plumbing_surface_defects", "plumbing_mounting", 
    "plumbing_mechanical_damage", "plumbing_decorative_covers",
    "wet_cleaning",
    "door_trim_connection_gaps", "door_trim_mounting", "door_trim_wall_gaps", "door_trim_surface_defects",
    "heating_pipes_paint_defects",
    "laminate_chips_scratches", "laminate_board_gaps", "laminate_ruler_gap", "laminate_steps", 
    "laminate_floor_level_deviation", "laminate_wall_gap_missing",
    "window_slopes_paint_uniformity", "window_slopes_surface_defects",
    "wall_tile_joint_displacement", "wall_tile_glue_residue", "wall_tile_layout_mismatch", "wall_tile_unevenness",
    "wall_tile_grout", "wall_tile_steps", "wall_tile_voids", "wall_tile_hole_shapes", "wall_tile_cracks_chips", "wall_tile_joint_width"
]


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
    defect: DefectKey = Field(..., description="Короткий ключ дефекта из справочника")
    work_type: Literal[
        "Отделочные работы", "Сантехнические работы", "Электромонтажные работы",
        "Плиточные работы", "Малярные работы", "Штукатурные работы",
        "Демонтажные работы"
    ] = Field(..., description="Наименование работ которые проводились при возникновении дефекта")
    
    def get_defect_full_name(self) -> str:
        """Получить полное название дефекта из справочника"""
        from data.defect_mapping import get_defect_full_name
        return get_defect_full_name(self.defect)


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