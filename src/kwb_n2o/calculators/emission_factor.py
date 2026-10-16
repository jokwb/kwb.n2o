"""TKN load of the inflow and the emission factor EF = N2O-N emitted / TKN load."""

import warnings
from dataclasses import dataclass
from functools import cached_property
from typing import ClassVar

import pandas as pd

from ..preprocessing import merge_td_on_dt
from ._validation import require_datetime_series, require_positive


@dataclass
class TKNMassflowCalculation:
    """TKN mass flow [g h-1] from inflow and TKN concentration.

    Parameters
    ----------
    tkn_mgl : float or Series
        TKN concentration [mg L-1] (= [g m-3]). Either one constant, or a
        daily profile with a regular ``TimedeltaIndex`` (e.g. hourly values
        for 0 h to 23 h) that is repeated over the inflow series.
    inflow_m3h : Series
        Inflow [m3 h-1] with a DatetimeIndex.
    """

    _tkn_name: ClassVar[str] = "tkn_g*m-3"
    _q_name: ClassVar[str] = "q_m3*h-1"
    _mf_name: ClassVar[str] = "mdot_g*h-1"

    tkn_mgl: float | pd.Series
    inflow_m3h: pd.Series

    def __post_init__(self) -> None:
        require_datetime_series("inflow_m3h", self.inflow_m3h)
        if isinstance(self.tkn_mgl, bool) or not isinstance(
            self.tkn_mgl, int | float | pd.Series
        ):
            raise TypeError(
                f"tkn_mgl must be a number or a Series, got {type(self.tkn_mgl).__name__}."
            )
        if isinstance(self.tkn_mgl, pd.Series):
            self._validate_tkn()

    def _validate_tkn(self) -> None:
        if not isinstance(self.tkn_mgl.index, pd.TimedeltaIndex):
            raise TypeError("A TKN profile needs a TimedeltaIndex.")

        self.freq = pd.infer_freq(self.tkn_mgl.index)

        if self.freq is None:
            raise ValueError("Unable to infer the frequency of the TKN profile.")

    @cached_property
    def data(self) -> pd.DataFrame:
        """Inflow [m3 h-1] and TKN [g m-3] per inflow timestamp."""
        data = self.inflow_m3h.to_frame()

        if isinstance(self.tkn_mgl, pd.Series):
            data = merge_td_on_dt(data, self.tkn_mgl)
        else:
            data[self._tkn_name] = self.tkn_mgl

        data.columns = [self._q_name, self._tkn_name]
        return data

    def get_massflow(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> pd.Series:
        """TKN mass flow [g h-1], optionally cut to ``start_date:end_date``.

        Parameters
        ----------
        start_date, end_date : str, optional
            Bounds as accepted by ``.loc`` on a DatetimeIndex, inclusive.
        """
        data = self.data.loc[pd.IndexSlice[start_date:end_date]]

        massflow = data[self._q_name] * data[self._tkn_name]  # m3 h-1 * g m-3 = g h-1
        massflow.name = self._mf_name

        return massflow


@dataclass
class EmissionFactorCalculation:
    """Emission factor EF [-] = emitted N2O-N [g h-1] / TKN load [g h-1].

    Parameters
    ----------
    mdot_n2o_area_gm2h1 : Series
        Area-specific N2O-N emission [g m-2 h-1], as returned by a calculator.
    mdot_tkn_gh : Series
        TKN mass flow [g h-1]. A tz-naive series is localized to the time
        zone of the emission series with a warning; a different time zone
        is converted with a warning.
    zone_area_m2 : float
        Area of the zone the emission refers to [m2].
    """

    _ef_name: ClassVar[str] = "ef"
    _n2o_mf_name: ClassVar[str] = "mdot_n2on_g*h-1"
    _tn_mf_name: ClassVar[str] = "mdot_tkn_g*h-1"

    mdot_n2o_area_gm2h1: pd.Series
    mdot_tkn_gh: pd.Series
    zone_area_m2: float

    def __post_init__(self) -> None:
        require_datetime_series("mdot_n2o_area_gm2h1", self.mdot_n2o_area_gm2h1)
        require_datetime_series("mdot_tkn_gh", self.mdot_tkn_gh)
        require_positive("zone_area_m2", self.zone_area_m2)
        self._align_timezones()

    def _align_timezones(self) -> None:
        """Bring the TKN series into the time zone of the emission series."""
        tz_n2o = self.mdot_n2o_area_gm2h1.index.tz
        tz_tkn = self.mdot_tkn_gh.index.tz

        if str(tz_n2o) != str(tz_tkn):
            if tz_tkn is None:
                warnings.warn(
                    f"tz-naive series {self._tn_mf_name} localized to {tz_n2o}.",
                    stacklevel=3,
                )
                self.mdot_tkn_gh = self.mdot_tkn_gh.tz_localize(
                    tz_n2o, ambiguous="infer"
                )
            elif tz_n2o is None:
                raise ValueError(
                    "mdot_n2o_area_gm2h1 is tz-naive but mdot_tkn_gh is tz-aware; "
                    "localize the emission series first."
                )
            else:
                warnings.warn(
                    f"Series {self._tn_mf_name} converted from {tz_tkn} to {tz_n2o}.",
                    stacklevel=3,
                )
                self.mdot_tkn_gh = self.mdot_tkn_gh.tz_convert(tz_n2o)

        self.tz = tz_n2o

    @cached_property
    def data(self) -> pd.DataFrame:
        """N2O-N emission of the zone [g h-1] and TKN load [g h-1], aligned."""
        data = pd.concat(
            [self.mdot_n2o_area_gm2h1, self.mdot_tkn_gh], axis=1, sort=True
        ).dropna(how="any")
        data = data.tz_convert(self.tz)
        data.columns = [self._n2o_mf_name, self._tn_mf_name]
        data[self._n2o_mf_name] = self.zone_area_m2 * data[self._n2o_mf_name]
        return data

    @cached_property
    def ef(self) -> pd.Series:
        """Emission factor [-] per timestamp."""
        ef = self.data[self._n2o_mf_name] / self.data[self._tn_mf_name]
        ef.name = self._ef_name

        return ef
