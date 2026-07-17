"""
Configuration store module.

All operational thresholds are stored in the PostgreSQL config table
and cached in memory with a configurable TTL. The config module is
the sole read/write path for configuration (FR-08).

Public exports:
  - CachedConfigService: the cache class
  - ConfigEntry: config entry dataclass
  - ConfigError, ConfigNotFound, InvalidConfigValue, ConfigCacheExpired: errors
  - STANDARD_CONFIG_KEYS: schema of required keys
  - get_cache(), set_cache(): access the global singleton cache
"""

from .cache import CachedConfigService, get_cache, set_cache
from .errors import ConfigCacheExpired, ConfigError, ConfigNotFound, InvalidConfigValue
from .models import ConfigEntry, STANDARD_CONFIG_KEYS

__all__ = [
    "CachedConfigService",
    "ConfigEntry",
    "ConfigError",
    "ConfigNotFound",
    "InvalidConfigValue",
    "ConfigCacheExpired",
    "STANDARD_CONFIG_KEYS",
    "get_cache",
    "set_cache",
]
