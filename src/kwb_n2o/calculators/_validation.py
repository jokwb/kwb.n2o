"""Input checks shared by the calculators. Explicit exceptions, no asserts."""

import pandas as pd


def require_datetime_series(name: str, series: object) -> None:
    """Raise ``TypeError`` unless ``series`` is a Series with a DatetimeIndex."""
    if not isinstance(series, pd.Series):
        raise TypeError(f"{name} must be a pandas Series, got {type(series).__name__}.")
    if not isinstance(series.index, pd.DatetimeIndex):
        raise TypeError(
            f"{name} must have a DatetimeIndex, got {type(series.index).__name__}."
        )


def require_same_timezone(**series: pd.Series) -> None:
    """Raise ``ValueError`` if the series are not all in the same time zone.

    Mixing tz-naive and tz-aware series, or different zones, would combine
    values of different instants, so it is never done silently.
    """
    zones = {name: s.index.tz for name, s in series.items()}
    if len({str(tz) for tz in zones.values()}) > 1:
        detail = ", ".join(f"{name}: {tz}" for name, tz in zones.items())
        raise ValueError(
            f"All input series must share one time zone; got {detail}. "
            "Localize or convert them explicitly first."
        )


def require_positive(name: str, value: float) -> None:
    """Raise ``ValueError`` unless ``value`` is a number greater than zero."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{name} must be a number, got {type(value).__name__}.")
    if not value > 0:
        raise ValueError(f"{name} must be greater than zero, got {value}.")
