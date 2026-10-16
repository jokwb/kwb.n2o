from typing import Protocol

import pandas as pd


class EmissionCalculator(Protocol):
    def get_emission(self, *args, **kwargs) -> pd.Series: ...
