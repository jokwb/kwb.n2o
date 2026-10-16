"""Mass transfer coefficient kLa for N2O from airflow and aeration field size.

Empirical method from the Unisense emission calculation note (v3), see
``references/links.json``. Pure formulas: floats or Series, no alignment.
"""

from dataclasses import dataclass
from typing import ClassVar

import numpy as np
import pandas as pd

from ._common import same_index


@dataclass
class N2OkLa:
    """kLa of N2O for one aerated zone.

    Parameters
    ----------
    aeration_field_m2 : float
        Area of the aerated field [m2].
    reactor_depth_m : float
        Water depth of the zone [m].
    """

    LABORATORY_REACTOR_DEPTH_M: ClassVar[float] = 0.815
    """Depth [m] of the laboratory reactor the empirical relation was fitted
    on (Unisense note)."""

    KLA20_COEFFICIENT_D: ClassVar[float] = 34500
    """Prefactor [d-1] of the empirical kLa20 relation (Unisense note)."""

    GAS_VELOCITY_EXPONENT: ClassVar[float] = 0.86
    """Exponent of the superficial gas velocity [-] (Unisense note)."""

    DEPTH_EXPONENT: ClassVar[float] = -0.49
    """Exponent of the depth ratio [-] (Unisense note)."""

    TEMPERATURE_COEFFICIENT: ClassVar[float] = 1.024
    """Arrhenius-type factor theta [-] per K for kLa (standard value)."""

    REFERENCE_TEMPERATURE_K: ClassVar[float] = 293.15
    """20 °C in K; airflow and kLa are referenced to it."""

    aeration_field_m2: float
    reactor_depth_m: float

    def get_kla_at_temperature(
        self,
        airflow_m3s: float | pd.Series,
        temperature_celsius: float | pd.Series,
    ) -> float | pd.Series:
        """kLa at process temperature.

        Parameters
        ----------
        airflow_m3s : float or Series
            Airflow into the zone at process temperature [m3 s-1].
        temperature_celsius : float or Series
            Process temperature [°C].

        Returns
        -------
        float or Series
            kLa [s-1].
        """
        same_index(airflow_m3s, temperature_celsius)

        airflow_20_m3s = self._qa20(airflow_m3s, temperature_celsius)
        vg20_ms = self._vg20(airflow_20_m3s, self.aeration_field_m2)

        kla20_d = (
            (self.reactor_depth_m / self.LABORATORY_REACTOR_DEPTH_M)
            ** self.DEPTH_EXPONENT
            * self.KLA20_COEFFICIENT_D
            * vg20_ms**self.GAS_VELOCITY_EXPONENT
        )

        kla_process_d = kla20_d * np.power(
            self.TEMPERATURE_COEFFICIENT, temperature_celsius - 20
        )

        return kla_process_d / (24 * 60 * 60)

    @staticmethod
    def _vg20(
        airflow_20_m3s: float | pd.Series, aeration_field_m2: float
    ) -> float | pd.Series:
        """Superficial gas velocity [m s-1] from airflow at 20 °C [m3 s-1]."""
        return airflow_20_m3s / aeration_field_m2

    @classmethod
    def _qa20(
        cls, airflow_m3s: float | pd.Series, temperature_celsius: float | pd.Series
    ) -> float | pd.Series:
        """Airflow volume at 20 °C [m3 s-1] (ideal gas, V2 = V1 * T2 / T1)."""
        return (
            airflow_m3s * cls.REFERENCE_TEMPERATURE_K / (temperature_celsius + 273.15)
        )
