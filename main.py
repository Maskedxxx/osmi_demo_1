from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram import F
from config import API_TOKEN, logger
from handlers.start import cmd_start
from handlers.documents import handle_upload_document, handle_pdf_document, handle_url_document
from handlers.common import fallback

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Регистрация обработчиков
dp.message.register(cmd_start, CommandStart())
dp.message.register(handle_upload_document, F.text == "Загрузить документ")
async def pdf_handler_wrapper(message):
    return await handle_pdf_document(message, bot)

async def url_handler_wrapper(message):
    return await handle_url_document(message, bot)

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

dp.message.register(pdf_handler_wrapper, F.document)
dp.message.register(url_handler_wrapper, F.text & F.func(is_url_message))
dp.message.register(fallback)

if __name__ == "__main__":
    import asyncio
    logger.info("Запуск бота...")
    asyncio.run(dp.start_polling(bot))
