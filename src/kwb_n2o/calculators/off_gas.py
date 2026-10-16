"""Gas-phase pathway: N2O in the off-gas, area-specific airflow and temperature."""

from dataclasses import dataclass, field
from typing import ClassVar

import pandas as pd

from ..physics import OffGasN2OEmission
from ._validation import require_datetime_series, require_same_timezone
from .base import EmissionCalculator


@dataclass
class OffGasCalculation(EmissionCalculator):
    """N2O emission per area of an aerated zone from the off-gas concentration.

    The method applies to any off-gas measurement, whatever the analyzer.

    Parameters
    ----------
    n2o_data_ppm : Series
        N2O in the off-gas [ppm] with a DatetimeIndex.
    air_data_m3m2h : Series
        Area-specific airflow [m3 m-2 h-1].
    temperature_data_C : Series
        Temperature used in the ideal gas law [°C]. See
        docs/open_questions.md entry 4.

    Notes
    -----
    The three series are aligned on their common timestamps between the
    first and last valid ppm value; timestamps with any NaN are dropped.
    """

    _n2o_name: ClassVar[str] = "n2o_[ppm]"
    _air_name: ClassVar[str] = "air_[m3/m2/h]"
    _tmp_name: ClassVar[str] = "temp_[°C]"

    N2O_N_PER_N2O: ClassVar[float] = 28 / 44
    """Mass ratio N2O-N / N2O [-] (2 * 14 / 44)."""

    n2o_data_ppm: pd.Series = field(repr=False)
    air_data_m3m2h: pd.Series = field(repr=False)
    temperature_data_C: pd.Series = field(repr=False)

    def __post_init__(self) -> None:
        require_datetime_series("n2o_data_ppm", self.n2o_data_ppm)
        require_datetime_series("air_data_m3m2h", self.air_data_m3m2h)
        require_datetime_series("temperature_data_C", self.temperature_data_C)
        require_same_timezone(
            n2o_data_ppm=self.n2o_data_ppm,
            air_data_m3m2h=self.air_data_m3m2h,
            temperature_data_C=self.temperature_data_C,
        )

        self._data = (
            pd.concat(
                [self.n2o_data_ppm, self.air_data_m3m2h, self.temperature_data_C],
                axis=1,
                sort=True,
            )
            .loc[
                self.n2o_data_ppm.first_valid_index() : self.n2o_data_ppm.last_valid_index()
            ]
            .dropna(how="any")
        )

        self._data.columns = [self._n2o_name, self._air_name, self._tmp_name]

    @property
    def data(self) -> pd.DataFrame:
        """Aligned inputs: N2O [ppm], airflow [m3 m-2 h-1], temperature [°C]."""
        return self._data

    def get_emission(self) -> pd.Series:
        """Emission rate per area.

        Returns
        -------
        Series
            ``emission_rate [g N2ON m-2 h-1]``. Negative rates are set to
            zero (docs/open_questions.md entry 5).
        """
        # g N2O m-2 s-1 -> g N2O-N m-2 h-1
        emission = (
            OffGasN2OEmission.calculate_n2o_mass_flow_gas(
                ppm_n2o_gas=self.data[self._n2o_name],
                q_air_m3s=self.data[self._air_name] / 3600,
                temperature_celsius=self.data[self._tmp_name],
            )
            * self.N2O_N_PER_N2O
            * 3600
        )

        emission.name = "emission_rate [g N2ON m-2 h-1]"

        return emission.where(emission >= 0, 0).dropna()
