"""Rate limiting service."""
import time
from typing import Dict
from collections import defaultdict


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)
        self._cooldowns: Dict[str, float] = {}

    def check(self, user_id: int, action: str = 'default') -> tuple:
        """Check if user is rate limited.

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

        # Set cooldown
        self._cooldowns[key] = now + Config.RATE_LIMIT_COOLDOWN

        return True, 0
