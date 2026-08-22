"""Compatibility facade for the decomposed admin handler stack.

The original monolithic admin.py has been retired. Existing dispatcher code
still includes ``admin.router``, so this facade registers only policies that
are not separately included by the dispatcher. Authoritative policies that
are registered directly by bot.py must not be nested here, otherwise the same
router can be attached twice and callback precedence becomes ambiguous.
"""
from aiogram import Router

from . import admin_order_list_policy
from . import admin_user_management_policy
from . import admin_utility_policy
from . import admin_maintenance_policy
from . import admin_settings_policy
from . import admin_settings_alias_policy

router = Router()

for policy_router in (
    admin_order_list_policy.router,
    admin_user_management_policy.router,
    admin_utility_policy.router,
    admin_maintenance_policy.router,
    admin_settings_policy.router,
    admin_settings_alias_policy.router,
):
    router.include_router(policy_router)
