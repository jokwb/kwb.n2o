"""Characterization tests: every calculator must reproduce the golden files.

The inputs and outputs live in ``tests/golden/``. If one of these tests
fails, the numbers changed. That is wrong unless different numbers were
asked for; see ``tests/golden/regenerate.py``.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tests.golden.regenerate import compute_outputs
from tests.golden.synthetic import TZ

GOLDEN = Path(__file__).parent / "golden"
RTOL = 1e-10


def _read(path: Path) -> pd.Series:
    df = pd.read_csv(path, index_col="time", float_precision="round_trip")
    series = df.iloc[:, 0]
    if path.stem == "tkn_profile_mgL":
        series.index = pd.TimedeltaIndex(pd.to_timedelta(series.index))
    else:
        series.index = pd.to_datetime(series.index, utc=True).tz_convert(TZ)
    series.index.name = None
    return series


def _utc_ns(index: pd.Index) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(index).tz_convert("UTC").as_unit("ns").rename(None)


@pytest.fixture(scope="module")
def params() -> dict:
    return json.loads((GOLDEN / "params.json").read_text())


@pytest.fixture(scope="module")
def inputs() -> dict[str, pd.Series]:
    return {p.stem: _read(p) for p in sorted((GOLDEN / "inputs").glob("*.csv"))}


@pytest.fixture(scope="module")
def outputs(inputs, params) -> dict[str, pd.Series]:
    return compute_outputs(inputs, params)


GOLDEN_NAMES = sorted(p.stem for p in (GOLDEN / "outputs").glob("*.csv"))


@pytest.mark.parametrize("name", GOLDEN_NAMES)
def test_matches_golden(name: str, outputs: dict[str, pd.Series]) -> None:
    expected = _read(GOLDEN / "outputs" / f"{name}.csv")
    actual = outputs[name]

    pd.testing.assert_index_equal(_utc_ns(actual.index), _utc_ns(expected.index))
    np.testing.assert_allclose(actual.to_numpy(), expected.to_numpy(), rtol=RTOL)


def test_every_output_has_a_golden_file(outputs: dict[str, pd.Series]) -> None:
    assert sorted(outputs) == GOLDEN_NAMES
