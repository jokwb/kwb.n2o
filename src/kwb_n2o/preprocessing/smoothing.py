"""Smoothing of the dissolved N2O signal before the Unisense calculation."""

import numpy as np
import pandas as pd


def unisense_smooth(s: pd.Series, window: str, threshold: float = 0.3) -> pd.Series:
    """Blank out noisy stretches of a signal and interpolate over them.

    A value is dropped where the rolling relative standard deviation
    (std / mean over ``window``) exceeds ``threshold``; the dropped values
    are filled by linear interpolation.

    Parameters
    ----------
    s : Series
        Signal with a DatetimeIndex, e.g. dissolved N2O [mg L-1].
    window : str
        Rolling window as a pandas offset string, e.g. ``"5 min"``.
    threshold : float, default 0.3
        Relative standard deviation [-] above which values are dropped.

    Returns
    -------
    Series
        Same index and unit as ``s``.
    """
    if not isinstance(s, pd.Series) or not isinstance(s.index, pd.DatetimeIndex):
        raise TypeError("unisense_smooth needs a Series with a DatetimeIndex.")

    std = s.rolling(window=window).std()
    mn = s.rolling(window=window).mean()

    new_s = pd.Series(np.where(std / mn > threshold, np.nan, s), index=s.index)

    return new_s.interpolate("linear")
