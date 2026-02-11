"""
Сервис для работы с пользователями
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from typing import Optional, List
from src.database.models import User
from src.config import REASONS


class UserService:
    """Сервис для управления пользователями"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_user(
            self,
            telegram_id: int,
            full_name: str,
            reason: str,
            document_photo: Optional[str] = None
    ) -> User:
        """Создание нового пользователя"""
        priority = REASONS.get(reason, {}).get("priority", 999)

        user = User(
            telegram_id=telegram_id,
            full_name=full_name,
            reason=reason,
            document_photo=document_photo,
            priority=priority,
            is_active=True
        )

        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)

        return user

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получение пользователя по Telegram ID"""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Получение пользователя по ID"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_all_users(self) -> List[User]:
        """Получение всех пользователей"""
        result = await self.session.execute(select(User))
        return list(result.scalars().all())

    async def get_active_users(self) -> List[User]:
        """Получение активных пользователей"""
        result = await self.session.execute(
            select(User).where(User.is_active == True)
        )
        return list(result.scalars().all())

    async def update_user(
            self,
            user_id: int,
            full_name: Optional[str] = None,
            reason: Optional[str] = None,
            is_active: Optional[bool] = None
    ) -> Optional[User]:
        """Обновление данных пользователя"""
        update_data = {}

        if full_name is not None:
            update_data["full_name"] = full_name

        if reason is not None:
            update_data["reason"] = reason
            update_data["priority"] = REASONS.get(reason, {}).get("priority", 999)

        if is_active is not None:
            update_data["is_active"] = is_active

        if update_data:
            await self.session.execute(
                update(User).where(User.id == user_id).values(**update_data)
            )
            await self.session.commit()

        return await self.get_user_by_id(user_id)

    async def deactivate_user(self, user_id: int) -> bool:
        """Деактивация пользователя"""
        result = await self.session.execute(
            update(User).where(User.id == user_id).values(is_active=False)
        )
        await self.session.commit()
        return result.rowcount > 0

    async def delete_user(self, user_id: int) -> bool:
        """Удаление пользователя"""
        result = await self.session.execute(
            delete(User).where(User.id == user_id)
        )
        await self.session.commit()
        return result.rowcount > 0

    async def user_exists(self, telegram_id: int) -> bool:
        """Проверка существования пользователя"""
        user = await self.get_user_by_telegram_id(telegram_id)
        return user is not None
