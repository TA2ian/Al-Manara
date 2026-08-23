"""Authoritative customer order confirmation flow.

This router owns confirm_order. It validates the FSM snapshot and the current
payment destination, then creates one immutable order snapshot and notifies admins.
"""
import logging
import uuid
from datetime import datetime, timedelta

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from config import Config
from database import get_pool
from keyboards.inline import main_menu_inline, order_admin_keyboard, receipt_upload_keyboard
from middleware.rate_limit import rate_limiter as global_rate_limiter
from services.formatters import money, usdt
from services.locale_service import locale_service
from services.notification_service import NotificationService
from services.order_state_service import InvalidOrderTransition, rollback_order, transition_order
from services.settings_service import SettingsService
from states import OrderStates

router = Router()
