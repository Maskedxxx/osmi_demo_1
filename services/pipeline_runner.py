"""Оркестрация полного пайплайна анализа дефектов для ссылок Google Drive."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import aiohttp

from config import (
    DEFECT_ANALYSIS_SCORE_THRESHOLD,
    DEFECT_ANALYSIS_TOP_PAGES,
    DEFECT_SEARCH_UTTERANCES,
    logger,
)
from models import DocumentData, VLMCleaningResult
from services.defect_analyzer import DefectAnalyzer
from services.ocr_service import process_pdf_ocr, save_ocr_result
from services.semantic_page_filter import analyze_document_from_json
from services.vlm_page_cleaner import VLMPageCleaner


class PipelineError(Exception):
    """Базовая ошибка пайплайна анализа дефектов."""


@dataclass
class DownloadMetadata:
    """Метаданные скачивания исходного PDF."""

    filename: str
    size_bytes: int
    local_path: Path
    duration: float


@dataclass
class OCRMetadata:
    """Результат OCR шага."""

    document: DocumentData
    json_path: Path
    txt_path: Path
    duration: float


@dataclass
class SemanticMetadata:
    """Итог семантического анализа релевантных страниц."""

    relevant_pages: List[int]
    duration: float


@dataclass
class VLMMetadata:
    """Итог Vision шага."""

    processed_pages: int
    duration: float


@dataclass
class AnalysisMetadata:
    """Результат финального анализа и формирования отчета."""

    excel_path: Path
    duration: float
    llm_usage: Optional[Dict[str, Optional[float]]]


def extract_google_drive_file_id(url: str) -> Optional[str]:
    """Извлекает идентификатор файла из ссылки Google Drive."""
    if not url:
        return None

    parsed = urlparse(url.strip())
    if "drive.google." not in parsed.netloc:
        return None

    path_parts = [part for part in parsed.path.split("/") if part]

    # Ссылки вида /file/d/<file_id>/...
    if len(path_parts) >= 3 and path_parts[0] == "file" and path_parts[1] == "d":
        return path_parts[2]

    # Ссылки вида /uc или /open, ID в query параметрах
    query_params = parse_qs(parsed.query)
    if "id" in query_params and query_params["id"]:
        return query_params["id"][0]

    # Прямые ссылки вида ...?export=download&id=<id>
    if "export" in query_params and "download" in query_params.get("export", []):
        if "id" in query_params and query_params["id"]:
            return query_params["id"][0]

    return None


def build_direct_download_url(file_id: str) -> str:
    """Формирует ссылку для прямого скачивания PDF из Google Drive."""
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def ensure_pipeline_directory() -> Path:
    """Создает уникальную директорию для артефактов пайплайна."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pipeline_dir = Path("result") / timestamp
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    return pipeline_dir


def safe_filename(filename: str, default: str) -> str:
    """Приводит имя файла к безопасному формату без спецсимволов."""
    name = filename.strip() if filename else default
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    sanitized = "".join(ch for ch in name if ch.isalnum() or ch in {"_", "-", "."})
    return sanitized or f"{default}.pdf"


def format_size(size_bytes: int) -> str:
    """Возвращает размер файла в человекочитаемом формате."""
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    kilobytes = size_bytes / 1024
    if kilobytes < 1024:
        return f"{kilobytes:.1f} КБ"
    megabytes = kilobytes / 1024
    return f"{megabytes:.2f} МБ"


