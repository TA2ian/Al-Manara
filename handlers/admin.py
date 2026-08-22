"""Compatibility facade for the decomposed admin handler stack.

The original monolithic admin.py has been retired.  Existing dispatcher code
still includes ``admin.router``, so this facade registers only the newly
extracted policies that are not separately included by the dispatcher yet.
Existing authoritative policies (rate, navigation, approval, payment
confirmation, transfer, note, broadcast, financial dashboard, verification)
are registered directly by bot.py and are deliberately not duplicated here.
"""
from aiogram import Router

from . import admin_order_list_policy
from . import admin_user_management_policy
from . import admin_utility_policy
from . import admin_maintenance_policy
from . import admin_settings_policy
from . import admin_rejection_policy

router = Router()

for policy_router in (
    admin_order_list_policy.router,
    admin_user_management_policy.router,
    admin_utility_policy.router,
    admin_maintenance_policy.router,
    admin_settings_policy.router,
    admin_rejection_policy.router,
):
    router.include_router(policy_router)
