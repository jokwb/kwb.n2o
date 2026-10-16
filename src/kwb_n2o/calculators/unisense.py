"""Liquid-phase pathway: dissolved N2O, airflow and temperature (Unisense)."""

from dataclasses import dataclass, field
from typing import ClassVar

import pandas as pd

from ..physics import N2OHenry, N2OkLa, UnisenseN2OEmission
from ..preprocessing import unisense_smooth
from ._validation import (
    require_datetime_series,
    require_positive,
    require_same_timezone,
)
from .base import EmissionCalculator


@dataclass
class UnisenseCalculation(EmissionCalculator):
    """N2O emission per area of an aerated zone from dissolved N2O.

    Based on the Unisense emission calculation note (v3) with two deliberate
    deviations: arbitrary timesteps, and the Henry constant derived at every
    timestep from the measured temperature (``static_henry=False``).

    Parameters
    ----------
    n2on_data_mgL : Series
        Dissolved N2O [mg L-1] with a DatetimeIndex. See
        docs/open_questions.md entry 1 for the N2O / N2O-N basis.
    air_data_zone_m3h : Series
        Airflow into the zone [m3 h-1].
    temperature_data_C : Series
        Liquid temperature [°C].
    zone_area_m2 : float
        Area of the aerated zone [m2].
    reactor_depth_m : float
        Water depth of the zone [m].
    smooth_data : bool, default False
        Apply ``unisense_smooth`` (5 min window, threshold 0.3) to the N2O
        series before aligning.
    static_henry : bool, default False
        One Henry constant for the whole period, as in the Unisense note,
        instead of one per timestep from the measured temperature.
    static_henry_temperature_C : float, optional
        Temperature [°C] at which the static Henry constant is formed.
        Default: mean of the aligned temperature series.
    static_henry_hcps_mol_m3_pa : float, optional
        Reference Hcps at 25 °C [mol m-3 Pa-1] for the static constant.
        Default: the value of the Unisense note (``UNISENSE_HCPS_MOL_M3_PA``).
        ``None`` uses the Sander (2023) mean, as the dynamic variant does.
    static_henry_b_k : float, optional
        Temperature dependence parameter B = -dsolnH/R [K] for the static
        constant. Default: the value of the Unisense note (``UNISENSE_B_K``).
        ``None`` uses the Sander (2023) mean, as the dynamic variant does.
        With both ``None`` the static variant is the dynamic one evaluated at
        a single temperature. See docs/open_questions.md entry 6.

    Notes
    -----
    The three series are aligned on their common timestamps between the
    first and last valid N2O value; timestamps with any NaN are dropped.
    """

    _n2o_name: ClassVar[str] = "n2o_[mg/L]"
    _air_name: ClassVar[str] = "air_[m3/h]"
    _tmp_name: ClassVar[str] = "temp_[°C]"

    SMOOTH_WINDOW: ClassVar[str] = "5 min"
    SMOOTH_THRESHOLD: ClassVar[float] = 0.3

    UNISENSE_HCPS_MOL_M3_PA: ClassVar[float] = 0.0247 * 1000 / 100_000
    """Henry solubility constant of N2O at 25 °C from the Unisense note (v3,
    table p. 2): 0.0247 mol L-1 bar-1 = 2.47e-4 mol m-3 Pa-1
    (1000 L m-3, 1e5 Pa bar-1)."""

    UNISENSE_B_K: ClassVar[float] = 2675.0
    """Temperature dependence -dsolnH/R of the Henry constant [K] from the
    Unisense note (v3, table p. 2), used in its eq. 4.2."""

    n2on_data_mgL: pd.Series = field(repr=False)
    air_data_zone_m3h: pd.Series = field(repr=False)
    temperature_data_C: pd.Series = field(repr=False)
    zone_area_m2: float
    reactor_depth_m: float
    smooth_data: bool = False
    static_henry: bool = False
    static_henry_temperature_C: float | None = None
    static_henry_hcps_mol_m3_pa: float | None = UNISENSE_HCPS_MOL_M3_PA
    static_henry_b_k: float | None = UNISENSE_B_K

    def __post_init__(self) -> None:
        require_datetime_series("n2on_data_mgL", self.n2on_data_mgL)
        require_datetime_series("air_data_zone_m3h", self.air_data_zone_m3h)
        require_datetime_series("temperature_data_C", self.temperature_data_C)
        require_same_timezone(
            n2on_data_mgL=self.n2on_data_mgL,
            air_data_zone_m3h=self.air_data_zone_m3h,
            temperature_data_C=self.temperature_data_C,
        )
        require_positive("zone_area_m2", self.zone_area_m2)
        require_positive("reactor_depth_m", self.reactor_depth_m)
        if self.static_henry_hcps_mol_m3_pa is not None:
            require_positive(
                "static_henry_hcps_mol_m3_pa", self.static_henry_hcps_mol_m3_pa
            )
        if self.static_henry_b_k is not None:
            require_positive("static_henry_b_k", self.static_henry_b_k)
        if self.static_henry_temperature_C is not None and not isinstance(
            self.static_henry_temperature_C, int | float
        ):
            raise TypeError("static_henry_temperature_C must be a number or None.")

        if self.smooth_data:
            self.n2on_data_mgL = unisense_smooth(
                self.n2on_data_mgL,
                window=self.SMOOTH_WINDOW,
                threshold=self.SMOOTH_THRESHOLD,
            )

        self._data = (
            pd.concat(
                [self.n2on_data_mgL, self.air_data_zone_m3h, self.temperature_data_C],
                axis=1,
                sort=True,
            )
            .loc[
                self.n2on_data_mgL.first_valid_index() : self.n2on_data_mgL.last_valid_index()
            ]
            .dropna(how="any")
        )

        self._data.columns = [self._n2o_name, self._air_name, self._tmp_name]

    @property
    def data(self) -> pd.DataFrame:
        """Aligned inputs: N2O [mg L-1], airflow [m3 h-1], temperature [°C]."""
        return self._data

    @property
    def henry_temperature_C(self) -> float:
        """Temperature [°C] the static Henry constant is formed at."""
        if self.static_henry_temperature_C is not None:
            return float(self.static_henry_temperature_C)
        return float(self.data[self._tmp_name].mean())

    @property
    def henry_series(self) -> pd.Series:
        """Dimensionless Henry volatility constant Hccv [-] per timestep.

        Dynamic (default): from the measured temperature at every timestep,
        with the Sander (2023) reference values.
        Static: one value at ``henry_temperature_C`` repeated over the period,
        by default with the constants of the Unisense note (eq. 4.1, 4.2).
        """
        temperature = self.data[self._tmp_name]

        if not self.static_henry:
            return N2OHenry().get_hccv_at_temperature(temperature_celsius=temperature)

        henry = N2OHenry()
        if self.static_henry_hcps_mol_m3_pa is not None:
            henry.override_standard_hcps(self.static_henry_hcps_mol_m3_pa)
        if self.static_henry_b_k is not None:
            henry.override_standard_correction_value(self.static_henry_b_k)
        hccv = henry.get_hccv_at_temperature(
            temperature_celsius=self.henry_temperature_C
        )

        return pd.Series(hccv, index=temperature.index, name=temperature.name)

    @property
    def kla(self) -> pd.Series:
        """Mass transfer coefficient kLa [s-1] per timestep."""
        return N2OkLa(
            aeration_field_m2=self.zone_area_m2, reactor_depth_m=self.reactor_depth_m
        ).get_kla_at_temperature(
            airflow_m3s=self.data[self._air_name] / 3600,
            temperature_celsius=self.data[self._tmp_name],
        )

    def get_emission(self) -> pd.Series:
        """Emission rate per area.

        Returns
        -------
        Series
            ``emission_rate [g N2ON m-2 h-1]``. Negative rates are set to
            zero (docs/open_questions.md entry 5).
        """
        rate_gm3s = UnisenseN2OEmission.calculate_n2o_emission_rate_aq(
            hccv=self.henry_series,
            c_n2o_aq=self.data[self._n2o_name],
            kla_s=self.kla,
            q_air_m3s=self.data[self._air_name] / 3600,
            v_r_m3=self.reactor_depth_m * self.zone_area_m2,
        )

        # g m-3 s-1 * m * s h-1 -> g m-2 h-1
        area_massflow = rate_gm3s * self.reactor_depth_m * 3600
        area_massflow.name = "emission_rate [g N2ON m-2 h-1]"

        return area_massflow.where(area_massflow >= 0, 0)
