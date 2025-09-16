# Анализ дефектов из PDF: Telegram‑бот с полным пайплайном

Бот принимает PDF с экспертизой/АПО или ссылку на файл, извлекает текст (OCR), находит релевантные страницы семантически, анализирует дефекты через LLM и возвращает Excel‑отчет.

## Что делает проект

- Принимает PDF или ссылку (Google Drive/Dropbox/Яндекс.Диск).
- OCR только текстовой части PDF без картинок/таблиц.
- Семантически находит страницы с описанием дефектов.
- LLM извлекает структурированные записи дефектов.
- Генерирует Excel с результатами и отправляет пользователю.

## Структура проекта

```
/
├── main.py                  # Точка входа, регистрация обработчиков
├── config.py                # Конфигурация, пороги и утилиты логирования
├── models.py                # Pydantic‑модели OCR и результатов анализа
├── handlers/                # Обработчики Telegram‑сообщений (aiogram)
│   ├── start.py             # /start и приветствие с клавиатурой
│   ├── documents.py         # Пайплайн: файл/URL → OCR → семантика → LLM → Excel
│   └── common.py            # Fallback‑ответы
├── services/                # Доменные сервисы пайплайна
│   ├── ocr_service.py       # OCR и сохранение результата
│   ├── semantic_page_filter.py   # Семантическая фильтрация страниц
│   └── defect_analyzer.py   # LLM‑анализ и Excel‑отчет
├── keyboards/               # Клавиатуры Telegram (основная кнопка)
├── result/                  # Выходные JSON/TXT/Excel
├── tests/                   # Скрипты проверки пайплайна и сервисов
├── requirements.txt         # Зависимости
└── .env                     # Секреты (BOT_TOKEN, OPENAI_API_KEY)
```

## Полный пайплайн: по шагам и по коду

1) Вход и маршрутизация (Telegram, aiogram)
- `main.py`
  - `dp.message.register(cmd_start, CommandStart())` — приветствие.
  - `dp.message.register(handle_upload_document, F.text == "Загрузить документ")` — показать инструкцию/варианты.
  - `defect_analysis_wrapper(message)` — обертка для полного анализа; регистрируется на `F.document` и на `F.text & is_url_message`.
  - `is_url_message(message)` — эвристика для ссылок Google Drive/Dropbox/Яндекс.Диск.

2) Загрузка файла и подготовка
- `handlers/documents.py`
  - `handle_full_defect_analysis(message, bot)` — оркестратор 4 этапов.
  - Если файл: `bot.get_file` → временный `.pdf`.
  - Если URL: `download_file_from_url(url)` → прямая ссылка через `get_direct_download_url` → временный `.pdf`.

3) OCR: извлечение текста и структурирование
- `services/ocr_service.py`
  - `process_pdf_ocr(pdf_path, original_filename)`
    - `unstructured.partition.pdf(..., strategy="hi_res", extract_image_block_to_payload=False, infer_table_structure=False, languages=["rus"])`.
    - Группировка элементов по страницам → `models.PageData`, `models.DocumentData`.
  - `save_ocr_result(document)` — сохраняет `result/ocr_result_<stem>.json` и `result/full_text_<stem>.txt`.

4) Семантическая фильтрация страниц
- `services/semantic_page_filter.py`
  - `SemanticPageFilter(utterances, score_threshold)` — инициализация порога; utterances берутся из `config.DEFECT_SEARCH_UTTERANCES`.
  - `setup_semantic_router()` — `OpenAIEncoder` + `SemanticRouter(Route(name="problems", ...))` (требуется `OPENAI_API_KEY`).
  - `analyze_document_pages(document)` — батч‑анализ страниц (по 5), собирает `PageAnalysisResult(page_number, route_name, similarity_score)`.
  - `filter_relevant_pages(results, top_limit)` — фильтр по порогу и топ‑N (по убыванию score).
  - `get_relevant_page_numbers(document, top_limit)` — основной метод; есть шорткат `analyze_document_from_json(json_path, utterances, score_threshold, top_limit)`.

5) LLM‑анализ дефектов и Excel
- `services/defect_analyzer.py`
  - `DefectAnalyzer._setup_openai_client()` — настраивает OpenAI SDK по `OPENAI_API_KEY`.
  - `analyze_combined_text(combined_text)` — Chat Completions с `response_format=DefectAnalysisListResult` (типизированный ответ), модель `gpt-4.1-mini-2025-04-14`.
  - `process_combined_pages(page_texts)` — объединяет выбранные страницы в единый текст.
  - `analyze_document_defects(document, relevant_page_numbers, output_path)` — полный прогон и `create_excel_report(...)` через pandas.
  - Шорткат: `analyze_document_from_json_with_excel(json_path, relevant_page_numbers, output_path)`.

