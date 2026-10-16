"""N2O mass flow from the gas phase, from an off-gas concentration in ppm.

Pure formulas: every argument is a float or a Series, Series must share
one index, nothing is aligned here.
"""

from typing import ClassVar

import pandas as pd

from ._common import same_index


class EmersonN2OEmission:
    """N2O mass flow in the off-gas via the ideal gas law."""

    ATMOSPHERIC_PRESSURE_PA: ClassVar[float] = 101325.0
    """Pressure assumed for the off-gas [Pa]. See docs/open_questions.md entry 4."""

    GAS_CONSTANT_J_MOL_K: ClassVar[float] = 8.314
    """Universal gas constant [J mol-1 K-1]."""

    MOLAR_MASS_N2O_G_MOL: ClassVar[float] = 44.0
    """Molar mass of N2O [g mol-1]."""

    @classmethod
    def calculate_n2o_mass_flow_gas(
        cls,
        q_air_m3s: float | pd.Series,
        ppm_n2o_gas: float | pd.Series,
        temperature_celsius: float | pd.Series,
    ) -> float | pd.Series:
        """N2O mass flow carried by the off-gas.

        Parameters
        ----------
        q_air_m3s : float or Series
            Airflow [m3 s-1]. If given per area [m3 m-2 s-1], the result is
            per area as well.
        ppm_n2o_gas : float or Series
            N2O volume fraction in the off-gas [ppm].
        temperature_celsius : float or Series
            Gas temperature used in the ideal gas law [°C]. See
            docs/open_questions.md entry 4.

        Returns
        -------
        float or Series
            Mass flow [g N2O s-1] (or [g N2O m-2 s-1] for area-specific airflow).
            Multiply by 28/44 for N2O-N.
        """
        same_index(q_air_m3s, ppm_n2o_gas, temperature_celsius)

        # n/V = p / (R T); c = p * x_ppm * 1e-6 / (R T) * M
        mass_flow = (
            (cls.ATMOSPHERIC_PRESSURE_PA * 10**-6 * ppm_n2o_gas)
            / (cls.GAS_CONSTANT_J_MOL_K * (273.15 + temperature_celsius))
            * q_air_m3s
            * cls.MOLAR_MASS_N2O_G_MOL
        )

        return mass_flow
