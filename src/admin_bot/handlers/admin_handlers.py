"""
Обработчики команд для админ-бота
"""
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import openpyxl
import csv

from src.admin_bot.keyboards.admin_keyboards import (
    get_admin_main_menu,
    get_queue_filters,
    get_user_actions,
    get_export_format,
    get_confirm_keyboard,
    get_back_to_menu
)
from src.services.user_service import UserService
from src.services.queue_service import QueueService
from src.database.models import AdminLog
from src.config import REASONS

router = Router()


async def log_admin_action(session: AsyncSession, admin_id: int, action: str, details: str = None):
    """Логирование действия администратора"""
    log_entry = AdminLog(
        admin_id=admin_id,
        action=action,
        details=details
    )
    session.add(log_entry)
    await session.commit()


@router.message(CommandStart())
async def admin_start(message: Message):
    """Главное меню админ-бота"""
    await message.answer(
        "👨‍💼 Панель администратора\n\nВыберите действие:",
        reply_markup=get_admin_main_menu()
    )


@router.message(F.text == "📊 Просмотр очереди")
async def view_queue(message: Message, session: AsyncSession):
    """Просмотр очереди"""
    await message.answer(
        "Выберите фильтр для просмотра очереди:",
        reply_markup=get_queue_filters()
    )


@router.callback_query(F.data.startswith("queue_filter_"))
async def filter_queue(callback: CallbackQuery, session: AsyncSession):
    """Фильтрация очереди"""
    filter_type = callback.data.replace("queue_filter_", "")

    queue_service = QueueService(session)

    if filter_type == "all":
        queue = await queue_service.get_full_queue(limit=50)
        title = "📊 Вся очередь (топ 50)"
    else:
        # Получаем приоритет из filter_type (например, "priority_1" -> 1)
        priority = int(filter_type.split("_")[1])
        queue = await queue_service.get_queue_by_priority(priority)
        title = f"📊 Очередь с приоритетом {priority}"

    if not queue:
        await callback.message.edit_text(
            "Очередь пуста",
            reply_markup=get_back_to_menu()
        )
        return

    # Формируем сообщение
    message_text = f"{title}\n\n"

    for idx, (queue_entry, user) in enumerate(queue, start=1):
        reason_name = REASONS.get(user.reason, {}).get("name", user.reason)
        message_text += (
            f"{idx}. {user.full_name}\n"
            f"   ID: {user.telegram_id}\n"
            f"   Причина: {reason_name}\n"
            f"   Приоритет: {queue_entry.priority}\n"
            f"   Дата: {user.join_date.strftime('%d.%m.%Y %H:%M')}\n"
            f"   /user_{user.id}\n\n"
        )

    await callback.message.edit_text(
        message_text,
        reply_markup=get_back_to_menu()
    )
    await callback.answer()


@router.message(F.text.startswith("/user_"))
async def view_user_details(message: Message, session: AsyncSession):
    """Просмотр деталей пользователя"""
    try:
        user_id = int(message.text.replace("/user_", ""))
    except ValueError:
        await message.answer("Неверный формат команды")
        return

    user_service = UserService(session)
    queue_service = QueueService(session)

    user = await user_service.get_user_by_id(user_id)
    if not user:
        await message.answer("Пользователь не найден")
        return

    position = await queue_service.get_user_position(user_id)
    reason_name = REASONS.get(user.reason, {}).get("name", user.reason)

    user_info = (
        f"👤 Информация о пользователе\n\n"
        f"ФИО: {user.full_name}\n"
        f"Telegram ID: {user.telegram_id}\n"
        f"Причина: {reason_name}\n"
        f"Приоритет: {user.priority}\n"
        f"Позиция в очереди: {position or 'нет в очереди'}\n"
        f"Дата регистрации: {user.join_date.strftime('%d.%m.%Y %H:%M')}\n"
        f"Статус: {'Активен' if user.is_active else 'Неактивен'}"
    )

    await message.answer(user_info, reply_markup=get_user_actions(user_id))


