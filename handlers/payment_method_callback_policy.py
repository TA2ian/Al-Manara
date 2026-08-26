"""Canonical ingress normalization for historical ShamCash callback identifiers."""
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from config import Config
from handlers import payment_method_setup_policy

router = Router()


HISTORICAL_CODE_ALIASES = {
    "USD": "shamcash_usd",
    "usd": "shamcash_usd",
    "shamcash_USD": "shamcash_usd",
    "NEW.SYP": "shamcash_new_syp",
    "new_syp": "shamcash_new_syp",
    "new.syp": "shamcash_new_syp",
    "syp": "shamcash_new_syp",
    "SYP": "shamcash_new_syp",
    "shamcash_syp": "shamcash_new_syp",
    "shamcash_new.syp": "shamcash_new_syp",
    "shamcash_NEW.SYP": "shamcash_new_syp",
}

HISTORICAL_CODE_PATTERN = r"(?:USD|usd|shamcash_USD|NEW\.SYP|new_syp|new\.syp|syp|SYP|shamcash_syp|shamcash_new\.syp|shamcash_NEW\.SYP)"
HISTORICAL_CALLBACK_PATTERN = re.compile(
    rf"^admin_pm_(?P<action>view|setup|enable|disable|toggle)_(?P<code>{HISTORICAL_CODE_PATTERN})$"
)


def normalize_historical_callback(data: str | None) -> tuple[str, str] | None:
    if not data:
        return None
    match = HISTORICAL_CALLBACK_PATTERN.fullmatch(data)
    if not match:
        return None
    canonical_code = HISTORICAL_CODE_ALIASES.get(match.group("code"))
    if canonical_code is None:
        return None
    return match.group("action"), canonical_code


async def _delegate_with_canonical_data(callback: CallbackQuery, canonical_data: str, handler, *args) -> None:
    original_data = callback.data
    try:
        callback.data = canonical_data
        await handler(callback, *args)
    finally:
        callback.data = original_data


@router.callback_query(F.data.regexp(rf"^admin_pm_(?:view|setup|enable|disable|toggle)_{HISTORICAL_CODE_PATTERN}$"))
async def historical_payment_method_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.from_user.id not in Config.ADMIN_IDS:
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    parsed = normalize_historical_callback(callback.data)
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
            audit_action="payment_method_enable_historical_callback",
        )
        return

    if action == "disable":
        await payment_method_setup_policy._set_payment_method_enabled(
            callback,
            code,
            False,
            audit_action="payment_method_disable_historical_callback",
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
        audit_action="payment_method_toggle_historical_callback",
    )
