"""Input validation of the calculators. Numbers are covered by the golden tests."""

import warnings

import numpy as np
import pandas as pd
import pytest

from kwb_n2o import (
    EmersonCalculation,
    EmissionFactorCalculation,
    TKNMassflowCalculation,
    UnisenseCalculation,
)

TZ = "Europe/Berlin"
IDX = pd.date_range("2025-01-01", periods=12, freq="5min", tz=TZ)


def _series(value, index=IDX):
    return pd.Series(np.full(len(index), float(value)), index)


def test_unisense_rejects_non_series():
    with pytest.raises(TypeError, match="pandas Series"):
        UnisenseCalculation([0.1] * 12, _series(2000), _series(18), 250.0, 5.0)


def test_unisense_rejects_non_datetime_index():
    with pytest.raises(TypeError, match="DatetimeIndex"):
        UnisenseCalculation(
            pd.Series(0.1, range(12)), _series(2000), _series(18), 250.0, 5.0
        )


def test_unisense_rejects_mixed_timezones():
    naive = _series(18, IDX.tz_localize(None))
    with pytest.raises(ValueError, match="time zone"):
        UnisenseCalculation(_series(0.1), _series(2000), naive, 250.0, 5.0)


@pytest.mark.parametrize("area, depth", [(0.0, 5.0), (250.0, -1.0)])
def test_unisense_rejects_non_positive_geometry(area, depth):
    with pytest.raises(ValueError, match="greater than zero"):
        UnisenseCalculation(_series(0.1), _series(2000), _series(18), area, depth)


def test_unisense_static_henry_not_implemented_yet():
    calc = UnisenseCalculation(
        _series(0.1), _series(2000), _series(18), 250.0, 5.0, static_henry=True
    )
    with pytest.raises(NotImplementedError):
        _ = calc.henry_series


def test_off_gas_rejects_mixed_timezones():
    utc = _series(18, IDX.tz_convert("UTC"))
    with pytest.raises(ValueError, match="time zone"):
        EmersonCalculation(_series(30), _series(8), utc)


def test_tkn_profile_needs_timedelta_index():
    with pytest.raises(TypeError, match="TimedeltaIndex"):
        TKNMassflowCalculation(_series(90), _series(100))


def test_tkn_profile_needs_regular_frequency():
    profile = pd.Series([90.0, 80.0, 70.0], pd.to_timedelta(["0h", "1h", "5h"]))
    with pytest.raises(ValueError, match="frequency"):
        TKNMassflowCalculation(profile, _series(100))


def test_tkn_rejects_wrong_type():
    with pytest.raises(TypeError, match="number or a Series"):
        TKNMassflowCalculation("90", _series(100))


def test_ef_localizes_naive_tkn_with_warning():
    emission = _series(1.0)
    naive_tkn = _series(9000, IDX.tz_localize(None))
    with pytest.warns(UserWarning, match="localized to Europe/Berlin"):
        ef = EmissionFactorCalculation(emission, naive_tkn, 250.0).ef
    assert len(ef) == len(IDX)
    np.testing.assert_allclose(ef.to_numpy(), 250.0 / 9000)


def test_ef_converts_other_timezone_with_warning():
    emission = _series(1.0)
    utc_tkn = _series(9000, IDX.tz_convert("UTC"))
    with pytest.warns(UserWarning, match="converted from UTC"):
        ef = EmissionFactorCalculation(emission, utc_tkn, 250.0).ef
    assert str(ef.index.tz) == TZ


def test_ef_same_timezone_is_silent():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _ = EmissionFactorCalculation(_series(1.0), _series(9000), 250.0).ef


def test_ef_rejects_naive_emission_with_aware_tkn():
    naive_emission = _series(1.0, IDX.tz_localize(None))
    with pytest.raises(ValueError, match="tz-naive"):
        EmissionFactorCalculation(naive_emission, _series(9000), 250.0)
