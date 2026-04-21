"""Simple in-memory cache for stable reference data.

This module provides a lightweight caching mechanism for data that rarely changes,
such as departments and task categories. Cache entries have a TTL (time-to-live)
and are automatically invalidated after expiry.
"""

import asyncio
from typing import TypeVar

T = TypeVar("T")


class SimpleAsyncCache:
    """Simple in-memory cache with TTL support.

    This cache is designed for use in async contexts and is thread-safe
    through asyncio locks. It's suitable for small-scale applications.

    For larger deployments, consider using Redis or a dedicated caching service.
    """

    def __init__(self, default_ttl: int = 300):
        """Initialize the cache.

        Args:
            default_ttl: Default time-to-live in seconds (default: 5 minutes)
        """
        self._cache: dict[str, tuple[T, float]] = {}
        self._ttl = default_ttl
        self._lock = asyncio.Lock()
        self._disabled = False  # Flag to disable caching (useful for tests)

    async def get(self, key: str) -> T | None:
        """Get a value from the cache.

        Args:
            key: Cache key to retrieve

        Returns:
            Cached value if present and not expired, None otherwise
            Returns None immediately if cache is disabled
        """
        if self._disabled:
            return None
        async with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if expiry > asyncio.get_running_loop().time():
                    return value
                # Entry expired, remove it
                del self._cache[key]
        return None

    async def set(self, key: str, value: T, ttl: int | None = None) -> None:
        """Set a value in the cache.

        Args:
            key: Cache key to set
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        if self._disabled:
            return
        async with self._lock:
            expiry = asyncio.get_running_loop().time() + (ttl or self._ttl)
            self._cache[key] = (value, expiry)

    async def invalidate(self, key: str) -> None:
        """Invalidate a specific cache entry.

        Args:
            key: Cache key to invalidate
        """
        if self._disabled:
            return
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        """Clear all cache entries."""
        if self._disabled:
            return
        async with self._lock:
            self._cache.clear()

    def disable(self) -> None:
        """Disable caching and clear all existing entries (useful for tests)."""
        self._disabled = True
        self._cache.clear()

    def enable(self) -> None:
        """Enable caching."""
        self._disabled = False


# Global cache instances for different data types
# These are created at module import time and shared across the application

# Cache for active departments (updated when departments are created/updated/deactivated)
departments_cache = SimpleAsyncCache(default_ttl=300)

# Cache for active task categories (updated when categories are created/updated/deactivated)
categories_cache = SimpleAsyncCache(default_ttl=300)
