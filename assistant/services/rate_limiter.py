"""
Cache-based User Rate Limiter for NyayaSahayak.
Enforces a configurable ceiling (e.g. 20 requests/hour) per authenticated user.
"""

import time
from django.core.cache import cache
from django.conf import settings


def is_rate_limited(user_id: int) -> bool:
    """
    Returns True if user has exceeded the hourly question allowance.
    """
    limit = getattr(settings, 'ASK_RATE_LIMIT_PER_HOUR', 20)
    cache_key = f"rate_limit_ask_{user_id}"

    # Get list of timestamps from cache
    timestamps = cache.get(cache_key, [])
    now = time.time()
    one_hour_ago = now - 3600

    # Filter timestamps within the last hour
    recent = [t for t in timestamps if t > one_hour_ago]

    if len(recent) >= limit:
        return True

    recent.append(now)
    cache.set(cache_key, recent, timeout=3600)
    return False


def get_remaining_requests(user_id: int) -> int:
    """
    Returns remaining requests allowed for user in current hour window.
    """
    limit = getattr(settings, 'ASK_RATE_LIMIT_PER_HOUR', 20)
    cache_key = f"rate_limit_ask_{user_id}"
    timestamps = cache.get(cache_key, [])
    now = time.time()
    recent = [t for t in timestamps if t > (now - 3600)]
    return max(0, limit - len(recent))

