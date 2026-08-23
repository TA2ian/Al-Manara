"""Static checks for accidental duplicate callback handlers."""

import re
from pathlib import Path


HANDLERS_DIR = Path(__file__).resolve().parents[1] / "handlers"
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
    root = HANDLERS_DIR.parent
    for relative_path in (
        "handlers/order.py",
        "handlers/menu.py",
        "handlers/admin.py",
        "handlers/admin_settings_alias_policy.py",
        "handlers/legacy_wallet_guard.py",
        "services/order_wallet_guard.py",
    ):
        assert not (root / relative_path).exists()
