# Карта проекта OSMI Demo 1-1

## Назначение проекта

Автоматизированная система анализа PDF-документов с экспертизами строительных работ. Извлекает текст, находит дефекты через AI и генерирует Excel-отчеты.

---

## Режимы работы

### 1. Telegram версия (`main.py`)
**Интерактивная обработка через бота**

```
Пользователь → Telegram бот → Получает Excel отчет
```

**Основные обработчики:**
- `/start` → Приветствие и инструкции
- `"Загрузить документ"` → Инструкции по загрузке
- **Google Drive ссылка** → Запуск полного анализа

**Процесс:**
1. Отправка ссылки на Google Drive
2. Скачивание PDF
3. Запуск 4-этапного пайплайна
4. Отправка Excel файла пользователю

**Файлы:**
- `main.py` → Инициализация бота
- `handlers/start.py` → Команда /start
- `handlers/documents.py` → Основная логика обработки
- `handlers/common.py` → Fallback обработчик

---

### 2. Batch версия (`batch_runner.py`)
**Автоматическая пакетная обработка**

```
data/input/*.pdf → Batch процессор → result/<timestamp>/*.xlsx
```

**Логика:**
- Сканирует папку `data/input/`
- Проверяет уже обработанные файлы
- Обрабатывает только новые PDF
- Выводит статистику (SUCCESS/ERROR/SKIPPED/ALREADY_DONE)

**Время обработки одного документа:** ~7-9 минут

**Этапы:**
1. OCR (~4-5 мин) — распознавание текста
2. Semantic filter (~30 сек) — отбор страниц с дефектами
3. VLM cleaning (~1-2 мин) — очистка текста через GPT Vision
4. Analysis (~1 мин) — генерация Excel отчета

---

### 3. Локальный запуск (`run_pipeline.py`)
**Тестирование отдельного PDF файла**

Для отладки и тестирования пайплайна на конкретном документе.

---

## Архитектура пайплайна

### Основной процесс (4 этапа)

```
PDF документ
    ↓
[1] OCR (unstructured)
    → DocumentData (текст + структура)
    ↓
[2] Semantic Filtering (semantic-router + OpenAI embeddings)
    → Отбор страниц с дефектами (порог 0.5)
    ↓
[3] VLM Cleaning (GPT-4 Vision)
    → Очистка и структурирование текста
    ↓
[4] Defect Analysis (OpenAI GPT-4)
    → Excel отчет с дефектами
```

---

## Основные сервисы (`services/`)

| Сервис | Назначение |
|--------|-----------|
| **pipeline_runner.py** | Оркестратор всех этапов. Класс `DefectAnalysisPipeline` |
| **ocr_service.py** | Распознавание текста (unstructured, hi_res, русский язык) |
| **semantic_page_filter.py** | Семантический анализ через embeddings. Отбор релевантных страниц |
| **vlm_page_cleaner.py** | Vision Language Model (GPT-4 Vision) для очистки текста |
| **defect_analyzer.py** | LLM-анализ. Извлечение структурированных дефектов |
| **llm_usage_tracker.py** | Подсчет токенов и стоимости LLM-запросов |

---

## Модели данных (`models.py`)

### Основные структуры

```python
TextElement          # Текстовый элемент (категория + содержимое)
PageData            # Страница документа (номер + элементы)
DocumentData        # Весь документ (файл + все страницы)

# Результаты анализа
DefectAnalysisResult        # Один дефект (помещение, локация, тип работ, ключ)
DefectAnalysisListResult    # Список всех найденных дефектов
CleanedPageData             # Очищенная страница
VLMCleaningResult          # Результат VLM обработки
```

### Enum для дефектов

`DefectKey` — **70+ ключей дефектов:**
- floor_tile_cracks
- window_trim_gaps
- plumbing_leaks
- и другие...

Маппинг на полные названия в `data/defect_mapping.py`

---

## Конфигурация (`config.py`)

### Токены и API
```python
API_TOKEN           # Telegram бот (из .env)
OPENAI_API_KEY      # OpenAI ключ (из .env)
```

### Параметры анализа
```python
SEMANTIC_SCORE_THRESHOLD = 0.5      # Порог схожести для отбора страниц
SEMANTIC_TOP_PAGES_LIMIT = 10        # Макс страниц для анализа
VLM_MODEL = "gpt-4.1-mini"          # Vision модель
```

### Утверанцы для поиска дефектов
`DEFECT_SEARCH_UTTERANCES` — 20+ примеров текстов про дефекты (трещины, протечки, нарушения и т.д.)

---

## Структура папок

```
osmi_demo_1-1/
├── data/
│   ├── input/                  # PDF для batch обработки
│   └── defect_mapping.py       # Справочник дефектов (70+)
│
├── result/                     # Результаты обработки
│   └── <timestamp>/
│       ├── full_text_*.txt     # OCR текст
│       ├── full_text_cleaned.json
│       └── *.xlsx              # Excel отчеты
│
├── services/                   # Основные сервисы
├── handlers/                   # Telegram обработчики
├── prompts/                    # System prompts для LLM
├── tests/                      # Тесты
│
├── main.py                     # Telegram бот
├── batch_runner.py             # Batch обработчик
├── run_pipeline.py             # Локальный запуск
├── config.py                   # Конфигурация
└── models.py                   # Модели данных
```

---

## Основные технологии

| Технология | Назначение |
|-----------|-----------|
| **aiogram 3.22.0** | Telegram бот (async API) |
| **unstructured[pdf]** | OCR (pytesseract/layoutparser) |
| **semantic-router** | Семантическое маршрутизирование (embeddings) |
| **openai** | OpenAI API (GPT-4, Vision) |
| **pdf2image** | Конвертация PDF в изображения |
| **tiktoken** | Подсчет токенов для LLM |
| **aiohttp** | Асинхронные HTTP запросы |

---

## Логирование и ошибки

- Используется стандартный `logging` (не print)
- Все ошибки логируются с контекстом
- Telegram: понятные сообщения пользователю
- Batch: статистика по каждому файлу

---

## Ключевые файлы для изучения

**Порядок чтения кода:**

1. `config.py` — конфигурация и параметры
2. `models.py` — структуры данных
3. `services/pipeline_runner.py` — оркестрация пайплайна
4. `handlers/documents.py` — Telegram логика
5. `batch_runner.py` — batch обработка
6. Отдельные сервисы по необходимости

---

## Время обработки

**Один документ: ~7-9 минут**

- OCR: ~4-5 мин
- Semantic filter: ~30 сек
- VLM cleaning: ~1-2 мин
- Analysis + Excel: ~1 мин

---

## Итого

Проект имеет **четкую архитектуру** с разделением ответственности:
- ✅ Модели → структурирование данных
- ✅ Сервисы → реализация функционала
- ✅ Handlers → интеграция с Telegram
- ✅ Config → все настройки централизованно
- ✅ Асинхронная обработка (asyncio)
- ✅ Современные LLM API (OpenAI GPT-4 + Vision)
