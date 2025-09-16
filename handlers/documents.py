"""Хендлеры работы с документами и запуск пайплайна анализа дефектов."""

from __future__ import annotations

from aiogram import Bot, types

from config import logger
from services.pipeline_runner import (
    DefectAnalysisPipeline,
    PipelineError,
    extract_google_drive_file_id,
    format_size,
)


async def handle_upload_document(message: types.Message) -> None:
    """Отвечает на нажатие кнопки «Загрузить документ» лаконичной инструкцией."""
    await message.answer(
        "Отправьте ссылку на PDF из Google Drive.\n\n"
        "Пайплайн включает 4 шага:"
        "\n1️⃣ OCR (~4-5 минут)"
        "\n2️⃣ Семантический анализ (~30 секунд)"
        "\n3️⃣ Очистка через Vision LM (~1-2 минуты)"
        "\n4️⃣ Таблица с параметрами дефектов (~1 минута)"
        "\n\nПросто пришлите ссылку, как будете готовы."
    )


def is_google_drive_link_message(message: types.Message) -> bool:
    """Проверяет, что сообщение содержит ссылку Google Drive с идентификатором файла."""
    text = (message.text or "").strip()
    return bool(extract_google_drive_file_id(text))


def format_cost(usage: dict | None) -> str:
    """Форматирует стоимость LLM-запроса для ответа пользователю."""
    if not usage:
        return "н/д"
    cost = usage.get("cost_usd")
    if cost is None:
        return "н/д"
    return f"${cost:.4f}"


async def handle_full_defect_analysis(message: types.Message, _bot: Bot) -> None:
    """Оркестрирует последовательный запуск всех шагов пайплайна."""
    link = (message.text or "").strip()
    if not extract_google_drive_file_id(link):
        await message.answer(
            "Не удалось распознать ссылку Google Drive. Проверьте, что отправляете ссылку вида "
            "https://drive.google.com/file/d/<ID>/view и повторите попытку."
        )
        return

    pipeline = DefectAnalysisPipeline(link)

    await message.answer("☁️ Принял ссылку, начинаю загрузку документа...")

    try:
        download_meta = await pipeline.download_document()
        await message.answer(
            "✅ Документ загружен успешно.\n"
            f"📄 Имя: {download_meta.filename}\n"
            f"📦 Размер: {format_size(download_meta.size_bytes)}\n"
            f"🗂️ Папка результатов: {pipeline.pipeline_dir.name}"
        )

        await message.answer(
            "🚀 Шаг 1/4: OCR документа. Это займёт около 4-5 минут, пожалуйста подождите."
        )
        ocr_meta = await pipeline.run_ocr()
        await message.answer(
            "✅ Шаг 1 завершён.\n"
            f"📖 Страниц обработано: {ocr_meta.document.total_pages}\n"
            f"⏱️ Время шага: {ocr_meta.duration:.1f} сек\n"
            "Переходим к шагу 2."
        )

        await message.answer(
            "🎯 Шаг 2/4: Семантический анализ релевантных страниц (~30 секунд)."
        )
        semantic_meta = await pipeline.run_semantic_analysis()
        if not semantic_meta.relevant_pages:
            await message.answer(
                "⚠️ Семантический анализ не обнаружил релевантных страниц с описанием дефектов."
                " Пайплайн остановлен."
            )
            return

        pages_str = ", ".join(str(page) for page in semantic_meta.relevant_pages)
        await message.answer(
            "✅ Шаг 2 завершён.\n"
            f"📑 Релевантных страниц: {len(semantic_meta.relevant_pages)}\n"
            f"🗂️ Номера страниц: {pages_str}\n"
            "Переходим к шагу 3."
        )

        await message.answer(
            "🧹 Шаг 3/4: Приведение текста через Vision LM (~1-2 минуты)."
        )
        vlm_meta = await pipeline.run_vlm_cleaning()
        await message.answer(
            "✅ Шаг 3 завершён.\n"
            f"🧾 Страниц очищено: {vlm_meta.processed_pages}\n"
            f"⏱️ Время шага: {vlm_meta.duration:.1f} сек\n"
            "Переходим к шагу 4."
        )

        await message.answer(
            "📊 Шаг 4/4: Формируем таблицу с параметрами дефектов (~1 минута)."
        )
        analysis_meta = await pipeline.run_analysis_and_report()

        await message.answer(
            "✅ Шаг 4 завершён. Отправляю Excel с результатами и сводку по пайплайну."
        )

        total_duration = pipeline.total_duration()
        cost_text = format_cost(analysis_meta.llm_usage)
        relevant_pages = ", ".join(str(page) for page in semantic_meta.relevant_pages)

        with open(analysis_meta.excel_path, "rb") as excel_file:
            excel_document = types.BufferedInputFile(
                excel_file.read(),
                filename=analysis_meta.excel_path.name,
            )
            await message.answer_document(
                excel_document,
                caption=(
                    "✅ Анализ дефектов завершён!\n\n"
                    f"📄 Документ: {ocr_meta.document.filename}\n"
                    f"📖 Страниц OCR: {ocr_meta.document.total_pages}\n"
                    f"🎯 Релевантные страницы: {relevant_pages}\n"
                    f"⏱️ Время пайплайна: {total_duration:.1f} сек\n"
                    f"💰 Стоимость LLM шага: {cost_text}\n"
                    f"🗂️ Папка результатов: {pipeline.pipeline_dir.name}"
                ),
            )

    except PipelineError as error:
        logger.warning("Пайплайн остановлен: %s", error)
        await message.answer(f"❌ {error}")
    except Exception as error:  # noqa: BLE001
        logger.exception("Неожиданная ошибка пайплайна", exc_info=error)
        await message.answer(
            "❌ Произошла непредвиденная ошибка при обработке документа. Попробуйте позже."
        )
