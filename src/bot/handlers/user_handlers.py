from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import random
import logging

from src.bot.states import RegistrationStates
from src.bot.keyboards.user_keyboards import (
    get_start_keyboard,
    get_captcha_keyboard,
    get_reason_keyboard,
    get_cancel_keyboard
)
from src.services.user_service import UserService
from src.services.queue_service import QueueService
from src.config import MESSAGES, REASONS

router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды /start"""
    user_service = UserService(session)

    # Проверяем, зарегистрирован ли пользователь
    if await user_service.user_exists(message.from_user.id):
        queue_service = QueueService(session)
        position = await queue_service.get_user_position(message.from_user.id)

        await message.answer(
            MESSAGES["already_registered"].format(position=position or "неизвестна"),
            reply_markup=get_start_keyboard()
        )
        return

    # Начинаем регистрацию
    await message.answer(
        MESSAGES["welcome"],
        reply_markup=get_start_keyboard()
    )


@router.message(F.text == "🚀 Начать регистрацию")
async def start_registration(message: Message, state: FSMContext):
    """Начало процесса регистрации с CAPTCHA"""
    # Генерируем простой пример для CAPTCHA
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    correct_answer = num1 + num2

    # Сохраняем правильный ответ в состояние
    await state.update_data(captcha_answer=correct_answer)
    await state.set_state(RegistrationStates.captcha)

    await message.answer(
        MESSAGES["captcha"].format(question=f"{num1} + {num2} = ?"),
        reply_markup=get_captcha_keyboard(correct_answer)
    )


@router.callback_query(F.data.startswith("captcha_"), RegistrationStates.captcha)
async def process_captcha(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на CAPTCHA"""
    # Парсим callback data: captcha_<выбранный_ответ>_<правильный_ответ>
    _, user_answer, correct_answer = callback.data.split("_")

    if user_answer == correct_answer:
        await callback.message.edit_text(MESSAGES["captcha_success"])
        await callback.message.answer(
            MESSAGES["ask_full_name"],
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(RegistrationStates.waiting_for_full_name)
    else:
        await callback.answer(MESSAGES["captcha_fail"], show_alert=True)

        # Генерируем новую CAPTCHA
        num1 = random.randint(1, 10)
        num2 = random.randint(1, 10)
        correct_answer = num1 + num2

        await state.update_data(captcha_answer=correct_answer)

        await callback.message.edit_text(
            MESSAGES["captcha"].format(question=f"{num1} + {num2} = ?")
        )
        await callback.message.edit_reply_markup(
            reply_markup=get_captcha_keyboard(correct_answer)
        )


@router.message(RegistrationStates.waiting_for_full_name, F.text)
async def process_full_name(message: Message, state: FSMContext):
    """Обработка ввода ФИО"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Регистрация отменена.", reply_markup=get_start_keyboard())
        return

    # Сохраняем ФИО
    await state.update_data(full_name=message.text)

    # Переходим к выбору причины
    await message.answer(
        MESSAGES["ask_reason"],
        reply_markup=get_reason_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_reason)


@router.callback_query(F.data.startswith("reason_"), RegistrationStates.waiting_for_reason)
async def process_reason(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка выбора причины вступления"""
    reason_key = callback.data.replace("reason_", "")
    reason_data = REASONS.get(reason_key)

    if not reason_data:
        await callback.answer("Ошибка выбора причины", show_alert=True)
        return

    # Сохраняем причину
    await state.update_data(
        reason=reason_key,
        requires_document=reason_data["requires_document"]
    )

    await callback.message.edit_text(f"✅ Выбрано: {reason_data['name']}")

    # Если требуется документ - запрашиваем
    if reason_data["requires_document"]:
        await callback.message.answer(
            MESSAGES["ask_document"],
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(RegistrationStates.waiting_for_document)
    else:
        # Если документ не требуется - завершаем регистрацию
        await finalize_registration(callback.message, state, session)


@router.message(RegistrationStates.waiting_for_document, F.photo)
async def process_document(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка загрузки фото документа"""
    # Получаем ID фото (самого большого размера)
    photo_id = message.photo[-1].file_id

    # Сохраняем ID фото
    await state.update_data(document_photo=photo_id)

    # Завершаем регистрацию
    await finalize_registration(message, state, session)


async def finalize_registration(message: Message, state: FSMContext, session: AsyncSession):
    """Финализация регистрации пользователя"""
    from src.services.notification_service import NotificationService
    from src.services.channel_service import ChannelManager
    from src.config import settings
    from aiogram import Bot

    data = await state.get_data()

    try:
        # Создаем пользователя
        user_service = UserService(session)
        user = await user_service.create_user(
            telegram_id=message.from_user.id,
            full_name=data["full_name"],
            reason=data["reason"],
            document_photo=data.get("document_photo")
        )

        # Добавляем в очередь
        queue_service = QueueService(session)
        await queue_service.add_to_queue(user.id, user.priority)

        # Получаем позицию в очереди
        position = await queue_service.get_user_position(user.id)

        # Добавляем в канал
        bot = Bot(token=settings.BOT_TOKEN)
        channel_manager = ChannelManager(bot, settings.CHANNEL_ID)

        invite_success = await channel_manager.add_user(message.from_user.id)

        if not invite_success:
            logger.warning(f"Failed to create invite link for user {message.from_user.id}")

        # Получаем информацию о канале
        channel_info = await channel_manager.get_channel_info()
        channel_name = channel_info[
            'title'] if channel_info else settings.CHANNEL_USERNAME or f"ID: {settings.CHANNEL_ID}"

        # Отправляем уведомление
        notification_service = NotificationService(bot)
        await notification_service.send_registration_complete(
            message.from_user.id,
            channel_name,
            position
        )

        # Очищаем состояние
        await state.clear()

        await message.answer(
            "✅ Регистрация завершена!",
            reply_markup=get_start_keyboard()
        )

    except Exception as e:
        logger.error(f"Error during registration: {e}")
        await message.answer(
            MESSAGES["error"],
            reply_markup=get_start_keyboard()
        )
        await state.clear()
