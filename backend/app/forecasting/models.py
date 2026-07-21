"""
Quantile forecasters backed by tree ensembles.

Two interchangeable engines, both producing p10 / p50 / p90 (matching the
``forecast_cache`` schema columns):

  * random_forest -- one RandomForestRegressor; quantiles are read off the
                     spread of the individual trees' predictions (a lightweight
                     quantile-regression-forest approximation).
  * xgboost       -- one XGBRegressor per quantile using the native quantile
                     loss (``reg:quantileerror``), available in xgboost >= 2.0.

Both expose the same ``fit`` / ``predict_quantiles`` interface so the service
layer is engine-agnostic.
"""

from __future__ import annotations

from typing import Dict, Sequence

import numpy as np
import pandas as pd

QUANTILES: tuple[float, float, float] = (0.10, 0.50, 0.90)
RANDOM_STATE = 42

MODEL_TYPES = ("random_forest", "xgboost")


class QuantileForecaster:
    """Engine-agnostic quantile regressor over the tabular features."""

    def __init__(
        self,
        model_type: str = "random_forest",
        quantiles: Sequence[float] = QUANTILES,
        random_state: int = RANDOM_STATE,
    ):
        if model_type not in MODEL_TYPES:
            raise ValueError(
                f"unknown model_type {model_type!r}; expected one of {MODEL_TYPES}"
            )
        self.model_type = model_type
        self.quantiles = tuple(quantiles)
        self.random_state = random_state
        self._rf = None
        self._xgb: Dict[float, object] = {}

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "QuantileForecaster":
        if len(X) == 0:
            raise ValueError("cannot fit on an empty training set")

        if self.model_type == "random_forest":
            from sklearn.ensemble import RandomForestRegressor

            # Modest depth/leaf size — series are short (weeks-to-months of daily
            # data), so we guard against overfitting the noise.
            self._rf = RandomForestRegressor(
                n_estimators=300,
                min_samples_leaf=3,
                max_features="sqrt",
                random_state=self.random_state,
                n_jobs=-1,
            )
            self._rf.fit(X.values, y.values)
        else:
            import xgboost as xgb

            for q in self.quantiles:
                model = xgb.XGBRegressor(
                    objective="reg:quantileerror",
                    quantile_alpha=q,
                    n_estimators=300,
                    max_depth=3,
                    learning_rate=0.05,
                    subsample=0.9,
                    colsample_bytree=0.9,
                    random_state=self.random_state,
                    n_jobs=-1,
                )
                model.fit(X.values, y.values)
                self._xgb[q] = model
        return self

    def predict_quantiles(self, X: pd.DataFrame) -> Dict[float, np.ndarray]:
        """Return {quantile: array-of-predictions}, one prediction per row of X."""
        if self.model_type == "random_forest":
            if self._rf is None:
                raise RuntimeError("model is not fitted")
            # Stack every tree's prediction -> (n_trees, n_rows), then read the
            # empirical quantiles across trees for each row.
            per_tree = np.stack(
                [est.predict(X.values) for est in self._rf.estimators_], axis=0
            )
            out = {
                q: np.percentile(per_tree, q * 100.0, axis=0) for q in self.quantiles
            }
        else:
            if not self._xgb:
                raise RuntimeError("model is not fitted")
            out = {q: self._xgb[q].predict(X.values) for q in self.quantiles}

        # Clamp to non-negative (consumption can't be negative) and enforce
        # monotonicity p10 <= p50 <= p90 (independent quantile models can cross).
        for q in out:
            out[q] = np.clip(out[q], 0.0, None)
        qs = sorted(self.quantiles)
        stacked = np.stack([out[q] for q in qs], axis=0)
        stacked = np.sort(stacked, axis=0)
        return {q: stacked[i] for i, q in enumerate(qs)}

    def predict_median(self, X: pd.DataFrame) -> np.ndarray:
        return self.predict_quantiles(X)[0.50]
