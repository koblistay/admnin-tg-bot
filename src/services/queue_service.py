"""
Сервис для работы с очередью
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, func
from typing import Optional, List, Tuple
from src.database.models import Queue, User, QueueStatus


class QueueService:
    """Сервис для управления очередью"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_to_queue(self, user_id: int, priority: int) -> Queue:
        """Добавление пользователя в очередь"""
        # Получаем последнюю позицию для данного приоритета
        position = await self._get_next_position(priority)

        queue_entry = Queue(
            user_id=user_id,
            priority=priority,
            position=position,
            status=QueueStatus.IN_QUEUE.value
        )

        self.session.add(queue_entry)
        await self.session.commit()
        await self.session.refresh(queue_entry)

        # Пересчитываем все позиции
        await self._recalculate_positions()

        return queue_entry

    async def _get_next_position(self, priority: int) -> int:
        """Получение следующей позиции в очереди для приоритета"""
        result = await self.session.execute(
            select(func.max(Queue.position))
            .where(
                and_(
                    Queue.priority == priority,
                    Queue.status == QueueStatus.IN_QUEUE.value
                )
            )
        )
        max_position = result.scalar()
        return (max_position or 0) + 1

    async def get_queue_entry_by_user_id(self, user_id: int) -> Optional[Queue]:
        """Получение записи очереди по ID пользователя"""
        result = await self.session.execute(
            select(Queue)
            .where(
                and_(
                    Queue.user_id == user_id,
                    Queue.status == QueueStatus.IN_QUEUE.value
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_user_position(self, user_id: int) -> Optional[int]:
        """Получение позиции пользователя в общей очереди"""
        queue_entry = await self.get_queue_entry_by_user_id(user_id)
        if not queue_entry:
            return None

        # Подсчитываем количество пользователей впереди
        result = await self.session.execute(
            select(func.count(Queue.id))
            .where(
                and_(
                    Queue.status == QueueStatus.IN_QUEUE.value,
                    (
                            (Queue.priority < queue_entry.priority) |
                            (
                                and_(
                                    Queue.priority == queue_entry.priority,
                                    Queue.position < queue_entry.position
                                )
                            )
                    )
                )
            )
        )
        count = result.scalar()
        return count + 1

    async def get_full_queue(self, limit: Optional[int] = None) -> List[Tuple[Queue, User]]:
        """Получение полной очереди с данными пользователей"""
        query = (
            select(Queue, User)
            .join(User, Queue.user_id == User.id)
            .where(Queue.status == QueueStatus.IN_QUEUE.value)
            .order_by(Queue.priority.asc(), Queue.position.asc())
        )

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.all())

    async def get_queue_by_priority(self, priority: int) -> List[Tuple[Queue, User]]:
        """Получение очереди по приоритету"""
        result = await self.session.execute(
            select(Queue, User)
            .join(User, Queue.user_id == User.id)
            .where(
                and_(
                    Queue.status == QueueStatus.IN_QUEUE.value,
                    Queue.priority == priority
                )
            )
            .order_by(Queue.position.asc())
        )
        return list(result.all())

    async def change_user_priority(self, user_id: int, new_priority: int) -> Optional[Queue]:
        """Изменение приоритета пользователя"""
        queue_entry = await self.get_queue_entry_by_user_id(user_id)
        if not queue_entry:
            return None

        # Получаем новую позицию для нового приоритета
        new_position = await self._get_next_position(new_priority)

        await self.session.execute(
            update(Queue)
            .where(Queue.id == queue_entry.id)
            .values(priority=new_priority, position=new_position)
        )
        await self.session.commit()

        # Пересчитываем позиции
        await self._recalculate_positions()

        return await self.get_queue_entry_by_user_id(user_id)

    async def move_user_position(self, user_id: int, new_position: int) -> Optional[Queue]:
        """Перемещение пользователя на конкретную позицию в рамках его приоритета"""
        queue_entry = await self.get_queue_entry_by_user_id(user_id)
        if not queue_entry:
            return None

        await self.session.execute(
            update(Queue)
            .where(Queue.id == queue_entry.id)
            .values(position=new_position)
        )
        await self.session.commit()

        # Пересчитываем позиции
        await self._recalculate_positions()

        return await self.get_queue_entry_by_user_id(user_id)

    async def mark_as_served(self, user_id: int) -> bool:
        """Отметка пользователя как обслуженного"""
        result = await self.session.execute(
            update(Queue)
            .where(
                and_(
                    Queue.user_id == user_id,
                    Queue.status == QueueStatus.IN_QUEUE.value
                )
            )
            .values(status=QueueStatus.SERVED.value)
        )
        await self.session.commit()

        if result.rowcount > 0:
            await self._recalculate_positions()
            return True
        return False

    async def remove_from_queue(self, user_id: int) -> bool:
        """Удаление пользователя из очереди"""
        result = await self.session.execute(
            update(Queue)
            .where(
                and_(
                    Queue.user_id == user_id,
                    Queue.status == QueueStatus.IN_QUEUE.value
                )
            )
            .values(status=QueueStatus.REMOVED.value)
        )
        await self.session.commit()

        if result.rowcount > 0:
            await self._recalculate_positions()
            return True
        return False

    async def _recalculate_positions(self):
        """Пересчет позиций в очереди"""
        # Получаем все активные записи очереди
        result = await self.session.execute(
            select(Queue)
            .where(Queue.status == QueueStatus.IN_QUEUE.value)
            .order_by(Queue.priority.asc(), Queue.position.asc())
        )
        queue_entries = list(result.scalars().all())

        # Группируем по приоритетам и переназначаем позиции
        priority_groups = {}
        for entry in queue_entries:
            if entry.priority not in priority_groups:
                priority_groups[entry.priority] = []
            priority_groups[entry.priority].append(entry)

        # Обновляем позиции
        for priority, entries in priority_groups.items():
            for idx, entry in enumerate(entries, start=1):
                if entry.position != idx:
                    await self.session.execute(
                        update(Queue)
                        .where(Queue.id == entry.id)
                        .values(position=idx)
                    )

        await self.session.commit()

    async def get_queue_stats(self) -> dict:
        """Получение статистики очереди"""
        # Общее количество в очереди
        result = await self.session.execute(
            select(func.count(Queue.id))
            .where(Queue.status == QueueStatus.IN_QUEUE.value)
        )
        total_in_queue = result.scalar()

        # Количество обслуженных
        result = await self.session.execute(
            select(func.count(Queue.id))
            .where(Queue.status == QueueStatus.SERVED.value)
        )
        total_served = result.scalar()

        # По приоритетам
        result = await self.session.execute(
            select(Queue.priority, func.count(Queue.id))
            .where(Queue.status == QueueStatus.IN_QUEUE.value)
            .group_by(Queue.priority)
        )
        by_priority = dict(result.all())

        return {
            "total_in_queue": total_in_queue,
            "total_served": total_served,
            "by_priority": by_priority
        }