class DefectAnalysisPipeline:
    """Оркестратор шагов анализа дефектов."""

    def __init__(self, source_url: str):
        self.source_url = source_url.strip()
        self.pipeline_dir = ensure_pipeline_directory()
        self.started_at = time.perf_counter()

        self.file_id: Optional[str] = None
        self.pdf_path: Optional[Path] = None
        self.download_info: Optional[DownloadMetadata] = None
        self.ocr_info: Optional[OCRMetadata] = None
        self.semantic_info: Optional[SemanticMetadata] = None
        self.vlm_info: Optional[VLMMetadata] = None
        self.analysis_info: Optional[AnalysisMetadata] = None
        self._vlm_result: Optional[VLMCleaningResult] = None

    async def download_document(self) -> DownloadMetadata:
        """Скачивает PDF из Google Drive и сохраняет его в папку пайплайна."""
        file_id = extract_google_drive_file_id(self.source_url)
        if not file_id:
            raise PipelineError("Не удалось определить идентификатор файла Google Drive.")

        direct_url = build_direct_download_url(file_id)
        start = time.perf_counter()

        async with aiohttp.ClientSession() as session:
            async with session.get(direct_url) as response:
                if response.status != 200:
                    raise PipelineError(f"Ошибка загрузки файла: HTTP {response.status}")

                disposition = response.headers.get("Content-Disposition", "")
                extracted = None
                if "filename*=" in disposition:
                    extracted = disposition.split("filename*=")[-1].split(";")[0]
                    if "''" in extracted:
                        extracted = extracted.split("''", maxsplit=1)[-1]
                    extracted = extracted.strip('"')
                if not extracted and "filename=" in disposition:
                    extracted = disposition.split("filename=")[-1].split(";")[0].strip('"')
                if not extracted:
                    extracted = f"document_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                local_filename = safe_filename(extracted, f"document_{file_id}")
                local_path = self.pipeline_dir / local_filename

                with open(local_path, "wb") as file_out:
                    async for chunk in response.content.iter_chunked(65536):
                        file_out.write(chunk)

        duration = time.perf_counter() - start
        size_bytes = os.path.getsize(local_path)

        self.file_id = file_id
        self.pdf_path = local_path

        metadata = DownloadMetadata(
            filename=local_filename,
            size_bytes=size_bytes,
            local_path=local_path,
            duration=duration,
        )
        self.download_info = metadata

        logger.info(
            "PDF скачан: %s (%.2f МБ) за %.2f с", local_filename, size_bytes / (1024 * 1024), duration
        )
        return metadata

    async def run_ocr(self) -> OCRMetadata:
        """Выполняет OCR обработку и сохраняет результаты."""
        if not self.pdf_path:
            raise PipelineError("PDF файл не найден для OCR.")

        start = time.perf_counter()
        document, processing_time = await process_pdf_ocr(str(self.pdf_path), self.pdf_path.name)
        json_path, txt_path = await save_ocr_result(document, result_folder=str(self.pipeline_dir))
        duration = time.perf_counter() - start

        metadata = OCRMetadata(
            document=document,
            json_path=Path(json_path),
            txt_path=Path(txt_path),
            duration=max(processing_time, duration),
        )
        self.ocr_info = metadata

        logger.info(
            "OCR завершен: %s страниц, %.2f с", document.total_pages, metadata.duration
        )
        return metadata

    async def run_semantic_analysis(self) -> SemanticMetadata:
        """Определяет релевантные страницы документа."""
        if not self.ocr_info:
            raise PipelineError("Нет данных OCR для семантического анализа.")

        start = time.perf_counter()
        relevant_pages = await analyze_document_from_json(
            json_path=str(self.ocr_info.json_path),
            utterances=DEFECT_SEARCH_UTTERANCES,
            score_threshold=DEFECT_ANALYSIS_SCORE_THRESHOLD,
            top_limit=DEFECT_ANALYSIS_TOP_PAGES,
        )
        duration = time.perf_counter() - start

        sorted_unique = sorted(set(relevant_pages))
        metadata = SemanticMetadata(relevant_pages=sorted_unique, duration=duration)
        self.semantic_info = metadata

        logger.info("Релевантные страницы: %s", sorted_unique)
        return metadata

    async def run_vlm_cleaning(self) -> VLMMetadata:
        """Очищает релевантные страницы через VLM."""
        if not self.semantic_info or not self.semantic_info.relevant_pages:
            raise PipelineError("Нет релевантных страниц для Vision-обработки.")
        if not self.pdf_path:
            raise PipelineError("PDF файл отсутствует для Vision-обработки.")

        start = time.perf_counter()
        vlm_cleaner = VLMPageCleaner()
        vlm_result = await asyncio.to_thread(
            vlm_cleaner.process_pages,
            Path(self.pdf_path),
            self.semantic_info.relevant_pages,
        )
        duration = time.perf_counter() - start

        self.vlm_info = VLMMetadata(processed_pages=vlm_result.processed_pages, duration=duration)
        self._vlm_result = vlm_result

        logger.info("VLM обработал %s страниц за %.2f с", vlm_result.processed_pages, duration)
        return self.vlm_info

    async def run_analysis_and_report(self) -> AnalysisMetadata:
        """Создает Excel отчет на основе очищенного текста."""
        if not hasattr(self, "_vlm_result"):
            raise PipelineError("Нет данных VLM для финального анализа.")

        vlm_result = self._vlm_result
        if not vlm_result.cleaned_pages:
            raise PipelineError("VLM не вернул очищенные страницы.")

        analyzer = DefectAnalyzer()
        start = time.perf_counter()
        page_texts = [page.cleaned_text for page in vlm_result.cleaned_pages]
        analysis_results = await analyzer.process_combined_pages(page_texts)

        excel_name = f"defect_analysis_{datetime.now().strftime('%H%M%S')}.xlsx"
        excel_path = self.pipeline_dir / excel_name
        excel_path_str = await asyncio.to_thread(
            analyzer.create_excel_report,
            analysis_results,
            str(excel_path),
        )
        duration = time.perf_counter() - start

        usage = getattr(analyzer, "last_usage", None)
        metadata = AnalysisMetadata(excel_path=Path(excel_path_str), duration=duration, llm_usage=usage)
        self.analysis_info = metadata

        logger.info("Excel отчет создан: %s", excel_path_str)
        return metadata

    def total_duration(self) -> float:
        """Возвращает общее время выполнения пайплайна."""
        return time.perf_counter() - self.started_at
