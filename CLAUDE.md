# kwb-n2o

Research code for estimating N2O emissions from aerated zones of activated-sludge tanks, based on timeseries. Each measurement pathway is one calculator class:

- **Unisense (liquid phase):** dissolved N2O + airflow + temperature → Henry constant (Sander 2023 table) and kLa (Unisense empirical method) → emission rate per area. Based on the Unisense emission calculation note (v3), with two deliberate deviations: it works on arbitrary timesteps, and it derives the Henry constant at every timestep from the measured temperature instead of once per period. Don't "fix" these back to the note.
- **Off-gas (gas phase):** N2O in off-gas (ppm) + area-specific airflow + temperature → mass flow via ideal gas law. `OffGasCalculation` and `OffGasN2OEmission`; the method applies to any off-gas measurement, whatever the analyzer.
- **Emission factor:** TKN load (inflow × TKN concentration) and EF = emitted N2O-N / TKN load.

Literature is listed in `references/links.json` (IWA N2O monitoring protocol, Unisense emission calculation note v3). The Henry data comes from Sander (2023), linked in `henry.py`.

## Where work is tracked

- `docs/roadmap.md`: current phase, planned tasks, target layout. Read it before starting work, and tick off tasks as they are done.
- `docs/open_questions.md`: suspected errors and unverified assumptions in the calculations. Add entries there; don't fix them silently.

## Commands

```bash
uv sync                      # install
uv run pytest                # tests
uv run ruff check --fix . && uv run ruff format .
```

Add dependencies with `uv add` (dev tools with `uv add --dev`), never with pip.

## Workflow

- **Results change only on purpose.** Characterization tests in `tests/golden/` pin the current outputs. If one fails, the change is wrong unless I asked for different numbers. Regenerate golden files only when I explicitly ask.
- **Suspected calculation errors go to `docs/open_questions.md`** (file, line, what looks wrong, why), not into a fix.
- **Small commits**, one logical change each. Tests pass after every commit.
- **Renaming is allowed anywhere** when there is a reason (clarity, vendor-neutral naming, consistency). State the reason in the commit message.
- **Deleting code:** check usage with grep first, list the candidates, and ask before deleting. Deleted code lives in git history; don't keep commented-out copies.
- **Ask before** structural decisions that deviate from `docs/roadmap.md`.

## Conventions

- Python 3.14, pandas 3, numpy 2.
- **Units are part of the name.** Keep the suffix convention (`_m3h`, `_m3s`, `_mgL`, `_C`, `_s`). Every physical constant gets a comment with its unit and source.
- Physics functions take and return floats or Series and do no alignment. Calculators handle alignment, NaN handling, and unit conversion.
- Timeseries use a `DatetimeIndex` (the TKN profile uses a `TimedeltaIndex`). Never localize or convert time zones silently; raise or warn.
- Type hints on public functions. Numpy-style docstrings stating the unit of every parameter and return value.
- Input validation with explicit exceptions (`ValueError`, `TypeError`), not `assert`. Warnings via `warnings.warn`, not `print`.

## Don't

- Don't modify `references/` or the contents of `Henry.xlsx`.
- Don't commit notebooks, measurement data, or pickled models (see `.gitignore`).
