from aiogram.fsm.state import StatesGroup, State

class DocumentUpload(StatesGroup):
    waiting_file = State()