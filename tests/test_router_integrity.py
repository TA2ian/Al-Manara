"""Static checks for accidental duplicate callback and infrastructure handlers."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDLERS_DIR = ROOT / "handlers"
CALLBACK_RE = re.compile(r"@router\.callback_query\((.*?)\)", re.DOTALL)


def _callback_signatures():
    signatures = {}
    for path in HANDLERS_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in CALLBACK_RE.finditer(text):
            expression = " ".join(match.group(1).split())
            signatures.setdefault(expression, []).append(path.name)
    return signatures


def test_no_exact_duplicate_callback_decorators_across_handlers():
    duplicates = {
        expression: files
        for expression, files in _callback_signatures().items()
        if len(set(files)) > 1
        and "startswith" not in expression
        and "in_" not in expression
    }
    assert not duplicates, "Duplicate exact callback decorators: " + repr(duplicates)


def test_retired_compatibility_modules_are_absent():
    for relative_path in (
        "handlers/order.py",
        "handlers/menu.py",
        "handlers/admin.py",
        "handlers/admin_settings_alias_policy.py",
        "handlers/legacy_wallet_guard.py",
        "services/order_wallet_guard.py",
        "database_wallet_guards.py",
    ):
        assert not (ROOT / relative_path).exists()


def test_payment_snapshot_trigger_has_one_canonical_authority():
    database_source = (ROOT / "database.py").read_text(encoding="utf-8")
    constraints_source = (ROOT / "database_order_constraints.py").read_text(encoding="utf-8")
    assert "CREATE OR REPLACE FUNCTION snapshot_order_payment_method" not in database_source
    assert "CREATE OR REPLACE FUNCTION snapshot_order_payment_method" in constraints_source
    assert "CREATE TRIGGER trg_snapshot_order_payment_method" in constraints_source
    assert "from database_order_constraints import install_order_constraints" in database_source
    assert "await install_order_constraints(conn)" in database_source
