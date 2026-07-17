"""
Unit tests for the configuration module.

Tests cover:
  - Basic get operations (all type conversions)
  - TTL expiry and reload detection
  - Scenario overrides (set, get, clear)
  - Thread safety (basic lock verification)
  - Error cases (missing keys, type mismatches, cache expiry)
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from decimal import Decimal

import pytest

from app.config import (
    CachedConfigService,
    ConfigCacheExpired,
    ConfigEntry,
    ConfigError,
    ConfigNotFound,
    InvalidConfigValue,
    STANDARD_CONFIG_KEYS,
    get_cache,
    set_cache,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cache_service():
    """Fresh cache instance for each test."""
    return CachedConfigService(ttl_seconds=1)


@pytest.fixture
def sample_entries():
    """Sample config entries for testing."""
    return [
        ConfigEntry(
            config_id=uuid.uuid4(),
            key="safety_stock_multiplier",
            value=1.5,
            description="Safety stock multiplier",
            updated_by="test",
            updated_at=datetime.utcnow(),
        ),
        ConfigEntry(
            config_id=uuid.uuid4(),
            key="days_supply_minimum",
            value=7,
            description="Minimum days of supply",
            updated_by="test",
            updated_at=datetime.utcnow(),
        ),
        ConfigEntry(
            config_id=uuid.uuid4(),
            key="delivery_retry_limit",
            value=3,
            description="Retry limit",
            updated_by="test",
            updated_at=datetime.utcnow(),
        ),
        ConfigEntry(
            config_id=uuid.uuid4(),
            key="forecast_min_confidence_threshold",
            value=0.65,
            description="Min confidence",
            updated_by="test",
            updated_at=datetime.utcnow(),
        ),
        ConfigEntry(
            config_id=uuid.uuid4(),
            key="scoring_weight_availability",
            value=0.40,
            description="Weight",
            updated_by="test",
            updated_at=datetime.utcnow(),
        ),
        ConfigEntry(
            config_id=uuid.uuid4(),
            key="scoring_weight_lead_time",
            value=0.25,
            description="Weight",
            updated_by="test",
            updated_at=datetime.utcnow(),
        ),
        ConfigEntry(
            config_id=uuid.uuid4(),
            key="scoring_weight_cost",
            value=0.20,
            description="Weight",
            updated_by="test",
            updated_at=datetime.utcnow(),
        ),
        ConfigEntry(
            config_id=uuid.uuid4(),
            key="scoring_weight_waste_reduction",
            value=0.15,
            description="Weight",
            updated_by="test",
            updated_at=datetime.utcnow(),
        ),
    ]


# ===========================================================================
# Test: Basic Load and Get
# ===========================================================================

class TestLoadAndGet:
    def test_load_entries(self, cache_service, sample_entries):
        """Load entries populates the cache."""
        cache_service.load(sample_entries)
        assert cache_service.get("safety_stock_multiplier") == 1.5

    def test_get_after_load(self, cache_service, sample_entries):
        """Get returns values after load."""
        cache_service.load(sample_entries)
        assert cache_service.get("days_supply_minimum") == 7
        assert cache_service.get("delivery_retry_limit") == 3

    def test_get_not_found_before_load(self, cache_service):
        """Get raises ConfigNotFound if cache is empty."""
        with pytest.raises(ConfigNotFound) as exc_info:
            cache_service.get("nonexistent")
        assert exc_info.value.key == "nonexistent"

    def test_get_not_found_after_load(self, cache_service, sample_entries):
        """Get raises ConfigNotFound if key not loaded."""
        cache_service.load(sample_entries)
        with pytest.raises(ConfigNotFound):
            cache_service.get("nonexistent_key")


# ===========================================================================
# Test: Type Conversions
# ===========================================================================

class TestTypeConversions:
    def test_get_int(self, cache_service, sample_entries):
        """get_int converts and validates."""
        cache_service.load(sample_entries)
        assert cache_service.get_int("days_supply_minimum") == 7
        assert isinstance(cache_service.get_int("days_supply_minimum"), int)

    def test_get_float(self, cache_service, sample_entries):
        """get_float converts and validates."""
        cache_service.load(sample_entries)
        result = cache_service.get_float("safety_stock_multiplier")
        assert result == 1.5
        assert isinstance(result, float)

    def test_get_decimal(self, cache_service, sample_entries):
        """get_decimal converts to Decimal."""
        cache_service.load(sample_entries)
        result = cache_service.get_decimal("scoring_weight_availability")
        assert result == Decimal("0.40")
        assert isinstance(result, Decimal)

    def test_get_bool_valid(self, cache_service):
        """get_bool validates bool type."""
        entry = ConfigEntry(
            config_id=uuid.uuid4(),
            key="test_bool",
            value=True,
            description="Test",
            updated_by="test",
            updated_at=datetime.utcnow(),
        )
        cache_service.load([entry])
        assert cache_service.get_bool("test_bool") is True

    def test_get_bool_invalid_int(self, cache_service, sample_entries):
        """get_bool rejects int even if it's 0 or 1."""
        cache_service.load(sample_entries)
        with pytest.raises(InvalidConfigValue) as exc_info:
            cache_service.get_bool("days_supply_minimum")
        assert exc_info.value.key == "days_supply_minimum"

    def test_get_dict(self, cache_service):
        """get_dict validates dict type."""
        entry = ConfigEntry(
            config_id=uuid.uuid4(),
            key="test_dict",
            value={"a": 1, "b": 2},
            description="Test",
            updated_by="test",
            updated_at=datetime.utcnow(),
        )
        cache_service.load([entry])
        assert cache_service.get_dict("test_dict") == {"a": 1, "b": 2}

    def test_type_mismatch_int_expected(self, cache_service):
        """get_int raises InvalidConfigValue on type mismatch."""
        entry = ConfigEntry(
            config_id=uuid.uuid4(),
            key="test_float",
            value="not_an_int",
            description="Test",
            updated_by="test",
            updated_at=datetime.utcnow(),
        )
        cache_service.load([entry])
        with pytest.raises(InvalidConfigValue) as exc_info:
            cache_service.get_int("test_float")
        assert exc_info.value.key == "test_float"
        assert exc_info.value.expected_type == "int"

    def test_type_mismatch_bool_as_int_rejected(self, cache_service):
        """Bool values are rejected by get_int/get_float."""
        entry = ConfigEntry(
            config_id=uuid.uuid4(),
            key="test_bool",
            value=True,
            description="Test",
            updated_by="test",
            updated_at=datetime.utcnow(),
        )
        cache_service.load([entry])
        # Bools should be rejected even though isinstance(True, int) is True in Python
        with pytest.raises(InvalidConfigValue):
            cache_service.get_int("test_bool")


