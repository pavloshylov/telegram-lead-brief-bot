from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.state import State, StatesGroup


# ---------------------------------------------------------------- FSM states

class NewBrief(StatesGroup):
    client_name = State()
    tone = State()
    office = State()


class ClientBrief(StatesGroup):
    service = State()
    service_text = State()
    budget = State()
    day = State()
    date_text = State()
    time = State()
    time_text = State()
    confirm = State()


class AdminInput(StatesGroup):
    broadcast_message = State()
    broadcast_confirm = State()
    catalog_label = State()


# Steps where the client must use buttons (free text gets a hint).
CLIENT_BUTTON_STEPS = (ClientBrief.service, ClientBrief.budget, ClientBrief.day, ClientBrief.time, ClientBrief.confirm)


# ---------------------------------------------------------------- callback data (<= 64 bytes each)

class ToneCb(CallbackData, prefix="tone"):
    tone: str


class OfficeCb(CallbackData, prefix="office"):
    item_id: int


class MgrCb(CallbackData, prefix="mgr"):
    action: str  # new | leads


class LeadCb(CallbackData, prefix="lead"):
    action: str  # open | set
    brief_id: int
    value: str = ""


class ClientCb(CallbackData, prefix="cl"):
    brief_id: int
    step: str  # go | svc | bud | day | time | back | send | restart
    value: str = ""


class AdminCb(CallbackData, prefix="adm"):
    action: str
    value: str = ""
