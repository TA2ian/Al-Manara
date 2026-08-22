"""Compatibility facade for the retired monolithic admin handler.

All admin behavior has been decomposed into dedicated policy modules.  This
module intentionally keeps only the historical ``handlers.admin.router``
import target so existing imports do not fail.  The dispatcher registers the
policy routers directly; this facade contains no handlers and therefore cannot
create duplicate callback registrations.
"""
from aiogram import Router

router = Router()
