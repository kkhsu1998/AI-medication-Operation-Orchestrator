"""
Typed errors and validation helpers for the decision engine.

The negative-input contract (Step 5 requirement #4) is:
  invalid input -> raise DecisionInputError (a typed error),
  never return a wrong numeric value.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Union

Number = Union[int, float, Decimal]


class DecisionInputError(ValueError):
    """
    Raised when a decision function receives invalid input
    (negative quantity, wrong type, out-of-range weight, empty series, etc.).

    Subclasses ValueError so callers can catch it as a validation error,
    but the specific type lets tests assert the engine rejected bad input
    instead of silently computing a wrong result.
    """


def to_decimal(value: Number, name: str) -> Decimal:
    """
    Convert a numeric input to Decimal, rejecting bools, None, non-numeric
    types, and non-finite values (NaN/Infinity) with a typed error.
    """
    # bool is a subclass of int — reject it explicitly, it is not a quantity.
    if isinstance(value, bool):
        raise DecisionInputError(f"{name} must be numeric, got bool: {value!r}")
    if value is None:
        raise DecisionInputError(f"{name} must be numeric, got None")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, (int, float)):
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise DecisionInputError(f"{name} is not a valid number: {value!r}") from exc
    else:
        raise DecisionInputError(
            f"{name} must be int/float/Decimal, got {type(value).__name__}"
        )
    if not result.is_finite():
        raise DecisionInputError(f"{name} must be finite, got {value!r}")
    return result


def require_non_negative(value: Number, name: str) -> Decimal:
    """Convert to Decimal and require value >= 0."""
    result = to_decimal(value, name)
    if result < 0:
        raise DecisionInputError(f"{name} must be >= 0, got {result}")
    return result


def require_positive(value: Number, name: str) -> Decimal:
    """Convert to Decimal and require value > 0."""
    result = to_decimal(value, name)
    if result <= 0:
        raise DecisionInputError(f"{name} must be > 0, got {result}")
    return result


def require_int_non_negative(value: int, name: str) -> int:
    """Require an integer >= 0 (rejects bools, floats, and negatives)."""
    if isinstance(value, bool):
        raise DecisionInputError(f"{name} must be an int, got bool: {value!r}")
    if not isinstance(value, int):
        raise DecisionInputError(f"{name} must be an int, got {type(value).__name__}")
    if value < 0:
        raise DecisionInputError(f"{name} must be >= 0, got {value}")
    return value


def require_date(value: Union[date, datetime], name: str) -> date:
    """Require a date (datetime is narrowed to its .date())."""
    if isinstance(value, bool):
        raise DecisionInputError(f"{name} must be a date, got bool")
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, date):
        raise DecisionInputError(f"{name} must be a date, got {type(value).__name__}")
    return value


def require_ratio(value: Number, name: str) -> Decimal:
    """Require a value in the closed interval [0, 1] (a normalized score)."""
    result = to_decimal(value, name)
    if result < 0 or result > 1:
        raise DecisionInputError(f"{name} must be in [0, 1], got {result}")
    return result
