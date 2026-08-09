from aiogram.fsm.state import State, StatesGroup


class RequestFSM(StatesGroup):
    waiting_for_query = State()
