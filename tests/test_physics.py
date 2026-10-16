"""Behaviour of the physics functions beyond the golden numbers."""

import numpy as np
import pandas as pd
import pytest

from kwb_n2o import EmersonN2OEmission, N2OHenry, N2OkLa, UnisenseN2OEmission

IDX = pd.date_range("2025-01-01", periods=3, freq="5min", tz="Europe/Berlin")


def test_liquid_phase_scalar_inputs_return_float():
    rate = UnisenseN2OEmission.calculate_n2o_emission_rate_aq(
        hccv=1.7, c_n2o_aq=0.2, q_air_m3s=0.5, v_r_m3=1000.0, kla_s=1e-3
    )
    assert isinstance(rate, float)
    assert rate > 0


def test_liquid_phase_series_inputs_return_series_with_same_index():
    rate = UnisenseN2OEmission.calculate_n2o_emission_rate_aq(
        hccv=pd.Series(1.7, IDX),
        c_n2o_aq=pd.Series([0.2, 0.2, 0.2], IDX),
        q_air_m3s=pd.Series([0.5, 0.0, 0.5], IDX),
        v_r_m3=1000.0,
        kla_s=pd.Series(1e-3, IDX),
    )
    assert isinstance(rate, pd.Series)
    assert rate.index.equals(IDX)


def test_liquid_phase_optional_emission_type():
    rate, kind = UnisenseN2OEmission.calculate_n2o_emission_rate_aq(
        hccv=pd.Series(1.7, IDX),
        c_n2o_aq=pd.Series(0.2, IDX),
        q_air_m3s=pd.Series([0.5, 0.001, 0.5], IDX),
        v_r_m3=1000.0,
        kla_s=pd.Series(1e-3, IDX),
        return_emission_type=True,
    )
    assert list(kind) == ["aerated", "non_aerated", "aerated"]
    assert rate.iloc[1] != rate.iloc[0]


def test_liquid_phase_rejects_misaligned_series():
    other = IDX.shift(1)
    with pytest.raises(ValueError, match="same index"):
        UnisenseN2OEmission.calculate_n2o_emission_rate_aq(
            hccv=pd.Series(1.7, IDX),
            c_n2o_aq=pd.Series(0.2, other),
            q_air_m3s=pd.Series(0.5, IDX),
            v_r_m3=1000.0,
            kla_s=pd.Series(1e-3, IDX),
        )


def test_off_gas_accepts_scalar_temperature():
    # Open question 3: the old length check raised TypeError on scalars.
    flow = EmersonN2OEmission.calculate_n2o_mass_flow_gas(
        q_air_m3s=pd.Series(0.01, IDX),
        ppm_n2o_gas=pd.Series(30.0, IDX),
        temperature_celsius=18.0,
    )
    assert isinstance(flow, pd.Series)
    expected = 101325 * 30e-6 / (8.314 * 291.15) * 0.01 * 44
    np.testing.assert_allclose(flow.to_numpy(), expected)


def test_off_gas_rejects_misaligned_series():
    with pytest.raises(ValueError, match="same index"):
        EmersonN2OEmission.calculate_n2o_mass_flow_gas(
            q_air_m3s=pd.Series(0.01, IDX),
            ppm_n2o_gas=pd.Series(30.0, IDX.shift(1)),
            temperature_celsius=18.0,
        )


def test_henry_hccv_decreases_with_solubility():
    henry = N2OHenry()
    assert henry.get_hccv_at_temperature(10.0) < henry.get_hccv_at_temperature(25.0)
    assert henry.get_hccs_at_temperature(25.0) == pytest.approx(
        1 / henry.get_hccv_at_temperature(25.0)
    )


def test_kla_scalar_and_series_agree():
    kla = N2OkLa(aeration_field_m2=250.0, reactor_depth_m=5.0)
    scalar = kla.get_kla_at_temperature(airflow_m3s=0.5, temperature_celsius=18.0)
    series = kla.get_kla_at_temperature(
        airflow_m3s=pd.Series(0.5, IDX), temperature_celsius=pd.Series(18.0, IDX)
    )
    np.testing.assert_allclose(series.to_numpy(), scalar)
