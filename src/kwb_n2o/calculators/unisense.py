from dataclasses import dataclass, field
from typing import ClassVar

import pandas as pd

from ..physics import N2OHenry, N2OkLa, UnisenseN2OEmission
from ..preprocessing import unisense_smooth
from .base import EmissionCalculator


@dataclass
class UnisenseCalculation(EmissionCalculator):
    _n2o_name: ClassVar[str] = "n2o_[mg/L]"
    _air_name: ClassVar[str] = "air_[m3/h]"
    _tmp_name: ClassVar[str] = "temp_[°C]"

    n2on_data_mgL: pd.Series = field(default_factory=pd.Series, repr=False)
    air_data_zone_m3h: pd.Series = field(default_factory=pd.Series, repr=False)
    temperature_data_C: pd.Series = field(default_factory=pd.Series, repr=False)
    zone_area_m2: float = field(default_factory=float, repr=False)
    reactor_depth_m: float = field(default_factory=float, repr=False)
    smooth_data: bool = field(default=False)
    static_henry: bool = False

    def __post_init__(self):
        if self.smooth_data:
            self.n2on_data_mgL = unisense_smooth(
                self.n2on_data_mgL, window="5 min", threshold=0.3
            )

        self._data = (
            pd.concat(
                [self.n2on_data_mgL, self.air_data_zone_m3h, self.temperature_data_C],
                axis=1,
            )
            .loc[
                self.n2on_data_mgL.first_valid_index() : self.n2on_data_mgL.last_valid_index()
            ]
            .dropna(how="any")
        )

        self._data.columns = [self._n2o_name, self._air_name, self._tmp_name]

    @property
    def data(self):
        return self._data

    @property
    def henry_series(self):
        if self.static_henry:
            # TODO: make this work
            raise NotImplementedError()

        else:
            return N2OHenry().get_hccv_at_temperature(
                temperature_celsius=self.data[self._tmp_name]
            )

    @property
    def kla(self):
        kla = N2OkLa(
            aeration_field_m2=self.zone_area_m2, reactor_depth_m=self.reactor_depth_m
        ).get_kla_at_temperature(
            airflow_m3s=self.data[self._air_name] / 3600,
            temperature_celsius=self.data[self._tmp_name],
        )
        return kla

    def get_emission(self) -> pd.Series:
        henry = self.henry_series
        kla = self.kla

        massflow = UnisenseN2OEmission.calculate_n2o_emission_rate_aq(
            hccv=henry,
            c_n2o_aq=self.data[self._n2o_name],
            kla_s=kla,
            q_air_m3s=self.data[self._air_name] / 3600,
            v_r_m3=self.reactor_depth_m * self.zone_area_m2,
        )

        area_massflow = massflow * self.reactor_depth_m * 3600
        area_massflow.name = "emission_rate [g N2ON m-2 h-1]"

        area_massflow = area_massflow.where(area_massflow >= 0, 0)

        return area_massflow
