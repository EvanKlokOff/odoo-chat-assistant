from aiogram.fsm.state import State, StatesGroup

class ComplianceStates(StatesGroup):
    """States for compliance command flow"""
    waiting_for_date = State()        # Ожидание выбора даты/периода
    waiting_for_instruction = State() # Ожидание ввода инструкции

class ReviewStates(StatesGroup):
    """States for review command flow"""
    waiting_for_date = State()        # Ожидание выбора даты/периода