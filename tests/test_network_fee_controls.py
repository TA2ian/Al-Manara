import asyncio
from decimal import Decimal
from unittest.mock import patch

import pytest

from services.network_fee_policy import AMOUNT_TOLERANCE_USDT, NetworkFeePolicy, amount_within_tolerance
from services.operational_policy_service import OperationalPolicyError, OperationalPolicyService
from services.settings_service import SettingsService


async def cache_setting(key: str, value: str):
    SettingsService._cache[key] = value
    SettingsService._initialized = True


def test_supported_fee_networks_are_canonical():
    assert set(OperationalPolicyService._normalize_network(network) for network in ("BEP20", "TRC20", "ARB", "SOLANA", "ETH", "POLYGON")) == {"BEP20", "TRC20", "ARB", "SOLANA", "ETH", "POLYGON"}


def test_network_policy_calculates_percentage_and_fixed_fee_independently():
    policy = NetworkFeePolicy("BEP20", Decimal("10"), Decimal("0.20"))
    result = policy.calculate(Decimal("100"))
    assert result["service_fee_usdt"] == Decimal("10.00")
    assert result["fixed_network_fee_usdt"] == Decimal("0.20")
    assert result["total_fee_usdt"] == Decimal("10.20")
    assert result["net_amount_usdt"] == Decimal("89.80")


def test_amount_tolerance_is_not_a_fee():
    assert AMOUNT_TOLERANCE_USDT == Decimal("0.04")
    assert amount_within_tolerance(Decimal("100.04"), Decimal("100.00"))
    assert amount_within_tolerance(Decimal("99.96"), Decimal("100.00"))
    assert not amount_within_tolerance(Decimal("100.05"), Decimal("100.00"))
    assert not amount_within_tolerance(Decimal("99.95"), Decimal("100.00"))


def test_percentage_fee_accepts_zero_to_one_hundred_only():
    SettingsService._cache = {"service_fee_percent_bep20": "10", "fixed_network_fee_usdt_bep20": "0.20"}
    SettingsService._initialized = True
    with patch.object(SettingsService, "set", new=cache_setting):
        assert asyncio.run(OperationalPolicyService.set_fee_percent("12.5", 123, network="BEP20")) == Decimal("12.5")
        with pytest.raises(OperationalPolicyError, match="cannot exceed 100"):
            asyncio.run(OperationalPolicyService.set_fee_percent("100.01", 123, network="BEP20"))


def test_fixed_network_fee_can_be_changed_per_network():
    SettingsService._cache = {"service_fee_percent_bep20": "10", "fixed_network_fee_usdt_bep20": "0.20"}
    SettingsService._initialized = True
    with patch.object(SettingsService, "set", new=cache_setting):
        assert asyncio.run(OperationalPolicyService.set_fixed_fee_usdt("0.75", 123, network="BEP20")) == Decimal("0.75")
        assert asyncio.run(OperationalPolicyService.get_fixed_fee_usdt("BEP20")) == Decimal("0.75")


def test_polygon_aliases_normalize_to_polygon():
    assert OperationalPolicyService._normalize_network("POLYGON") == "POLYGON"
    assert OperationalPolicyService._normalize_network("POL") == "POLYGON"
    assert OperationalPolicyService._normalize_network("MATIC") == "POLYGON"
