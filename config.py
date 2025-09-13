import logging
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Настройки для семантического анализа страниц
SEMANTIC_SCORE_THRESHOLD = 0.5  # Минимальный порог схожести для отбора страниц
SEMANTIC_TOP_PAGES_LIMIT = 10   # Максимальное количество страниц для анализа

# Настройка базового логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Создаем логгер для бота
logger = logging.getLogger(__name__)