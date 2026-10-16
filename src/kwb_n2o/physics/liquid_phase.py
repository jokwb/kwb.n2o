from dataclasses import dataclass, field
from typing import ClassVar

import numpy as np
import pandas as pd


@dataclass
class UnisenseN2OEmission:
    # _N2O_ENV_AIR_CONC = equilibrium concentration (g/m3)

    AERATION_THRESHOLD_M3S: ClassVar[float] = field(default=50 / 3600, init=False)
    KLA_NON_AERATED: ClassVar[float] = field(
        default=3 / (24 * 3600), init=False
    )  # 2-4 d-1
    N2O_ENV_AIR_CONC: ClassVar[float] = field(
        default=0.0003 / 0.636483023, init=False
    )  # g m-3 N2O Baresel et al. 2016

    @classmethod
    def calculate_n2o_emission_rate_aq(
        cls,
        hccv: float | pd.Series,
        c_n2o_aq: float | pd.Series,
        q_air_m3s: float | pd.Series,
        v_r_m3: float | pd.Series | None = None,
        kla_s: float | pd.Series | None = None,
    ) -> pd.Series:
        """
        hccv = dimensionless henry volatility constant
        c_n2o_aq = aqueous n2o concentration (g m-3)
        q_air_m3s = airflow per second
        v_r_m3 = reactor volume
        klas_s = mass transfer coefficient for n2o (s-1)
        """
        df = pd.DataFrame(columns=["H", "c_aq", "q_air", "kla"])
        df["H"] = hccv  # -
        df["c_aq"] = c_n2o_aq  # g m-3
        df["q_air"] = q_air_m3s  # m3 s-1
        df["kla"] = kla_s  # s-1

        df["emission_type"] = np.where(
            df["q_air"] >= cls.AERATION_THRESHOLD_M3S, "aerated", "non_aerated"
        )

        df["emission_rate [g N2O m-3 s-1]"] = np.where(
            df["emission_type"] == "aerated",
            cls._calculate_aerated_emission(
                c_n2o_aq=df["c_aq"],
                hccv=df["H"],
                kla_s=df["kla"],
                q_air_m3s=df["q_air"],
                v_reactor_m3=v_r_m3,
            ),  # yes
            cls._calculate_non_aerated_emission(
                c_n2o_aq=df["c_aq"], hccv=df["H"]
            ),  # no
        )

        return df[["emission_type", "emission_rate [g N2O m-3 s-1]"]]

    @classmethod
    def _calculate_aerated_emission(
        cls,
        hccv: float | pd.Series,
        c_n2o_aq: float | pd.Series,
        kla_s: float | pd.Series,
        q_air_m3s: float | pd.Series,
        v_reactor_m3: float,
    ):

        e = np.exp((-kla_s / hccv) * (v_reactor_m3 / q_air_m3s))

        emission = hccv * c_n2o_aq * (1 - e) * q_air_m3s / v_reactor_m3

        return emission

    @classmethod
    def _calculate_non_aerated_emission(
        cls,
        c_n2o_aq: float | pd.Series,
        hccv: float | pd.Series,
    ):

        emission = cls.KLA_NON_AERATED * (c_n2o_aq - cls.N2O_ENV_AIR_CONC / hccv)

        return emission
