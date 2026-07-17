"""
Unit tests for the 19 decision engine functions.

Each function has EXACTLY four tests, per Step 5 requirements:
  1. happy    — happy path with a documented expected output
  2. boundary — a boundary condition (exactly-at-threshold cases)
  3. edge     — an edge case (zero demand, zero inventory, max lead time)
  4. negative — invalid/negative input returns a typed DecisionInputError
                (never a wrong numeric value)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.decision_engine import (
    DecisionInputError,
    available_quantity,
    average_daily_demand,
    days_of_supply,
    projected_stockout_date,
    safety_stock,
    excess_quantity,
    expiration_risk_quantity,
    transferable_quantity,
    supplier_arrival_date,
    transfer_arrival_date,
    source_location_safety_check,
    transfer_cost,
    procurement_cost,
    option_feasibility,
    recommendation_score,
    effective_daily_demand,
    forecast_horizon_stockout_scan,
    demand_adjusted_safety_stock,
    expiration_risk_adjusted_horizon,
)
from app.types import (
    DemandSignal,
    DemandSignalSource,
    ForecastPoint,
    LotInfo,
    ScoringWeights,
)


# ---------------------------------------------------------------------------
# Test data builders
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS = ScoringWeights(
    availability=Decimal("0.40"),
    lead_time=Decimal("0.25"),
    cost=Decimal("0.20"),
    waste_reduction=Decimal("0.15"),
)


def make_lot(quantity, expiration_date, lot_number="LOT") -> LotInfo:
    return LotInfo(
        lot_id=uuid.uuid4(),
        lot_number=lot_number,
        quantity=Decimal(str(quantity)),
        expiration_date=expiration_date,
    )


def make_forecast_point(forecast_date, p50, p10=None, p90=None) -> ForecastPoint:
    p50d = Decimal(str(p50))
    return ForecastPoint(
        forecast_date=forecast_date,
        p10=Decimal(str(p10)) if p10 is not None else p50d,
        p50=p50d,
        p90=Decimal(str(p90)) if p90 is not None else p50d,
    )


def make_demand_signal(
    effective, source=DemandSignalSource.ML_FORECAST
) -> DemandSignal:
    return DemandSignal(
        effective_daily_demand=Decimal(str(effective)),
        demand_signal_source=source,
        forecast_confidence=Decimal("0.80"),
        forecast_id=uuid.uuid4(),
        fallback_reason=None,
    )


# ===========================================================================
# 1. available_quantity
# ===========================================================================

class TestAvailableQuantity:
    def test_happy(self):
        # 100 on hand, 30 reserved -> 70 available
        assert available_quantity(100, 30) == Decimal("70")

    def test_boundary(self):
        # reserved exactly equals on hand -> 0 available (not negative)
        assert available_quantity(50, 50) == Decimal("0")

    def test_edge(self):
        # zero inventory on hand -> 0 available
        assert available_quantity(0) == Decimal("0")

    def test_negative(self):
        with pytest.raises(DecisionInputError):
            available_quantity(-5, 0)


# ===========================================================================
# 2. average_daily_demand
# ===========================================================================

class TestAverageDailyDemand:
    def test_happy(self):
        # mean of [10, 20, 30] = 20
        assert average_daily_demand([10, 20, 30]) == Decimal("20")

    def test_boundary(self):
        # all but one day excluded as stockout -> average of the single day
        result = average_daily_demand([10, 20, 30], [True, True, False])
        assert result == Decimal("30")

    def test_edge(self):
        # legitimate zero-demand series averages to 0 (not an error)
        assert average_daily_demand([0, 0, 0]) == Decimal("0")

    def test_negative(self):
        with pytest.raises(DecisionInputError):
            average_daily_demand([10, -5, 30])


# ===========================================================================
# 3. days_of_supply
# ===========================================================================

class TestDaysOfSupply:
    def test_happy(self):
        # 100 available / 10 per day = 10 days
        assert days_of_supply(100, 10) == Decimal("10")

    def test_boundary(self):
        # zero inventory -> 0 days of supply
        assert days_of_supply(0, 10) == Decimal("0")

    def test_edge(self):
        # zero demand -> stock never depletes -> infinite days
        assert days_of_supply(100, 0) == Decimal("Infinity")

    def test_negative(self):
        with pytest.raises(DecisionInputError):
            days_of_supply(-1, 10)


# ===========================================================================
# 4. projected_stockout_date
# ===========================================================================

class TestProjectedStockoutDate:
    def test_happy(self):
        # 100 / 10 = 10 full days -> Jan 1 + 10 = Jan 11
        assert projected_stockout_date(100, 10, date(2026, 1, 1)) == date(2026, 1, 11)

    def test_boundary(self):
        # 95 / 10 = 9.5 -> floored to 9 full days -> Jan 10
        assert projected_stockout_date(95, 10, date(2026, 1, 1)) == date(2026, 1, 10)

    def test_edge(self):
        # zero demand -> never stocks out -> None
        assert projected_stockout_date(100, 0, date(2026, 1, 1)) is None

    def test_negative(self):
        with pytest.raises(DecisionInputError):
            projected_stockout_date(-100, 10, date(2026, 1, 1))


# ===========================================================================
# 5. safety_stock
# ===========================================================================

class TestSafetyStock:
    def test_happy(self):
        # 10/day * (5 lead + 2 buffer) = 70
        assert safety_stock(10, 5, 2) == Decimal("70")

    def test_boundary(self):
        # zero extra buffer days -> covers lead time only: 10 * 5 = 50
        assert safety_stock(10, 5, 0) == Decimal("50")

    def test_edge(self):
        # zero demand -> zero safety stock needed
        assert safety_stock(0, 5, 2) == Decimal("0")

    def test_negative(self):
        with pytest.raises(DecisionInputError):
            safety_stock(10, -1, 2)


# ===========================================================================
# 6. excess_quantity
# ===========================================================================

class TestExcessQuantity:
    def test_happy(self):
        # needed = 10*30 + 50 = 350; excess = 500 - 350 = 150
        assert excess_quantity(500, 10, 30, 50) == Decimal("150")

    def test_boundary(self):
        # available exactly equals needed (350) -> no excess
        assert excess_quantity(350, 10, 30, 50) == Decimal("0")

    def test_edge(self):
        # available below needed -> excess floored at 0
        assert excess_quantity(100, 10, 30, 50) == Decimal("0")

    def test_negative(self):
        with pytest.raises(DecisionInputError):
            excess_quantity(-500, 10, 30, 50)


# ===========================================================================
# 7. expiration_risk_quantity
# ===========================================================================

class TestExpirationRiskQuantity:
    def test_happy(self):
        # cutoff = Jan 1 + 30 = Jan 31; at-risk lot (Jan 15) qty 200,
        # far lot (Jun 1) excluded; consumable = 5*30 = 150; risk = 50
        lots = [
            make_lot(200, date(2026, 1, 15), "NEAR"),
            make_lot(100, date(2026, 6, 1), "FAR"),
        ]
        assert expiration_risk_quantity(lots, 5, date(2026, 1, 1), 30) == Decimal("50")

    def test_boundary(self):
        # at-risk quantity (150) exactly equals consumable (5*30=150) -> risk 0
        lots = [make_lot(150, date(2026, 1, 15), "NEAR")]
        assert expiration_risk_quantity(lots, 5, date(2026, 1, 1), 30) == Decimal("0")

    def test_edge(self):
        # zero demand -> nothing consumed -> entire at-risk quantity is at risk
        lots = [make_lot(80, date(2026, 1, 15), "NEAR")]
        assert expiration_risk_quantity(lots, 0, date(2026, 1, 1), 30) == Decimal("80")

    def test_negative(self):
        lots = [make_lot(80, date(2026, 1, 15), "NEAR")]
        with pytest.raises(DecisionInputError):
            expiration_risk_quantity(lots, -5, date(2026, 1, 1), 30)


# ===========================================================================
# 8. transferable_quantity
# ===========================================================================

class TestTransferableQuantity:
    def test_happy(self):
        # 200 available - 50 safety stock = 150 transferable
        assert transferable_quantity(200, 50) == Decimal("150")

    def test_boundary(self):
        # available exactly at safety stock -> nothing transferable
        assert transferable_quantity(50, 50) == Decimal("0")

    def test_edge(self):
        # available below safety stock -> floored at 0 (never negative)
        assert transferable_quantity(10, 50) == Decimal("0")

    def test_negative(self):
        with pytest.raises(DecisionInputError):
            transferable_quantity(-200, 50)


# ===========================================================================
# 9. supplier_arrival_date
# ===========================================================================

class TestSupplierArrivalDate:
    def test_happy(self):
        # Jan 1 + 7 day lead time = Jan 8
        assert supplier_arrival_date(date(2026, 1, 1), 7) == date(2026, 1, 8)

    def test_boundary(self):
        # zero lead time -> arrives same day
        assert supplier_arrival_date(date(2026, 1, 1), 0) == date(2026, 1, 1)

    def test_edge(self):
        # very long (max-ish) lead time crosses the year boundary
        assert supplier_arrival_date(date(2026, 1, 1), 365) == date(2027, 1, 1)

    def test_negative(self):
        with pytest.raises(DecisionInputError):
            supplier_arrival_date(date(2026, 1, 1), -1)


# ===========================================================================
# 10. transfer_arrival_date
# ===========================================================================

class TestTransferArrivalDate:
    def test_happy(self):
        # 08:00 + 6 hours = 14:00 same day
        assert transfer_arrival_date(datetime(2026, 1, 1, 8, 0), 6) == datetime(
            2026, 1, 1, 14, 0
        )

    def test_boundary(self):
        # zero transfer time -> arrives at dispatch instant
        assert transfer_arrival_date(datetime(2026, 1, 1, 8, 0), 0) == datetime(
            2026, 1, 1, 8, 0
        )

    def test_edge(self):
        # 48 hours rolls forward two days
        assert transfer_arrival_date(datetime(2026, 1, 1, 8, 0), 48) == datetime(
            2026, 1, 3, 8, 0
        )

    def test_negative(self):
        with pytest.raises(DecisionInputError):
            transfer_arrival_date(datetime(2026, 1, 1, 8, 0), -1)


# ===========================================================================
# 11. source_location_safety_check
# ===========================================================================

class TestSourceLocationSafetyCheck:
    def test_happy(self):
        # 200 - 100 = 100 >= 50 safety -> OK
        assert source_location_safety_check(200, 50, 100) is True

    def test_boundary(self):
        # transfer leaves source EXACTLY at safety stock (150-100=50>=50) -> OK
        assert source_location_safety_check(150, 50, 100) is True

    def test_edge(self):
        # transfer would drop source below safety (120-100=20 < 50) -> not OK
        assert source_location_safety_check(120, 50, 100) is False

    def test_negative(self):
        with pytest.raises(DecisionInputError):
            source_location_safety_check(200, 50, -100)


# ===========================================================================
# 12. transfer_cost
# ===========================================================================

class TestTransferCost:
    def test_happy(self):
        # 100 units * 0.50 handling + 10 flat = 60
        assert transfer_cost(100, Decimal("0.50"), 10) == Decimal("60.00")

    def test_boundary(self):
        # zero units -> only the flat fee remains
        assert transfer_cost(0, Decimal("0.50"), 10) == Decimal("10")

    def test_edge(self):
        # default flat fee (0): 100 * 0.50 = 50
        assert transfer_cost(100, Decimal("0.50")) == Decimal("50.00")

    def test_negative(self):
        with pytest.raises(DecisionInputError):
            transfer_cost(-100, Decimal("0.50"), 10)


# ===========================================================================
# 13. procurement_cost
# ===========================================================================

class TestProcurementCost:
    def test_happy(self):
        # 100 units * 0.15 + 25 shipping = 40
        assert procurement_cost(100, Decimal("0.15"), 25) == Decimal("40.00")

    def test_boundary(self):
        # zero units -> only shipping remains
        assert procurement_cost(0, Decimal("0.15"), 25) == Decimal("25")

    def test_edge(self):
        # default shipping (0): 200 * 0.08 = 16
        assert procurement_cost(200, Decimal("0.08")) == Decimal("16.00")

    def test_negative(self):
        with pytest.raises(DecisionInputError):
            procurement_cost(100, Decimal("-0.15"), 25)


# ===========================================================================
# 14. option_feasibility
# ===========================================================================

class TestOptionFeasibility:
    def test_happy(self):
        # enough stock, arrives in time, passes safety -> feasible
        assert option_feasibility(120, 100, True, True) is True

    def test_boundary(self):
        # available EXACTLY equals needed -> still feasible
        assert option_feasibility(100, 100, True, True) is True

    def test_edge(self):
        # enough stock but does NOT arrive before stockout -> infeasible
        assert option_feasibility(120, 100, False, True) is False

    def test_negative(self):
        with pytest.raises(DecisionInputError):
            option_feasibility(120, -100, True, True)


# ===========================================================================
# 15. recommendation_score
# ===========================================================================

class TestRecommendationScore:
    def test_happy(self):
        # 0.9*0.40 + 0.8*0.25 + 0.7*0.20 + 0.6*0.15
        #   = 0.36 + 0.20 + 0.14 + 0.09 = 0.79
        result = recommendation_score(
            Decimal("0.9"), Decimal("0.8"), Decimal("0.7"), Decimal("0.6"),
            DEFAULT_WEIGHTS,
        )
        assert result == Decimal("0.79")

    def test_boundary(self):
        # all dimension scores at the max (1.0) -> score equals sum of weights = 1.0
        result = recommendation_score(
            Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), DEFAULT_WEIGHTS
        )
        assert result == Decimal("1.00")

    def test_edge(self):
        # all dimension scores at the min (0.0) -> score 0
        result = recommendation_score(
            Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), DEFAULT_WEIGHTS
        )
        assert result == Decimal("0.00")

    def test_negative(self):
        # a negative (out-of-range) dimension score is rejected
        with pytest.raises(DecisionInputError):
            recommendation_score(
                Decimal("-0.1"), Decimal("0.8"), Decimal("0.7"), Decimal("0.6"),
                DEFAULT_WEIGHTS,
            )


# ===========================================================================
# 16. effective_daily_demand
# ===========================================================================

class TestEffectiveDailyDemand:
    def test_happy(self):
        # returns the effective demand carried by an ML forecast signal
        signal = make_demand_signal(12.5, DemandSignalSource.ML_FORECAST)
        assert effective_daily_demand(signal) == Decimal("12.5")

    def test_boundary(self):
        # zero effective demand is a valid boundary value
        signal = make_demand_signal(0, DemandSignalSource.ML_FORECAST)
        assert effective_daily_demand(signal) == Decimal("0")

    def test_edge(self):
        # ML unavailable -> baseline fallback still supplies a usable value
        signal = make_demand_signal(8, DemandSignalSource.DETERMINISTIC_BASELINE)
        assert effective_daily_demand(signal) == Decimal("8")

    def test_negative(self):
        signal = make_demand_signal(-1, DemandSignalSource.ML_FORECAST)
        with pytest.raises(DecisionInputError):
            effective_daily_demand(signal)


# ===========================================================================
# 17. forecast_horizon_stockout_scan
# ===========================================================================

class TestForecastHorizonStockoutScan:
    def test_happy(self):
        # available 25; p50 demand 10/day; cumulative 10,20,30 -> exceeds 25
        # on the third day (Jan 4). Points passed out of order to prove sorting.
        points = [
            make_forecast_point(date(2026, 1, 4), 10),
            make_forecast_point(date(2026, 1, 2), 10),
            make_forecast_point(date(2026, 1, 3), 10),
        ]
        result = forecast_horizon_stockout_scan(25, points, date(2026, 1, 1))
        assert result == date(2026, 1, 4)

    def test_boundary(self):
        # cumulative demand reaches EXACTLY available (30) but never exceeds
        # it -> no stockout within the horizon -> None
        points = [
            make_forecast_point(date(2026, 1, 2), 10),
            make_forecast_point(date(2026, 1, 3), 10),
            make_forecast_point(date(2026, 1, 4), 10),
        ]
        assert forecast_horizon_stockout_scan(30, points, date(2026, 1, 1)) is None

    def test_edge(self):
        # zero forecast demand every day -> never stocks out -> None
        points = [
            make_forecast_point(date(2026, 1, 2), 0),
            make_forecast_point(date(2026, 1, 3), 0),
        ]
        assert forecast_horizon_stockout_scan(30, points, date(2026, 1, 1)) is None

    def test_negative(self):
        points = [make_forecast_point(date(2026, 1, 2), 10)]
        with pytest.raises(DecisionInputError):
            forecast_horizon_stockout_scan(-30, points, date(2026, 1, 1))


# ===========================================================================
# 18. demand_adjusted_safety_stock
# ===========================================================================

class TestDemandAdjustedSafetyStock:
    def test_happy(self):
        # 10/day * 5 lead days * 1.5 safety factor = 75
        assert demand_adjusted_safety_stock(10, 5, Decimal("1.5")) == Decimal("75.0")

    def test_boundary(self):
        # safety factor of exactly 1.0 -> plain lead-time demand: 10*5*1 = 50
        assert demand_adjusted_safety_stock(10, 5, Decimal("1.0")) == Decimal("50.0")

    def test_edge(self):
        # zero effective demand -> zero safety stock
        assert demand_adjusted_safety_stock(0, 5, Decimal("1.5")) == Decimal("0.0")

    def test_negative(self):
        with pytest.raises(DecisionInputError):
            demand_adjusted_safety_stock(10, 5, Decimal("-1.5"))


# ===========================================================================
# 19. expiration_risk_adjusted_horizon
# ===========================================================================

class TestExpirationRiskAdjustedHorizon:
    def test_happy(self):
        # demand 5/day, horizon 10 days from Jan 1 (cutoff Jan 11).
        # LotA (40 units) expires Jan 6: consumable only on Jan 1-5 (5 days)
        #   = 25 units; 15 units remain and are at risk.
        # LotB (100 units) expires Feb 1: outside cutoff, not at risk.
        lots = [
            make_lot(40, date(2026, 1, 6), "A"),
            make_lot(100, date(2026, 2, 1), "B"),
        ]
        result = expiration_risk_adjusted_horizon(lots, 5, date(2026, 1, 1), 10)
        assert result == Decimal("15")

    def test_boundary(self):
        # LotA (25 units) is EXACTLY consumable before its Jan 6 expiry
        # (5 days * 5/day = 25) -> nothing left -> zero risk.
        lots = [
            make_lot(25, date(2026, 1, 6), "A"),
            make_lot(100, date(2026, 2, 1), "B"),
        ]
        result = expiration_risk_adjusted_horizon(lots, 5, date(2026, 1, 1), 10)
        assert result == Decimal("0")

    def test_edge(self):
        # zero demand -> nothing consumed -> whole near-expiry lot at risk;
        # far lot (outside cutoff) still excluded.
        lots = [
            make_lot(40, date(2026, 1, 6), "A"),
            make_lot(100, date(2026, 2, 1), "B"),
        ]
        result = expiration_risk_adjusted_horizon(lots, 0, date(2026, 1, 1), 10)
        assert result == Decimal("40")

    def test_negative(self):
        lots = [make_lot(40, date(2026, 1, 6), "A")]
        with pytest.raises(DecisionInputError):
            expiration_risk_adjusted_horizon(lots, -5, date(2026, 1, 1), 10)
