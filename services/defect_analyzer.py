"""
Сервис для LLM-анализа технических отчетов и заполнения Excel форм дефектов
"""

import json
from pathlib import Path
from typing import List
from datetime import datetime

from openai import OpenAI
import pandas as pd

from models import DocumentData, DefectAnalysisResult, DefectAnalysisListResult
from config import logger, OPENAI_API_KEY


# Экспертный промпт для анализа технических отчетов
EXPERT_DEFECT_ANALYSIS_PROMPT = """Вы - опытный эксперт по строительной экспертизе и техническому контролю качества ремонтных работ.

СТРУКТУРА ДОКУМЕНТА: 
Предоставленный текст - это экспертиза строительных работ, которая организована по РАЗДЕЛАМ. Каждый раздел посвящен определенному ТИПУ КОНСТРУКЦИИ помещения (пол, потолок, стена, дверь, окно и т.д.). В каждом разделе перечислены конкретные недостатки, выявленные для данного типа конструкции.

ЗАДАЧА: 
Извлеките ВСЕ недостатки из каждого раздела экспертизы и структурируйте их согласно полям схемы.

ПРАВИЛА АНАЛИЗА:

1. ОПРЕДЕЛЕНИЕ РАЗДЕЛА И ЛОКАЛИЗАЦИИ:
   - Найдите разделы по типам конструкций (например: "ПОТОЛКИ", "ПОЛЫ", "СТЕНЫ", "ДВЕРИ")
   - Все недостатки из раздела "ПОТОЛКИ" → location = "Потолок"  
   - Все недостатки из раздела "ПОЛЫ" → location = "Пол"
   - Все недостатки из раздела "СТЕНЫ" → location = "Стена"
   - И так далее для каждого типа конструкции

2. ИЗВЛЕЧЕНИЕ НЕДОСТАТКОВ:
   - Внутри каждого раздела найдите ВСЕ перечисленные недостатки
   - Каждый недостаток = отдельная запись в результате
   - Если у недостатка есть вложенные детали/подробности - включите их в описание дефекта, НЕ создавайте отдельную запись

3. ЗАПОЛНЕНИЕ ПОЛЕЙ:

   ПОМЕЩЕНИЕ - определите из контекста или выберите общую категорию:
   - Гостиная, Спальня, Детская, Кабинет, Кухня, Ванная, Туалет, Коридор, Прихожая, Балкон, Лоджия, Кладовая, Гардеробная
   - Если не указано: "Жилое помещение" или "Подсобное помещение"

   ЛОКАЛИЗАЦИЯ - согласно разделу экспертизы:
   - Пол, Потолок, Стена, Дверь, Окно, Оконный блок, Сантехника, Электрика, Отопление, Плитка, Покрытие, Штукатурка, Краска

   ДЕФЕКТ - сжатое техническое описание недостатка:
   - Скопируйте описание из экспертизы с сохранением терминологии
   - Включите количественные характеристики (размеры, площади)
   - Если есть вложенные детали - объедините в одно описание
   - У местите все в раткое предложение не больше 10 слов

   НАИМЕНОВАНИЕ РАБОТЫ - тип работ для устранения:
   - Отделочные работы, Сантехнические работы, Электромонтажные работы, Плиточные работы, Малярные работы, Штукатурные работы, Демонтажные работы, Замена конструкций

   SOURCE_TEXT - краткая выдержка в 5 слов из текста экспертизы, на основе которой выявлен дефект

ВАЖНО:
- НЕ ПРОПУСКАЙТЕ недостатки из-за того что они кажутся мелкими
- НЕ СОЗДАВАЙТЕ отдельные записи для вложенных деталей недостатка  
- ОБЪЕДИНЯЙТЕ детали в основное описание дефекта
- Если раздел не содержит недостатков - не создавайте записи для него
- Используйте ТОЛЬКО значения из предложенных списков для полей с ограниченным выбором"""


