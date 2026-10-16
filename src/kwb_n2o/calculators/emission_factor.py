from dataclasses import dataclass, field
from functools import cached_property
from typing import ClassVar

import pandas as pd

from ..preprocessing import merge_td_on_dt


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
