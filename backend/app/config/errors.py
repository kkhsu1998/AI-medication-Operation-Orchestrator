"""
Typed errors for the configuration module.
"""

from __future__ import annotations


class ConfigError(RuntimeError):
    """Base exception for configuration module errors."""


class ConfigNotFound(ConfigError):
    """Raised when a required config key is not found."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(f"Config key not found: {key!r}")


class InvalidConfigValue(ConfigError):
    """Raised when a config value is invalid for the expected type."""

    def __init__(self, key: str, expected_type: str, actual_value: object):
        self.key = key
        self.expected_type = expected_type
        self.actual_value = actual_value
        super().__init__(
            f"Config key {key!r}: expected {expected_type}, "
            f"got {type(actual_value).__name__}: {actual_value!r}"
        )


class ConfigCacheExpired(ConfigError):
    """Raised when the config cache TTL has expired and must be reloaded."""

    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        super().__init__(f"Config cache expired (TTL: {ttl_seconds}s)")
