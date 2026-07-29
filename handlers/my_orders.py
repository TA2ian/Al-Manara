"""My orders handlers."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from keyboards.inline import main_menu_inline
from keyboards.reply import compact_reply_keyboard
from services.locale_service import locale_service
from database import get_pool

router = Router()


@router.message(F.text.in_(["📋 طلباتي", "📋 Orders"]))
async def show_my_orders(message: Message):
    """Show user's orders."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, language FROM users WHERE telegram_id = $1",
            message.from_user.id
        )

        if not user:
            await message.answer("Please start the bot first: /start")
            return

        orders = await conn.fetch(
            "SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC LIMIT 10",
            user['id']
        )

    lang = user['language']

    if not orders:
        await message.answer(locale_service.get('no_orders', lang))
        return

    text = f"📋 <b>{locale_service.get('my_orders', lang)}</b>

"

    for order in orders:
        status_key = f"order_status_{order['status']}"
        status_text = locale_service.get(status_key, lang)

        text += f"📦 #{order['order_number']}
"
        text += f"   💰 {order['amount_usdt']} USDT ({order['network']})
"
        text += f"   📊 {status_text}
"
        text += f"   📅 {order['created_at'].strftime('%Y-%m-%d %H:%M')}

"

    await message.answer(text, parse_mode='HTML', reply_markup=main_menu_inline(lang))
