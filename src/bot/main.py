"""
Главный файл основного пользовательского бота
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from src.config import settings
from src.database.database import create_tables
from src.bot.handlers import user_handlers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Главная функция запуска бота"""

    # Создаем таблицы в БД
    logger.info("Creating database tables...")
    await create_tables()
    logger.info("Database tables created successfully")

    # Инициализация бота и диспетчера
    bot = Bot(token=settings.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Добавляем middleware для работы с БД
    from src.database.database import async_session_maker

    @dp.update.middleware()
    async def db_session_middleware(handler, event, data):
        async with async_session_maker() as session:
            data["session"] = session
            return await handler(event, data)

    # Регистрация роутеров
    dp.include_router(user_handlers.router)

    logger.info("Bot starting...")
    logger.info(f"Channel ID: {settings.CHANNEL_ID}")

    # Запуск бота
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
