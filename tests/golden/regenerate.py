"""Regenerate the golden files.

Run only when different numbers are wanted on purpose:

    uv run python -m tests.golden.regenerate

Writes the synthetic inputs to ``inputs/`` and the calculator outputs to
``outputs/`` next to this file. ``params.json`` holds the plant
parameters shared by the generator and the tests.
"""

import json
from pathlib import Path

import pandas as pd

from kwb_n2o import (
    EmersonCalculation,
    EmissionFactorCalculation,
    TKNMassflowCalculation,
    UnisenseCalculation,
)
from tests.golden.synthetic import PARAMS, make_inputs

HERE = Path(__file__).parent
FLOAT_FORMAT = "%.17g"  # exact round trip for float64


def write(series: pd.Series, path: Path) -> None:
    series.to_frame().to_csv(path, index_label="time", float_format=FLOAT_FORMAT)


def compute_outputs(inp: dict[str, pd.Series], params: dict) -> dict[str, pd.Series]:
    """Run every calculator on the inputs. Shared with the tests."""
    unisense = UnisenseCalculation(
        n2on_data_mgL=inp["n2o_mgL"],
        air_data_zone_m3h=inp["air_m3h"],
        temperature_data_C=inp["temp_C"],
        zone_area_m2=params["zone_area_m2"],
        reactor_depth_m=params["reactor_depth_m"],
    )
    unisense_smoothed = UnisenseCalculation(
        n2on_data_mgL=inp["n2o_mgL"],
        air_data_zone_m3h=inp["air_m3h"],
        temperature_data_C=inp["temp_C"],
        zone_area_m2=params["zone_area_m2"],
        reactor_depth_m=params["reactor_depth_m"],
        smooth_data=True,
    )
    off_gas = EmersonCalculation(
        n2o_data_ppm=inp["n2o_ppm"],
        air_data_m3m2h=inp["air_m3m2h"],
        temperature_data_C=inp["temp_C"],
    )
    tkn_profile = TKNMassflowCalculation(
        tkn_mgl=inp["tkn_profile_mgL"], inflow_m3h=inp["inflow_m3h"]
    )
    tkn_const = TKNMassflowCalculation(
        tkn_mgl=params["tkn_const_mgL"], inflow_m3h=inp["inflow_m3h"]
    )

    out = {
        "unisense_henry": unisense.henry_series.rename("hccv"),
        "unisense_kla_s": unisense.kla.rename("kla_s"),
        "unisense_emission": unisense.get_emission(),
        "unisense_emission_smoothed": unisense_smoothed.get_emission(),
        "offgas_emission": off_gas.get_emission(),
        "tkn_massflow_profile": tkn_profile.get_massflow(),
        "tkn_massflow_const": tkn_const.get_massflow(),
    }
    out["ef_unisense"] = EmissionFactorCalculation(
        mdot_n2o_area_gm2h1=out["unisense_emission"],
        mdot_tkn_gh=out["tkn_massflow_profile"],
        zone_area_m2=params["zone_area_m2"],
    ).ef
    # tz-naive TKN massflow on a sub-period: pins the localization path.
    naive_massflow = tkn_profile.get_massflow(
        params["ef_naive_start"], params["ef_naive_end"]
    ).tz_localize(None)
    out["ef_offgas_naive_tkn"] = EmissionFactorCalculation(
        mdot_n2o_area_gm2h1=out["offgas_emission"],
        mdot_tkn_gh=naive_massflow,
        zone_area_m2=params["zone_area_m2"],
    ).ef
    return out


def main() -> None:
    (HERE / "inputs").mkdir(exist_ok=True)
    (HERE / "outputs").mkdir(exist_ok=True)
    (HERE / "params.json").write_text(json.dumps(PARAMS, indent=2) + "\n")

    inp = make_inputs()
    for name, series in inp.items():
        write(series, HERE / "inputs" / f"{name}.csv")

    for name, series in compute_outputs(inp, PARAMS).items():
        write(series, HERE / "outputs" / f"{name}.csv")


if __name__ == "__main__":
    main()
