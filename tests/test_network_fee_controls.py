import asyncio
from decimal import Decimal

import pytest

from services.operational_policy_service import FIXED_SERVICE_FEE_USDT, OperationalPolicyError, OperationalPolicyService, SUPPORTED_FEE_NETWORKS
from services.settings_service import SettingsService


def test_fee_policy_is_fixed_across_all_supported_networks():
    assert set(SUPPORTED_FEE_NETWORKS) == {"BEP20", "TRC20", "ARB", "SOLANA", "ETH", "POLYGON"}
    SettingsService._cache = {f"service_fee_percent_{network.lower()}": str(index) for index, network in enumerate(SUPPORTED_FEE_NETWORKS, start=1)}
    SettingsService._initialized = True
    values = asyncio.run(OperationalPolicyService.get_all_fee_percents())
    assert all(value == Decimal("0") for value in values.values())
    for network in SUPPORTED_FEE_NETWORKS:
        assert asyncio.run(OperationalPolicyService.get_fixed_fee_usdt(network)) == FIXED_SERVICE_FEE_USDT


def test_percentage_fee_configuration_is_disabled():
    with pytest.raises(OperationalPolicyError, match=r"fixed at 0\.04 USDT"):
        asyncio.run(OperationalPolicyService.set_fee_percent(10, 123, network="BEP20"))


def test_polygon_aliases_normalize_to_polygon():
    assert OperationalPolicyService._normalize_network("POLYGON") == "POLYGON"
    assert OperationalPolicyService._normalize_network("POL") == "POLYGON"
    assert OperationalPolicyService._normalize_network("MATIC") == "POLYGON"
