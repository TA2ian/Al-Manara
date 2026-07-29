"""Verification handlers for user account verification."""
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import VerificationStates
from keyboards.inline import main_menu_inline, skip_keyboard, start_verification_keyboard, admin_verify_keyboard
from keyboards.reply import compact_reply_keyboard
from services.locale_service import locale_service
from services.notification_service import NotificationService
from config import Config
from database import get_pool

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "start_verification")
async def start_verification(callback: CallbackQuery, state: FSMContext):
    """Start the verification process."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1",
            callback.from_user.id
        )

    if not user:
        await callback.answer("الرجاء البدء أولاً: /start", show_alert=True)
        return

    lang = user['language']

    await callback.message.edit_text(
        locale_service.get('verification_prompt', lang),
        parse_mode='HTML'
    )
    await callback.message.answer(
        locale_service.get('enter_full_name', lang)
    )

    await state.set_state(VerificationStates.waiting_full_name)
    await callback.answer()


@router.message(VerificationStates.waiting_full_name)
async def enter_full_name(message: Message, state: FSMContext):
    """Handle full name input."""
    name = message.text.strip()

    if len(name) < 3 or len(name) > 100:
        await message.answer("📛 الاسم يجب أن يكون بين 3 و 100 حرف. أعد المحاولة:")
        return

    await state.update_data(full_name=name)

    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT language FROM users WHERE telegram_id = $1",
            message.from_user.id
        )

    lang = user['language'] if user else 'ar'

    await message.answer(locale_service.get('enter_shamcash', lang))
    await state.set_state(VerificationStates.waiting_shamcash_account)


@router.message(VerificationStates.waiting_shamcash_account)
async def enter_shamcash(message: Message, state: FSMContext):
    """Handle Sham Cash account input."""
    account = message.text.strip()

    if len(account) < 5:
        pool = await get_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT language FROM users WHERE telegram_id = $1",
                message.from_user.id
            )
        lang = user['language'] if user else 'ar'
        await message.answer(locale_service.get('enter_shamcash', lang))
        return

    await state.update_data(shamcash_account=account)

    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT language FROM users WHERE telegram_id = $1",
            message.from_user.id
        )

    lang = user['language'] if user else 'ar'

    await message.answer(
        locale_service.get('upload_shamcash_qr', lang),
        reply_markup=skip_keyboard(lang)
    )
    await state.set_state(VerificationStates.waiting_shamcash_qr)


@router.message(VerificationStates.waiting_shamcash_qr, F.photo)
async def upload_shamcash_qr(message: Message, state: FSMContext):
    """Handle Sham Cash QR code photo (optional)."""
    photo_id = message.photo[-1].file_id
    await state.update_data(shamcash_qr_photo_id=photo_id)
    await submit_verification(message, state)


@router.callback_query(VerificationStates.waiting_shamcash_qr, F.data == "skip_qr")
async def skip_shamcash_qr(callback: CallbackQuery, state: FSMContext):
    """Skip Sham Cash QR upload."""
    await callback.message.delete()
    await submit_verification(callback.message, state)
    await callback.answer()


async def submit_verification(msg: Message, state: FSMContext):
    """Submit verification request and notify admins."""
    data = await state.get_data()
    full_name = data['full_name']
    shamcash_account = data['shamcash_account']
    shamcash_qr_photo_id = data.get('shamcash_qr_photo_id')

    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1",
            msg.chat.id
        )

        if user:
            await conn.execute(
                """UPDATE users
                   SET full_name = $1, shamcash_account = $2,
                       shamcash_qr_photo_id = $3,
                       verification_status = 'pending'
                   WHERE telegram_id = $4""",
                full_name, shamcash_account, shamcash_qr_photo_id, msg.chat.id
            )

    if not user:
        return

    lang = user['language']
    bot = Bot(token=Config.BOT_TOKEN)

    # Notify admins with action buttons
    verify_kb = admin_verify_keyboard(msg.chat.id, full_name, shamcash_account)
    admin_text = (
        f"🔔 <b>طلب توثيق جديد</b>\n\n"
        f"👤 المستخدم: @{msg.chat.username or 'بدون'}\n"
        f"🆔 ID: <code>{msg.chat.id}</code>\n"
        f"📛 الاسم: {full_name}\n"
        f"📱 شام كاش: <code>{shamcash_account}</code>\n\n"
        f"اختر إجراء:"
    )

    for admin_id in Config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=verify_kb,
                parse_mode='HTML'
            )
            if shamcash_qr_photo_id:
                await bot.send_photo(
                    admin_id,
                    shamcash_qr_photo_id,
                    caption=f"📸 QR لحساب شام كاش للمستخدم {full_name}"
                )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

    await msg.answer(
        locale_service.get('verification_submitted', lang),
        reply_markup=main_menu_inline(lang)
    )
    await msg.answer("👇", reply_markup=compact_reply_keyboard(lang))

    await state.clear()
