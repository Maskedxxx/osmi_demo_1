import logging

API_TOKEN = "8439840418:AAGqbsaURh9-AzbvxChH9xjh5QPyIT4eE08"

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