class DefectAnalyzer:
    """Класс для анализа дефектов через LLM и генерации Excel отчетов"""
    
    def __init__(self):
        """Инициализация анализатора дефектов"""
        self.client = None
        
    def _setup_openai_client(self) -> bool:
        """
        Настройка OpenAI клиента
        
        Returns:
            bool: True если клиент успешно настроен
        """
        try:
            if not OPENAI_API_KEY:
                logger.error("OPENAI_API_KEY не найден в переменных окружения")
                return False
                
            self.client = OpenAI(api_key=OPENAI_API_KEY)
            logger.info("✅ OpenAI клиент настроен успешно")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка при настройке OpenAI клиента: {e}")
            return False
    
    async def analyze_combined_text(self, combined_text: str) -> DefectAnalysisListResult:
        """
        Анализ объединенного текста через LLM с получением списка дефектов
        
        Args:
            combined_text: Объединенный текст со всех страниц для анализа
            
        Returns:
            DefectAnalysisListResult: Список найденных дефектов
        """
        if not self.client:
            if not self._setup_openai_client():
                raise ValueError("Не удалось настроить OpenAI клиент")
        
        logger.info(f"Анализирую объединенный текст через LLM ({len(combined_text)} символов)")
        
        try:
            completion = self.client.chat.completions.parse(
                model="gpt-4.1-mini-2025-04-14",
                messages=[
                    {
                        "role": "system", 
                        "content": EXPERT_DEFECT_ANALYSIS_PROMPT
                    },
                    {
                        "role": "user", 
                        "content": f"Проанализируйте следующий объединенный текст из технического отчета и найдите все дефекты:\n\n{combined_text}"
                    }
                ],
                response_format=DefectAnalysisListResult,
            )
            
            result = completion.choices[0].message.parsed
            
            logger.info(f"✅ Анализ завершен: найдено {len(result.defects)} дефектов")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка при анализе текста через LLM: {e}")
            raise
    
    def create_excel_report(self, analysis_results: List[DefectAnalysisResult], 
                          output_path: str = None) -> str:
        """
        Создание Excel отчета из результатов анализа через pandas
        
        Args:
            analysis_results: Список результатов анализа дефектов
            output_path: Путь для сохранения файла
            
        Returns:
            str: Путь к созданному Excel файлу
        """
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"result/defect_analysis_{timestamp}.xlsx"
        
        logger.info(f"Создаю Excel отчет: {output_path}")
        
        try:
            # Создаем директорию если не существует
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Преобразуем результаты в словарь для DataFrame
            data = {
                "Текст из АПО/экспертизы": [r.source_text for r in analysis_results],
                "Помещение": [r.room for r in analysis_results],
                "Локализация": [r.location for r in analysis_results],
                "Дефект": [r.defect for r in analysis_results],
                "Наименование работы": [r.work_type for r in analysis_results]
            }
            
            # Создаем DataFrame
            df = pd.DataFrame(data)
            
            # Сохраняем в Excel с индексом начиная с 1
            df.to_excel(output_path, index=False, sheet_name="Анализ дефектов")
            
            logger.info(f"✅ Excel отчет создан: {output_path} ({len(analysis_results)} записей)")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка при создании Excel отчета: {e}")
            raise
    
    async def process_combined_pages(self, page_texts: List[str]) -> List[DefectAnalysisResult]:
        """
        Обработка объединенного текста со всех страниц
        
        Args:
            page_texts: Список текстов для анализа
            
        Returns:
            List[DefectAnalysisResult]: Список найденных дефектов
        """
        logger.info(f"Объединяю {len(page_texts)} страниц для анализа")
        
        # Объединяем все тексты в одну строку
        combined_text = "\n\n".join([f"=== Страница {i+1} ===\n{text.strip()}" for i, text in enumerate(page_texts)])
        
        logger.info(f"Объединенный текст: {len(combined_text)} символов")
        
        try:
            result = await self.analyze_combined_text(combined_text)
            logger.info(f"✅ Обработка завершена: найдено {len(result.defects)} дефектов")
            return result.defects
            
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке объединенного текста: {e}")
            raise
    
    async def analyze_document_defects(self, document: DocumentData, 
                                     relevant_page_numbers: List[int] = None,
                                     output_path: str = None) -> str:
        """
        Полный анализ дефектов документа с созданием Excel отчета
        
        Args:
            document: Данные документа
            relevant_page_numbers: Номера релевантных страниц (если None - все страницы)
            output_path: Путь для Excel файла
            
        Returns:
            str: Путь к созданному Excel файлу
        """
        logger.info(f"Начинаю полный анализ дефектов документа: {document.filename}")
        
        try:
            # Определяем какие страницы анализировать
            pages_to_analyze = []
            if relevant_page_numbers:
                # Анализируем только релевантные страницы
                for page in document.pages:
                    if page.page_number in relevant_page_numbers:
                        pages_to_analyze.append(page.full_text)
                logger.info(f"Выбрано {len(pages_to_analyze)} релевантных страниц для анализа")
            else:
                # Анализируем все страницы
                pages_to_analyze = [page.full_text for page in document.pages]
                logger.info(f"Анализирую все {len(pages_to_analyze)} страниц документа")
            
            if not pages_to_analyze:
                raise ValueError("Нет страниц для анализа")
            
            # Анализируем тексты через LLM
            analysis_results = await self.process_combined_pages(pages_to_analyze)
            
            if not analysis_results:
                raise ValueError("Не удалось получить результаты анализа")
            
            # Создаем Excel отчет
            excel_path = self.create_excel_report(analysis_results, output_path)
            
            logger.info(f"✅ Анализ документа завершен: {excel_path}")
            return excel_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка при анализе документа: {e}")
            raise


async def analyze_document_from_json_with_excel(json_path: str, 
                                              relevant_page_numbers: List[int] = None,
                                              output_path: str = None) -> str:
    """
    Удобная функция для анализа документа из JSON с созданием Excel отчета
    
    Args:
        json_path: Путь к JSON файлу с данными документа
        relevant_page_numbers: Номера релевантных страниц
        output_path: Путь для Excel файла
        
    Returns:
        str: Путь к созданному Excel файлу
    """
    # Загружаем документ из JSON
    logger.info(f"Загружаю документ из JSON: {json_path}")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        document = DocumentData(**data)
        logger.info(f"✅ Документ загружен: {document.filename}, страниц: {document.total_pages}")
        
        # Создаем анализатор и запускаем анализ
        analyzer = DefectAnalyzer()
        excel_path = await analyzer.analyze_document_defects(
            document=document,
            relevant_page_numbers=relevant_page_numbers,
            output_path=output_path
        )
        
        return excel_path
        
    except Exception as e:
        logger.error(f"❌ Ошибка при анализе документа из JSON: {e}")
        raise