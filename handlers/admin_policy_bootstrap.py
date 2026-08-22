"""Bootstrap extracted admin policies into the legacy admin router.

This temporary compatibility bridge lets us remove functionality from the
95KB legacy admin.py incrementally without changing dispatcher behavior.
Extracted policy routers are inserted before legacy handlers, making the new
implementation authoritative for their callback/state flows.
"""
from . import admin
from . import admin_user_management_policy


# Register once when the handlers package is imported.
if admin_user_management_policy.router not in admin.router.sub_routers:
    admin.router.include_router(admin_user_management_policy.router)
