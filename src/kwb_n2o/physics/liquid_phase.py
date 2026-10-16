"""N2O emission from the liquid phase, from dissolved N2O (Unisense method).

Follows the Unisense emission calculation note (v3), see
``references/links.json``. Pure formulas: every argument is a float or a
Series, Series must share one index, nothing is aligned here.
"""

from typing import ClassVar

import numpy as np
import pandas as pd

from ._common import as_series_like, same_index


class UnisenseN2OEmission:
    """Emission rate of N2O from the liquid phase per reactor volume."""

    AERATION_THRESHOLD_M3S: ClassVar[float] = 50 / 3600
    """Airflow [m3 s-1] from which a timestep counts as aerated (50 m3 h-1)."""

    KLA_NON_AERATED_S: ClassVar[float] = 3 / (24 * 3600)
    """Mass transfer coefficient [s-1] without aeration: 3 d-1, range 2-4 d-1
    (Unisense note)."""

    N2O_ENV_AIR_CONC_GM3: ClassVar[float] = 0.0003 / 0.636483023
    """N2O concentration of ambient air [g N2O m-3], Baresel et al. (2016).
    See docs/open_questions.md entry 2 for the divisor."""

    @classmethod
    def calculate_n2o_emission_rate_aq(
        cls,
        hccv: float | pd.Series,
        c_n2o_aq: float | pd.Series,
        q_air_m3s: float | pd.Series,
        v_r_m3: float,
        kla_s: float | pd.Series,
        return_emission_type: bool = False,
    ) -> float | pd.Series | tuple[float | pd.Series, str | pd.Series]:
        """Emission rate per reactor volume, aerated or non-aerated per timestep.

        Parameters
        ----------
        hccv : float or Series
            Dimensionless Henry volatility constant (c_gas / c_aq) [-].
        c_n2o_aq : float or Series
            Dissolved N2O concentration [g m-3].
        q_air_m3s : float or Series
            Airflow into the zone [m3 s-1]. Decides aerated / non-aerated
            against ``AERATION_THRESHOLD_M3S``.
        v_r_m3 : float
            Volume of the zone [m3].
        kla_s : float or Series
            Mass transfer coefficient for N2O when aerated [s-1].
        return_emission_type : bool, default False
            Also return which formula was used per timestep.

        Returns
        -------
        float or Series
            Emission rate [g N2O m-3 s-1].
        str or Series, optional
            ``"aerated"`` or ``"non_aerated"``, only with
            ``return_emission_type=True``.
        """
        same_index(hccv, c_n2o_aq, q_air_m3s, kla_s)

        aerated = q_air_m3s >= cls.AERATION_THRESHOLD_M3S

        rate = np.where(
            aerated,
            cls._calculate_aerated_emission(
                c_n2o_aq=c_n2o_aq,
                hccv=hccv,
                kla_s=kla_s,
                q_air_m3s=q_air_m3s,
                v_reactor_m3=v_r_m3,
            ),
            cls._calculate_non_aerated_emission(c_n2o_aq=c_n2o_aq, hccv=hccv),
        )
        rate = as_series_like(rate, hccv, c_n2o_aq, q_air_m3s, kla_s)

        if not return_emission_type:
            return rate

        emission_type = np.where(aerated, "aerated", "non_aerated")
        emission_type = as_series_like(emission_type, hccv, c_n2o_aq, q_air_m3s, kla_s)
        return rate, emission_type

    @classmethod
    def _calculate_aerated_emission(
        cls,
        hccv: float | pd.Series,
        c_n2o_aq: float | pd.Series,
        kla_s: float | pd.Series,
        q_air_m3s: float | pd.Series,
        v_reactor_m3: float,
    ) -> float | pd.Series:
        """Stripping by the air bubbles [g N2O m-3 s-1], Unisense note."""
        e = np.exp((-kla_s / hccv) * (v_reactor_m3 / q_air_m3s))

        emission = hccv * c_n2o_aq * (1 - e) * q_air_m3s / v_reactor_m3

        return emission

    @classmethod
    def _calculate_non_aerated_emission(
        cls,
        c_n2o_aq: float | pd.Series,
        hccv: float | pd.Series,
    ) -> float | pd.Series:
        """Surface exchange against ambient air [g N2O m-3 s-1], Unisense note.

        See docs/open_questions.md entry 1 for the unit basis of the two terms.
        """
        emission = cls.KLA_NON_AERATED_S * (c_n2o_aq - cls.N2O_ENV_AIR_CONC_GM3 / hccv)

        return emission
