from itertools import cycle
from more_itertools import windowed
from typing import Literal, Sequence, Union
import pandas as pd

_tcomponents = ["days", "hours", "minutes", "seconds", "milliseconds", "microseconds", "nanoseconds"]
TimedeltaComponents = Sequence[Literal[*_tcomponents]]
TimedeltaComponentsAttrMapping = {
    "days": "day",
    "hours": "hour",
    "minutes": "minute",
    "seconds": "second",
    "milliseconds": "millisecond",
    "microseconds": "microsecond",
    "nanoseconds": "nanosecond",
}

def merge_td_on_dt(
        datetime_data: Union[pd.DataFrame, pd.Series],
        timedelta_data: Union[pd.DataFrame, pd.Series]
        ):

    assert isinstance(datetime_data.index, pd.DatetimeIndex), "datetime_data must have a DatetimeIndex."
    assert isinstance(timedelta_data.index, pd.TimedeltaIndex), "timedelta_data must have a TimedeltaIndex."

    copy_as_df = lambda x: x.copy() if isinstance(x, pd.DataFrame) else x.to_frame().copy()

    _out = copy_as_df(datetime_data)
    _td = copy_as_df(timedelta_data)

    _comp = timedelta_data.index.components.loc[:, (timedelta_data.index.components != 0).any()]

    _td.index = pd.MultiIndex.from_arrays(arrays=[data for _, data in _comp.items()],
                                          names=[TimedeltaComponentsAttrMapping[c] for c in _comp.columns])

    index_levels = {c:getattr(_out.index, c) for c in _td.index.names}

    if "day" in index_levels.keys():
        _cycle = cycle(_td.index.get_level_values("day").unique())
        _current = next(_cycle)
        new_values = [_current]
        for v, w in windowed(index_levels["day"], 2):
            if w != v:
                _current = next(_cycle)
            new_values.append(_current)
        index_levels["day"] = pd.Index(data=new_values, name="day")

    _out.index = pd.MultiIndex.from_arrays([_out.index, *index_levels.values()],
                                           names=[_out.index.name, *index_levels.keys()])


    _out = _out.join(_td, how="left", on=_td.index.names)
    _out.index = _out.index.droplevel(list(range(1, _out.index.nlevels)))

    return _out
