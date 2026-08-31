"""Authoritative admin tools: customer search entry and database backup/restore."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import date, datetime
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Config
from database import get_pool
from keyboards.inline import admin_menu_keyboard
from services.settings_service import SettingsService
from states import AdminStates

logger = logging.getLogger(__name__)
router = Router()

BACKUP_TABLES = (
    "users",
    "orders",
    "exchange_rates",
    "audit_logs",
    "blocked_users",
    "feedback_messages",
    "saved_addresses",
    "payment_methods",
    "bot_settings",
)
BACKUP_VERSION = 1
SEQUENCE_TABLES = (
    "users", "orders", "exchange_rates", "audit_logs", "blocked_users",
    "feedback_messages", "saved_addresses", "payment_methods",
)


def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


def _backup_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 تصدير نسخة الآن", callback_data="admin_backup_export")],
        [InlineKeyboardButton(text="📥 استعادة نسخة", callback_data="admin_backup_restore")],
        [InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_menu")],
    ])


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Unsupported backup value: {type(value)!r}")


def _restore_value(value, column_type: str):
    """Convert JSON values back to PostgreSQL scalar types safely."""
    if value is None:
        return None
    if column_type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "t", "1", "yes", "on"}:
                return True
            if normalized in {"false", "f", "0", "no", "off", ""}:
                return False
            raise ValueError(f"Invalid boolean backup value: {value!r}")
        return bool(value)
    if "timestamp" in column_type:
        return datetime.fromisoformat(value)
    if column_type == "date":
        return date.fromisoformat(value)
    if "numeric" in column_type or "decimal" in column_type:
        return Decimal(str(value))
    if column_type in ("bigint", "integer", "smallint"):
        return int(value)
    if column_type in ("json", "jsonb") and isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


async def _get_table_columns(conn, table: str) -> dict[str, str]:
    rows = await conn.fetch(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        ORDER BY ordinal_position
        """,
        table,
    )
    return {row["column_name"]: row["data_type"] for row in rows}


def _validate_restore_rows(rows, schema: dict[str, str], table: str) -> None:
    if not isinstance(rows, list):
        raise ValueError(f"Backup table {table!r} must contain a list")
    if not rows:
        return

    allowed_columns = set(schema)
    expected_columns = set(rows[0])
    unknown_columns = expected_columns - allowed_columns
    if unknown_columns:
        raise ValueError(
            f"Backup table {table!r} contains unknown columns: {sorted(unknown_columns)!r}"
        )

    for index, item in enumerate(rows):
        if not isinstance(item, dict):
            raise ValueError(f"Backup table {table!r} row {index} must be an object")
        columns = set(item)
        if columns != expected_columns:
            raise ValueError(
                f"Backup table {table!r} row {index} has inconsistent columns"
            )


@router.callback_query(F.data == "admin_search_user")
async def search_user_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await state.clear()
    await state.update_data(admin_search_type="user")
    await state.set_state(AdminStates.waiting_search)
    await callback.message.edit_text(
        "🔍 <b>بحث عن عميل</b>\n\n"
        "أرسل أحد البيانات التالية:\n"
        "• Telegram ID\n• @username\n• رقم الهاتف\n• اسم العميل\n• رقم/معرّف ShamCash",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_cancel_input")
        ]]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_backups")
async def backups_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await state.clear()
    pool = await get_pool()
    async with pool.acquire() as conn:
        counts = {table: await conn.fetchval(f"SELECT COUNT(*) FROM {table}") for table in BACKUP_TABLES}
    await callback.message.edit_text(
        "📋 <b>النسخ الاحتياطية والتصدير</b>\n\n"
        f"👤 المستخدمون: {counts['users']:,}\n"
        f"📦 الطلبات: {counts['orders']:,}\n"
        f"💱 أسعار الصرف: {counts['exchange_rates']:,}\n"
        f"📝 سجلات التدقيق: {counts['audit_logs']:,}\n"
        f"💳 وسائل الدفع: {counts['payment_methods']:,}\n"
        f"💬 الرسائل: {counts['feedback_messages']:,}\n\n"
        "النسخة تصدّر يدوياً كملف JSON حساس. لا تُحفظ النسخة داخل قاعدة البيانات ولا تتضمن أسرار البيئة أو الملفات الثنائية.",
        reply_markup=_backup_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_backup_export")
async def backup_export(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        tables = {}
        for table in BACKUP_TABLES:
            rows = await conn.fetch(f"SELECT * FROM {table} ORDER BY 1")
            tables[table] = [dict(row) for row in rows]
    payload = {
        "format": "al-manara-backup",
        "version": BACKUP_VERSION,
        "created_at": datetime.now().isoformat(),
        "tables": tables,
    }
    data = json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default).encode("utf-8")
    filename = f"al-manara-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    await callback.message.answer_document(
        BufferedInputFile(data, filename=filename),
        caption="📦 <b>نسخة Al-Manara الاحتياطية</b>\nتتضمن البيانات التشغيلية وقيم الإعدادات ومعرّفات ملفات Telegram المحفوظة.\n🔐 الملف حساس ويجب حفظه بأمان.",
        parse_mode="HTML",
    )
    await callback.answer("✅ تم تصدير النسخة")


