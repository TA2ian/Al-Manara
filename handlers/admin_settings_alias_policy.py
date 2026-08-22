"""Compatibility aliases for admin settings callbacks.

The settings keyboard historically exposed ``setting_shamcash_new_syp`` while
its handler uses ``setting_shamcash_syp``. Keep the public keyboard callback
and route it to the authoritative settings implementation.
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from . import admin_settings_policy

router = Router()


@router.callback_query(F.data == "setting_shamcash_new_syp")
async def setting_shamcash_new_syp_alias(callback: CallbackQuery, state: FSMContext):
    await admin_settings_policy.setting_shamcash_syp(callback, state)