@router.callback_query(F.data.startswith("mark_served_"))
async def mark_as_served(callback: CallbackQuery, session: AsyncSession):
    """Отметить пользователя как обслуженного"""
    user_id = int(callback.data.replace("mark_served_", ""))

    queue_service = QueueService(session)
    success = await queue_service.mark_as_served(user_id)

    if success:
        # Уведомляем пользователя
        from aiogram import Bot
        from src.config import settings
        from src.services.notification_service import NotificationService

        user_service = UserService(session)
        user = await user_service.get_user_by_id(user_id)

        if user:
            bot = Bot(token=settings.BOT_TOKEN)
            notification_service = NotificationService(bot)
            await notification_service.send_service_completed(user.telegram_id)

        # Логируем действие
        await log_admin_action(
            session,
            callback.from_user.id,
            "mark_served",
            f"User ID: {user_id}"
        )

        await callback.answer("✅ Пользователь отмечен как обслуженный", show_alert=True)
        await callback.message.edit_text("✅ Услуга оказана, пользователь удален из очереди")
    else:
        await callback.answer("❌ Ошибка при обновлении статуса", show_alert=True)


@router.callback_query(F.data.startswith("increase_priority_"))
async def increase_priority(callback: CallbackQuery, session: AsyncSession):
    """Повышение приоритета пользователя"""
    user_id = int(callback.data.replace("increase_priority_", ""))

    queue_service = QueueService(session)
    queue_entry = await queue_service.get_queue_entry_by_user_id(user_id)

    if not queue_entry:
        await callback.answer("❌ Пользователь не найден в очереди", show_alert=True)
        return

    new_priority = max(1, queue_entry.priority - 1)

    if new_priority == queue_entry.priority:
        await callback.answer("⚠️ Уже максимальный приоритет", show_alert=True)
        return

    await queue_service.change_user_priority(user_id, new_priority)

    # Уведомляем пользователя
    new_position = await queue_service.get_user_position(user_id)

    from aiogram import Bot
    from src.config import settings
    from src.services.notification_service import NotificationService

    user_service = UserService(session)
    user = await user_service.get_user_by_id(user_id)

    if user:
        bot = Bot(token=settings.BOT_TOKEN)
        notification_service = NotificationService(bot)
        await notification_service.send_queue_updated(user.telegram_id, new_position)

    # Логируем
    await log_admin_action(
        session,
        callback.from_user.id,
        "increase_priority",
        f"User ID: {user_id}, new priority: {new_priority}"
    )

    await callback.answer(f"✅ Приоритет повышен до {new_priority}", show_alert=True)


@router.callback_query(F.data.startswith("decrease_priority_"))
async def decrease_priority(callback: CallbackQuery, session: AsyncSession):
    """Понижение приоритета пользователя"""
    user_id = int(callback.data.replace("decrease_priority_", ""))

    queue_service = QueueService(session)
    queue_entry = await queue_service.get_queue_entry_by_user_id(user_id)

    if not queue_entry:
        await callback.answer("❌ Пользователь не найден в очереди", show_alert=True)
        return

    new_priority = queue_entry.priority + 1
    await queue_service.change_user_priority(user_id, new_priority)

    # Уведомляем пользователя
    new_position = await queue_service.get_user_position(user_id)

    from aiogram import Bot
    from src.config import settings
    from src.services.notification_service import NotificationService

    user_service = UserService(session)
    user = await user_service.get_user_by_id(user_id)

    if user:
        bot = Bot(token=settings.BOT_TOKEN)
        notification_service = NotificationService(bot)
        await notification_service.send_queue_updated(user.telegram_id, new_position)

    # Логируем
    await log_admin_action(
        session,
        callback.from_user.id,
        "decrease_priority",
        f"User ID: {user_id}, new priority: {new_priority}"
    )

    await callback.answer(f"✅ Приоритет понижен до {new_priority}", show_alert=True)


@router.callback_query(F.data.startswith("remove_queue_"))
async def remove_from_queue_confirm(callback: CallbackQuery):
    """Подтверждение удаления из очереди"""
    user_id = callback.data.replace("remove_queue_", "")

    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите удалить пользователя из очереди?",
        reply_markup=get_confirm_keyboard("remove_queue", int(user_id))
    )


