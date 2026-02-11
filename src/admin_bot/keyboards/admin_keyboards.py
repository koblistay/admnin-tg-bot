"""
Клавиатуры для админ-бота
"""
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


def get_admin_main_menu() -> ReplyKeyboardMarkup:
    """Главное меню администратора"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="📊 Просмотр очереди")
    builder.button(text="📈 Статистика")
    builder.button(text="👥 Все пользователи")
    builder.button(text="📤 Массовая рассылка")
    builder.button(text="📁 Экспорт данных")
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


def get_queue_filters() -> InlineKeyboardMarkup:
    """Фильтры для очереди"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Все", callback_data="queue_filter_all")
    builder.button(text="Приоритет 1", callback_data="queue_filter_priority_1")
    builder.button(text="Приоритет 2", callback_data="queue_filter_priority_2")
    builder.button(text="Приоритет 3", callback_data="queue_filter_priority_3")
    builder.adjust(2, 2)
    return builder.as_markup()


def get_user_actions(user_id: int) -> InlineKeyboardMarkup:
    """Действия с пользователем"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Отметить как обслуженного",
        callback_data=f"mark_served_{user_id}"
    )
    builder.button(
        text="⬆️ Повысить приоритет",
        callback_data=f"increase_priority_{user_id}"
    )
    builder.button(
        text="⬇️ Понизить приоритет",
        callback_data=f"decrease_priority_{user_id}"
    )
    builder.button(
        text="❌ Удалить из очереди",
        callback_data=f"remove_queue_{user_id}"
    )
    builder.adjust(1)
    return builder.as_markup()


def get_export_format() -> InlineKeyboardMarkup:
    """Выбор формата экспорта"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Excel (.xlsx)", callback_data="export_xlsx")
    builder.button(text="CSV", callback_data="export_csv")
    builder.adjust(1)
    return builder.as_markup()


def get_confirm_keyboard(action: str, user_id: int = None) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения действия"""
    builder = InlineKeyboardBuilder()

    callback_data = action if not user_id else f"{action}_{user_id}"

    builder.button(text="✅ Да", callback_data=f"confirm_{callback_data}")
    builder.button(text="❌ Нет", callback_data=f"cancel_{callback_data}")
    builder.adjust(2)
    return builder.as_markup()


def get_back_to_menu() -> InlineKeyboardMarkup:
    """Кнопка возврата в меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_menu")
    return builder.as_markup()
