import asyncio
from decimal import Decimal

from services.operational_policy_service import OperationalPolicyService, SUPPORTED_FEE_NETWORKS
from services.settings_service import SettingsService


def test_fee_policy_has_independent_network_keys():
    assert set(SUPPORTED_FEE_NETWORKS) == {"BEP20", "TRC20", "TON", "ARB", "SOLANA", "ETH"}
    SettingsService._cache = {f"service_fee_percent_{network.lower()}": str(index) for index, network in enumerate(SUPPORTED_FEE_NETWORKS, start=1)}
    SettingsService._initialized = True
    values = asyncio.run(OperationalPolicyService.get_all_fee_percents())
    assert values["BEP20"] == Decimal("1")
    assert values["ETH"] == Decimal("6")
