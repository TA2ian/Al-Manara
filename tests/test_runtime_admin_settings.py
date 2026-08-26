"""Regression coverage for runtime operational policies used by new orders."""
import inspect

from handlers import order_amount_policy, order_confirmation_policy
from services.operational_policy_service import OperationalPolicyService


def test_order_limits_are_loaded_from_single_operational_policy_owner():
    source = inspect.getsource(order_amount_policy)
    assert "OperationalPolicyService" in source
    assert '"min_order"' in source
    assert '"max_order"' in source
    assert '"daily_limit"' in source


def test_payment_timeout_is_loaded_from_single_operational_policy_owner():
    source = inspect.getsource(order_confirmation_policy)
    assert "OperationalPolicyService" in source
    assert "get_payment_timeout_minutes()" in source


def test_operational_policy_exposes_runtime_order_limits_and_timeout():
    assert callable(OperationalPolicyService.get_limits)
    assert callable(OperationalPolicyService.get_payment_timeout_minutes)
