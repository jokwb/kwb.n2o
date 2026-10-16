import numpy as np
import pandas as pd


def unisense_signal_correction(
    s: pd.Series, rstd_treshold: float = 0.3, window: str = "1 h"
) -> pd.Series:
    _s = s.copy()

    _s = _s.rolling(window=window).std() / _s.rolling(window=window).mean()

    s_new = np.where(_s > rstd_treshold, np.nan, s)

    s_new = pd.Series(s_new, index=s.index).interpolate("linear")

    return s_new


def unisense_signal_correction_quantile(
    s: pd.Series, q: float = 0.9, window: str = "2 h"
):
    # nicht gut, es gibt IMMER Werte die davon betroffen sind, auch bei vernünftigem Verlauf

    _s = s.rolling(window=window).quantile(q)

    return pd.Series(np.where(s > _s, np.nan, s), index=s.index).interpolate("linear")


def unisense_smooth(s, window, treshold=0.3):
    std = s.rolling(window=window).std()
    mn = s.rolling(window=window).mean()

    new_s = pd.Series(
        np.where(std / mn > treshold, np.nan, s), index=s.index
    ).interpolate("linear")

    return new_s


def add_next_day_to_index(idx: pd.DatetimeIndex):
    if not isinstance(idx, pd.DatetimeIndex):
        _idx = pd.to_datetime(idx)
    else:
        _idx = idx

    next_date = pd.DatetimeIndex([pd.Timestamp(_idx[-1]) + pd.DateOffset(days=1)])

    _idx = _idx.append(next_date)

    return _idx


def cut_peaks(s: pd.Series, peak_treshold: float, n_bfill: int, n_ffill: int):
    _s = pd.Series(np.where(s > peak_treshold, 1, np.nan))
    _s = _s.bfill(limit=n_bfill).ffill(limit=n_ffill)

    new_s = pd.Series(np.where(_s == 1, np.nan, s), index=s.index)

    new_s = new_s.interpolate("linear")

    return new_s


def dtindex_timesteps(datetime_index: pd.DatetimeIndex) -> pd.Series:
    # Returns difference between idx n+1 and idx n as seconds
    delta = (
        datetime_index.to_series() - datetime_index.to_series().shift(1)
    ).dt.total_seconds()
    delta.iloc[0] = (datetime_index[1] - datetime_index[0]).total_seconds()

    return delta
