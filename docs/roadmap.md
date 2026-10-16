# Roadmap

**Current phase: 1, structural refactor.**

Tick off tasks as they are done. Add new tasks when they come up, and ask before reordering or dropping planned ones.

---

## Phase 1: Structural refactor

Goal: better structure, identical numbers. With default settings, all outputs must match the golden files. New options are allowed as long as the defaults stay unchanged.

- [x] **1. Fix the package structure, nothing else.** The repo was just moved to the `src/` layout without updating imports. Rename `src/kwb.n2o/` to `src/kwb_n2o/` (a dot is not valid in a package name), fix the imports (e.g. `formulas/__init__.py` imports a non-existent `.util`), add missing dependencies (`more-itertools`, `python-calamine`) and a `[build-system]` to `pyproject.toml`. Done when `uv run python -c "import kwb_n2o"` works. No logic changes.
- [x] **2. Characterization tests.** Run every calculator on small synthetic timeseries (a few days, 1–5 min resolution, including aerated and non-aerated periods and a gap with NaNs) and store the outputs in `tests/golden/`. Compare with `np.testing.assert_allclose(..., rtol=1e-10)`.
- [ ] **3. Restructure** toward the target layout below. Pass `sort=True` explicitly to the `pd.concat` calls that align series: the current results rely on pandas 3 sorting concatenated `DatetimeIndex`es by default, which pandas 4 drops (`Pandas4Warning`).
- [ ] **4. Vendor-neutral naming for the off-gas pathway.** Rename `EmersonCalculation` → `OffGasCalculation` and `EmersonN2OEmission` → `OffGasN2OEmission` (or similar), since the method applies to any off-gas measurement. Keep the `Unisense*` names, because the method follows the Unisense calculation note.
- [ ] **5. Implement the static Henry option** (`static_henry=True` in the Unisense calculator, currently `NotImplementedError`): one Henry value for the whole period, as in the original Unisense note, instead of one per timestep. Check the exact definition against the note before implementing. Proposed default: Henry at the mean temperature of the period, with an optional fixed temperature parameter. The default `static_henry=False` must keep matching the golden files. Add tests: the result is constant over the period, and with constant temperature it equals the dynamic variant.
- [ ] **6. Remove unused code.** Ask before deleting. Candidates: `data_manipulation/data_enhancements.py` (CUSUM and sklearn helpers, the only user of scikit-learn), `unisense_signal_correction`, `unisense_signal_correction_quantile`, `add_next_day_to_index`, `cut_peaks`, `dtindex_timesteps`, `inner_concat`, `UnisenseCalculation.get_freight` (raises `NotImplementedError`), the unused matplotlib import in `main.py`.

### Target layout

```
src/kwb_n2o/
  __init__.py              # explicit public API, no star imports
  calculators/             # one module per pathway: input alignment → result series
    base.py                # EmissionCalculator protocol
    unisense.py
    off_gas.py
    emission_factor.py     # TKNMassflowCalculation, EmissionFactorCalculation
  physics/                 # pure formulas: no index alignment, no I/O
    henry.py
    kla.py
    liquid_phase.py        # UnisenseN2OEmission
    off_gas.py             # OffGasN2OEmission
  preprocessing/
    smoothing.py           # unisense_smooth
    alignment.py           # merge_td_on_dt
  data/Henry.xlsx          # package data, load via importlib.resources
tests/
docs/
references/
```

## Phase 2: Literature check

- Work through `docs/open_questions.md` against the sources in `references/`.
- For each entry, record the outcome and the source used. Keep the entry; don't delete it.
- Changes to numbers are made deliberately, one per commit, with golden files regenerated only after explicit approval.

## Phase 3: Visualisation

Scope still to be defined. Starting point: a separate plotting module that takes calculator results and returns matplotlib figures, with no calculations inside the plotting code.
