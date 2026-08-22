"""Compatibility facade for the decomposed admin handler stack.

The former monolithic admin.py has been retired.  Keep this module as the
stable ``handlers.admin`` import target while the dispatcher and any external
imports transition to the policy modules.

All authoritative admin flows live in dedicated policy routers.  Their order
below is intentional: specialized policies are registered before the generic
navigation/legacy compatibility layer.
"""
from aiogram import Router

from . import admin_broadcast_policy
from . import admin_financial_dashboard_policy
from . import admin_navigation_policy
from . import admin_approval_policy
from . import admin_payment_confirmation_policy
from . import admin_transfer_policy
from . import admin_note_policy
from . import admin_rate_policy
from . import admin_order_list_policy
from . import admin_user_management_policy
from . import admin_utility_policy
from . import admin_maintenance_policy
from . import admin_settings_policy
from . import admin_rejection_policy

router = Router()

for policy_router in (
    admin_broadcast_policy.router,
    admin_financial_dashboard_policy.router,
    admin_rate_policy.router,
    admin_navigation_policy.router,
    admin_approval_policy.router,
    admin_payment_confirmation_policy.router,
    admin_transfer_policy.router,
    admin_note_policy.router,
    admin_order_list_policy.router,
    admin_user_management_policy.router,
    admin_utility_policy.router,
    admin_maintenance_policy.router,
    admin_settings_policy.router,
    admin_rejection_policy.router,
):
    router.include_router(policy_router)
