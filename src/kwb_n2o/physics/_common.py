"""Helpers shared by the physics modules."""

import numpy as np
import pandas as pd


def same_index(*args: float | pd.Series) -> None:
    """Raise ``ValueError`` if the Series among ``args`` do not share one index.

    Physics functions do no alignment, so differing indexes would combine
    values of different timestamps.
    """
    series = [a for a in args if isinstance(a, pd.Series)]
    for s in series[1:]:
        if not s.index.equals(series[0].index):
            raise ValueError(
                "All Series arguments must share the same index; align them first."
            )


def as_series_like(values: np.ndarray, *args: float | pd.Series) -> float | pd.Series:
    """Wrap an array as a Series with the index of the first Series in ``args``.

    With no Series among ``args`` the scalar value is returned.
    """
    for a in args:
        if isinstance(a, pd.Series):
            return pd.Series(values, index=a.index)
    return values.item()