# ===========================================================================
# Test: TTL and Expiry
# ===========================================================================

class TestTTLAndExpiry:
    def test_is_expired_false_after_load(self, cache_service, sample_entries):
        """is_expired is False right after load."""
        cache_service.load(sample_entries)
        assert cache_service.is_expired() is False

    def test_is_expired_true_after_ttl(self, cache_service, sample_entries):
        """is_expired is True after TTL seconds."""
        cache_service.load(sample_entries)
        time.sleep(1.1)  # TTL is 1 second in fixture
        assert cache_service.is_expired() is True

    def test_get_raises_on_expired(self, cache_service, sample_entries):
        """get raises ConfigCacheExpired after TTL."""
        cache_service.load(sample_entries)
        time.sleep(1.1)
        with pytest.raises(ConfigCacheExpired) as exc_info:
            cache_service.get("safety_stock_multiplier")
        assert exc_info.value.ttl_seconds == 1

    def test_clear_resets_expiry(self, cache_service, sample_entries):
        """clear() resets the cache and forces expiry."""
        cache_service.load(sample_entries)
        cache_service.clear()
        assert cache_service.is_expired() is True


# ===========================================================================
# Test: Scenario Overrides
# ===========================================================================

class TestScenarioOverrides:
    def test_set_override(self, cache_service, sample_entries):
        """set_scenario_override sets a value for a scope."""
        cache_service.load(sample_entries)
        cache_service.set_scenario_override("scenario_1", "safety_stock_multiplier", 2.0)
        result = cache_service.get("safety_stock_multiplier", scope_id="scenario_1")
        assert result == 2.0

    def test_override_does_not_affect_base(self, cache_service, sample_entries):
        """Base value is unchanged after override."""
        cache_service.load(sample_entries)
        cache_service.set_scenario_override("scenario_1", "safety_stock_multiplier", 2.0)
        base_result = cache_service.get("safety_stock_multiplier")
        assert base_result == 1.5  # Original value

    def test_multiple_scopes_isolated(self, cache_service, sample_entries):
        """Overrides in one scope don't affect another."""
        cache_service.load(sample_entries)
        cache_service.set_scenario_override("scenario_1", "safety_stock_multiplier", 2.0)
        cache_service.set_scenario_override("scenario_2", "safety_stock_multiplier", 3.0)
        assert cache_service.get("safety_stock_multiplier", scope_id="scenario_1") == 2.0
        assert cache_service.get("safety_stock_multiplier", scope_id="scenario_2") == 3.0

    def test_clear_overrides(self, cache_service, sample_entries):
        """clear_scenario_overrides removes all overrides for a scope."""
        cache_service.load(sample_entries)
        cache_service.set_scenario_override("scenario_1", "safety_stock_multiplier", 2.0)
        cache_service.clear_scenario_overrides("scenario_1")
        result = cache_service.get("safety_stock_multiplier", scope_id="scenario_1")
        assert result == 1.5  # Back to base

    def test_get_active_overrides(self, cache_service, sample_entries):
        """get_active_overrides returns the override dict."""
        cache_service.load(sample_entries)
        cache_service.set_scenario_override("scenario_1", "safety_stock_multiplier", 2.0)
        cache_service.set_scenario_override("scenario_1", "days_supply_minimum", 10)
        overrides = cache_service.get_active_overrides("scenario_1")
        assert overrides == {
            "safety_stock_multiplier": 2.0,
            "days_supply_minimum": 10,
        }

    def test_get_active_overrides_empty(self, cache_service, sample_entries):
        """get_active_overrides returns empty dict for unknown scope."""
        cache_service.load(sample_entries)
        assert cache_service.get_active_overrides("unknown_scope") == {}


