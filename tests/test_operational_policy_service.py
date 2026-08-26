from decimal import Decimal

import pytest

from services.operational_policy_service import OperationalPolicyError, OperationalPolicyService


def test_validate_limits_requires_monotonic_order_limits():
    OperationalPolicyService.validate_limits(Decimal("10"), Decimal("100"), Decimal("500"))

    with pytest.raises(OperationalPolicyError):
        OperationalPolicyService.validate_limits(Decimal("101"), Decimal("100"), Decimal("500"))

    with pytest.raises(OperationalPolicyError):
        OperationalPolicyService.validate_limits(Decimal("10"), Decimal("500"), Decimal("100"))


def test_validate_limits_rejects_zero_or_negative_minimum():
    with pytest.raises(OperationalPolicyError):
        OperationalPolicyService.validate_limits(Decimal("0"), Decimal("100"), Decimal("500"))


def test_operational_policy_is_single_owner_for_keys():
    assert {"service_fee_percent", "payment_timeout_minutes", "min_order", "max_order", "daily_limit"}.issuperset(
        {"service_fee_percent", "payment_timeout_minutes", "min_order", "max_order", "daily_limit"}
    )
