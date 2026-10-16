from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class N2OkLa:
    """
    get_kla_at_temperature: returns kla[1/s]
    """

    # constants
    LABORATORY_REACTOR_DEPTH: float = field(default=0.815, init=False, repr=False)

    # need attributes
    aearation_field_size: float = field(default_factory=float)  # m2
    reactor_depth: float = field(default_factory=float)  # m

    def get_kla_at_temperature(
        self,
        airflow_m3s: float | pd.Series,
        temperature_celsius: float | pd.Series,
    ):

        # normalize airflows to 20 °C
        _airflows = self._qa20(
            airflows=airflow_m3s, temperatures_celsius=temperature_celsius
        )  # m3 s-1 -> m3 s-1

        # gas velocity
        vg20 = self._vg20(
            airflows_normalized=_airflows, aeration_field_size=self.aearation_field_size
        )  # m3 s-1 -> m s-1

        # derive from laboraroty results
        kla20 = (
            (self.reactor_depth / self.LABORATORY_REACTOR_DEPTH) ** (-0.49)
            * 34500
            * vg20 ** (0.86)
        )  # -d EMPIRICAL!

        # adjust process temperature
        kla_process_d = kla20 * np.power(1.024, temperature_celsius - 20)

        kla_process_s = kla_process_d / (24 * 60 * 60)  # -d -> -s

        return kla_process_s

    @staticmethod
    def _vg20(airflows_normalized, aeration_field_size):
        # returns gas velocity at 20 °C using the normalized volume flow

        return airflows_normalized / aeration_field_size

    @staticmethod
    def _qa20(airflows, temperatures_celsius):
        # normalizes airflow volume to 20 °C
        # pV1 = nRT1, pV2 = nRT2
        # V1 / T1 = V2 / T2
        # V2 = V1 * T2/T1

        t20 = 293.15

        corrected_airflow = airflows * t20 / (temperatures_celsius + 273.15)

        return corrected_airflow
