# Literature check

Phase 2 of the roadmap: formulas and constants in the code compared with the sources in `references/links.json`. Suspected errors found here go to `open_questions.md`; this file records what was verified and where.

Sources used so far:

- **Unisense note v3:** "N2O Mass Transfer Coefficient Calculation from Aeration Field Size and Air Flow", Unisense Environment, two pages. Read in full.
- **IWA protocol:** not yet available in the development environment (see open questions 4 and 5).

## Unisense note v3 vs. `physics/kla.py`, `physics/liquid_phase.py`, `physics/henry.py`

| Note | Code | Result |
|---|---|---|
| (1.1) v_g,20°C = Q_A,20°C / aeration field size | `N2OkLa._vg20` | Same. Code converts the measured airflow to 20 °C first (`_qa20`); the note does not say how Q_A,20°C is obtained, see open question 7. |
| (1.2)/(1.3) kLa20 = (D_R / 0.815 m)^-0.49 · 34500 · v_g^0.86 [d-1] | `N2OkLa.get_kla_at_temperature`, constants `LABORATORY_REACTOR_DEPTH_M`, `KLA20_COEFFICIENT_D`, `GAS_VELOCITY_EXPONENT`, `DEPTH_EXPONENT` | Same constants and exponents. |
| (1.4) kLa_T = kLa20 · 1.024^(T − 20) | `TEMPERATURE_COEFFICIENT` | Same. |
| (2) aerated: r = H · S · [1 − exp(−kLa / H · V_R / Q_A)] · Q_A / V_R | `UnisenseN2OEmission._calculate_aerated_emission` | Same structure. Note uses d-1 and m3 d-1, code uses s-1 and m3 s-1 consistently; the ratio kLa·V_R/Q_A is unit-free either way. |
| (3) non-aerated: r = kLa_non-aerated · [S − C_air / H] | `_calculate_non_aerated_emission` | Same structure. kLa_non-aerated = 3 d-1 is inside the note's range 2 to 4 d-1. C_air basis differs, see open question 2. |
| Aeration threshold | `AERATION_THRESHOLD_M3S` = 50 m3 h-1 | Not in the note; a choice made in this code. |
| (4.1) H = 1 / (k_H · R · T · 10^3 L m-3), R = 8.314e-5 m3 bar mol-1 K-1 | `N2OHenry.get_hccv_at_temperature` = 1 / (Hcps · 8.314 · T) with Hcps in mol m-3 Pa-1 | Identical after unit conversion (mol L-1 bar-1 · 10^3 L m-3 / 10^5 Pa bar-1 = mol m-3 Pa-1). |
| (4.2) k_H = k_H° · exp(−Δ_soln H / R · (1/T − 1/T°)), T° = 25 °C | `N2OHenry._apply_temperature_correction`, `STANDARD_TEMPERATURE_CELSIUS` = 25 | Same form and reference temperature. |
| k_H° = 0.0247 mol L-1 bar-1, −Δ_soln H / R = 2675 K | Dynamic default: Sander (2023) means of the flagged rows, Hcps = 2.45e-4 mol m-3 Pa-1 (= 0.0245 mol L-1 bar-1), B = 2562.5 K | Deliberate deviation (CLAUDE.md). Hccv from the note's constants is 0.8 % lower at 25 °C, 1.7 % at 18 °C, 2.8 % at 10 °C. The static variant uses the note's constants. |
| Result per area | `get_emission`: r [g m-3 s-1] · depth [m] · 3600 | r · V_R / area = r · depth. Same. |

Not covered by the note: off-gas method (open question 4), clipping of negative rates (open question 5), unit of the sensor export (open question 1, data question).
