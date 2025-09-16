# Архитектура проекта

Telegram-бот для анализа дефектов строительных работ из PDF документов.

## Компоненты системы

### Основные модули

**main.py** - точка входа приложения
- Инициализация aiogram Bot и Dispatcher  
- Регистрация обработчиков сообщений
- Запуск polling loop

**config.py** - конфигурация и константы
- Переменные окружения (BOT_TOKEN, OPENAI_API_KEY)
- Пороги для семантического анализа и лимиты
- Настройка логирования

**models.py** - модели данных (Pydantic)
- TextElement - элемент текста
- PageData - данные страницы PDF  
- DocumentData - структура документа
- DefectAnalysisResult - результат анализа дефекта

### Обработчики (handlers/)

**start.py** - команда /start
- Отправка приветствия с основной клавиатурой

**documents.py** - основной пайплайн
- handle_upload_document() - инструкция пользователю
- handle_full_defect_analysis() - оркестратор всего процесса
- is_google_drive_link_message() - валидация ссылок

**common.py** - fallback обработчик

### Сервисы (services/)

**pipeline_runner.py** - оркестратор пайплайна
- DefectAnalysisPipeline - главный класс управления процессом
- Скачивание файлов из Google Drive
- Координация всех этапов обработки

**ocr_service.py** - извлечение текста
- process_pdf_ocr() - OCR через unstructured
- save_ocr_result() - сохранение в JSON/TXT

**semantic_page_filter.py** - поиск релевантных страниц
- SemanticPageFilter - семантический анализ через OpenAI embeddings
- Фильтрация страниц по релевантности к дефектам

**defect_analyzer.py** - анализ дефектов
- DefectAnalyzer - извлечение дефектов через OpenAI GPT
- Генерация Excel отчетов через pandas

**vlm_page_cleaner.py** - очистка текста
- VLMPageCleaner - улучшение качества текста через Vision LM

### Вспомогательные модули

**keyboards/** - интерфейсы Telegram
- main.py - основная клавиатура с кнопкой "Загрузить документ"

## Поток данных

```
1. Пользователь → Telegram → aiogram handlers
2. Google Drive ссылка → pipeline_runner → скачивание PDF
3. PDF → ocr_service → JSON структура документа
4. DocumentData → semantic_page_filter → список релевантных страниц
5. Релевантные страницы → vlm_page_cleaner → очищенный текст  
6. Очищенный текст → defect_analyzer → список дефектов
7. Список дефектов → Excel файл → отправка пользователю
```

## Взаимодействие между компонентами

**main.py** регистрирует обработчики из **handlers/**

**handlers/documents.py** использует **services/pipeline_runner.py** для координации

**pipeline_runner.py** последовательно вызывает:
- **ocr_service.py** для извлечения текста
- **semantic_page_filter.py** для поиска релевантных страниц  
- **vlm_page_cleaner.py** для очистки текста
- **defect_analyzer.py** для анализа и генерации отчета

Все сервисы используют **models.py** для передачи структурированных данных

**config.py** импортируется всеми модулями для получения настроек

## Зависимости

**Внешние API:**
- OpenAI API - для семантического анализа, VLM и извлечения дефектов
- Telegram Bot API - через aiogram

**Основные библиотеки:**
- aiogram - Telegram бот framework
- unstructured - OCR PDF документов
- pdf2image - конвертация PDF в изображения для VLM
- pandas - генерация Excel файлов
- pydantic - валидация данных
- semantic-router - семантическая маршрутизация

## Файловая система

**result/** - выходные файлы с результатами обработки
- OCR JSON/TXT файлы
- Excel отчеты с дефектами

**.env** - переменные окружения (не в репозитории)