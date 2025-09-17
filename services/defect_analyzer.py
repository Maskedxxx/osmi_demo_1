"""
Сервис для LLM-анализа технических отчетов и заполнения Excel форм дефектов
"""

import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from openai import OpenAI
import pandas as pd

from models import DocumentData, DefectAnalysisResult, DefectAnalysisListResult, VLMCleaningResult
from services.llm_usage_tracker import log_chat_completion_usage
from config import logger, OPENAI_API_KEY
from prompts import EXPERT_DEFECT_ANALYSIS_PROMPT


class DefectAnalyzer:
    """Класс для анализа дефектов через LLM и генерации Excel отчетов"""
    
    def __init__(self):
        """Инициализация анализатора дефектов"""
        self.client = None
        self.last_usage: Optional[dict] = None
        
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
            logger.info("OpenAI клиент настроен успешно")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при настройке OpenAI клиента: {e}")
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
        
        self.last_usage = None

        try:
            model_name = "gpt-4.1-mini-2025-04-14"
            messages = [
                {
                    "role": "system",
                    "content": EXPERT_DEFECT_ANALYSIS_PROMPT,
                },
                {
                    "role": "user",
                    "content": (
                        "Проанализируйте следующий объединенный текст из технического отчета и "
                        "найдите все дефекты:\n\n"
                        f"{combined_text}"
                    ),
                },
            ]

            completion = self.client.chat.completions.parse(
                model=model_name,
                messages=messages,
                response_format=DefectAnalysisListResult,
            )

            self.last_usage = log_chat_completion_usage(model_name, messages, completion, logger)

            result = completion.choices[0].message.parsed
            
            logger.info(f"Анализ завершен: найдено {len(result.defects)} дефектов")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при анализе текста через LLM: {e}")
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
                "Дефект": [r.get_defect_full_name() for r in analysis_results],
                "Наименование работы": [r.work_type for r in analysis_results]
            }
            
            # Создаем DataFrame
            df = pd.DataFrame(data)
            
            # Сохраняем в Excel с индексом начиная с 1
            df.to_excel(output_path, index=False, sheet_name="Анализ дефектов")
            
            logger.info(f"Excel отчет создан: {output_path} ({len(analysis_results)} записей)")
            return output_path
            
        except Exception as e:
            logger.error(f"Ошибка при создании Excel отчета: {e}")
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
            logger.info(f"Обработка завершена: найдено {len(result.defects)} дефектов")
            return result.defects
            
        except Exception as e:
            logger.error(f"Ошибка при обработке объединенного текста: {e}")
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
            
            logger.info(f"Анализ документа завершен: {excel_path}")
            return excel_path
            
        except Exception as e:
            logger.error(f"Ошибка при анализе документа: {e}")
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
        logger.info(f"Документ загружен: {document.filename}, страниц: {document.total_pages}")
        
        # Создаем анализатор и запускаем анализ
        analyzer = DefectAnalyzer()
        excel_path = await analyzer.analyze_document_defects(
            document=document,
            relevant_page_numbers=relevant_page_numbers,
            output_path=output_path
        )
        
        return excel_path
        
    except Exception as e:
        logger.error(f"Ошибка при анализе документа из JSON: {e}")
        raise


async def analyze_vlm_cleaned_pages_with_excel(vlm_result: VLMCleaningResult,
                                             output_path: str = None) -> str:
    """
    Анализ VLM-очищенных страниц с созданием Excel отчета
    
    Args:
        vlm_result: Результат VLM обработки страниц  
        output_path: Путь для Excel файла
        
    Returns:
        str: Путь к созданному Excel файлу
    """
    logger.info(f"Анализирую {vlm_result.processed_pages} VLM-очищенных страниц")
    
    try:
        # Извлекаем очищенные тексты из VLM результата
        page_texts = [page.cleaned_text for page in vlm_result.cleaned_pages]
        
        if not page_texts:
            raise ValueError("Нет VLM-очищенных страниц для анализа")
        
        # Создаем анализатор и обрабатываем очищенные тексты
        analyzer = DefectAnalyzer()
        analysis_results = await analyzer.process_combined_pages(page_texts)
        
        if not analysis_results:
            raise ValueError("Не удалось получить результаты анализа VLM-данных")
        
        # Создаем Excel отчет
        excel_path = analyzer.create_excel_report(analysis_results, output_path)
        
        logger.info(f"Анализ VLM-данных завершен: {excel_path}")
        return excel_path
        
    except Exception as e:
        logger.error(f"Ошибка при анализе VLM-данных: {e}")
        raise
