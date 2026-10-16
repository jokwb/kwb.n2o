from dataclasses import dataclass, field
from functools import cached_property
from typing import ClassVar, Protocol

import pandas as pd

from .preprocessing import merge_td_on_dt, unisense_smooth
from .physics import EmersonN2OEmission, N2OHenry, N2OkLa, UnisenseN2OEmission


class EmissionCalculator(Protocol):
    def get_emission(self, *args, **kwargs) -> pd.Series: ...


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
                self.n2on_data_mgL, window="5 min", treshold=0.3
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
            aearation_field_size=self.zone_area_m2, reactor_depth=self.reactor_depth_m
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

        area_massflow = massflow[massflow.columns[-1]] * self.reactor_depth_m * 3600
        area_massflow.name = "emission_rate [g N2ON m-2 h-1]"

        area_massflow = area_massflow.where(area_massflow >= 0, 0)

        return area_massflow


@dataclass
class EmersonCalculation(EmissionCalculator):
    _n2o_name: ClassVar[str] = "n2o_[ppm]"
    _air_name: ClassVar[str] = "air_[m3/h]"
    _tmp_name: ClassVar[str] = "temp_[°C]"

    n2o_data_ppm: pd.Series = field(default_factory=pd.Series, repr=False)
    air_data_m3m2h: pd.Series = field(default_factory=pd.Series, repr=False)
    temperature_data_C: pd.Series = field(default_factory=pd.Series, repr=False)

    def __post_init__(self):
        self._data = (
            pd.concat(
                [self.n2o_data_ppm, self.air_data_m3m2h, self.temperature_data_C],
                axis=1,
            )
            .loc[
                self.n2o_data_ppm.first_valid_index() : self.n2o_data_ppm.last_valid_index()
            ]
            .dropna(how="any")
        )

        self._data.columns = [self._n2o_name, self._air_name, self._tmp_name]

    @property
    def data(self):
        return self._data

    def get_emission(self) -> pd.Series:
        emission = (
            EmersonN2OEmission.calculate_n2o_mass_flow_gas(
                ppm_n2o_gas=self.data[self._n2o_name],
                q_air_m3s=self.data[self._air_name] / 3600,
                temperature_celsius=self.data[self._tmp_name],
            )
            * 28
            / 44
            * 3600
        )

        emission.name = "emission_rate [g N2ON m-2 h-1]"

        emission = emission.where(emission >= 0, 0)

        return emission.dropna()


@dataclass
class TKNMassflowCalculation:
    _tkn_name: ClassVar[str] = "tkn_g*m-3"
    _q_name: ClassVar[str] = "q_m3*h-1"
    _mf_name: ClassVar[str] = "mdot_g*h-1"

    tkn_mgl: int | float | pd.Series = field(default_factory=float)
    inflow_m3h: pd.Series = field(default_factory=pd.Series)

    def __post_init__(self):
        if not isinstance(self.tkn_mgl, (float, int)):
            self._validate_tkn()

    def _validate_tkn(self):
        assert isinstance(self.tkn_mgl.index, pd.TimedeltaIndex), (
            "TKN series needs timedelta index."
        )

        self.freq = pd.infer_freq(self.tkn_mgl.index)

        assert self.freq is not None, "Unable to extract series frequency."

    @cached_property
    def data(self):
        data = self.inflow_m3h.to_frame()

        if isinstance(self.tkn_mgl, (float, int)):
            data[self._tkn_name] = self.tkn_mgl

        else:
            data = merge_td_on_dt(data, self.tkn_mgl)

        data.columns = [self._q_name, self._tkn_name]
        return data

    def get_massflow(self, start_date: str | None = None, end_date: str | None = None):
        indexer = pd.IndexSlice[start_date:end_date]

        data = self.data.loc[indexer]

        massflow = (
            data[self._q_name] * data[self._tkn_name]
        )  # m3 * h-1  *  g * m-3 => g * h-1
        massflow.name = self._mf_name

        return massflow


@dataclass
class EmissionFactorCalculation:
    _ef_name: ClassVar[str] = "ef"
    _n2o_mf_name: ClassVar[str] = "mdot_n2on_g*h-1"
    _tn_mf_name: ClassVar[str] = "mdot_tkn_g*h-1"

    mdot_n2o_area_gm2h1: pd.Series
    mdot_tkn_gh: pd.Series
    zone_area_m2: float

    def __post_init__(self):
        self._validate()

    def _validate(self):
        """
        tz: n2o tz > flow tz
        """

        if (tzn := self.mdot_n2o_area_gm2h1.index.tz) != (
            tzf := self.mdot_tkn_gh.index.tz
        ):
            if tzf is None:
                print(f"Warning! tz-naive series {self._tn_mf_name} converted to {tzn}")
                self.mdot_tkn_gh = self.mdot_tkn_gh.tz_localize(tzn, ambiguous="infer")
            else:
                self.mdot_tkn_gh = self.mdot_tkn_gh.tz_convert(tzn)

        self.tz = tzn

    @cached_property
    def data(self):
        data = pd.concat([self.mdot_n2o_area_gm2h1, self.mdot_tkn_gh], axis=1).dropna(
            how="any"
        )
        data = data.tz_convert(self.tz)
        data.columns = [self._n2o_mf_name, self._tn_mf_name]
        data[self._n2o_mf_name] = self.zone_area_m2 * data[self._n2o_mf_name]
        return data

    @cached_property
    def ef(self):
        ef = self.data[self._n2o_mf_name] / self.data[self._tn_mf_name]
        ef.name = self._ef_name

        return ef
