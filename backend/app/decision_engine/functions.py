"""
The 19 decision engine functions.

Conventions
-----------
* Money and quantities are Decimal. Callers may pass int/float/Decimal;
  inputs are converted and validated at the boundary.
* Dates are datetime.date (datetime is narrowed to .date()).
* "Days of supply" and horizons are whole days unless documented otherwise.
* Every function validates its inputs and raises DecisionInputError on
  invalid input (negative quantity, wrong type, out-of-range score, etc.).
* No LLM, no I/O, no global state — pure functions only.

A note on "infinite" days of supply: when demand is zero, a quantity will
never be consumed. Functions that would divide by zero return an explicit
sentinel (None for a stockout date, Decimal('Infinity') for days_of_supply)
rather than raising — zero demand is a valid business state, not bad input.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, Sequence

from ..types import (
    DemandSignal,
    ForecastPoint,
    LotInfo,
    ScoringWeights,
)
from .errors import (
    DecisionInputError,
    require_date,
    require_int_non_negative,
    require_non_negative,
    require_positive,
    require_ratio,
    to_decimal,
)

# Quantize target for day counts derived from Decimal division.
_ZERO = Decimal("0")


# ===========================================================================
# 1-15: DETERMINISTIC ENGINE
# ===========================================================================


def available_quantity(
    quantity_on_hand: object,
    reserved_quantity: object = 0,
) -> Decimal:
    """
    (1) Quantity actually available to allocate.

    available = quantity_on_hand - reserved_quantity, floored at 0.

    A location may have stock physically on hand that is already committed
    (reserved) to other orders; that stock is not available. If reservations
    exceed on-hand, available is 0 (never negative).

    Raises DecisionInputError if either input is negative or non-numeric.
    """
    on_hand = require_non_negative(quantity_on_hand, "quantity_on_hand")
    reserved = require_non_negative(reserved_quantity, "reserved_quantity")
    available = on_hand - reserved
    return available if available > _ZERO else _ZERO


def average_daily_demand(
    daily_consumption: Sequence[object],
    stockout_flags: Optional[Sequence[bool]] = None,
) -> Decimal:
    """
    (2) Average daily demand over an observed consumption series.

    Stockout days are excluded from the average (they represent suppressed,
    not true, demand — matching the forecasting training rule "exclude
    stockout periods, mark as missing not zero").

    * daily_consumption: per-day consumed quantities (>= 0).
    * stockout_flags: optional parallel list; True marks a day to exclude.

    Returns the mean of the included days. If every day is excluded there is
    no observable demand, which is invalid input (nothing to average) ->
    DecisionInputError. A series of legitimate zeros averages to 0.

    Raises DecisionInputError on empty series, length mismatch, or negatives.
    """
    if daily_consumption is None or len(daily_consumption) == 0:
        raise DecisionInputError("daily_consumption must be a non-empty series")
    if stockout_flags is not None and len(stockout_flags) != len(daily_consumption):
        raise DecisionInputError(
            "stockout_flags must be the same length as daily_consumption"
        )

    total = _ZERO
    count = 0
    for i, raw in enumerate(daily_consumption):
        if stockout_flags is not None:
            flag = stockout_flags[i]
            if not isinstance(flag, bool):
                raise DecisionInputError("stockout_flags must contain only booleans")
            if flag:
                continue
        value = require_non_negative(raw, f"daily_consumption[{i}]")
        total += value
        count += 1

    if count == 0:
        raise DecisionInputError("all days excluded — no demand observations to average")
    return total / Decimal(count)


def days_of_supply(
    available: object,
    daily_demand: object,
) -> Decimal:
    """
    (3) How many days the available stock will last at the given demand.

    days_of_supply = available / daily_demand.

    When daily_demand is 0, the stock never depletes -> Decimal('Infinity').
    (Zero demand is a valid state, not an error.)

    Raises DecisionInputError if either input is negative or non-numeric.
    """
    avail = require_non_negative(available, "available")
    demand = require_non_negative(daily_demand, "daily_demand")
    if demand == _ZERO:
        return Decimal("Infinity")
    return avail / demand


def projected_stockout_date(
    available: object,
    daily_demand: object,
    as_of_date: object,
) -> Optional[date]:
    """
    (4) The date on which available stock is projected to reach zero.

    stockout_date = as_of_date + floor(available / daily_demand) days.

    Returns None when daily_demand is 0 (stock never depletes).

    Raises DecisionInputError on negative quantities or invalid date/type.
    """
    avail = require_non_negative(available, "available")
    demand = require_non_negative(daily_demand, "daily_demand")
    base = require_date(as_of_date, "as_of_date")
    if demand == _ZERO:
        return None
    full_days = int((avail / demand).to_integral_value(rounding="ROUND_FLOOR"))
    return base + timedelta(days=full_days)


def safety_stock(
    daily_demand: object,
    lead_time_days: int,
    safety_stock_days: int,
) -> Decimal:
    """
    (5) Buffer stock that should be kept on hand.

    safety_stock = daily_demand * (lead_time_days + safety_stock_days)

    Covers expected consumption during replenishment lead time plus an extra
    safety buffer of `safety_stock_days`.

    Raises DecisionInputError on negative/invalid inputs.
    """
    demand = require_non_negative(daily_demand, "daily_demand")
    lead = require_int_non_negative(lead_time_days, "lead_time_days")
    buffer_days = require_int_non_negative(safety_stock_days, "safety_stock_days")
    return demand * Decimal(lead + buffer_days)


def excess_quantity(
    available: object,
    daily_demand: object,
    target_cover_days: int,
    safety_stock_quantity: object,
) -> Decimal:
    """
    (6) Quantity in excess of what is needed to cover a target horizon.

    needed  = daily_demand * target_cover_days + safety_stock_quantity
    excess  = max(0, available - needed)

    Used to flag excess-inventory conditions and transfer candidates.

    Raises DecisionInputError on negative/invalid inputs.
    """
    avail = require_non_negative(available, "available")
    demand = require_non_negative(daily_demand, "daily_demand")
    cover = require_int_non_negative(target_cover_days, "target_cover_days")
    ss = require_non_negative(safety_stock_quantity, "safety_stock_quantity")
    needed = demand * Decimal(cover) + ss
    excess = avail - needed
    return excess if excess > _ZERO else _ZERO


def expiration_risk_quantity(
    lots: Sequence[LotInfo],
    daily_demand: object,
    as_of_date: object,
    horizon_days: int,
) -> Decimal:
    """
    (7) Quantity likely to expire unused within the horizon (deterministic).

    Approach:
      consumable = daily_demand * horizon_days
      at_risk_on_hand = sum of lot quantities that expire on or before
                        (as_of_date + horizon_days)
      risk = max(0, at_risk_on_hand - consumable)

    Interpretation: of the stock that will expire within the horizon, only
    the portion that cannot be consumed (given the demand rate) is at risk.

    Raises DecisionInputError on negative/invalid inputs.
    """
    demand = require_non_negative(daily_demand, "daily_demand")
    base = require_date(as_of_date, "as_of_date")
    horizon = require_int_non_negative(horizon_days, "horizon_days")
    cutoff = base + timedelta(days=horizon)

    at_risk_on_hand = _ZERO
    for i, lot in enumerate(lots):
        lot_qty = require_non_negative(lot.quantity, f"lots[{i}].quantity")
        if not isinstance(lot.expiration_date, date):
            raise DecisionInputError(f"lots[{i}].expiration_date must be a date")
        if lot.expiration_date <= cutoff:
            at_risk_on_hand += lot_qty

    consumable = demand * Decimal(horizon)
    risk = at_risk_on_hand - consumable
    return risk if risk > _ZERO else _ZERO


def transferable_quantity(
    available: object,
    safety_stock_quantity: object,
) -> Decimal:
    """
    (8) Quantity a source location can give up without breaching its own
    safety stock.

    transferable = max(0, available - safety_stock_quantity)

    Raises DecisionInputError on negative/invalid inputs.
    """
    avail = require_non_negative(available, "available")
    ss = require_non_negative(safety_stock_quantity, "safety_stock_quantity")
    transferable = avail - ss
    return transferable if transferable > _ZERO else _ZERO


def supplier_arrival_date(
    order_date: object,
    lead_time_days: int,
) -> date:
    """
    (9) Projected arrival date for a procurement order.

    arrival = order_date + lead_time_days

    Raises DecisionInputError on negative lead time or invalid date/type.
    """
    base = require_date(order_date, "order_date")
    lead = require_int_non_negative(lead_time_days, "lead_time_days")
    return base + timedelta(days=lead)


def transfer_arrival_date(
    dispatch_datetime: object,
    transfer_time_hours: int,
) -> datetime:
    """
    (10) Projected arrival time for an internal transfer.

    arrival = dispatch_datetime + transfer_time_hours

    Internal transfers are modeled in hours (same-day movements are common),
    unlike procurement which is modeled in whole days.

    Raises DecisionInputError on negative hours or invalid datetime/type.
    """
    if isinstance(dispatch_datetime, bool) or not isinstance(dispatch_datetime, datetime):
        raise DecisionInputError("dispatch_datetime must be a datetime")
    hours = require_int_non_negative(transfer_time_hours, "transfer_time_hours")
    return dispatch_datetime + timedelta(hours=hours)


def source_location_safety_check(
    source_available: object,
    source_safety_stock: object,
    transfer_quantity: object,
) -> bool:
    """
    (11) Whether a source location can fulfill a transfer without dropping
    below its own safety stock.

    Returns True iff (source_available - transfer_quantity) >= source_safety_stock.

    This is a protective gate: a transfer that would leave the source below
    its safety stock must not be approved.

    Raises DecisionInputError on negative/invalid inputs.
    """
    avail = require_non_negative(source_available, "source_available")
    ss = require_non_negative(source_safety_stock, "source_safety_stock")
    qty = require_non_negative(transfer_quantity, "transfer_quantity")
    return (avail - qty) >= ss


def transfer_cost(
    quantity: object,
    per_unit_handling_cost: object,
    flat_transfer_fee: object = 0,
) -> Decimal:
    """
    (12) Total cost of an internal transfer.

    cost = quantity * per_unit_handling_cost + flat_transfer_fee

    Raises DecisionInputError on negative/invalid inputs.
    """
    qty = require_non_negative(quantity, "quantity")
    per_unit = require_non_negative(per_unit_handling_cost, "per_unit_handling_cost")
    flat = require_non_negative(flat_transfer_fee, "flat_transfer_fee")
    return qty * per_unit + flat


def procurement_cost(
    quantity: object,
    unit_cost: object,
    shipping_cost: object = 0,
) -> Decimal:
    """
    (13) Total cost of a procurement order.

    cost = quantity * unit_cost + shipping_cost

    Raises DecisionInputError on negative/invalid inputs.
    """
    qty = require_non_negative(quantity, "quantity")
    unit = require_non_negative(unit_cost, "unit_cost")
    shipping = require_non_negative(shipping_cost, "shipping_cost")
    return qty * unit + shipping


def option_feasibility(
    quantity_available_to_fulfill: object,
    quantity_needed: object,
    arrives_before_stockout: bool,
    passes_source_safety_check: bool = True,
) -> bool:
    """
    (14) Boolean feasibility gate — runs BEFORE scoring (FR-04).

    An option is feasible iff ALL hold:
      * quantity_available_to_fulfill >= quantity_needed (can meet the need)
      * arrives_before_stockout is True (arrives in time to matter)
      * passes_source_safety_check is True (does not breach source safety)

    Infeasible options are excluded from scoring entirely and recorded as
    rejected options with a reason. Returns a plain bool.

    Raises DecisionInputError on negative quantities or non-boolean flags.
    """
    avail = require_non_negative(
        quantity_available_to_fulfill, "quantity_available_to_fulfill"
    )
    needed = require_non_negative(quantity_needed, "quantity_needed")
    if not isinstance(arrives_before_stockout, bool):
        raise DecisionInputError("arrives_before_stockout must be a bool")
    if not isinstance(passes_source_safety_check, bool):
        raise DecisionInputError("passes_source_safety_check must be a bool")
    return (avail >= needed) and arrives_before_stockout and passes_source_safety_check


def recommendation_score(
    availability_score: object,
    lead_time_score: object,
    cost_score: object,
    waste_reduction_score: object,
    weights: ScoringWeights,
) -> Decimal:
    """
    (15) Weighted-sum recommendation score (FR-04).

    score = availability * w_availability
          + lead_time    * w_lead_time
          + cost         * w_cost
          + waste        * w_waste_reduction

    Each per-dimension score must be a normalized value in [0, 1].
    Weights (documented defaults: availability 0.40, lead_time 0.25,
    cost 0.20, waste_reduction 0.15) must be non-negative and sum to 1.0.
    The result therefore also lies in [0, 1].

    Raises DecisionInputError on out-of-range scores or weights that do not
    sum to 1.0.
    """
    a = require_ratio(availability_score, "availability_score")
    lt = require_ratio(lead_time_score, "lead_time_score")
    c = require_ratio(cost_score, "cost_score")
    w = require_ratio(waste_reduction_score, "waste_reduction_score")

    wa = require_non_negative(weights.availability, "weights.availability")
    wlt = require_non_negative(weights.lead_time, "weights.lead_time")
    wc = require_non_negative(weights.cost, "weights.cost")
    ww = require_non_negative(weights.waste_reduction, "weights.waste_reduction")

    weight_sum = wa + wlt + wc + ww
    # Weights must sum to 1.0 (allow a tiny tolerance for Decimal representation).
    if abs(weight_sum - Decimal("1")) > Decimal("0.0001"):
        raise DecisionInputError(f"scoring weights must sum to 1.0, got {weight_sum}")

    return a * wa + lt * wlt + c * wc + w * ww


# ===========================================================================
# 16-19: DEMAND SIGNAL INTEGRATION
# ===========================================================================
# These consume the forecasting module's output (DemandSignal / ForecastPoint).
# The ML layer only SUPPLIES input values; the arithmetic below is pure,
# deterministic Python (ADR-001 D7). None of these call an LLM or the ML
# pipeline directly — they operate on values already produced upstream, so
# they remain fully testable in isolation and work identically whether the
# signal came from an ML forecast or the deterministic baseline fallback.


def effective_daily_demand(demand_signal: DemandSignal) -> Decimal:
    """
    (16) The effective daily demand to plan against, taken from the demand
    signal produced by the forecasting module's get_demand_signal().

    This is the single point where the decision engine reads the demand
    signal. It returns signal.effective_daily_demand regardless of whether
    the source was `ml_forecast` or `deterministic_baseline` — the platform
    remains fully functional when the ML layer is unavailable (the baseline
    simply supplies the value instead).

    Validation only: the returned value must be a finite, non-negative
    Decimal. A signal carrying a negative demand is invalid input.

    Raises DecisionInputError if the signal is missing or carries a negative
    or non-numeric effective_daily_demand.
    """
    if demand_signal is None:
        raise DecisionInputError("demand_signal must not be None")
    return require_non_negative(
        demand_signal.effective_daily_demand, "demand_signal.effective_daily_demand"
    )


def forecast_horizon_stockout_scan(
    available: object,
    forecast_points: Sequence[ForecastPoint],
    as_of_date: object,
) -> Optional[date]:
    """
    (17) Scan a multi-day ML forecast horizon for the projected stockout day.

    Walks the forecast points in chronological order, accumulating the p50
    (median) predicted daily demand, and returns the first forecast_date on
    which cumulative demand strictly exceeds `available` — i.e. the day the
    projected on-hand goes negative.

    This detects stockouts earlier than the flat-rate projected_stockout_date
    (function 4) when demand is expected to rise within the horizon
    (Scenario 6: "ML forecast enables earlier detection").

    Returns None if cumulative demand never exceeds available within the
    provided points (including the empty / all-zero-demand cases).

    Raises DecisionInputError on negative available, invalid date, or invalid
    forecast points.
    """
    avail = require_non_negative(available, "available")
    require_date(as_of_date, "as_of_date")

    # Sort chronologically so callers may pass points in any order.
    points = list(forecast_points)
    for i, pt in enumerate(points):
        if not isinstance(pt, ForecastPoint):
            raise DecisionInputError(f"forecast_points[{i}] must be a ForecastPoint")
        if not isinstance(pt.forecast_date, date):
            raise DecisionInputError(f"forecast_points[{i}].forecast_date must be a date")
    points.sort(key=lambda p: p.forecast_date)

    cumulative = _ZERO
    for i, pt in enumerate(points):
        demand = require_non_negative(pt.p50, f"forecast_points[{i}].p50")
        cumulative += demand
        if cumulative > avail:
            return pt.forecast_date
    return None


def demand_adjusted_safety_stock(
    effective_daily_demand_value: object,
    lead_time_days: int,
    safety_factor: object,
) -> Decimal:
    """
    (18) Safety stock sized from the (ML-adjusted) effective daily demand.

    demand_adjusted_safety_stock = effective_daily_demand * lead_time_days
                                   * safety_factor

    Unlike function 5 (safety_stock), which uses a plain average demand and
    an additive day buffer, this uses the effective demand from the demand
    signal and a multiplicative safety_factor (e.g. 1.5) applied to the
    lead-time demand. When the ML signal indicates rising demand, the buffer
    grows proportionally.

    Raises DecisionInputError on negative/invalid inputs.
    """
    demand = require_non_negative(
        effective_daily_demand_value, "effective_daily_demand_value"
    )
    lead = require_int_non_negative(lead_time_days, "lead_time_days")
    factor = require_non_negative(safety_factor, "safety_factor")
    return demand * Decimal(lead) * factor


def expiration_risk_adjusted_horizon(
    lots: Sequence[LotInfo],
    effective_daily_demand_value: object,
    as_of_date: object,
    base_horizon_days: int,
) -> Decimal:
    """
    (19) Expiration-risk quantity using the effective (ML) demand with a
    per-lot FEFO simulation across the horizon.

    This is the demand-signal-integrated, more precise counterpart to
    function 7. Instead of comparing aggregate at-risk stock to aggregate
    consumption, it simulates day-by-day First-Expiry-First-Out consumption:

      * Lots are consumed soonest-expiry first.
      * On each day within the horizon, the effective daily demand is drawn
        from lots that have NOT yet expired (a lot expiring on/before the
        current day can no longer be consumed).
      * After the horizon, any quantity remaining in lots that expire on or
        before (as_of_date + base_horizon_days) is at risk of expiring unused.

    The "adjusted horizon" is the per-lot consumption window: each lot can
    only absorb demand up to the day before it expires, so a nearer-term
    expiry gets a shorter effective horizon than the base horizon.

    Raises DecisionInputError on negative/invalid inputs.
    """
    demand = require_non_negative(
        effective_daily_demand_value, "effective_daily_demand_value"
    )
    base = require_date(as_of_date, "as_of_date")
    horizon = require_int_non_negative(base_horizon_days, "base_horizon_days")
    cutoff = base + timedelta(days=horizon)

    # Build a mutable FEFO ledger: [expiration_date, remaining_quantity].
    ledger = []
    for i, lot in enumerate(lots):
        qty = require_non_negative(lot.quantity, f"lots[{i}].quantity")
        if not isinstance(lot.expiration_date, date):
            raise DecisionInputError(f"lots[{i}].expiration_date must be a date")
        ledger.append([lot.expiration_date, qty])
    ledger.sort(key=lambda entry: entry[0])  # FEFO

    # Simulate consumption for each day in the horizon.
    for day in range(horizon):
        current = base + timedelta(days=day)
        remaining_demand = demand
        if remaining_demand <= _ZERO:
            continue
        for entry in ledger:
            exp, qty = entry
            if qty <= _ZERO or exp <= current:
                continue  # empty lot, or expired and no longer consumable
            take = qty if qty < remaining_demand else remaining_demand
            entry[1] = qty - take
            remaining_demand -= take
            if remaining_demand <= _ZERO:
                break

    # Whatever is left in lots expiring within the horizon is at risk.
    risk = _ZERO
    for exp, qty in ledger:
        if exp <= cutoff and qty > _ZERO:
            risk += qty
    return risk