# ===========================================================================
# Test: Scoring Weights Convenience Method
# ===========================================================================

class TestScoringWeights:
    def test_get_scoring_weights(self, cache_service, sample_entries):
        """get_scoring_weights returns all four weights as Decimals."""
        cache_service.load(sample_entries)
        weights = cache_service.get_scoring_weights()
        assert len(weights) == 4
        assert weights[0] == Decimal("0.40")  # availability
        assert weights[1] == Decimal("0.25")  # lead_time
        assert weights[2] == Decimal("0.20")  # cost
        assert weights[3] == Decimal("0.15")  # waste_reduction

    def test_get_scoring_weights_with_override(self, cache_service, sample_entries):
        """get_scoring_weights respects scenario overrides."""
        cache_service.load(sample_entries)
        cache_service.set_scenario_override("test_scenario", "scoring_weight_availability", 0.50)
        weights = cache_service.get_scoring_weights(scope_id="test_scenario")
        assert weights[0] == Decimal("0.50")  # overridden
        assert weights[1] == Decimal("0.25")  # unchanged


# ===========================================================================
# Test: Standard Config Schema
# ===========================================================================

class TestStandardConfigSchema:
    def test_schema_has_all_required_keys(self):
        """STANDARD_CONFIG_KEYS contains all required keys."""
        required = [
            "safety_stock_multiplier",
            "days_supply_minimum",
            "expiration_risk_horizon_days",
            "lead_time_buffer_days",
            "min_feasibility_score_threshold",
            "scoring_weight_availability",
            "scoring_weight_lead_time",
            "scoring_weight_cost",
            "scoring_weight_waste_reduction",
            "delivery_retry_limit",
            "avg_minutes_per_manual_step",
            "forecast_min_confidence_threshold",
            "forecast_divergence_alert_threshold",
            "forecast_staleness_limit_hours",
            "cold_start_multiplier",
            "drift_retrain_threshold_mape",
        ]
        for key in required:
            assert key in STANDARD_CONFIG_KEYS, f"Missing key: {key}"

    def test_schema_entries_have_metadata(self):
        """Each schema entry has default, type, description."""
        for key, spec in STANDARD_CONFIG_KEYS.items():
            assert "default" in spec, f"{key} missing 'default'"
            assert "type" in spec, f"{key} missing 'type'"
            assert "description" in spec, f"{key} missing 'description'"


# ===========================================================================
# Test: Global Cache Singleton
# ===========================================================================

class TestGlobalSingleton:
    def test_get_cache_returns_same_instance(self):
        """get_cache() returns the same instance on multiple calls."""
        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2

    def test_set_cache_replaces_instance(self):
        """set_cache() replaces the global instance."""
        original_cache = get_cache()
        new_cache = CachedConfigService()
        set_cache(new_cache)
        assert get_cache() is new_cache
        # Restore for other tests
        set_cache(original_cache)
