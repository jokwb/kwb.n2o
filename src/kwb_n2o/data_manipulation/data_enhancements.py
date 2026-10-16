import pickle
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator

if TYPE_CHECKING:
    from sklearn.linear_model import Lasso


class DiscreteRecoveryCUSUM:
    def __init__(
        self,
        series: pd.Series,
        k: float,
        H: float,
        recovery_thresh: float,
        recovery_steps: int,
    ):
        """
        Two-phase CUSUM with recovery detection.

        Parameters
        ----------
        series : pd.Series
            The input signal (e.g. diff between measured and predicted).
        k : float
            Allowance / slack — deviations smaller than this are absorbed.
        H : float
            Decision threshold — cumulative sum must exceed this to flag a fault.
        recovery_thresh : float
            Raw signal must stay below this (absolute) to begin recovery.
        recovery_steps : int
            Number of consecutive steps below recovery_thresh to exit fault state.
        """

        self.series = series
        self.k = k
        self.H = H
        self.recovery_thresh = recovery_thresh
        self.recovery_steps = recovery_steps
        self.result_: pd.DataFrame | None = None

    def run(self) -> "DiscreteRecoveryCUSUM":
        n = len(self.series)
        cusum = np.zeros(n)
        faulty = np.zeros(n, dtype=bool)
        in_fault = False
        recovery_count = 0

        for i in range(1, n):
            val = self.series.iloc[i]

            if in_fault:
                faulty[i] = True
                cusum[i] = 0.0

                if abs(val) < self.recovery_thresh:
                    recovery_count += 1
                    if recovery_count >= self.recovery_steps:
                        in_fault = False
                        recovery_count = 0
                else:
                    recovery_count = 0
            else:
                cusum[i] = max(0, cusum[i - 1] + val - self.k)
                if cusum[i] >= self.H:
                    in_fault = True
                    faulty[i] = True
                    cusum[i] = 0.0
                    recovery_count = 0

        recovery_count_trace = self._recovery_trace(n, faulty)

        self.result_ = pd.DataFrame(
            {
                "signal": self.series.values,
                "cusum": cusum,
                "faulty": faulty,
                "recovery_count": recovery_count_trace,
            },
            index=self.series.index,
        )

        return self

    def _recovery_trace(self, n, faulty):
        trace = np.zeros(n, dtype=int)
        count = 0
        for i in range(1, n):
            if faulty[i]:
                if abs(self.series.iloc[i]) < self.recovery_thresh:
                    count += 1
                else:
                    count = 0
                trace[i] = count
            else:
                count = 0
        return trace

    def _faulty_spans(self):
        """Extract faulty regions as a list of (start, end) tuples."""
        df = self.result_
        faulty = df["faulty"].values
        diff = np.diff(faulty.astype(int), prepend=0, append=0)
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]
        return [
            (df.index[s], df.index[min(e, len(df) - 1)]) for s, e in zip(starts, ends)
        ]

    def plot(self, figsize=(14, 8)) -> plt.Figure:
        if self.result_ is None:
            raise ValueError("Call .run() first.")

        df = self.result_
        spans = self._faulty_spans()

        fig, axes = plt.subplots(3, 1, figsize=figsize, sharex=True)

        def shade_faulty(ax):
            for s, e in spans:
                ax.axvspan(s, e, color="red", alpha=0.12)

        # signal
        axes[0].plot(df.index, df["signal"], linewidth=0.5)
        axes[0].axhline(
            self.recovery_thresh,
            ls="--",
            color="green",
            alpha=0.5,
            label=f"±recovery_thresh ({self.recovery_thresh})",
        )
        axes[0].axhline(-self.recovery_thresh, ls="--", color="green", alpha=0.5)
        axes[0].set_ylabel("Signal")
        axes[0].legend(fontsize=8)
        shade_faulty(axes[0])

        # cusum
        axes[1].plot(df.index, df["cusum"], linewidth=0.5, color="tab:orange")
        axes[1].axhline(self.H, ls="--", color="red", alpha=0.5, label=f"H ({self.H})")
        axes[1].set_ylabel("CUSUM")
        axes[1].legend(fontsize=8)
        shade_faulty(axes[1])

        # recovery count as fill instead of bars
        axes[2].fill_between(
            df.index, df["recovery_count"], step="mid", color="tab:green", alpha=0.4
        )
        axes[2].axhline(
            self.recovery_steps,
            ls="--",
            color="blue",
            alpha=0.5,
            label=f"recovery_steps ({self.recovery_steps})",
        )
        axes[2].set_ylabel("Recovery count")
        axes[2].legend(fontsize=8)
        shade_faulty(axes[2])

        fig.suptitle(f"CUSUM (k={self.k}, H={self.H})", fontsize=12)
        fig.tight_layout()
        return fig


def merge_with_prediction(
    s_real: pd.Series, s_pred: pd.Series, s_update: pd.Series, fill: bool = False
) -> pd.Series:
    """
    Replace real values with predictions where s_update is True.

    Parameters
    ----------
    s_real : pd.Series
        Measured data.
    s_pred : pd.Series
        Model predictions.
    s_update : pd.Series[bool]
        True where s_pred should replace s_real (e.g. result_["faulty_discrete"]).
    """
    result = s_real.copy()
    match fill:
        case False:
            mask = s_update.reindex(result.index, fill_value=False)
        case True:
            mask = s_update.reindex(result.index).ffill()
    result.loc[mask] = s_pred.reindex(result.index).loc[mask]
    return result


def train_sk_model(
    data: pd.DataFrame,
    y_col: str | tuple,
    model: BaseEstimator,
    numpy_only: bool = False,
) -> BaseEstimator:
    _data = data.dropna(how="any")

    diff = len(data) - len(_data)
    if diff:
        print(f"Dropped {diff} datapoints ({1 - len(_data) / len(data):.2%}).")

    X = _data.loc[:, [c for c in data.columns if c != y_col]]  # .values
    y = _data.loc[:, y_col]  # .values

    if numpy_only:
        X = X.values
        y = y.values

    model.fit(X, y)

    return model


def predict(
    data: pd.DataFrame,
    model: BaseEstimator,
    y_name: None | str | tuple,
    numpy_only: bool = False,
) -> pd.Series | pd.DataFrame:
    X = data.loc[:, [c for c in data.columns if c != y_name]].dropna(how="any")

    if numpy_only:
        X = X.values

    pred = model.predict(X)

    pred = pd.Series(pred, X.index)

    if y_name is None:
        return pred

    elif isinstance(y_name, str):
        pred.name = y_name

    elif isinstance(y_name, tuple):
        pred = pred.to_frame()
        pred.columns = pd.MultiIndex.from_tuples([y_name])

    return pred


def pickle_sk_model(
    model: BaseEstimator, path: str | Path, assert_feature_names: bool = True
) -> Path:
    if assert_feature_names:
        model.feature_names_in_

    if not isinstance(path, Path):
        path = Path(path)

    if path.exists():
        raise FileExistsError(str(path))

    with open(path, "wb") as file:
        pickle.dump(model, file)

    return path


def _import_pickled_model(path: Path):
    with open(path, "rb") as file:
        model = pickle.load(file)

    return model


class _Singleton(type):
    _instances: dict[type, Any] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class _Models(metaclass=_Singleton): ...


MODELS = _Models()


if __name__ == "__main__":
    ...
