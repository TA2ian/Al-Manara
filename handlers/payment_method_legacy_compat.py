"""Compatibility router for historical ShamCash admin callbacks.

Telegram inline keyboards are persistent messages. Messages created before the
payment-method callback IDs were canonicalized can therefore remain visible
and can still send callbacks containing old currency labels or old method-code
spellings. This router accepts only a closed set of known aliases and delegates
all state changes to the canonical payment-method implementation.
"""
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from config import Config
from handlers import payment_method_setup_policy

router = Router()

_CODE_ALIASES = {
    "USD": "shamcash_usd",
    "usd": "shamcash_usd",
    "shamcash_usd": "shamcash_usd",
    "shamcash_USD": "shamcash_usd",
    "NEW.SYP": "shamcash_new_syp",
    "new_syp": "shamcash_new_syp",
    "syp": "shamcash_new_syp",
    "SYP": "shamcash_new_syp",
    "shamcash_syp": "shamcash_new_syp",
    "shamcash_new_syp": "shamcash_new_syp",
    "shamcash_NEW.SYP": "shamcash_new_syp",
}

_CALLBACK_PATTERN = re.compile(
    r"^admin_pm_(?P<action>view|setup|enable|disable|toggle)_(?P<code>[^\s]+)$"
)


def _canonicalize_legacy_callback(data: str | None) -> tuple[str, str] | None:
    if not data:
        return None
    match = _CALLBACK_PATTERN.fullmatch(data)
    if not match:
        return None
    code = _CODE_ALIASES.get(match.group("code"))
    if code is None:
        return None
    return match.group("action"), code


async def _delegate_with_canonical_data(callback: CallbackQuery, canonical_data: str, handler, *args):
    original_data = callback.data
    try:
        callback.data = canonical_data
        await handler(callback, *args)
    finally:
        callback.data = original_data


@router.callback_query(F.data.regexp(r"^admin_pm_(?:view|setup|enable|disable|toggle)_[^\s]+$"))
async def legacy_payment_method_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user is None or callback.from_user.id not in Config.ADMIN_IDS:
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    parsed = _canonicalize_legacy_callback(callback.data)
    if parsed is None:
        await callback.answer("وسيلة الدفع غير صالحة", show_alert=True)
        return

    action, code = parsed

    if action == "view":
        await _delegate_with_canonical_data(
            callback,
            f"admin_pm_view_{code}",
            payment_method_setup_policy.payment_method_view,
        )
        return

    if action == "setup":
        await _delegate_with_canonical_data(
            callback,
            f"admin_pm_setup_{code}",
            payment_method_setup_policy.payment_method_setup_start,
            state,
        )
        return

    if action == "enable":
        await payment_method_setup_policy._set_payment_method_enabled(
            callback,
            code,
            True,
            audit_action="payment_method_enable_legacy_callback",
        )
        return

    if action == "disable":
        await payment_method_setup_policy._set_payment_method_enabled(
            callback,
            code,
            False,
            audit_action="payment_method_disable_legacy_callback",
        )
        return

    pool = await payment_method_setup_policy.get_pool()
    async with pool.acquire() as conn:
        method = await conn.fetchrow(
            "SELECT enabled FROM payment_methods WHERE code=$1 AND provider='ShamCash'",
            code,
        )

    if not method:
        await callback.answer("وسيلة الدفع غير موجودة", show_alert=True)
        return

    await payment_method_setup_policy._set_payment_method_enabled(
        callback,
        code,
        not method["enabled"],
        audit_action="payment_method_toggle_legacy_callback",
    )
