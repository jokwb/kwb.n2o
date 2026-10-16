"""Synthetic input timeseries for the characterization tests.

Everything here is deterministic (fixed seed, fixed timestamps). The
generated series are written to ``tests/golden/inputs/`` once by
``regenerate.py``; the tests read the stored CSV files and never call
this module, so the golden files do not depend on the random number
generator.

Shapes follow real measurements from an aerated zone:

* three days at 1 min resolution in Europe/Berlin, including the DST
  fall-back on 2025-10-26,
* intermittent aeration (40 min on, 20 min off) so both the aerated and
  the non-aerated branch of the Unisense formula are used,
* NaN gaps and series that start or end at different times,
* temperature at 5 min and inflow at 15 min resolution, so the
  calculators have to align series of different resolution.
"""

import numpy as np
import pandas as pd

TZ = "Europe/Berlin"
START = "2025-10-24 00:00"
END = "2025-10-27 00:00"  # exclusive
SEED = 20251024

# Plant parameters used for the golden runs.
PARAMS = {
    "zone_area_m2": 250.0,
    "reactor_depth_m": 5.0,
    "tkn_const_mgL": 90.0,
    "ef_naive_start": "2025-10-24 06:00",
    "ef_naive_end": "2025-10-25 18:00",
}


def _index(freq: str) -> pd.DatetimeIndex:
    return pd.date_range(START, END, freq=freq, tz=TZ, inclusive="left")


def _diurnal(index: pd.DatetimeIndex, phase_h: float = 0.0) -> np.ndarray:
    """Sine with a 24 h period, 1 at ``phase_h`` hours after local midnight."""
    hours = np.asarray(index.hour + index.minute / 60, dtype=float)
    return np.sin(2 * np.pi * (hours - phase_h + 6) / 24)


def _spikes(
    index: pd.DatetimeIndex, centers: list[str], heights: list[float], width_min: float
) -> np.ndarray:
    """Sum of Gaussian bumps, ``height`` high, ``width_min`` minutes wide (sigma).

    ``centers`` are UTC timestamps, so a spike can sit inside the repeated
    local hour of the DST fall-back without being ambiguous.
    """
    epoch = pd.Timestamp(0, tz="UTC")
    t = (index - epoch).total_seconds().to_numpy() / 60  # minutes since epoch
    out = np.zeros(len(index))
    for c, h in zip(centers, heights, strict=True):
        tc = (pd.Timestamp(c, tz="UTC") - epoch).total_seconds() / 60
        out += h * np.exp(-0.5 * ((t - tc) / width_min) ** 2)
    return out


def make_inputs() -> dict[str, pd.Series]:
    rng = np.random.default_rng(SEED)
    idx1 = _index("1min")
    idx5 = _index("5min")

    # Aeration cycles: 40 min on, 20 min off.
    aerated = np.asarray(idx1.minute < 40)

    # Zone airflow [m3 h-1], ~2000 when aerated, a few m3 h-1 of leakage when not.
    air_m3h = np.where(
        aerated,
        2000 + 150 * _diurnal(idx1, 14) + rng.normal(0, 40, len(idx1)),
        5 + rng.normal(0, 1.5, len(idx1)),
    ).clip(min=0)
    air_m3h = pd.Series(air_m3h, idx1, name="air_m3h")
    air_m3h.loc["2025-10-25 18:00":"2025-10-25 18:30"] = np.nan

    # Dissolved N2O [mg L-1]: 0.05-0.25 baseline, spikes up to ~1.5.
    n2o_mgL = (
        0.15
        + 0.09 * _diurnal(idx1, 11)
        + rng.normal(0, 0.006, len(idx1))
        + _spikes(
            idx1,
            [
                "2025-10-24 07:30",
                "2025-10-25 12:10",
                "2025-10-26 00:50",
                "2025-10-26 15:45",
            ],
            [1.3, 0.8, 1.35, 0.5],
            width_min=12,
        )
    ).clip(min=0.0)
    n2o_mgL = pd.Series(n2o_mgL, idx1, name="n2o_mgL")
    # Sensor glitches: short jumps that trip the relative-std threshold of
    # unisense_smooth, and a dip to zero in a non-aerated period so the
    # negative non-aerated emission gets clipped.
    n2o_mgL.loc["2025-10-24 15:12":"2025-10-24 15:13"] = 0.95
    n2o_mgL.loc["2025-10-25 21:40"] = 1.1
    n2o_mgL.loc["2025-10-26 11:03":"2025-10-26 11:04"] = 0.01
    n2o_mgL.loc["2025-10-25 03:44":"2025-10-25 03:52"] = 0.0
    n2o_mgL = n2o_mgL.loc["2025-10-24 00:30":"2025-10-26 23:00"]
    n2o_mgL.loc["2025-10-25 10:00":"2025-10-25 12:00"] = np.nan

    # Liquid temperature [°C] at 5 min resolution.
    temp_C = pd.Series(
        18.0 + 1.5 * _diurnal(idx5, 15) + rng.normal(0, 0.05, len(idx5)),
        idx5,
        name="temp_C",
    )

    # Off-gas N2O [ppm]: 15-50 baseline, spikes up to ~650.
    ppm = (
        32
        + 14 * _diurnal(idx1, 11)
        + rng.normal(0, 1.5, len(idx1))
        + _spikes(
            idx1,
            ["2025-10-24 07:40", "2025-10-25 12:20", "2025-10-26 01:00"],
            [620, 300, 650],
            width_min=10,
        )
    ).clip(min=0.0)
    ppm = pd.Series(ppm, idx1, name="n2o_ppm")
    ppm = ppm.loc["2025-10-24 01:00":]
    ppm.loc["2025-10-26 08:00":"2025-10-26 09:30"] = np.nan

    # Area-specific airflow [m3 m-2 h-1] for the off-gas pathway.
    air_m3m2h = (air_m3h / PARAMS["zone_area_m2"]).rename("air_m3m2h")

    # Inflow [m3 h-1] at 15 min resolution, starting a day earlier.
    idx_in = pd.date_range(
        "2025-10-23 00:00", END, freq="15min", tz=TZ, inclusive="left"
    )
    inflow_m3h = pd.Series(
        100 + 30 * _diurnal(idx_in, 12) + rng.normal(0, 3, len(idx_in)),
        idx_in,
        name="inflow_m3h",
    )

    # Daily TKN profile [mg L-1], hourly, TimedeltaIndex 0..23 h.
    td = pd.timedelta_range("0h", "23h", freq="h")
    tkn_profile_mgL = pd.Series(
        90 + 15 * np.sin(2 * np.pi * (td.total_seconds() / 3600 - 10 + 6) / 24),
        td,
        name="tkn_mgL",
    )

    return {
        "n2o_mgL": n2o_mgL,
        "air_m3h": air_m3h,
        "temp_C": temp_C,
        "n2o_ppm": ppm,
        "air_m3m2h": air_m3m2h,
        "inflow_m3h": inflow_m3h,
        "tkn_profile_mgL": tkn_profile_mgL,
    }
