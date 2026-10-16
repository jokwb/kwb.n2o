import numpy as np
import pandas as pd


def unisense_smooth(s, window, treshold=0.3):
    std = s.rolling(window=window).std()
    mn = s.rolling(window=window).mean()

    new_s = pd.Series(
        np.where(std / mn > treshold, np.nan, s), index=s.index
    ).interpolate("linear")

    return new_s
