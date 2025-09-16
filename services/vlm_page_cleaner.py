import base64
import logging
from io import BytesIO
from pathlib import Path
from typing import List

from pdf2image import convert_from_path
from openai import OpenAI

from config import OPENAI_API_KEY, VLM_MODEL, VLM_CLEAN_PROMPT
from models import CleanedPageData, VLMCleaningResult

logger = logging.getLogger(__name__)


class VLMPageCleaner:
    """Сервис для очистки и структурирования страниц PDF через Vision Language Model."""
    
    def __init__(self, openai_api_key: str = OPENAI_API_KEY):
        self.client = OpenAI(api_key=openai_api_key)
        self.model = VLM_MODEL
        self.clean_prompt_template = VLM_CLEAN_PROMPT
    
    def convert_pdf_page_to_image(self, pdf_path: Path, page_number: int) -> str:
        """Конвертирует страницу PDF в base64 изображение."""
        try:
            images = convert_from_path(
                str(pdf_path),
                first_page=page_number,
                last_page=page_number,
                fmt="png"
            )
            
            if not images:
                raise RuntimeError(f"Не удалось получить страницу {page_number}")
            
            buffer = BytesIO()
            images[0].save(buffer, format="PNG")
            image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            
            logger.info(f"Страница {page_number} конвертирована в изображение")
            return image_base64
            
        except Exception as e:
            logger.error(f"Ошибка конвертации страницы {page_number}: {e}")
            raise
    
    def clean_page_with_vlm(self, image_base64: str, page_number: int) -> str:
        """Отправляет изображение страницы в VLM для очистки текста."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"{self.clean_prompt_template}\nСтраница: {page_number}."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                    ],
                }],
            )
            
            cleaned_text = response.choices[0].message.content.strip()
            logger.info(f"Страница {page_number} обработана VLM")
            return cleaned_text
            
        except Exception as e:
            logger.error(f"Ошибка VLM обработки страницы {page_number}: {e}")
            raise
    
    def process_pages(self, pdf_path: Path, page_numbers: List[int]) -> VLMCleaningResult:
        """Обрабатывает список страниц PDF через VLM."""
        if not page_numbers:
            raise ValueError("Не переданы номера страниц для VLM обработки")

        ordered_page_numbers = sorted(set(page_numbers))
        logger.info(
            "Начинаю VLM обработку %d страниц (исходно: %d) -> %s",
            len(ordered_page_numbers),
            len(page_numbers),
            ordered_page_numbers,
        )

        cleaned_pages = []

        for page_num in ordered_page_numbers:
            try:
                # Конвертируем страницу в изображение
                image_base64 = self.convert_pdf_page_to_image(pdf_path, page_num)
                
                # Обрабатываем через VLM
                cleaned_text = self.clean_page_with_vlm(image_base64, page_num)
                
                # Создаем объект очищенной страницы
                cleaned_page = CleanedPageData(
                    page_number=page_num,
                    cleaned_text=cleaned_text
                )
                cleaned_pages.append(cleaned_page)
                
                logger.info(f"Страница {page_num} успешно обработана")
                
            except Exception as e:
                logger.error(f"Ошибка обработки страницы {page_num}: {e}")
                raise
        
        result = VLMCleaningResult(
            source_pdf=str(pdf_path),
            processed_pages=len(cleaned_pages),
            cleaned_pages=cleaned_pages
        )

        logger.info(f"VLM обработка завершена: {len(cleaned_pages)} страниц")
        return result
