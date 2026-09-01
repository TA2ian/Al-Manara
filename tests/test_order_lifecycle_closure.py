from services.order_state_service import ALLOWED_TRANSITIONS, ALLOWED_ORDER_UPDATE_FIELDS


def test_closed_without_fulfillment_is_a_terminal_state():
    assert ALLOWED_TRANSITIONS["closed_without_fulfillment"] == frozenset()


def test_only_payment_confirmed_can_enter_administrative_closure():
    assert "closed_without_fulfillment" in ALLOWED_TRANSITIONS["payment_confirmed"]
    for status, transitions in ALLOWED_TRANSITIONS.items():
        if status != "payment_confirmed":
            assert "closed_without_fulfillment" not in transitions


def test_administrative_closure_cannot_bypass_fulfillment_lifecycle():
    assert "completed" in ALLOWED_TRANSITIONS["payment_confirmed"]
    assert "closed_without_fulfillment" in ALLOWED_TRANSITIONS["payment_confirmed"]
    assert "completed" not in ALLOWED_TRANSITIONS["closed_without_fulfillment"]
    assert "payment_confirmed" not in ALLOWED_TRANSITIONS["closed_without_fulfillment"]


def test_closure_reason_is_storable_as_admin_notes():
    assert "admin_notes" in ALLOWED_ORDER_UPDATE_FIELDS
