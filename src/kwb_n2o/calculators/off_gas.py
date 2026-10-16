from dataclasses import dataclass, field
from typing import ClassVar

import pandas as pd

from ..physics import EmersonN2OEmission
from .base import EmissionCalculator


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
