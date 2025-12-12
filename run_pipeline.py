import asyncio
import sys
from pathlib import Path
from services.pipeline_runner import DefectAnalysisPipeline

# === НАСТРОЙКИ ===
# Если файл лежит в корне, просто укажите его имя
DEFAULT_PDF_NAME = "/Users/mask/Downloads/1037 от 30.03.2023_экспертиза_смета.pdf"
# =================

async def run_local_pipeline(filename: str):
    # Ищем файл
    input_path = Path(filename).resolve()
    if not input_path.exists():
        # Попробуем поискать в папке data/
        input_path = Path("data") / filename
    
    if not input_path.exists():
        print(f"❌ Файл не найден: {filename}")
        print("Убедитесь, что файл лежит в корне проекта или в папке data/")
        return

    print(f"🚀 ЗАПУСК ПАЙПЛАЙНА для: {input_path.name}")
    
    # Инициализация с фейковой ссылкой (она не нужна для локального запуска)
    pipeline = DefectAnalysisPipeline("http://localhost/dummy")
    pipeline.pdf_path = input_path # ПОДМЕНА: используем локальный файл
    
    try:
        # 1. OCR
        print("\n🔹 ШАГ 1: OCR (Распознавание текста)...")
        ocr_meta = await pipeline.run_ocr()
        print(f"   ✅ OCR готов. Страниц: {ocr_meta.document.total_pages}, Время: {ocr_meta.duration:.1f}с")

        # 2. Семантический фильтр
        print("\n🔹 ШАГ 2: Семантический фильтр...")
        semantic_meta = await pipeline.run_semantic_analysis()
        if not semantic_meta.relevant_pages:
            print("   ⚠️ Нет страниц с дефектами (ни одна не прошла порог). Пайплайн остановлен.")
            return
        print(f"   ✅ Найдено страниц: {len(semantic_meta.relevant_pages)} {semantic_meta.relevant_pages}")

        # 3. Очистка VLM
        print("\n🔹 ШАГ 3: Очистка текста (GPT Vision)...")
        vlm_meta = await pipeline.run_vlm_cleaning()
        print(f"   ✅ Очищено страниц: {vlm_meta.processed_pages}, Время: {vlm_meta.duration:.1f}с")

        # 4. Анализ и отчет
        print("\n🔹 ШАГ 4: Анализ и Excel...")
        analysis_meta = await pipeline.run_analysis_and_report()
        print(f"\n🎉 ГОТОВО! Отчет создан:\n   📂 {analysis_meta.excel_path}")
        
        if analysis_meta.llm_usage:
             print(f"   💰 Стоимость: ${analysis_meta.llm_usage.get('cost_usd', 0):.4f}")

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        # import traceback
        # traceback.print_exc()

if __name__ == "__main__":
    # Можно передать имя файла аргументом: python run_pipeline.py my_doc.pdf
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PDF_NAME
    asyncio.run(run_local_pipeline(target))