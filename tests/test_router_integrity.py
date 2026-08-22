"""Static checks for accidental duplicate callback handlers."""

import re
from pathlib import Path


HANDLERS_DIR = Path(__file__).resolve().parents[1] / "handlers"
CALLBACK_RE = re.compile(r"@router\.callback_query\((.*?)\)", re.DOTALL)
# menu.py remains a deliberately registered compatibility router for legacy
# customer UI callbacks. Authoritative policy routers are registered before it
# and own the guarded implementations. It is therefore excluded from the
# duplicate-authority check below; removing it requires migrating its remaining
# unique UI callbacks first.
LEGACY_COMPATIBILITY_FILES = {"menu.py"}


def _callback_signatures():
    signatures = {}
    for path in HANDLERS_DIR.glob("*.py"):
        if path.name in LEGACY_COMPATIBILITY_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        for match in CALLBACK_RE.finditer(text):
            expression = " ".join(match.group(1).split())
            signatures.setdefault(expression, []).append(path.name)
    return signatures


def test_no_exact_duplicate_callback_decorators_across_authoritative_handlers():
    duplicates = {
        expression: files
        for expression, files in _callback_signatures().items()
        if len(set(files)) > 1
        and "startswith" not in expression
        and "in_" not in expression
    }
    assert not duplicates, "Duplicate exact callback decorators: " + repr(duplicates)


def test_retired_monolithic_order_handler_is_absent():
    assert not (HANDLERS_DIR / "order.py").exists()


def test_admin_facade_does_not_nest_directly_registered_policies():
    text = (HANDLERS_DIR / "admin.py").read_text(encoding="utf-8")
    for policy in (
        "admin_tools_policy",
        "admin_search_policy",
        "admin_approval_policy",
        "admin_rejection_policy",
        "admin_note_policy",
        "admin_payment_confirmation_policy",
        "admin_transfer_policy",
    ):
        assert policy not in text, policy
