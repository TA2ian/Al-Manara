"""Canonical operational policy service for fees, deadlines and order limits."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from config import Config
from database import get_pool
from services.network_fee_policy import SUPPORTED_NETWORKS, NetworkFeePolicy, parse_non_negative_decimal
from services.settings_service import SettingsService

MONEY_QUANT = Decimal("0.01")


class OperationalPolicyError(ValueError):
    """Raised when an operational policy value violates domain rules."""


class OperationalPolicyService:
    """Single runtime authority for network-specific fees and operational limits."""

    @staticmethod
    def _decimal(value: object, default: Decimal) -> Decimal:
        try:
            parsed = value if isinstance(value, Decimal) else Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return default
        return parsed

    @staticmethod
    def _normalize_network(network: str | None) -> str:
        value = (network or "").strip().upper()
        aliases = {"ERC20": "ETH", "ETHEREUM": "ETH", "ARBITRUM": "ARB", "SOL": "SOLANA", "MATIC": "POLYGON", "POL": "POLYGON"}
        return aliases.get(value, value)

    @classmethod
    async def get_network_fee_policy(cls, network: str) -> NetworkFeePolicy:
        normalized = cls._normalize_network(network)
        if normalized not in SUPPORTED_NETWORKS:
            raise OperationalPolicyError("Unknown fee network")
        service_raw = await SettingsService.get(f"service_fee_percent_{normalized.lower()}", str(Config.SERVICE_FEE_PERCENT))
        fixed_raw = await SettingsService.get(f"fixed_network_fee_usdt_{normalized.lower()}", str(Config.SERVICE_FEE_FIXED))
        service = parse_non_negative_decimal(service_raw, "service_fee_percent")
        fixed = parse_non_negative_decimal(fixed_raw, "fixed_network_fee_usdt")
        if service > Decimal("100"):
            raise OperationalPolicyError("service_fee_percent cannot exceed 100")
        return NetworkFeePolicy(normalized, service, fixed)

    @classmethod
    async def get_fee_percent(cls, network: str | None = None) -> Decimal:
        if network is None:
            return Decimal("0")
        return (await cls.get_network_fee_policy(network)).service_fee_percent

    @classmethod
    async def get_fixed_fee_usdt(cls, network: str | None = None) -> Decimal:
        if network is None:
            return Decimal("0")
        return (await cls.get_network_fee_policy(network)).fixed_network_fee_usdt

    @classmethod
    async def get_all_fee_percents(cls) -> dict[str, Decimal]:
        return {network: (await cls.get_network_fee_policy(network)).service_fee_percent for network in SUPPORTED_NETWORKS}

    @classmethod
    async def set_fee_percent(cls, value: object, admin_id: int, network: str | None = None) -> Decimal:
        normalized = cls._normalize_network(network)
        if normalized not in SUPPORTED_NETWORKS:
            raise OperationalPolicyError("Unknown fee network")
        parsed = parse_non_negative_decimal(value, "service_fee_percent")
        if parsed > Decimal("100"):
            raise OperationalPolicyError("service_fee_percent cannot exceed 100")
        previous = await SettingsService.get(f"service_fee_percent_{normalized.lower()}", str(Config.SERVICE_FEE_PERCENT))
        await SettingsService.set(f"service_fee_percent_{normalized.lower()}", str(parsed))
        await cls._audit(admin_id, "setting_update", "service_fee_percent", previous, str(parsed), f"Updated service fee [{normalized}]")
        return parsed

    @classmethod
    async def set_fixed_fee_usdt(cls, value: object, admin_id: int, network: str) -> Decimal:
        normalized = cls._normalize_network(network)
        if normalized not in SUPPORTED_NETWORKS:
            raise OperationalPolicyError("Unknown fee network")
        parsed = parse_non_negative_decimal(value, "fixed_network_fee_usdt").quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        previous = await SettingsService.get(f"fixed_network_fee_usdt_{normalized.lower()}", str(Config.SERVICE_FEE_FIXED))
        await SettingsService.set(f"fixed_network_fee_usdt_{normalized.lower()}", str(parsed))
        await cls._audit(admin_id, "setting_update", "fixed_network_fee_usdt", previous, str(parsed), f"Updated fixed network fee [{normalized}]")
        return parsed

    @classmethod
    async def get_payment_timeout_minutes(cls) -> int:
        raw = await SettingsService.get("payment_timeout_minutes", str(Config.PAYMENT_TIMEOUT))
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = int(Config.PAYMENT_TIMEOUT)
        return max(1, min(value, 1440))

    @classmethod
    async def get_limits(cls) -> dict[str, Decimal]:
        minimum = cls._decimal(await SettingsService.get("min_order", str(Config.MIN_ORDER)), cls._decimal(Config.MIN_ORDER, Decimal("0")))
        maximum = cls._decimal(await SettingsService.get("max_order", str(Config.MAX_ORDER)), cls._decimal(Config.MAX_ORDER, Decimal("0")))
        daily = cls._decimal(await SettingsService.get("daily_limit", str(Config.DAILY_LIMIT)), cls._decimal(Config.DAILY_LIMIT, Decimal("0")))
        return {"min_order": minimum, "max_order": maximum, "daily_limit": daily}

    @staticmethod
    def validate_limits(minimum: Decimal, maximum: Decimal, daily: Decimal) -> None:
        if minimum <= 0:
            raise OperationalPolicyError("Minimum order must be greater than zero")
        if maximum < minimum:
            raise OperationalPolicyError("Maximum order cannot be below minimum order")
        if daily < maximum:
            raise OperationalPolicyError("Daily limit cannot be below maximum order")

    @classmethod
    async def set_payment_timeout(cls, value: object, admin_id: int) -> int:
        try:
            timeout = int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise OperationalPolicyError("Payment timeout must be an integer") from exc
        if timeout < 1 or timeout > 1440:
            raise OperationalPolicyError("Payment timeout must be between 1 and 1440 minutes")
        previous = await SettingsService.get("payment_timeout_minutes", str(Config.PAYMENT_TIMEOUT))
        await SettingsService.set("payment_timeout_minutes", str(timeout))
        await cls._audit(admin_id, "setting_update", "payment_timeout_minutes", previous, str(timeout), "Updated payment deadline policy")
        return timeout

    @classmethod
    async def set_limit(cls, key: str, value: object, admin_id: int) -> Decimal:
        if key not in {"min_order", "max_order", "daily_limit"}:
            raise OperationalPolicyError("Unknown limit key")
        try:
            parsed = Decimal(str(value).strip().replace(",", ""))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise OperationalPolicyError("Limit must be a valid number") from exc
        if not parsed.is_finite():
            raise OperationalPolicyError("Limit must be finite")
        current = await cls.get_limits()
        candidate = dict(current)
        candidate[key] = parsed
        cls.validate_limits(candidate["min_order"], candidate["max_order"], candidate["daily_limit"])
        parsed = parsed.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        previous = str(current[key])
        await SettingsService.set(key, str(parsed))
        await cls._audit(admin_id, "setting_update", "limit", previous, str(parsed), f"Updated order limit policy [{key}]")
        return parsed

    @staticmethod
    async def _audit(admin_id: int, action: str, key: str, previous: str | None, new_value: str, details: str) -> None:
        pool = await get_pool()
        if not pool:
            return
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO audit_logs (admin_id, action, details, previous_value, new_value, severity)
                   VALUES ($1, $2, $3, $4, $5, 'info')""",
                admin_id, action, details + f" [{key}]", previous, new_value,
            )
