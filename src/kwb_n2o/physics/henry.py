"""Henry constant of N2O in water, from the Sander (2023) compilation.

The table ``kwb_n2o/data/Henry.xlsx`` lists literature values of Hcps and
of the temperature dependence parameter B for N2O, with a flag
``use_in_calc``. Source: Sander, R. (2023), Atmos. Chem. Phys. 23,
10901-12440, https://acp.copernicus.org/articles/23/10901/2023/.

Notation (Sander 2023):

* Hcps: solubility constant, c_aq / p_gas [mol m-3 Pa-1]
* Hccs: dimensionless solubility constant, c_aq / c_gas [-]
* Hcpv = 1 / Hcps, Hccv = 1 / Hccs: the volatility forms. Hccv is the
  constant used by the Unisense emission formula.
"""

from functools import cache
from importlib.resources import as_file, files
from typing import ClassVar

import numpy as np
import pandas as pd


@cache
def _read_henry_table() -> pd.DataFrame:
    """Read the Sander (2023) table once per process."""
    with as_file(files("kwb_n2o.data") / "Henry.xlsx") as path:
        return pd.read_excel(path, engine="calamine")


class N2OHenry:
    """Henry constant of N2O at a given temperature.

    The reference values are the means of the table rows flagged
    ``use_in_calc == 1``; they can be overridden.
    """

    STANDARD_TEMPERATURE_CELSIUS: ClassVar[float] = 25.0
    """Reference temperature of Hcps in Sander (2023) [°C] (298.15 K)."""

    R: ClassVar[float] = 8.314
    """Universal gas constant [J mol-1 K-1]."""

    def __init__(self) -> None:
        self.data = _read_henry_table()
        self._hcps: float | None = None
        self._B: float | None = None

    @property
    def Hcps(self) -> float:
        """Reference Hcps at 25 °C [mol m-3 Pa-1]."""
        if self._hcps is None:
            self._hcps = self.data.loc[self.data["use_in_calc"] == 1]["Hcps"].mean()
        return self._hcps

    @property
    def B(self) -> float:
        """Temperature dependence parameter d(ln H) / d(1/T) [K]."""
        if self._B is None:
            self._B = self.data.loc[self.data["use_in_calc"] == 1]["B"].mean()
        return self._B

    def override_standard_hcps(self, new_hcps: float) -> None:
        """Replace the reference Hcps [mol m-3 Pa-1]."""
        self._hcps = new_hcps

    def override_standard_correction_value(self, new_value: float) -> None:
        """Replace the temperature dependence parameter B [K]."""
        self._B = new_value

    @staticmethod
    def _apply_temperature_correction(
        h_standard: float,
        correction_factor: float,
        temperature_celsius: float | pd.Series,
    ) -> float | pd.Series:
        """Van 't Hoff correction: H(T) = H(T0) * exp(B * (1/T - 1/T0))."""
        correction_arg = correction_factor * (
            1 / (temperature_celsius + 273.15)
            - 1 / (N2OHenry.STANDARD_TEMPERATURE_CELSIUS + 273.15)
        )
        return h_standard * np.exp(correction_arg)

    def get_hcps_at_temperature(
        self, temperature_celsius: float | pd.Series
    ) -> float | pd.Series:
        """Hcps [mol m-3 Pa-1] at ``temperature_celsius`` [°C]."""
        return self._apply_temperature_correction(
            self.Hcps, self.B, temperature_celsius
        )

    def get_hccs_at_temperature(
        self, temperature_celsius: float | pd.Series
    ) -> float | pd.Series:
        """Hccs [-] at ``temperature_celsius`` [°C]: Hccs = Hcps * R * T."""
        return (
            self.R
            * (temperature_celsius + 273.15)
            * self.get_hcps_at_temperature(temperature_celsius)
        )

    def get_hcpv_at_temperature(
        self, temperature_celsius: float | pd.Series
    ) -> float | pd.Series:
        """Hcpv [Pa m3 mol-1] at ``temperature_celsius`` [°C]."""
        return 1 / self.get_hcps_at_temperature(temperature_celsius)

    def get_hccv_at_temperature(
        self, temperature_celsius: float | pd.Series
    ) -> float | pd.Series:
        """Hccv [-] at ``temperature_celsius`` [°C], as used by the Unisense formula."""
        return 1 / self.get_hccs_at_temperature(temperature_celsius)
