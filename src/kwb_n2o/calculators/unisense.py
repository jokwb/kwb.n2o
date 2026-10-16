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
        One Henry constant for the whole period instead of one per timestep.
        Not implemented yet (roadmap task 5).

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

    n2on_data_mgL: pd.Series = field(repr=False)
    air_data_zone_m3h: pd.Series = field(repr=False)
    temperature_data_C: pd.Series = field(repr=False)
    zone_area_m2: float
    reactor_depth_m: float
    smooth_data: bool = False
    static_henry: bool = False

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
    def henry_series(self) -> pd.Series:
        """Dimensionless Henry volatility constant Hccv [-] per timestep."""
        if self.static_henry:
            raise NotImplementedError("static_henry is roadmap task 5.")

        return N2OHenry().get_hccv_at_temperature(
            temperature_celsius=self.data[self._tmp_name]
        )

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
