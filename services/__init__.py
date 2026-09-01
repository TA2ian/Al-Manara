"""Services package with lazy exports for database-dependent services."""
from .locale_service import locale_service
from .wallet_validator import WalletValidator
from .rate_limiter import RateLimiter

__all__ = [
    "locale_service",
    "WalletValidator",
    "ExchangeService",
    "RateLimiter",
    "NotificationService",
]


def __getattr__(name: str):
    """Load services that depend on database modules only when requested."""
    if name == "ExchangeService":
        from .exchange_service import ExchangeService
        return ExchangeService
    if name == "NotificationService":
        from .notification_service import NotificationService
        return NotificationService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
