"""Behaviour of the preprocessing functions beyond the golden numbers."""

import numpy as np
import pandas as pd
import pytest

from kwb_n2o import merge_td_on_dt, unisense_smooth

IDX = pd.date_range("2025-01-01", periods=60, freq="1min", tz="Europe/Berlin")


def test_smooth_replaces_glitch_by_interpolation():
    s = pd.Series(1.0, IDX)
    s.iloc[30] = 10.0
    smoothed = unisense_smooth(s, window="5 min", threshold=0.3)
    np.testing.assert_allclose(smoothed.to_numpy(), 1.0)


def test_smooth_keeps_quiet_signal():
    s = pd.Series(np.linspace(1.0, 1.1, len(IDX)), IDX)
    pd.testing.assert_series_equal(
        unisense_smooth(s, window="5 min"), s, check_names=False
    )


def test_smooth_rejects_non_datetime_index():
    with pytest.raises(TypeError, match="DatetimeIndex"):
        unisense_smooth(pd.Series([1.0, 2.0]), window="5 min")


def test_merge_hourly_profile_matches_on_hour():
    profile = pd.Series(
        np.arange(24.0), pd.timedelta_range("0h", "23h", freq="h"), name="tkn"
    )
    data = pd.Series(
        1.0,
        pd.date_range("2025-01-01", periods=48, freq="30min", tz="Europe/Berlin"),
        name="q",
    )
    merged = merge_td_on_dt(data, profile)
    assert list(merged.columns) == ["q", "tkn"]
    np.testing.assert_array_equal(
        merged["tkn"].to_numpy(), np.repeat(np.arange(24.0), 2)
    )


def test_merge_rejects_wrong_index_types():
    profile = pd.Series([1.0], pd.timedelta_range("0h", periods=1, freq="h"))
    with pytest.raises(TypeError, match="DatetimeIndex"):
        merge_td_on_dt(pd.Series([1.0], [0]), profile)
    with pytest.raises(TypeError, match="TimedeltaIndex"):
        merge_td_on_dt(pd.Series([1.0], IDX[:1]), pd.Series([1.0], IDX[:1]))
