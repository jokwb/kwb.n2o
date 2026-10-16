"""Joining a repeating profile (TimedeltaIndex) onto a timeseries (DatetimeIndex)."""

from itertools import cycle

import pandas as pd
from more_itertools import windowed

TIMEDELTA_COMPONENT_TO_DATETIME_ATTR = {
    "days": "day",
    "hours": "hour",
    "minutes": "minute",
    "seconds": "second",
    "milliseconds": "millisecond",
    "microseconds": "microsecond",
    "nanoseconds": "nanosecond",
}


def merge_td_on_dt(
    datetime_data: pd.DataFrame | pd.Series,
    timedelta_data: pd.DataFrame | pd.Series,
) -> pd.DataFrame:
    """Left-join a profile with a TimedeltaIndex onto data with a DatetimeIndex.

    The profile is matched on the time-of-day components that are non-zero
    somewhere in its index: an hourly profile over one day is matched on
    the hour, a 15 min profile on hour and minute. If the profile spans
    several days, its ``days`` component is cycled over the calendar days
    of ``datetime_data``.

    Parameters
    ----------
    datetime_data : DataFrame or Series
        Timeseries with a DatetimeIndex.
    timedelta_data : DataFrame or Series
        Profile with a TimedeltaIndex. Column (or Series) names must not
        overlap with those of ``datetime_data``.

    Returns
    -------
    DataFrame
        ``datetime_data`` with the profile columns appended; rows without a
        matching profile entry get NaN.
    """
    if not isinstance(datetime_data.index, pd.DatetimeIndex):
        raise TypeError("datetime_data must have a DatetimeIndex.")
    if not isinstance(timedelta_data.index, pd.TimedeltaIndex):
        raise TypeError("timedelta_data must have a TimedeltaIndex.")

    def copy_as_df(x: pd.DataFrame | pd.Series) -> pd.DataFrame:
        return x.copy() if isinstance(x, pd.DataFrame) else x.to_frame().copy()

    _out = copy_as_df(datetime_data)
    _td = copy_as_df(timedelta_data)

    components = timedelta_data.index.components
    _comp = components.loc[:, (components != 0).any()]

    _td.index = pd.MultiIndex.from_arrays(
        arrays=[data for _, data in _comp.items()],
        names=[TIMEDELTA_COMPONENT_TO_DATETIME_ATTR[c] for c in _comp.columns],
    )

    index_levels = {c: getattr(_out.index, c) for c in _td.index.names}

    if "day" in index_levels:
        _cycle = cycle(_td.index.get_level_values("day").unique())
        _current = next(_cycle)
        new_values = [_current]
        for v, w in windowed(index_levels["day"], 2):
            if w != v:
                _current = next(_cycle)
            new_values.append(_current)
        index_levels["day"] = pd.Index(data=new_values, name="day")

    _out.index = pd.MultiIndex.from_arrays(
        [_out.index, *index_levels.values()],
        names=[_out.index.name, *index_levels.keys()],
    )

    _out = _out.join(_td, how="left", on=_td.index.names)
    _out.index = _out.index.droplevel(list(range(1, _out.index.nlevels)))

    return _out
