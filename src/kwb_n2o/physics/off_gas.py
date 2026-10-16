from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class EmersonN2OEmission:
    ATMOSPHERIC_PRESSURE_PASCAL: ClassVar[float] = 101325.0  # Pa
    GAS_CONSTANT: ClassVar[float] = 8.314  # J mol-1 K-1

    @classmethod
    def calculate_n2o_mass_flow_gas(
        cls,
        q_air_m3s: Iterable,
        ppm_n2o_gas: Iterable,
        temperature_celsius: float | Iterable,
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
