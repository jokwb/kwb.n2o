from typing import Protocol

import pandas as pd


class EmissionCalculator(Protocol):
    """A calculator turns aligned measurement series into one emission series."""

    def get_emission(self, *args, **kwargs) -> pd.Series:
        """Emission rate per area [g N2O-N m-2 h-1] with a DatetimeIndex."""
        ...
