from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from config import API_TOKEN, logger
from handlers.start import cmd_start
from handlers.documents import handle_upload_document
from handlers.common import fallback

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Регистрация обработчиков
dp.message.register(cmd_start, CommandStart())
dp.message.register(handle_upload_document, lambda msg: msg.text == "Загрузить документ")
dp.message.register(fallback)

if __name__ == "__main__":
    import asyncio
    logger.info("Запуск бота...")
    asyncio.run(dp.start_polling(bot))
