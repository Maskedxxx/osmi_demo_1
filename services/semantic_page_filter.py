"""
Сервис для семантического анализа и фильтрации страниц документов
"""

import os
import json
from typing import List
from dataclasses import dataclass

from semantic_router import Route
from semantic_router.encoders import OpenAIEncoder
from semantic_router.routers import SemanticRouter

from models import DocumentData
from config import logger, OPENAI_API_KEY, SEMANTIC_SCORE_THRESHOLD, SEMANTIC_TOP_PAGES_LIMIT


@dataclass
class PageAnalysisResult:
    """Результат анализа страницы"""
    page_number: int
    route_name: str
    similarity_score: float


class SemanticPageFilter:
    """Класс для семантического анализа и фильтрации страниц документов"""
    
    def __init__(self, utterances: List[str], score_threshold: float = None):
        """
        Инициализация фильтра
        
        Args:
            utterances: Список примеров текстов для обучения роутера
            score_threshold: Порог схожести для отбора релевантных страниц
        """
        self.utterances = utterances
        self.score_threshold = score_threshold or SEMANTIC_SCORE_THRESHOLD
        self.router = None
        
    async def setup_semantic_router(self) -> bool:
        """
        Настройка семантического роутера
        
        Returns:
            bool: True если роутер успешно настроен
        """
        try:
            logger.info("Настраиваю семантический роутер для анализа страниц")
            
            # Проверяем наличие OpenAI API ключа
            if not OPENAI_API_KEY:
                logger.error("OPENAI_API_KEY не найден в переменных окружения")
                return False
                
            # Устанавливаем переменную окружения для semantic-router
            os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
            
            # Создаем маршрут для проблем
            problems_route = Route(
                name="problems",
                score_threshold=self.score_threshold,
                utterances=self.utterances
            )
            
            # Инициализируем энкодер и роутер
            encoder = OpenAIEncoder()
            self.router = SemanticRouter(
                encoder=encoder, 
                routes=[problems_route], 
                auto_sync="local"
            )
            
            logger.info(f"✅ Семантический роутер настроен с порогом схожести: {self.score_threshold}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка при настройке семантического роутера: {e}")
            return False
    
    async def analyze_document_pages(self, document: DocumentData) -> List[PageAnalysisResult]:
        """
        Анализ всех страниц документа через семантический роутер с батчевой обработкой
        
        Args:
            document: Данные документа для анализа
            
        Returns:
            List[PageAnalysisResult]: Результаты анализа каждой страницы
        """
        if not self.router:
            raise ValueError("Семантический роутер не настроен. Вызовите setup_semantic_router() сначала")
            
        logger.info(f"Начинаю семантический анализ документа: {document.filename}")
        results = []
        
        try:
            # Обрабатываем страницы батчами по 5 штук
            batch_size = 5
            pages = document.pages
            
            for i in range(0, len(pages), batch_size):
                batch_pages = pages[i:i + batch_size]
                logger.info(f"Обрабатываю батч страниц {i+1}-{min(i+batch_size, len(pages))} из {len(pages)}")
                
                # Анализируем каждую страницу в батче
                batch_results = []
                for page in batch_pages:
                    logger.info(f"Анализирую страницу {page.page_number}")
                    
                    # Проверяем на пустой текст
                    if not page.full_text or not page.full_text.strip():
                        logger.warning(f"Страница {page.page_number} пуста, пропускаю")
                        continue
                    
                    # Анализируем текст страницы
                    router_result = self.router(page.full_text, limit=1)
                    
                    # Обрабатываем результат
                    if isinstance(router_result, list) and len(router_result) > 0:
                        similarity = router_result[0].similarity_score or 0.0
                        route_name = router_result[0].name
                    elif hasattr(router_result, 'similarity_score'):
                        similarity = router_result.similarity_score or 0.0
                        route_name = router_result.name if hasattr(router_result, 'name') else 'unknown'
                    else:
                        similarity = 0.0
                        route_name = 'unknown'
                    
                    # Создаем результат анализа
                    analysis_result = PageAnalysisResult(
                        page_number=page.page_number,
                        route_name=route_name,
                        similarity_score=similarity
                    )
                    batch_results.append(analysis_result)
                    
                    logger.info(f"Страница {page.page_number}: маршрут '{route_name}', оценка {similarity:.4f}")
                
                # Добавляем результаты батча к общим результатам
                results.extend(batch_results)
                
                # Небольшая задержка между батчами для контроля нагрузки на API
                if i + batch_size < len(pages):
                    import asyncio
                    await asyncio.sleep(0.1)
            
            logger.info(f"✅ Завершен анализ документа, обработано страниц: {len(results)}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Ошибка при анализе документа: {e}")
            raise
    
    def filter_relevant_pages(self, analysis_results: List[PageAnalysisResult], 
                            top_limit: int = None) -> List[int]:
        """
        Фильтрация и сортировка релевантных страниц
        
        Args:
            analysis_results: Результаты анализа страниц
            top_limit: Максимальное количество страниц для возврата
            
        Returns:
            List[int]: Отсортированный список номеров релевантных страниц
        """
        limit = top_limit or SEMANTIC_TOP_PAGES_LIMIT
        
        # Фильтруем по порогу схожести и убираем None значения
        relevant_pages = [
            result for result in analysis_results 
            if result.similarity_score is not None and result.similarity_score >= self.score_threshold
        ]
        
        # Сортируем по убыванию схожести
        relevant_pages.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # Ограничиваем количество
        relevant_pages = relevant_pages[:limit]
        
        # Возвращаем только номера страниц
        page_numbers = [page.page_number for page in relevant_pages]
        
        logger.info(f"Найдено релевантных страниц: {len(page_numbers)}")
        logger.info(f"Номера страниц: {page_numbers}")
        
        return page_numbers
    
    async def get_relevant_page_numbers(self, document: DocumentData, 
                                      top_limit: int = None) -> List[int]:
        """
        Главная функция для получения номеров релевантных страниц
        
        Args:
            document: Данные документа
            top_limit: Максимальное количество страниц для возврата
            
        Returns:
            List[int]: Отсортированный список номеров релевантных страниц
        """
        logger.info(f"Получение релевантных страниц для документа: {document.filename}")
        
        try:
            # Настраиваем роутер если он не настроен
            if not self.router:
                setup_success = await self.setup_semantic_router()
                if not setup_success:
                    raise ValueError("Не удалось настроить семантический роутер")
            
            # Анализируем страницы документа
            analysis_results = await self.analyze_document_pages(document)
            
            # Фильтруем и сортируем релевантные страницы
            relevant_page_numbers = self.filter_relevant_pages(analysis_results, top_limit)
            
            logger.info(f"✅ Успешно получены релевантные страницы: {relevant_page_numbers}")
            return relevant_page_numbers
            
        except Exception as e:
            logger.error(f"❌ Ошибка при получении релевантных страниц: {e}")
            raise