6) Результат пользователю
- `handlers/documents.py`
  - После анализа отправляет Excel‑файл через `message.answer_document(...)` и краткую сводку.

## Модели данных (models.py)

- `TextElement { category: str, content: str, type: "text" }` — атом текста.
- `PageData { page_number: int, full_text: str, elements: List[TextElement], total_elements: int }` — страница.
- `DocumentData { filename: str, total_pages: int, pages: List[PageData] }` — документ; утилиты: `get_all_text()`, `get_elements_by_category(...)`.
- `DefectAnalysisResult { source_text, room, location, defect, work_type }` — запись дефекта (значения некоторых полей ограничены наборами, см. код).
- `DefectAnalysisListResult { defects: List[DefectAnalysisResult] }` — список дефектов (для типизированного ответа LLM).

## Конфигурация и важные пороги (config.py)

- `SEMANTIC_SCORE_THRESHOLD` — порог релевантности страницы (по умолчанию 0.5).
- `SEMANTIC_TOP_PAGES_LIMIT` — верхняя граница страниц к анализу (по умолчанию 10).
- `DEFECT_SEARCH_UTTERANCES` — примеры формулировок для маршрутизатора семантики.
- `DEFECT_ANALYSIS_SCORE_THRESHOLD` — порог для этапа поиска дефектов (обычно ниже базового; по умолчанию 0.4).
- `DEFECT_ANALYSIS_TOP_PAGES` — лимит страниц в анализ LLM (по умолчанию 8).
- Секреты: `BOT_TOKEN` (Telegram), `OPENAI_API_KEY` (семантика и LLM).

## Установка и запуск

1) Python и зависимости
- Рекомендуется Python 3.10+.
- Установка зависимостей: `pip install -r requirements.txt`.
- Для `unstructured[pdf]` могут потребоваться системные пакеты (OCR/рекомендации см. документацию Unstructured).

2) Переменные окружения (`.env`)
```
BOT_TOKEN=ваш_токен_бота_от_BotFather
OPENAI_API_KEY=ваш_openai_api_key
```

3) Запуск бота
```
python main.py
```

## Использование бота

- `/start` → появляется клавиатура с кнопкой `Загрузить документ`.
- Отправьте PDF (до ~20 МБ) или ссылку на файл (Google Drive/Dropbox/Я.Диск).
- Бот выполнит 4 этапа и пришлет Excel‑отчет.

## Выходные файлы (result/)

- `ocr_result_<stem>.json` — документ в структуре Pydantic.
- `full_text_<stem>.txt` — конкатенация текста по страницам.
- `defect_analysis_<timestamp>.xlsx` — итоговый отчет по дефектам.

## Нюансы и ограничения

- OCR извлекает только текст; изображения/таблицы не анализируются (`extract_image_block_to_payload=False`, `infer_table_structure=False`).
- Семантический фильтр и LLM требуют сети и валидного `OPENAI_API_KEY`.
- Обработка ссылок:
  - Google Drive: конвертация в прямую загрузку по `file_id`.
  - Dropbox: замена `dl=0` → `dl=1`.
  - Яндекс.Диск: прямая ссылка не нормализуется (нужен API), используется как есть.
- Семантический анализ выполняется батчами по 5 страниц с небольшой задержкой между батчами.
- Модель LLM указана как `gpt-4.1-mini-2025-04-14` (должна быть доступна в аккаунте OpenAI; при необходимости замените в коде).

## Карта функций: где что происходит

- Вход/роутинг: `main.py` → `defect_analysis_wrapper`, `is_url_message`.
- Инструкция: `handlers/start.py: cmd_start`, `keyboards/main.py: main_keyboard`.
- Оркестрация пайплайна: `handlers/documents.py: handle_full_defect_analysis`.
- Загрузка по URL: `handlers/documents.py: download_file_from_url`, `get_direct_download_url`.
- OCR: `services/ocr_service.py: process_pdf_ocr`, `save_ocr_result`.
- Семантика: `services/semantic_page_filter.py: SemanticPageFilter.setup_semantic_router`, `analyze_document_pages`, `filter_relevant_pages`, `get_relevant_page_numbers`, `analyze_document_from_json`.
- LLM и Excel: `services/defect_analyzer.py: DefectAnalyzer._setup_openai_client`, `analyze_combined_text`, `process_combined_pages`, `analyze_document_defects`, `create_excel_report`, `analyze_document_from_json_with_excel`.

## Тесты и локальная проверка

- Без сети можно проверить только OCR: `tests/test_ocr.py` (нужен тестовый PDF).
- Полный пайплайн с сетью: `tests/test_full_pipeline.py` — OCR → семантика → LLM → Excel.
- Дополнительно: `tests/test_semantic_page_filter.py`, `tests/test_defect_analyzer.py`.

При отсутствии сети/ключей тесты семантики/LLM завершаются ошибкой — это ожидаемо.

