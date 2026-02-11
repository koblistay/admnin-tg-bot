"""
Клавиатуры для основного бота
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from src.config import REASONS
import random


def get_start_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для начала регистрации"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="🚀 Начать регистрацию")
    return builder.as_markup(resize_keyboard=True)


def get_captcha_keyboard(correct_answer: int) -> InlineKeyboardMarkup:
    """Клавиатура для CAPTCHA"""
    builder = InlineKeyboardBuilder()

    # Генерируем варианты ответов (включая правильный)
    answers = [correct_answer]
    while len(answers) < 4:
        wrong = random.randint(1, 20)
        if wrong not in answers:
            answers.append(wrong)

    random.shuffle(answers)

    # Создаем кнопки
    for answer in answers:
        builder.button(
            text=str(answer),
            callback_data=f"captcha_{answer}_{correct_answer}"
        )

    builder.adjust(2, 2)  # 2 кнопки в ряд
    return builder.as_markup()


def get_reason_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора причины вступления"""
    builder = InlineKeyboardBuilder()

    for reason_key, reason_data in REASONS.items():
        builder.button(
            text=reason_data["name"],
            callback_data=f"reason_{reason_key}"
        )

    builder.adjust(1)  # По одной кнопке в ряд
    return builder.as_markup()


def get_skip_document_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для пропуска загрузки документа (если не требуется)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Пропустить", callback_data="skip_document")
    return builder.as_markup()


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура отмены"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Отменить")
    return builder.as_markup(resize_keyboard=True)
