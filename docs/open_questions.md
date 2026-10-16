# Open questions

Possible errors and unverified assumptions in the calculations. Collected during the structural refactor, to be checked against the literature in the next phase. **Nothing listed here is fixed during the refactor.**

Line numbers refer to commit `5891a11` (before restructuring). Each entry also names the function, so it can be found after files move.

Format per entry: where, what looks wrong, why, how to check. When resolved, add the outcome and the source used, and keep the entry.

---

## 1. Unit of the Unisense emission rate (N2O vs. N2O-N)

**Where:** `UnisenseCalculation.get_emission` (`main.py` L74–91), `UnisenseN2OEmission._calculate_non_aerated_emission` (`formulas/emission.py` L80–88)

**What:** The result is labeled `emission_rate [g N2ON m-2 h-1]`, but no 28/44 conversion is applied. `EmersonCalculation.get_emission` (L135–144) does apply `* 28 / 44` for the same label.

**Why it may be fine:** If the dissolved input is already N2O-N (the name `n2on_data_mgL` suggests so), no conversion is needed.

**Why it may not be:** In the non-aerated formula, `c_n2o_aq` is combined with `N2O_ENV_AIR_CONC / hccv`, and `N2O_ENV_AIR_CONC` is commented as g N2O m⁻³. If `c_n2o_aq` is N2O-N, the two terms are in different units.

**Check:** Confirm the unit delivered by the Unisense sensor export. Make both terms of the non-aerated formula use the same basis. Make the Unisense and Emerson outputs comparable on the same basis.

## 2. Value of `N2O_ENV_AIR_CONC`

**Where:** `UnisenseN2OEmission.N2O_ENV_AIR_CONC` (`formulas/emission.py` L17–19)

**What:** `0.0003 / 0.636483023` ≈ 4.71e-4, commented as g N2O m⁻³ with the source Baresel et al. (2016). The divisor is close to 28/44 = 0.636364 but not equal to it. It's unclear where the extra digits come from.

**Rough plausibility check:** Atmospheric N2O at about 0.33–0.34 ppm, 20 °C and 1 atm gives about 6e-4 g N2O m⁻³, or about 3.9e-4 g N2O-N m⁻³. The current value is of the right order but matches neither exactly.

**Check:** Look up the value and its unit in Baresel et al. (2016). Decide whether 0.0003 is meant as g N2O-N m⁻³. Replace the divisor with an exact molar-mass ratio, or document where it comes from.

## 3. Inverted length check in `EmersonN2OEmission`

**Where:** `EmersonN2OEmission.calculate_n2o_mass_flow_gas` (`formulas/emission.py` L107–108)

**What:** `if not isinstance(temperature_celsius, Iterable): assert len(temperature_celsius) == ...` calls `len()` exactly when the temperature is a scalar. That raises `TypeError`. When the temperature is a Series, its length is never checked.

**Impact:** Does not affect results when the calculator passes Series (the current use). It breaks scalar temperature input, which the type hint allows.

**Check:** Probably just a missing `not` the other way around. It's validation, not numerics, so it could be fixed during the refactor if the user agrees.

**Outcome (phase 1, task 3):** Fixed during the refactor with the user's agreement (answer to question 9: raise what can falsify results). The length check is replaced by `physics._common.same_index`, which raises `ValueError` when Series arguments have different indexes, and scalar temperature is accepted (`tests/test_physics.py::test_off_gas_accepts_scalar_temperature`). Numbers unchanged, golden files pass.

## 4. Gas temperature and pressure in the off-gas calculation

**Where:** `EmersonN2OEmission.calculate_n2o_mass_flow_gas` (`formulas/emission.py` L112–117), called from `EmersonCalculation.get_emission`

**What:** The ppm → g m⁻³ conversion uses the temperature passed in (the process/liquid temperature from the calculator) and a fixed 101325 Pa.

**Question:** Is the off-gas concentration measured at liquid temperature and atmospheric pressure? Or should the conversion use the analyzer conditions, or normalized conditions matching the airflow measurement? Also check whether the airflow is given in normal m³ (Nm³) or actual m³. Mixing the two bases shifts results by roughly 5–10 %.

**Check:** Compare with the IWA protocol (off-gas method) and the Emerson analyzer documentation.

## 5. Clipping negative emissions to zero

**Where:** `UnisenseCalculation.get_emission` (`main.py` L89), `EmersonCalculation.get_emission` (`main.py` L148)

**What:** Negative emission rates are set to 0 before being returned.

**Question:** This is a methodological choice, not necessarily an error. It biases sums and means upward when noise around zero is common, for example in non-aerated periods where `c_aq` is below equilibrium. Consider whether clipping belongs in the calculator or should be an option applied later, and how often it happens in real data.

**Check:** Look at what the IWA protocol recommends. Count the clipped time steps on a real dataset.
