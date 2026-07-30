"""Rate limiting service with per-action cooldowns."""
import time
from typing import Dict
from collections import defaultdict


# Action-specific cooldowns (seconds)
# Sensitive actions get longer cooldowns to prevent abuse
ACTION_COOLDOWNS = {
    'default': 0,           # Navigation / clicks — instant
    'order_network': 1,     # Network selection
    'order_amount': 1,      # Amount input
    'order_wallet': 2,      # Wallet address input
    'order_confirm': 3,     # Order confirmation
    'receipt_upload': 5,    # Receipt upload
    'feedback': 10,         # Feedback submission
    'admin_action': 0,      # Admin actions — always instant
}


class RateLimiter:
    """In-memory rate limiter with per-action cooldowns."""

    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)
        self._cooldowns: Dict[str, float] = {}

    def check(self, user_id: int, action: str = 'default') -> tuple:
        """Check if user is rate limited.

        Args:
            user_id: Telegram user ID.
            action: Action type — determines cooldown length.

        Returns:
            (allowed: bool, wait_seconds: int)
        """
        now = time.time()
        key = f"{user_id}:{action}"

        # Check cooldown
        if key in self._cooldowns:
            if now < self._cooldowns[key]:
                wait = int(self._cooldowns[key] - now)
                return False, wait

        # Clean old requests
        self._requests[key] = [
            req_time for req_time in self._requests[key]
            if now - req_time < 3600  # 1 hour window
        ]

        # Check hourly limit
        from config import Config
        if len(self._requests[key]) >= Config.RATE_LIMIT_HOURLY:
            return False, 3600

        # Check daily limit
        daily_key = f"{user_id}:daily"
        daily_requests = [
            req_time for req_time in self._requests.get(daily_key, [])
            if now - req_time < 86400  # 24 hours
        ]

        if len(daily_requests) >= Config.RATE_LIMIT_DAILY:
            return False, 86400

        # Record request
        self._requests[key].append(now)
        self._requests[daily_key].append(now)

        # Set cooldown based on action type
        cooldown = ACTION_COOLDOWNS.get(action, Config.RATE_LIMIT_COOLDOWN)
        self._cooldowns[key] = now + cooldown

        return True, 0
