from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram import F
from config import API_TOKEN, logger
from handlers.start import cmd_start
from handlers.documents import handle_upload_document, handle_pdf_document
from handlers.common import fallback

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Регистрация обработчиков
dp.message.register(cmd_start, CommandStart())
dp.message.register(handle_upload_document, F.text == "Загрузить документ")
async def pdf_handler_wrapper(message):
    return await handle_pdf_document(message, bot)

dp.message.register(pdf_handler_wrapper, F.document)
dp.message.register(fallback)

if __name__ == "__main__":
    import asyncio
    logger.info("Запуск бота...")
    asyncio.run(dp.start_polling(bot))