async def load_document_from_json(json_path: str) -> DocumentData:
    """
    Загрузка документа из JSON файла
    
    Args:
        json_path: Путь к JSON файлу с данными документа
        
    Returns:
        DocumentData: Загруженные данные документа
    """
    logger.info(f"Загружаю документ из JSON: {json_path}")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        document = DocumentData(**data)
        logger.info(f"✅ Документ загружен: {document.filename}, страниц: {document.total_pages}")
        return document
        
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке документа из JSON: {e}")
        raise


async def analyze_document_from_json(json_path: str, utterances: List[str], 
                                   score_threshold: float = None, 
                                   top_limit: int = None) -> List[int]:
    """
    Удобная функция для анализа документа из JSON файла
    
    Args:
        json_path: Путь к JSON файлу с данными документа
        utterances: Список примеров текстов для обучения роутера
        score_threshold: Порог схожести
        top_limit: Максимальное количество страниц
        
    Returns:
        List[int]: Номера релевантных страниц
    """
    # Загружаем документ
    document = await load_document_from_json(json_path)
    
    # Создаем фильтр и анализируем
    page_filter = SemanticPageFilter(utterances, score_threshold)
    relevant_pages = await page_filter.get_relevant_page_numbers(document, top_limit)
    
    return relevant_pages