"""
Модели базы данных
"""
from datetime import datetime
from sqlalchemy import BigInteger, Integer, String, Boolean, DateTime, Text, Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from typing import Optional
import enum


class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""
    pass


class QueueStatus(enum.Enum):
    """Статусы очереди"""
    IN_QUEUE = "in_queue"  # В очереди
    SERVED = "served"  # Обслужен
    REMOVED = "removed"  # Удален


class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    document_photo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    join_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"User(id={self.id}, telegram_id={self.telegram_id}, full_name='{self.full_name}')"


class Queue(Base):
    """Модель очереди"""
    __tablename__ = "queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=QueueStatus.IN_QUEUE.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                                                 nullable=False)

    def __repr__(self) -> str:
        return f"Queue(id={self.id}, user_id={self.user_id}, position={self.position}, status='{self.status}')"


class AdminLog(Base):
    """Журнал действий администраторов"""
    __tablename__ = "admin_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"AdminLog(id={self.id}, admin_id={self.admin_id}, action='{self.action}')"
