"""FSM States for the bot."""
from aiogram.fsm.state import State, StatesGroup


class TermsStates(StatesGroup):
    waiting_acceptance = State()


class VerificationStates(StatesGroup):
    waiting_full_name = State()
    waiting_shamcash_account = State()
    waiting_shamcash_qr = State()


class OrderStates(StatesGroup):
    waiting_network = State()
    waiting_amount = State()
    waiting_wallet = State()
    waiting_wallet_qr = State()
    waiting_save_address = State()
    waiting_address_label = State()
    waiting_currency = State()
    waiting_confirmation = State()


class WalletStates(StatesGroup):
    """Dedicated customer wallet registry flow."""
    waiting_address = State()
    waiting_qr = State()
    waiting_label = State()


class ReceiptStates(StatesGroup):
    waiting_receipt = State()


class FeedbackStates(StatesGroup):
    waiting_message = State()


class AdminStates(StatesGroup):
    waiting_rate = State()
    waiting_admin_note = State()
    waiting_typing_txid = State()
    waiting_transfer_screenshot = State()
    waiting_broadcast = State()
    waiting_shamcash_usd = State()
    waiting_shamcash_syp = State()
    waiting_min_order = State()
    waiting_max_order = State()
    waiting_fee_percent = State()
    waiting_fee_fixed = State()
    waiting_search = State()
    waiting_timeout = State()
    waiting_note_text = State()
    waiting_shamcash_name = State()