@router.callback_query(F.data.startswith("confirm_remove_queue_"))
async def confirm_remove_from_queue(callback: CallbackQuery, session: AsyncSession):
    """Удаление пользователя из очереди"""
    user_id = int(callback.data.replace("confirm_remove_queue_", ""))

    queue_service = QueueService(session)
    success = await queue_service.remove_from_queue(user_id)

    if success:
        await log_admin_action(
            session,
            callback.from_user.id,
            "remove_from_queue",
            f"User ID: {user_id}"
        )

        await callback.message.edit_text("✅ Пользователь удален из очереди")
    else:
        await callback.message.edit_text("❌ Ошибка при удалении")

    await callback.answer()


@router.message(F.text == "📈 Статистика")
async def show_statistics(message: Message, session: AsyncSession):
    """Отображение статистики"""
    queue_service = QueueService(session)
    user_service = UserService(session)

    stats = await queue_service.get_queue_stats()
    all_users = await user_service.get_all_users()
    active_users = await user_service.get_active_users()

    stats_text = (
        f"📈 Статистика системы\n\n"
        f"👥 Всего пользователей: {len(all_users)}\n"
        f"✅ Активных: {len(active_users)}\n"
        f"⏳ В очереди: {stats['total_in_queue']}\n"
        f"✔️ Обслужено: {stats['total_served']}\n\n"
        f"По приоритетам:\n"
    )

    for priority, count in sorted(stats['by_priority'].items()):
        stats_text += f"  Приоритет {priority}: {count}\n"

    await message.answer(stats_text, reply_markup=get_back_to_menu())


@router.message(F.text == "👥 Все пользователи")
async def show_all_users(message: Message, session: AsyncSession):
    """Отображение всех пользователей"""
    user_service = UserService(session)
    users = await user_service.get_all_users()

    if not users:
        await message.answer("Пользователи не найдены")
        return

    users_text = "👥 Все пользователи:\n\n"

    for user in users[:30]:  # Ограничиваем 30 пользователями
        users_text += (
            f"• {user.full_name}\n"
            f"  ID: {user.telegram_id}\n"
            f"  /user_{user.id}\n\n"
        )

    if len(users) > 30:
        users_text += f"\n... и еще {len(users) - 30} пользователей"

    await message.answer(users_text)


@router.message(F.text == "📁 Экспорт данных")
async def export_data_menu(message: Message):
    """Меню экспорта данных"""
    await message.answer(
        "Выберите формат для экспорта:",
        reply_markup=get_export_format()
    )


@router.callback_query(F.data == "export_xlsx")
async def export_to_excel(callback: CallbackQuery, session: AsyncSession):
    """Экспорт данных в Excel"""
    await callback.message.edit_text("⏳ Формирую Excel файл...")

    queue_service = QueueService(session)
    queue = await queue_service.get_full_queue()

    # Создаем Excel файл
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Очередь"

    # Заголовки
    headers = ["№", "ФИО", "Telegram ID", "Причина", "Приоритет", "Позиция", "Дата регистрации"]
    ws.append(headers)

    # Данные
    for idx, (queue_entry, user) in enumerate(queue, start=1):
        reason_name = REASONS.get(user.reason, {}).get("name", user.reason)
        ws.append([
            idx,
            user.full_name,
            user.telegram_id,
            reason_name,
            queue_entry.priority,
            queue_entry.position,
            user.join_date.strftime('%d.%m.%Y %H:%M')
        ])

    # Сохраняем файл
    filename = f"queue_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = f"/tmp/{filename}"
    wb.save(filepath)

    # Отправляем файл
    file = FSInputFile(filepath)
    await callback.message.answer_document(file, caption="📊 Экспорт очереди")

    await log_admin_action(
        session,
        callback.from_user.id,
        "export_data",
        "Format: XLSX"
    )

    await callback.answer()


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.message.delete()
    await callback.message.answer(
        "👨‍💼 Панель администратора\n\nВыберите действие:",
        reply_markup=get_admin_main_menu()
    )
    await callback.answer()
