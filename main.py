from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from config import API_TOKEN, logger
from handlers.start import cmd_start
from handlers.documents import handle_upload_document, handle_document_file
from handlers.common import fallback
from states import DocumentUpload

# Инициализация бота и диспетчера с хранилищем состояний
storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=storage)

# Регистрация обработчиков
dp.message.register(cmd_start, CommandStart())
dp.message.register(handle_upload_document, lambda msg: msg.text == "Загрузить документ")
dp.message.register(handle_document_file, DocumentUpload.waiting_file)
dp.message.register(fallback)

if __name__ == "__main__":
    import asyncio
    logger.info("Запуск бота...")
    asyncio.run(dp.start_polling(bot))
