"""
Сервис для отправки уведомлений
"""
from aiogram import Bot
from typing import List
from src.config import MESSAGES


class NotificationService:
    """Сервис для отправки уведомлений пользователям"""

    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_registration_complete(
            self,
            telegram_id: int,
            channel_username: str,
            position: int
    ):
        """Уведомление об успешной регистрации"""
        message = MESSAGES["registration_complete"].format(
            channel=channel_username,
            position=position
        )
        await self.bot.send_message(telegram_id, message)

    async def send_queue_updated(self, telegram_id: int, position: int):
        """Уведомление об изменении позиции в очереди"""
        message = MESSAGES["queue_updated"].format(position=position)
        await self.bot.send_message(telegram_id, message)

    async def send_service_completed(self, telegram_id: int):
        """Уведомление о завершении обслуживания"""
        message = MESSAGES["service_completed"]
        await self.bot.send_message(telegram_id, message)

    async def broadcast_message(self, telegram_ids: List[int], message: str):
        """Массовая рассылка сообщений"""
        success_count = 0
        fail_count = 0

        for telegram_id in telegram_ids:
            try:
                await self.bot.send_message(telegram_id, message)
                success_count += 1
            except Exception as e:
                fail_count += 1
                print(f"Failed to send to {telegram_id}: {e}")

        return {
            "success": success_count,
            "failed": fail_count,
            "total": len(telegram_ids)
        }
