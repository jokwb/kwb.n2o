from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import ClassVar, Optional, Union

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
        hccv: Union[float, pd.Series],
        c_n2o_aq: Union[float, pd.Series],
        q_air_m3s: Union[float, pd.Series],
        v_r_m3: Optional[Union[float, pd.Series]] = None,
        kla_s: Optional[Union[float, pd.Series]] = None,
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
        hccv: Union[float, pd.Series],
        c_n2o_aq: Union[float, pd.Series],
        kla_s: Union[float, pd.Series],
        q_air_m3s: Union[float, pd.Series],
        v_reactor_m3: float,
    ):

        e = np.exp((-kla_s / hccv) * (v_reactor_m3 / q_air_m3s))

        emission = hccv * c_n2o_aq * (1 - e) * q_air_m3s / v_reactor_m3

        return emission

    @classmethod
    def _calculate_non_aerated_emission(
        cls,
        c_n2o_aq: Union[float, pd.Series],
        hccv: Union[float, pd.Series],
    ):

        emission = cls.KLA_NON_AERATED * (c_n2o_aq - cls.N2O_ENV_AIR_CONC / hccv)

        return emission


@dataclass
class EmersonN2OEmission:
    ATMOSPHERIC_PRESSURE_PASCAL: ClassVar[float] = 101325.0  # Pa
    GAS_CONSTANT: ClassVar[float] = 8.314  # J mol-1 K-1

    @classmethod
    def calculate_n2o_mass_flow_gas(
        cls,
        q_air_m3s: Iterable,
        ppm_n2o_gas: Iterable,
        temperature_celsius: Union[float, Iterable],
    ):
        """
        return unit: [g] (precisely [g <time>-1] because q is a flow)
        """

        if not isinstance(temperature_celsius, Iterable):
            assert len(temperature_celsius) == len(ppm_n2o_gas), "Lengths do not match"
        assert len(q_air_m3s) == len(ppm_n2o_gas), "Lengths do not match"

        # freight=             pressure             * f      * c_ppm        / (R * (T_°C + 273.15)) * Q_air * 44 g/mol
        freight = (
            (cls.ATMOSPHERIC_PRESSURE_PASCAL * 10**-6 * ppm_n2o_gas)
            / (cls.GAS_CONSTANT * (273.15 + temperature_celsius))
            * q_air_m3s
            * 44
        )

        return freight  # g s-1  n2o! --> n2: *28/44
