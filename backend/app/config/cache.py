"""
In-memory configuration cache with TTL and scenario overrides.

The cache holds all config values in memory after loading from the database,
with a configurable time-to-live (TTL). After TTL expires, a reload is
triggered. Scenario overrides allow tests/demos to temporarily change values
without modifying the persistent config.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional

from .errors import ConfigCacheExpired, ConfigNotFound, InvalidConfigValue
from .models import ConfigEntry, STANDARD_CONFIG_KEYS


class CachedConfigService:
    """
    In-memory config cache with TTL and scenario overrides.

    Behavior:
      * Load all config from database on init
      * Cache for TTL seconds; after expiry, on next access, reload
      * Scenario overrides: store temporary overrides per scope_id
      * Thread-safe via a lock
    """

    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize the cache.

        Args:
            ttl_seconds: Time-to-live for cached values (default 1 hour).
        """
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, ConfigEntry] = {}
        self._scenario_overrides: Dict[str, Dict[str, Any]] = {}  # scope_id -> {key: value}
        self._cache_loaded_at: Optional[datetime] = None
        self._lock = threading.Lock()

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def get(self, key: str, scope_id: Optional[str] = None) -> Any:
        """
        Get a config value by key.

        Returns the raw value (may need type conversion by caller).
        If a scenario override exists for (scope_id, key), return that.
        Otherwise return the cached value.

        Raises ConfigNotFound if key is not in cache.
        Raises ConfigCacheExpired if TTL has elapsed (caller must reload).
        """
        with self._lock:
            # Check cache expiry
            if self._cache_loaded_at is None:
                raise ConfigNotFound(key)
            if time.time() > self._cache_loaded_at.timestamp() + self.ttl_seconds:
                raise ConfigCacheExpired(self.ttl_seconds)

            # Check scenario override first
            if scope_id and scope_id in self._scenario_overrides:
                if key in self._scenario_overrides[scope_id]:
                    return self._scenario_overrides[scope_id][key]

            # Fall back to cache
            if key not in self._cache:
                raise ConfigNotFound(key)
            return self._cache[key].value

    def get_int(self, key: str, scope_id: Optional[str] = None) -> int:
        """Get a config value as an int."""
        value = self.get(key, scope_id)
        if isinstance(value, bool):
            raise InvalidConfigValue(key, "int", value)
        if not isinstance(value, int):
            raise InvalidConfigValue(key, "int", value)
        return value

    def get_float(self, key: str, scope_id: Optional[str] = None) -> float:
        """Get a config value as a float."""
        value = self.get(key, scope_id)
        if isinstance(value, bool):
            raise InvalidConfigValue(key, "float", value)
        try:
            return float(value)
        except (TypeError, ValueError):
            raise InvalidConfigValue(key, "float", value)

    def get_decimal(self, key: str, scope_id: Optional[str] = None) -> Decimal:
        """Get a config value as a Decimal."""
        value = self.get(key, scope_id)
        if isinstance(value, bool):
            raise InvalidConfigValue(key, "Decimal", value)
        try:
            return Decimal(str(value))
        except:
            raise InvalidConfigValue(key, "Decimal", value)

    def get_bool(self, key: str, scope_id: Optional[str] = None) -> bool:
        """Get a config value as a bool."""
        value = self.get(key, scope_id)
        if not isinstance(value, bool):
            raise InvalidConfigValue(key, "bool", value)
        return value

    def get_dict(self, key: str, scope_id: Optional[str] = None) -> dict:
        """Get a config value as a dict."""
        value = self.get(key, scope_id)
        if not isinstance(value, dict):
            raise InvalidConfigValue(key, "dict", value)
        return value

    def get_scoring_weights(self, scope_id: Optional[str] = None) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        """
        Get the four scoring weights as Decimals in order:
        (availability, lead_time, cost, waste_reduction).
        """
        return (
            self.get_decimal("scoring_weight_availability", scope_id),
            self.get_decimal("scoring_weight_lead_time", scope_id),
            self.get_decimal("scoring_weight_cost", scope_id),
            self.get_decimal("scoring_weight_waste_reduction", scope_id),
        )

    # -----------------------------------------------------------------------
    # Cache Management
    # -----------------------------------------------------------------------

    def load(self, entries: list[ConfigEntry]) -> None:
        """
        Load entries into the cache (typically called after reading from DB).

        Resets the TTL expiry clock. Thread-safe.
        """
        with self._lock:
            self._cache = {entry.key: entry for entry in entries}
            self._cache_loaded_at = datetime.utcnow()

    def is_expired(self) -> bool:
        """Check whether the cache TTL has expired."""
        with self._lock:
            if self._cache_loaded_at is None:
                return True
            return time.time() > self._cache_loaded_at.timestamp() + self.ttl_seconds

    def clear(self) -> None:
        """Clear all cached values (forces reload on next access)."""
        with self._lock:
            self._cache.clear()
            self._cache_loaded_at = None

    # -----------------------------------------------------------------------
    # Scenario Overrides (for testing/demo without modifying persistent config)
    # -----------------------------------------------------------------------

    def set_scenario_override(self, scope_id: str, key: str, value: Any) -> None:
        """
        Set a temporary override for a key within a scope (e.g., scenario run).

        All gets within that scope return the override until cleared.
        Thread-safe.
        """
        with self._lock:
            if scope_id not in self._scenario_overrides:
                self._scenario_overrides[scope_id] = {}
            self._scenario_overrides[scope_id][key] = value

    def clear_scenario_overrides(self, scope_id: str) -> None:
        """
        Clear all overrides for a scope.

        Subsequent gets will return the base config values.
        """
        with self._lock:
            self._scenario_overrides.pop(scope_id, None)

    def get_active_overrides(self, scope_id: str) -> dict:
        """Return the active overrides for a scope (for inspection)."""
        with self._lock:
            return self._scenario_overrides.get(scope_id, {}).copy()


# Global singleton instance (initialized by the module's init())
_cache_instance: Optional[CachedConfigService] = None


def get_cache() -> CachedConfigService:
    """Return the global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CachedConfigService()
    return _cache_instance


def set_cache(instance: CachedConfigService) -> None:
    """Replace the global cache instance (for testing)."""
    global _cache_instance
    _cache_instance = instance