@router.callback_query(F.data == "admin_backup_restore")
async def backup_restore_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    await state.clear()
    await state.update_data(admin_search_type="restore")
    await state.set_state(AdminStates.waiting_search)
    await callback.message.edit_text(
        "📥 <b>استعادة نسخة احتياطية</b>\n\n"
        "أرسل ملف <code>.json</code> صادر من Al-Manara.\n"
        "لن يتم حذف البيانات قبل تأكيد الاستعادة.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_cancel_input")
        ]]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminStates.waiting_search, F.document)
async def receive_restore_document(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("admin_search_type") != "restore":
        return
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    document = message.document
    if not document or not (document.file_name or "").lower().endswith(".json"):
        await message.answer("❌ أرسل ملف النسخة الاحتياطية JSON فقط.")
        return

    fd, path = tempfile.mkstemp(prefix="almanara_restore_", suffix=".json")
    os.close(fd)
    try:
        await message.bot.download(document.file_id, destination=path)
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("format") != "al-manara-backup" or payload.get("version") != BACKUP_VERSION:
            raise ValueError("unsupported backup format")
        tables = payload.get("tables")
        if not isinstance(tables, dict):
            raise ValueError("backup tables must be an object")
        missing = [table for table in BACKUP_TABLES if table not in tables]
        if missing:
            raise ValueError("missing tables: " + ", ".join(missing))

        pool = await get_pool()
        async with pool.acquire() as conn:
            schemas = {table: await _get_table_columns(conn, table) for table in BACKUP_TABLES}
            for table in BACKUP_TABLES:
                _validate_restore_rows(tables[table], schemas[table], table)
    except Exception as exc:
        try:
            os.remove(path)
        except OSError:
            pass
        logger.warning("Invalid restore upload: %s", exc)
        await message.answer("❌ ملف النسخة غير صالح أو غير متوافق مع هذا الإصدار.")
        return

    await state.update_data(restore_path=path)
    await message.answer(
        "⚠️ <b>تأكيد استعادة النسخة</b>\n\n"
        "الاستعادة ستستبدل بيانات الجداول التشغيلية الحالية بالنسخة المرفوعة.\n"
        "تأكد من الملف قبل المتابعة.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ نعم، استعادة الآن", callback_data="admin_backup_restore_confirm")],
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_backup_restore_cancel")],
        ]),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_backup_restore_cancel")
async def backup_restore_cancel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    data = await state.get_data()
    path = data.get("restore_path")
    if path:
        try:
            os.remove(path)
        except OSError:
            pass
    await state.clear()
    await callback.message.edit_text("❌ تم إلغاء الاستعادة.", reply_markup=admin_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_backup_restore_confirm")
async def backup_restore_confirm(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return
    data = await state.get_data()
    path = data.get("restore_path")
    if not path or not os.path.exists(path):
        await state.clear()
        await callback.answer("❌ ملف الاستعادة غير موجود. أعد رفعه.", show_alert=True)
        return

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "TRUNCATE TABLE users, orders, exchange_rates, audit_logs, blocked_users, feedback_messages, saved_addresses, payment_methods, bot_settings RESTART IDENTITY CASCADE"
                )
                await conn.execute("DELETE FROM maintenance_notification_jobs")
                for table in BACKUP_TABLES:
                    rows = payload["tables"][table]
                    if not rows:
                        continue
                    schema = await _get_table_columns(conn, table)
                    _validate_restore_rows(rows, schema, table)
                    columns = list(rows[0].keys())
                    placeholders = ", ".join(f"${i}" for i in range(1, len(columns) + 1))
                    quoted = ", ".join(f'"{column}"' for column in columns)
                    for item in rows:
                        values = [_restore_value(item.get(column), schema[column]) for column in columns]
                        await conn.execute(f"INSERT INTO {table} ({quoted}) VALUES ({placeholders})", *values)

                for table in SEQUENCE_TABLES:
                    await conn.execute(
                        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {table}"
                    )

        await SettingsService.reload()
        maintenance = await SettingsService.get_bool("maintenance_mode", False)
        Config.set_maintenance_mode_sync(maintenance)
        shamcash_name = await SettingsService.get("shamcash_name", "")
        shamcash_usd = await SettingsService.get("shamcash_usd", "")
        shamcash_syp = await SettingsService.get("shamcash_syp", "")
        if shamcash_name:
            Config.set_shamcash_name(shamcash_name)
        if shamcash_usd:
            Config.set_shamcash_usd(shamcash_usd)
        if shamcash_syp:
            Config.set_shamcash_syp(shamcash_syp)

        await callback.message.edit_text(
            "✅ <b>تمت استعادة النسخة بنجاح.</b>\n\nتم تحديث قاعدة البيانات وذاكرة الإعدادات الحالية. تأكد من تهيئة وسائل الدفع المعتمدة قبل استقبال طلبات جديدة.",
            reply_markup=admin_menu_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer("✅ تمت الاستعادة")
    except Exception:
        logger.exception("Database restore failed")
        await callback.message.edit_text(
            "❌ <b>فشلت استعادة النسخة.</b>\n\nلم يتم اعتماد استعادة جزئية؛ العملية داخل Transaction واحدة.",
            reply_markup=admin_menu_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer("❌ فشلت الاستعادة", show_alert=True)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
        await state.clear()
