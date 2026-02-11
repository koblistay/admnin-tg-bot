"""
Состояния FSM для регистрации пользователя
"""
from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Состояния процесса регистрации"""
    captcha = State()
    waiting_for_full_name = State()
    waiting_for_reason = State()
    waiting_for_document = State()
