"""FSM states for the bot."""
from aiogram.fsm.state import State, StatesGroup


class TermsStates(StatesGroup):
    waiting_acceptance = State()


class VerificationStates(StatesGroup):
    waiting_phone = State()
    waiting_full_name = State()
    waiting_shamcash_identity = State()


class OrderStates(StatesGroup):
    waiting_network = State()
    waiting_amount = State()
    waiting_wallet = State()
    waiting_currency = State()
    waiting_confirmation = State()


class WalletStates(StatesGroup):
    """Dedicated customer wallet registry flow."""
    waiting_network = State()
    waiting_address = State()
    waiting_qr = State()
    waiting_label = State()


class ReceiptStates(StatesGroup):
    waiting_receipt = State()


class FeedbackStates(StatesGroup):
    waiting_message = State()


class AdminStates(StatesGroup):
    waiting_rate = State()
    waiting_typing_txid = State()
    waiting_transfer_screenshot = State()
    waiting_broadcast = State()
    waiting_broadcast_preview = State()
    waiting_personal_message = State()
    waiting_personal_message_preview = State()
    waiting_min_order = State()
    waiting_max_order = State()
    waiting_daily_limit = State()
    waiting_fee_percent = State()
    waiting_search = State()
    waiting_timeout = State()
    waiting_note_text = State()
