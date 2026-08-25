"""Remove the one-time phone-sharing reply keyboard after successful contact sharing."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove

from states import VerificationStates
from handlers.verification_policy import receive_phone

router = Router()


@router.message(VerificationStates.waiting_phone, F.contact)
async def receive_phone_and_remove_keyboard(message: Message, state: FSMContext):
    """Delegate phone validation to the canonical handler, then remove its reply keyboard."""
    contact = message.contact
    phone = (contact.phone_number or "").strip()
    if contact.user_id != message.from_user.id or not phone:
        await receive_phone(message, state)
        return

    await receive_phone(message, state)
    if await state.get_state() == VerificationStates.waiting_full_name:
        await message.answer("✓", reply_markup=ReplyKeyboardRemove())
