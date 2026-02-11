"""
Главный файл админ-бота
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from src.config import settings
from src.database.database import create_tables, async_session_maker
from src.admin_bot.handlers import admin_handlers
from src.admin_bot.middleware.admin_middleware import AdminCheckMiddleware

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Главная функция запуска админ-бота"""

    # Создаем таблицы в БД (если еще не созданы)
    logger.info("Checking database tables...")
    await create_tables()
    logger.info("Database check completed")

    # Инициализация бота и диспетчера
    bot = Bot(token=settings.ADMIN_BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Добавляем middleware для проверки администратора
    dp.message.middleware(AdminCheckMiddleware())
    dp.callback_query.middleware(AdminCheckMiddleware())

    # Добавляем middleware для работы с БД
    @dp.update.middleware()
    async def db_session_middleware(handler, event, data):
        async with async_session_maker() as session:
            data["session"] = session
            return await handler(event, data)

    # Регистрация роутеров
    dp.include_router(admin_handlers.router)

    logger.info("Admin bot starting...")
    logger.info(f"Authorized admin IDs: {settings.admin_ids_list}")

    # Запуск бота
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Admin bot stopped by user")
