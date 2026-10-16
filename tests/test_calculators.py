"""Input validation of the calculators. Numbers are covered by the golden tests."""

import warnings

import numpy as np
import pandas as pd
import pytest

from kwb_n2o import (
    EmissionFactorCalculation,
    OffGasCalculation,
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


def _varying_temperature():
    return pd.Series(np.linspace(16.0, 20.0, len(IDX)), IDX)


def test_static_henry_is_constant_over_the_period():
    calc = UnisenseCalculation(
        _series(0.1),
        _series(2000),
        _varying_temperature(),
        250.0,
        5.0,
        static_henry=True,
    )
    henry = calc.henry_series
    assert henry.index.equals(calc.data.index)
    assert henry.nunique() == 1
    assert calc.henry_temperature_C == pytest.approx(18.0)


def test_dynamic_henry_varies_with_temperature():
    calc = UnisenseCalculation(
        _series(0.1), _series(2000), _varying_temperature(), 250.0, 5.0
    )
    assert calc.henry_series.nunique() == len(IDX)


def test_static_henry_with_sander_data_equals_dynamic_at_constant_temperature():
    kwargs = {
        "static_henry": True,
        "static_henry_hcps_mol_m3_pa": None,
        "static_henry_b_k": None,
    }
    static = UnisenseCalculation(
        _series(0.1), _series(2000), _series(18), 250.0, 5.0, **kwargs
    )
    dynamic = UnisenseCalculation(_series(0.1), _series(2000), _series(18), 250.0, 5.0)
    np.testing.assert_allclose(
        static.henry_series.to_numpy(), dynamic.henry_series.to_numpy(), rtol=1e-12
    )
    np.testing.assert_allclose(
        static.get_emission().to_numpy(), dynamic.get_emission().to_numpy(), rtol=1e-12
    )


def test_static_henry_default_is_the_unisense_constant():
    # At the 25 °C reference temperature no temperature correction applies:
    # Hccv = 1 / (Hcps * R * T) with Hcps = 0.0247 mol L-1 bar-1.
    calc = UnisenseCalculation(
        _series(0.1),
        _series(2000),
        _series(18),
        250.0,
        5.0,
        static_henry=True,
        static_henry_temperature_C=25.0,
    )
    expected = 1 / (2.47e-4 * 8.314 * 298.15)
    np.testing.assert_allclose(calc.henry_series.to_numpy(), expected, rtol=1e-12)
    assert calc.henry_temperature_C == 25.0


def test_static_henry_follows_the_unisense_note_at_process_temperature():
    # Unisense note v3, eq. 4.1 and 4.2 with k_H° = 0.0247 mol L-1 bar-1,
    # -dsolnH/R = 2675 K, T° = 25 °C, R = 8.314e-5 m3 bar mol-1 K-1.
    calc = UnisenseCalculation(
        _series(0.1), _series(2000), _series(18), 250.0, 5.0, static_henry=True
    )
    t_k = 18.0 + 273.15
    k_h = 0.0247 * np.exp(2675 * (1 / t_k - 1 / 298.15))  # mol L-1 bar-1
    expected = 1 / (k_h * 8.314e-5 * t_k * 1e3)
    np.testing.assert_allclose(calc.henry_series.to_numpy(), expected, rtol=1e-12)


def test_static_henry_differs_from_dynamic_with_varying_temperature():
    static = UnisenseCalculation(
        _series(0.1),
        _series(2000),
        _varying_temperature(),
        250.0,
        5.0,
        static_henry=True,
    )
    dynamic = UnisenseCalculation(
        _series(0.1), _series(2000), _varying_temperature(), 250.0, 5.0
    )
    assert not np.allclose(
        static.get_emission().to_numpy(), dynamic.get_emission().to_numpy()
    )
    assert np.isfinite(static.get_emission().to_numpy()).all()


def test_static_henry_rejects_bad_parameters():
    with pytest.raises(ValueError, match="greater than zero"):
        UnisenseCalculation(
            _series(0.1),
            _series(2000),
            _series(18),
            250.0,
            5.0,
            static_henry_hcps_mol_m3_pa=0.0,
        )
    with pytest.raises(ValueError, match="greater than zero"):
        UnisenseCalculation(
            _series(0.1), _series(2000), _series(18), 250.0, 5.0, static_henry_b_k=-1.0
        )
    with pytest.raises(TypeError, match="number or None"):
        UnisenseCalculation(
            _series(0.1),
            _series(2000),
            _series(18),
            250.0,
            5.0,
            static_henry_temperature_C="20",
        )


def test_off_gas_rejects_mixed_timezones():
    utc = _series(18, IDX.tz_convert("UTC"))
    with pytest.raises(ValueError, match="time zone"):
        OffGasCalculation(_series(30), _series(8), utc)


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
