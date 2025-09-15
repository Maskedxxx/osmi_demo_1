from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram import F
from config import API_TOKEN, logger
from handlers.start import cmd_start
from handlers.documents import (
    handle_upload_document, 
    handle_full_defect_analysis
)
from handlers.common import fallback

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Регистрация обработчиков команд
dp.message.register(cmd_start, CommandStart())

# Регистрация обработчиков загрузки документов
dp.message.register(handle_upload_document, F.text == "Загрузить документ")

async def defect_analysis_wrapper(message):
    """Обработчик полного пайплайна анализа дефектов для файлов и ссылок"""
    return await handle_full_defect_analysis(message, bot)

def is_url_message(message):
    """Проверяет, содержит ли сообщение ссылку на облачное хранилище"""
    if not message.text:
        return False
    text = message.text.strip()
    return any(domain in text for domain in [
        "drive.google.com", 
        "dropbox.com", 
        "disk.yandex"
    ])

# Регистрация обработчиков файлов и ссылок (полный пайплайн анализа дефектов)
dp.message.register(defect_analysis_wrapper, F.document)
dp.message.register(defect_analysis_wrapper, F.text & F.func(is_url_message))

# Fallback обработчик (должен быть последним)
dp.message.register(fallback)

if __name__ == "__main__":
    import asyncio
    logger.info("Запуск бота...")
    asyncio.run(dp.start_polling(bot))
