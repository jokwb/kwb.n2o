import os
from dataclasses import dataclass, field
from typing import ClassVar, Union

import numpy as np
import pandas as pd


@dataclass
class N2OHenry:
    """
    Read table of Sander, 2023 values for N2O and calculate default values
    conversion factors access the document https://acp.copernicus.org/articles/23/10901/2023/acp-23-10901-2023.pdf

    Hcps = (s)olubility (H)enry constant using (c)aq and (p)artial pressure gas
    Hccs = (s)olubility (H)enry constant using (p)artial pressure aq and (p)artial pressure gas

    Hcpv = 1/Hcps
    Hccv = 1/Hccs (--> calc unit for Unisense emission calculation)


    Hcps unit = mol m-3 Pa-1 --> 10^3/10^6 * mol L-1 bar-1

    """

    STANDARD_TEMPERATURE_CELSIUS: ClassVar[float] = field(default=25.0, init=False)
    R: ClassVar[float] = field(default=8.314, init=False)

    HENRY_DATA_PATH: ClassVar[os.PathLike] = field(
        default=os.path.join(os.path.dirname(__file__), "datasheets", "Henry.xlsx"),
        init=False,
    )

    _hcps: float = field(init=False)
    _B: float = field(init=False)

    def __post_init__(self):
        self._read_sheet_data()

    def _read_sheet_data(self):
        self.data = pd.read_excel(self.HENRY_DATA_PATH, engine="calamine")

    @property
    def Hcps(self):
        if not hasattr(self, "_hcps"):
            self._hcps = self.data.loc[self.data["use_in_calc"] == 1]["Hcps"].mean()
        return self._hcps

    @property
    def B(self):
        if not hasattr(self, "_B"):
            self._B = self.data.loc[self.data["use_in_calc"] == 1]["B"].mean()
        return self._B

    def override_standard_hcps(self, new_hcps):
        self._hcps = new_hcps

    def override_standard_correction_value(self, new_value):
        self._B = new_value

    @staticmethod
    def _apply_temperature_correction(
        h_standard, correction_factor, temperature_celsius
    ):
        correction_arg = correction_factor * (
            1 / (temperature_celsius + 273.15)
            - 1 / (N2OHenry.STANDARD_TEMPERATURE_CELSIUS + 273.15)
        )
        h = h_standard * np.exp(correction_arg)
        return h

    def get_hcps_at_temperature(
        self, temperature_celsius: Union[float, pd.Series]
    ) -> Union[float, pd.Series]:
        h_new = self._apply_temperature_correction(
            self.Hcps, self.B, temperature_celsius
        )
        return h_new

    def get_hccs_at_temperature(self, temperature_celsius: Union[float, pd.Series]):
        """
        1. convert standard hcps to hccs
        """
        # hcps = self._apply_temperature_correction(self.Hcps, self.B, temperature_celsius)
        h_new = (
            self.R
            * (temperature_celsius + 273.15)
            * self.get_hcps_at_temperature(temperature_celsius)
        )
        return h_new

    def get_hcpv_at_temperature(self, temperature_celsius: Union[float, pd.Series]):
        return 1 / self.get_hcps_at_temperature(temperature_celsius)

    def get_hccv_at_temperature(self, temperature_celsius: Union[float, pd.Series]):
        return 1 / self.get_hccs_at_temperature(temperature_celsius)
