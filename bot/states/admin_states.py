from aiogram.fsm.state import State, StatesGroup

class BroadcastFSM(StatesGroup):
    waiting_for_message = State()
