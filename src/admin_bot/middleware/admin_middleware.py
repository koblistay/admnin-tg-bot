"""
Middleware для проверки администратора
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from src.config import settings


class AdminCheckMiddleware(BaseMiddleware):
    """Middleware для проверки прав администратора"""

    async def __call__(
            self,
            handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
            event: Message | CallbackQuery,
            data: Dict[str, Any]
    ) -> Any:
        """Проверка, является ли пользователь администратором"""

        user_id = event.from_user.id

        # Проверяем, есть ли пользователь в списке администраторов
        if user_id not in settings.admin_ids_list:
            if isinstance(event, Message):
                await event.answer("❌ У вас нет доступа к этому боту.")
            elif isinstance(event, CallbackQuery):
                await event.answer("❌ У вас нет доступа к этому боту.", show_alert=True)
            return

        # Передаем управление дальше
        return await handler(event, data)
