"""Bootstrap extracted admin policies into the legacy admin router.

This temporary compatibility bridge lets us remove functionality from the
95KB legacy admin.py incrementally without changing dispatcher behavior.
Extracted policy routers are inserted before legacy handlers, making the new
implementation authoritative for their callback/state flows.
"""
from . import admin
from . import admin_maintenance_policy
from . import admin_order_list_policy
from . import admin_settings_policy
from . import admin_user_management_policy
from . import admin_utility_policy


# Register once when the handlers package is imported.
for extracted_router in (
    admin_order_list_policy.router,
    admin_user_management_policy.router,
    admin_utility_policy.router,
    admin_maintenance_policy.router,
    admin_settings_policy.router,
):
    if extracted_router not in admin.router.sub_routers:
        admin.router.include_router(extracted_router)
