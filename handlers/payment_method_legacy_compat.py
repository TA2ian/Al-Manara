"""Compatibility router for legacy ShamCash admin callbacks.

Telegram inline keyboards are persistent messages. Messages created before the
payment-method callback IDs were canonicalized can therefore remain visible
and can still send callbacks containing the old currency labels. This router
accepts only the known historical aliases and delegates state changes to the
canonical payment-method implementation.
"""
import re

from aiogram import F, Router
from aiogram.types import CallbackQuery

from config import Config
from handlers import payment_method_setup_policy

router = Router()

_LEGACY_CODE_MAP = {
    "USD": "shamcash_usd",
    "NEW.SYP": "shamcash_new_syp",
    "usd": "shamcash_usd",
    "new_syp": "shamcash_new_syp",
}
_LEGACY_CALLBACK_PATTERN = re.compile(
    r"^admin_pm_(?P<action>enable|disable|toggle)_(?P<code>USD|NEW\.SYP|usd|new_syp)$"
)


def _canonicalize_legacy_callback(data: str | None) -> tuple[str, str] | None:
    if not data:
        return None
    match = _LEGACY_CALLBACK_PATTERN.fullmatch(data)
    if not match:
        return None
    code = _LEGACY_CODE_MAP.get(match.group("code"))
    if code is None:
        return None
    return match.group("action"), code


@router.callback_query(F.data.regexp(r"^admin_pm_(?:enable|disable|toggle)_(?:USD|NEW\.SYP|usd|new_syp)$"))
async def legacy_payment_method_callback(callback: CallbackQuery):
    if callback.from_user is None or callback.from_user.id not in Config.ADMIN_IDS:
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    parsed = _canonicalize_legacy_callback(callback.data)
    if parsed is None:
        await callback.answer("وسيلة الدفع غير صالحة", show_alert=True)
        return

    action, code = parsed
    if action == "enable":
        await payment_method_setup_policy._set_payment_method_enabled(
            callback, code, True, audit_action="payment_method_enable_legacy_callback"
        )
        return
    if action == "disable":
        await payment_method_setup_policy._set_payment_method_enabled(
            callback, code, False, audit_action="payment_method_disable_legacy_callback"
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
