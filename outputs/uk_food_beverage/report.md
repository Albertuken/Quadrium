# UK I56 — Food And Beverage Service Activities   — sector split
Generated 2026-09-01 19:44 UTC · Quadrium 0.1.0 (MVP 0.1)

> **Sizes are real; structures are the parent's.** The table is the ONS 2023 analytical IOT and the size split uses real ABS turnover for SIC 56.1/56.2/56.3. Deliberately, no attempt is made to differentiate the subsectors' input structures, so all three carry the parent's multiplier. See the assumption ledger, and `INFORME_PILOTO.md` §4 for why.

**2 scenario(s)** · 1 sector(s) divided: `I56` into I561, I562, I563

---

## Original table

- **Source:** ONS, (consistent with UK National Accounts Blue Book 2025 & UK Balance of Payments Pink Book 2025)
- **Reference year:** 2023 · **Unit:** GBP million, current prices, basic prices · **Classification:** SIC 2007 (104 industries)
- **What the loader decided when reading this file:** Industry-by-industry, domestic use, basic prices, 104 x 104. The first two VA rows are imports and taxes on products, not value added — see the loader docstring. Reference year read from the Menu sheet, never from the filename (OQ-D-01); the size and both axes read from the sheet's own `_T` totals, never from a fixed offset — the ONS changed both between editions. Dropped 1 final-demand subtotal column(s) (P3 S1) to avoid double counting.

**Scenario `__original__`** — PASSED

- `OK  ` **check_original_balance** — row balance max dev 1.16e-10 against 1e-06, column balance max dev 1.16e-10 against 1e-06 — derived from float64 accumulation over the terms summed — this source does not round  
  <sub>ID-11 / ID-02, A_core_accounting_spec.md §A.6; D_open_questions.md OQ-B-02</sub>
- `OK  ` **check_sign_structure** — 129 negative cell(s): Z=1, Y=85, VA=43. Negatives are legitimate and select GRAS over RAS; they are not an error.  
  <sub>A_core_accounting_spec.md §A.8.1; CORE_012 ¶11.66, pp. 333–334</sub>
- `OK  ` **check_zero_output** — all sectors have non-zero output
- `OK  ` **check_leontief_productive** — spectral radius of A = 0.582408 (must be < 1), largest column sum 0.8007. Below 1 the Neumann series converges, the inverse is non-negative and a multiplier means what it says; at or above it the economy consumes at least as much as it makes and the multipliers are not large but undefined  
  <sub>ID-12, CORE_005 ¶36.36–36.39, pp. 1015–1016</sub>
- `OK  ` **check_leontief_identity** — max |Ax + y − x| = 1.16e-10 against 1e-06; the same statement through the inverse, max |Ly − x| = 8.73e-11 against 7.76e-06, which is that bound amplified by ‖L‖∞ = 7.76. Both are accounting, bounded by this source's own printed precision and by how far its books were already out  
  <sub>ID-12, CORE_005 ¶36.36, p. 1015</sub>
- `WARN` **check_leontief_nonnegative** — 19 of 10816 cells of the Leontief inverse are negative, and they sit in the column(s) for L68A; the deepest is -0.07917. A negative L[i,j] says that MORE final demand for j lowers output of i. It follows from negative cells in A, which are legitimate — the ONS's own published table has 19 — but a multiplier drawn from such a column is a sum with cancellation in it, and should be quoted knowing that  
  <sub>ID-12; A_core_accounting_spec.md §A.8.1</sub>
- `OK  ` **check_leontief_inverse** — ‖(I−A)L − I‖ = 1.33e-15 against 2.44e-12 for a matrix with condition number 3. This one is arithmetic and nothing else: it asks whether the inverse was computed, not whether the table adds up. An ill-conditioned system loses digits no source precision can restore  
  <sub>ID-12, CORE_005 ¶36.37, p. 1015</sub>

> Solver convergence is necessary but **not sufficient** for statistical validity (CORE_006 ¶9.51, p. 288; CORE_012 ¶11.105, pp. 342–343).

---

## Scenario `S1_abs`

### Balancing

- **Method: GRAS** — 1 negative cell(s) in the expanded table; RAS is undefined there (CORE_012 Box 11.3, p. 345)
- Converged: True; iterations by split: I56 1
- Max deviation from target row / column totals: 1.02e-10 / 1.46e-10
- Negatives: 1 in the seed, 1 in the result, **0 sign changes**

### `I56` — Food And Beverage Service Activities  

| Block | Key | Chosen? | Strength | Year | vs table | Weights |
|---|---|---|---|---|---|---|
| output | `key_turnover_abs_2023` | chosen | strong | 2023 | same year | 0.572, 0.150, 0.278 |
| final_demand | `key_turnover_abs_2023` | inherited | strong | 2023 | same year | 0.572, 0.150, 0.278 |
| value_added | `key_turnover_abs_2023` | inherited | strong | 2023 | same year | 0.572, 0.150, 0.278 |
| intermediate_rows | `key_turnover_abs_2023` | inherited | strong | 2023 | same year | 0.572, 0.150, 0.278 |
| intermediate_cols | `key_turnover_abs_2023` | inherited | strong | 2023 | same year | 0.572, 0.150, 0.278 |

**How wrong will each subsector's SIZE be?**

| Subsector | share of the parent | typical | p90 |
|---|---:|---:|---:|
| `I561` | 57.2% | 13 % | 48 % |
| `I562` | 15.0% | 49 % | 183 % |
| `I563` | 27.8% | 26 % | 99 % |

> A proportional split gives each part `share x parent output`, so an error of *e* **points** in a share is an error of `e / share` in that part's own size. The two columns put the median and p90 error of a real downloadable key — 7.3 and 27.4 points (`validators/run_real_key.py`) — through that division. Measured on 1,583 subsector-and-proxy pairs, the typical column runs about 0.65 of the truth and the p90 column contains it **92 %** of the time, holding at 88.7 to 92.9 % with each country held out.
>
> **A small part is where this bites.** A few points of key error is the whole of a 5 % subsector. If your key came from the office's own published split for another year rather than from a proxy, use 1.2 points instead of 7.3 (`validators/run_key_carryover.py`) and these numbers fall by six. See `validators/run_size_screen.py`.


- `key_turnover_abs_2023` — ONS Annual Business Survey, 'Non-financial business economy, UK: Sections A to S', Table 13 Section I, released 2026-05-26, retrieved 2026-08-09. United Kingdom, SIC 56.1/56.2/56.3 published directly at 3-digit level.

*inherited* — no key was named for that block, so it took the output key. That is a default, not a decision by the analyst, and it means the block carries whatever the output proxy implies rather than a measurement of its own.

| Subsector | Output | Intermediate sales | Final demand | Value added | Output multiplier |
|---|---:|---:|---:|---:|---:|
| I561 | 54,270.3 | 6,250.0 | 48,020.3 | 30,645.2 | 1.848 |
| I562 | 14,193.1 | 1,634.5 | 12,558.6 | 8,014.5 | 1.848 |
| I563 | 26,346.6 | 3,034.2 | 23,312.4 | 14,877.3 | 1.848 |

*Corroboration against `key_agva_abs_2023` (strong, 2023), which did **not** drive this split:*

| Subsector | implied by the split | measured | gap |
|---|---:|---:|---:|
| I561 | 0.5724 | 0.5651 | +1.3% |
| I562 | 0.1497 | 0.1643 | -8.9% |
| I563 | 0.2779 | 0.2706 | +2.7% |

Largest disagreement **8.9%**, against the `value_added` weights. Every other check in this report asks whether the arithmetic is self-consistent and would pass on any key; this one asks whether an independent measurement agrees. Source: ONS Annual Business Survey, 'Non-financial business economy, UK: Sections A to S', Table 13 Section I, released 2026-05-26, retrieved 2026-08-09. United Kingdom, SIC 56.1/56.2/56.3 published directly at 3-digit level.

*Corroboration against `key_employment_bres_2023` (medium, 2023), which did **not** drive this split:*

| Subsector | implied by the split | measured | gap |
|---|---:|---:|---:|
| I561 | 0.5724 | 0.5969 | -4.1% |
| I562 | 0.1497 | 0.1392 | +7.5% |
| I563 | 0.2779 | 0.2639 | +5.3% |

Largest disagreement **7.5%**, against the `output` weights. Every other check in this report asks whether the arithmetic is self-consistent and would pass on any key; this one asks whether an independent measurement agrees. Source: ONS Business Register and Employment Survey (BRES), employment including working proprietors, Great Britain, via NOMIS dataset NM_189_1, retrieved 2026-08-09. GREAT BRITAIN, not UK: Northern Ireland is surveyed separately by NISRA and is excluded from these shares.

*Corroboration against `key_purchases_abs_2023` (strong, 2023), which did **not** drive this split:*

| Subsector | implied by the split | measured | gap |
|---|---:|---:|---:|
| I561 | 0.5724 | 0.5830 | -1.8% |
| I562 | 0.1497 | 0.1362 | +9.9% |
| I563 | 0.2779 | 0.2808 | -1.0% |

Largest disagreement **9.9%**, against the `intermediate_cols` weights. Every other check in this report asks whether the arithmetic is self-consistent and would pass on any key; this one asks whether an independent measurement agrees. Source: ONS Annual Business Survey, 'Non-financial business economy, UK: Sections A to S', Table 13 Section I, released 2026-05-26, retrieved 2026-08-09. United Kingdom, SIC 56.1/56.2/56.3 published directly at 3-digit level.

*Classification:* I56 (division) -> I561, I562, I563; hierarchy OK, coverage not checked: whether these children exhaust the parent needs the classification's own list of positions, which this project does not hold (OQ-S-01)

*Headroom:* the tightest subsector still has 197.96 of internal trade left, 15.0 % of this sector's own diagonal of 1,322.4. That margin is the budget any differentiated input structure has to fit inside — a sector that barely trades with itself leaves little room to claim its subsectors buy differently.

*Input structures:* these subsectors buy the **same mix** in different amounts — cosine distance -0.00000, effectively zero. Each is a scaled copy of the parent's input structure, so any difference in their multipliers is an artefact of the internal block, not a finding. Supply `input_profiles` to give them genuinely different purchasing patterns.

> **What a profile is worth, measured.** On 96 splits where the office publishes both the parent and its parts, giving the engine the parts' TRUE input profile moves the SEED's multiplier error from a median 7.78 % to 3.48 %. **The balancer then gives all of that back**: the delivered table is a median 7.79 % against 7.78 % for using no profile at all, and it beats doing nothing in 30 of 56. Balancing adjusts the internal block only — correct when a split is proportional, since nothing else moves — so a profiled column pushes the whole adjustment into the least reliable part of the table. The engine also refuses the profiled scenario outright in 19 of 54.
>
> **Borrowing one from a country that publishes your split is a coin flip** — 162 borrowings, better in 78 and worse in 84, helping by a median 4.2 points and hurting by 3.1. It helps where the split was going badly anyway and hurts where it was fine (r = +0.42 against the baseline error), which is only knowable afterwards; the ex-ante screen does not predict it (r = +0.17 for the parent multiplier, -0.22 for the number of parts). See `validators/run_input_profiles_backtest.py`.

The estimated **internal block** for this sector is 0.07 % of the absolute value of the intermediate matrix. It has no direct observation behind it: the original table held a single diagonal cell of 1,322.4, and the split assumes the propensity to trade internally is proportional to each subsector's weight (MVP_0.1 §6.3).

> **It is the weakest assumption here, and the result does not rest on it.** Measured on 96 splits where the office publishes both the parent and its parts, this block misses the published one by a median of **60 %** — the worst-estimated part of a split, against 42 % for the touched block as a whole. But how wrong it is does not predict how wrong the subsectors' multipliers are: correlation **+0.03**. Raising `internal_block_alpha` to the 1.5 that real blocks show makes the multipliers worse, not better, on 37 of those 68. See `validators/run_internal_block_backtest.py`.

> One caution about the percentage above: it is the block over the **whole** intermediate matrix, which is why it reads small. Over this subsector's own input column the same block runs from nothing to 56 %, and that is the share with anything to do with its multiplier.

### Cell provenance

| Provenance | Cells | Share | Data status (§A.1) |
|---|---:|---:|---|
| observed | 10609 | 94.4 % | OBSERVED |
| proxy_estimated | 627 | 5.6 % | **ESTIMATED** |
| balanced_adjustment | 0 | 0.0 % | **BALANCED** |
| user_constraint | 0 | 0.0 % | OBSERVED (analyst-pinned) |

> **This is a map of what was estimated, not a warning about your multipliers.** Measured on 68 real splits where the office publishes both the parent and its parts, the share of the table a split had to estimate has **no relationship** to how far the subsectors' multipliers land from the published truth — correlation −0.01. A split can be 112 % out cell by cell and still put its multipliers inside 4 %, or be tidy in the cells and 40 % out in the multipliers. What the multiplier error does track, at +0.92, is how UNLIKE the parts are: the worst error is about two thirds of the spread between their true multipliers, because proportional splitting hands every part the parent's average structure. See `validators/run_split_backtest.py`.

### Validation

**Scenario `S1_abs`** — PASSED

Method: **GRAS** — 1 negative cell(s) in the expanded table; RAS is undefined there (CORE_012 Box 11.3, p. 345)

- `OK  ` **check_proxy_coverage** — every subsector of every split has a positive proxy in every block (1 split(s))
- `OK  ` **check_key_vintage** — all 5 key(s) and profile(s) are measured in 2023, the table's own reference year
- `OK  ` **check_solver_convergence** — GRAS converged in 1 iterations (step 6.88e-15, tolerance 1e-09, PROJECT CHOICE)  
  <sub>CORE_006 ¶9.51, p. 288 — convergence is necessary, not sufficient</sub>
- `OK  ` **check_margins_attained** — max deviation from target row/column totals 1.46e-10 against a tolerance of 0.000238; margin imbalance sum(rows)-sum(cols) = 0. 1.16e-10 of the tolerance is the source's own unclosed identities, which the targets inherit  
  <sub>OQ-B-02 v1.57; quadrium.precision.infeasibility_floor</sub>
- `OK  ` **check_reaggregation_untouched** — cells involving no split sector reproduce the original to 0 (must be ~0: they were copied, not estimated)
- `OK  ` **check_reaggregation** — max reaggregation error 3.44e-13 % against a tolerance of 1e-06 % (PROJECT CHOICE); grand total off by 0
- `OK  ` **check_leontief_productive** — spectral radius of A = 0.582408 (must be < 1), largest column sum 0.8007. Below 1 the Neumann series converges, the inverse is non-negative and a multiplier means what it says; at or above it the economy consumes at least as much as it makes and the multipliers are not large but undefined  
  <sub>ID-12, CORE_005 ¶36.36–36.39, pp. 1015–1016</sub>
- `OK  ` **check_leontief_identity** — max |Ax + y − x| = 1.16e-10 against 1e-06; the same statement through the inverse, max |Ly − x| = 8.73e-11 against 7.9e-06, which is that bound amplified by ‖L‖∞ = 7.9. Both are accounting, bounded by this source's own printed precision and by how far its books were already out  
  <sub>ID-12, CORE_005 ¶36.36, p. 1015</sub>
- `WARN` **check_leontief_nonnegative** — 21 of 11236 cells of the Leontief inverse are negative, and they sit in the column(s) for L68A; the deepest is -0.07917. A negative L[i,j] says that MORE final demand for j lowers output of i. It follows from negative cells in A, which are legitimate — the ONS's own published table has 19 — but a multiplier drawn from such a column is a sum with cancellation in it, and should be quoted knowing that  
  <sub>ID-12; A_core_accounting_spec.md §A.8.1</sub>
- `OK  ` **check_leontief_inverse** — ‖(I−A)L − I‖ = 1.33e-15 against 2.49e-12 for a matrix with condition number 3. This one is arithmetic and nothing else: it asks whether the inverse was computed, not whether the table adds up. An ill-conditioned system loses digits no source precision can restore  
  <sub>ID-12, CORE_005 ¶36.37, p. 1015</sub>
- `OK  ` **check_sign_preserved** — 0 cell(s) changed sign during balancing; 1 negative(s) in the result against 1 in the seed  
  <sub>UNH_18 ¶18.35, p. 558 — GRAS is sign preserving</sub>
- `OK  ` **check_extreme_coefficients** — 0 technical coefficient(s) above 1 (PROJECT CHOICE); max = 0.439, min = -0.0799
- `OK  ` **check_internal_block_share** — estimated internal block(s) as a share of the absolute value of the whole intermediate matrix: I56 0.07 %. This is the least certain part of the result and is labelled PROXY_ESTIMATED throughout  
  <sub>MVP_0.1 §6.3 — double-proportionality hypothesis</sub>
- `OK  ` **check_zero_row_col** — 0 zero row/column(s) created by balancing. Zero means below 2.948e-07, which is what this source's own precision can distinguish from it. 3 were already zero in the seed and are not attributable to the solver: row L68A, row T97, col T97
- `OK  ` **check_user_constraints_held** — every analyst-pinned cell still holds the value it was given  
  <sub>UNH_18 ¶18.81, p. 569 — GRAS accepts row and column totals only</sub>
- `OK  ` **check_provenance_complete** — 10609 observed, 627 proxy-estimated, 0 balanced-adjustment, 0 user-constrained, of 11236 cells  
  <sub>MVP_0.1 §2.6; A_core_accounting_spec.md §A.1</sub>

> Solver convergence is necessary but **not sufficient** for statistical validity (CORE_006 ¶9.51, p. 288; CORE_012 ¶11.105, pp. 342–343).

---

## Scenario `S2_employment`

### Balancing

- **Method: GRAS** — 1 negative cell(s) in the expanded table; RAS is undefined there (CORE_012 Box 11.3, p. 345)
- Converged: True; iterations by split: I56 1
- Max deviation from target row / column totals: 1.02e-10 / 1.46e-10
- Negatives: 1 in the seed, 1 in the result, **0 sign changes**

### `I56` — Food And Beverage Service Activities  

| Block | Key | Chosen? | Strength | Year | vs table | Weights |
|---|---|---|---|---|---|---|
| output | `key_employment_bres_2023` | chosen | medium | 2023 | same year | 0.597, 0.139, 0.264 |
| final_demand | `key_employment_bres_2023` | inherited | medium | 2023 | same year | 0.597, 0.139, 0.264 |
| value_added | `key_employment_bres_2023` | inherited | medium | 2023 | same year | 0.597, 0.139, 0.264 |
| intermediate_rows | `key_employment_bres_2023` | inherited | medium | 2023 | same year | 0.597, 0.139, 0.264 |
| intermediate_cols | `key_employment_bres_2023` | inherited | medium | 2023 | same year | 0.597, 0.139, 0.264 |

**How wrong will each subsector's SIZE be?**

| Subsector | share of the parent | typical | p90 |
|---|---:|---:|---:|
| `I561` | 59.7% | 12 % | 46 % |
| `I562` | 13.9% | 52 % | 197 % |
| `I563` | 26.4% | 28 % | 104 % |

> A proportional split gives each part `share x parent output`, so an error of *e* **points** in a share is an error of `e / share` in that part's own size. The two columns put the median and p90 error of a real downloadable key — 7.3 and 27.4 points (`validators/run_real_key.py`) — through that division. Measured on 1,583 subsector-and-proxy pairs, the typical column runs about 0.65 of the truth and the p90 column contains it **92 %** of the time, holding at 88.7 to 92.9 % with each country held out.
>
> **A small part is where this bites.** A few points of key error is the whole of a 5 % subsector. If your key came from the office's own published split for another year rather than from a proxy, use 1.2 points instead of 7.3 (`validators/run_key_carryover.py`) and these numbers fall by six. See `validators/run_size_screen.py`.


- `key_employment_bres_2023` — ONS Business Register and Employment Survey (BRES), employment including working proprietors, Great Britain, via NOMIS dataset NM_189_1, retrieved 2026-08-09. GREAT BRITAIN, not UK: Northern Ireland is surveyed separately by NISRA and is excluded from these shares.

*inherited* — no key was named for that block, so it took the output key. That is a default, not a decision by the analyst, and it means the block carries whatever the output proxy implies rather than a measurement of its own.

| Subsector | Output | Intermediate sales | Final demand | Value added | Output multiplier |
|---|---:|---:|---:|---:|---:|
| I561 | 56,590.6 | 6,517.2 | 50,073.4 | 31,955.4 | 1.848 |
| I562 | 13,201.4 | 1,520.3 | 11,681.1 | 7,454.5 | 1.848 |
| I563 | 25,018.0 | 2,881.2 | 22,136.9 | 14,127.1 | 1.848 |

*Corroboration against `key_agva_abs_2023` (strong, 2023), which did **not** drive this split:*

| Subsector | implied by the split | measured | gap |
|---|---:|---:|---:|
| I561 | 0.5969 | 0.5651 | +5.6% |
| I562 | 0.1392 | 0.1643 | -15.3% |
| I563 | 0.2639 | 0.2706 | -2.5% |

Largest disagreement **15.3%**, against the `value_added` weights. Every other check in this report asks whether the arithmetic is self-consistent and would pass on any key; this one asks whether an independent measurement agrees. Source: ONS Annual Business Survey, 'Non-financial business economy, UK: Sections A to S', Table 13 Section I, released 2026-05-26, retrieved 2026-08-09. United Kingdom, SIC 56.1/56.2/56.3 published directly at 3-digit level.

*Corroboration against `key_purchases_abs_2023` (strong, 2023), which did **not** drive this split:*

| Subsector | implied by the split | measured | gap |
|---|---:|---:|---:|
| I561 | 0.5969 | 0.5830 | +2.4% |
| I562 | 0.1392 | 0.1362 | +2.2% |
| I563 | 0.2639 | 0.2808 | -6.0% |

Largest disagreement **6.0%**, against the `intermediate_cols` weights. Every other check in this report asks whether the arithmetic is self-consistent and would pass on any key; this one asks whether an independent measurement agrees. Source: ONS Annual Business Survey, 'Non-financial business economy, UK: Sections A to S', Table 13 Section I, released 2026-05-26, retrieved 2026-08-09. United Kingdom, SIC 56.1/56.2/56.3 published directly at 3-digit level.

*Corroboration against `key_turnover_abs_2023` (strong, 2023), which did **not** drive this split:*

| Subsector | implied by the split | measured | gap |
|---|---:|---:|---:|
| I561 | 0.5969 | 0.5724 | +4.3% |
| I562 | 0.1392 | 0.1497 | -7.0% |
| I563 | 0.2639 | 0.2779 | -5.0% |

Largest disagreement **7.0%**, against the `output` weights. Every other check in this report asks whether the arithmetic is self-consistent and would pass on any key; this one asks whether an independent measurement agrees. Source: ONS Annual Business Survey, 'Non-financial business economy, UK: Sections A to S', Table 13 Section I, released 2026-05-26, retrieved 2026-08-09. United Kingdom, SIC 56.1/56.2/56.3 published directly at 3-digit level.

*Classification:* I56 (division) -> I561, I562, I563; hierarchy OK, coverage not checked: whether these children exhaust the parent needs the classification's own list of positions, which this project does not hold (OQ-S-01)

*Headroom:* the tightest subsector still has 184.13 of internal trade left, 13.9 % of this sector's own diagonal of 1,322.4. That margin is the budget any differentiated input structure has to fit inside — a sector that barely trades with itself leaves little room to claim its subsectors buy differently.

*Input structures:* these subsectors buy the **same mix** in different amounts — cosine distance -0.00000, effectively zero. Each is a scaled copy of the parent's input structure, so any difference in their multipliers is an artefact of the internal block, not a finding. Supply `input_profiles` to give them genuinely different purchasing patterns.

> **What a profile is worth, measured.** On 96 splits where the office publishes both the parent and its parts, giving the engine the parts' TRUE input profile moves the SEED's multiplier error from a median 7.78 % to 3.48 %. **The balancer then gives all of that back**: the delivered table is a median 7.79 % against 7.78 % for using no profile at all, and it beats doing nothing in 30 of 56. Balancing adjusts the internal block only — correct when a split is proportional, since nothing else moves — so a profiled column pushes the whole adjustment into the least reliable part of the table. The engine also refuses the profiled scenario outright in 19 of 54.
>
> **Borrowing one from a country that publishes your split is a coin flip** — 162 borrowings, better in 78 and worse in 84, helping by a median 4.2 points and hurting by 3.1. It helps where the split was going badly anyway and hurts where it was fine (r = +0.42 against the baseline error), which is only knowable afterwards; the ex-ante screen does not predict it (r = +0.17 for the parent multiplier, -0.22 for the number of parts). See `validators/run_input_profiles_backtest.py`.

The estimated **internal block** for this sector is 0.07 % of the absolute value of the intermediate matrix. It has no direct observation behind it: the original table held a single diagonal cell of 1,322.4, and the split assumes the propensity to trade internally is proportional to each subsector's weight (MVP_0.1 §6.3).

> **It is the weakest assumption here, and the result does not rest on it.** Measured on 96 splits where the office publishes both the parent and its parts, this block misses the published one by a median of **60 %** — the worst-estimated part of a split, against 42 % for the touched block as a whole. But how wrong it is does not predict how wrong the subsectors' multipliers are: correlation **+0.03**. Raising `internal_block_alpha` to the 1.5 that real blocks show makes the multipliers worse, not better, on 37 of those 68. See `validators/run_internal_block_backtest.py`.

> One caution about the percentage above: it is the block over the **whole** intermediate matrix, which is why it reads small. Over this subsector's own input column the same block runs from nothing to 56 %, and that is the share with anything to do with its multiplier.

### Cell provenance

| Provenance | Cells | Share | Data status (§A.1) |
|---|---:|---:|---|
| observed | 10609 | 94.4 % | OBSERVED |
| proxy_estimated | 627 | 5.6 % | **ESTIMATED** |
| balanced_adjustment | 0 | 0.0 % | **BALANCED** |
| user_constraint | 0 | 0.0 % | OBSERVED (analyst-pinned) |

> **This is a map of what was estimated, not a warning about your multipliers.** Measured on 68 real splits where the office publishes both the parent and its parts, the share of the table a split had to estimate has **no relationship** to how far the subsectors' multipliers land from the published truth — correlation −0.01. A split can be 112 % out cell by cell and still put its multipliers inside 4 %, or be tidy in the cells and 40 % out in the multipliers. What the multiplier error does track, at +0.92, is how UNLIKE the parts are: the worst error is about two thirds of the spread between their true multipliers, because proportional splitting hands every part the parent's average structure. See `validators/run_split_backtest.py`.

### Validation

**Scenario `S2_employment`** — PASSED

Method: **GRAS** — 1 negative cell(s) in the expanded table; RAS is undefined there (CORE_012 Box 11.3, p. 345)

- `OK  ` **check_proxy_coverage** — every subsector of every split has a positive proxy in every block (1 split(s))
- `OK  ` **check_key_vintage** — all 5 key(s) and profile(s) are measured in 2023, the table's own reference year
- `OK  ` **check_solver_convergence** — GRAS converged in 1 iterations (step 1.02e-14, tolerance 1e-09, PROJECT CHOICE)  
  <sub>CORE_006 ¶9.51, p. 288 — convergence is necessary, not sufficient</sub>
- `OK  ` **check_margins_attained** — max deviation from target row/column totals 1.46e-10 against a tolerance of 0.000238; margin imbalance sum(rows)-sum(cols) = 0. 1.16e-10 of the tolerance is the source's own unclosed identities, which the targets inherit  
  <sub>OQ-B-02 v1.57; quadrium.precision.infeasibility_floor</sub>
- `OK  ` **check_reaggregation_untouched** — cells involving no split sector reproduce the original to 0 (must be ~0: they were copied, not estimated)
- `OK  ` **check_reaggregation** — max reaggregation error 2.06e-13 % against a tolerance of 1e-06 % (PROJECT CHOICE); grand total off by 0
- `OK  ` **check_leontief_productive** — spectral radius of A = 0.582408 (must be < 1), largest column sum 0.8007. Below 1 the Neumann series converges, the inverse is non-negative and a multiplier means what it says; at or above it the economy consumes at least as much as it makes and the multipliers are not large but undefined  
  <sub>ID-12, CORE_005 ¶36.36–36.39, pp. 1015–1016</sub>
- `OK  ` **check_leontief_identity** — max |Ax + y − x| = 1.16e-10 against 1e-06; the same statement through the inverse, max |Ly − x| = 8.73e-11 against 7.9e-06, which is that bound amplified by ‖L‖∞ = 7.9. Both are accounting, bounded by this source's own printed precision and by how far its books were already out  
  <sub>ID-12, CORE_005 ¶36.36, p. 1015</sub>
- `WARN` **check_leontief_nonnegative** — 21 of 11236 cells of the Leontief inverse are negative, and they sit in the column(s) for L68A; the deepest is -0.07917. A negative L[i,j] says that MORE final demand for j lowers output of i. It follows from negative cells in A, which are legitimate — the ONS's own published table has 19 — but a multiplier drawn from such a column is a sum with cancellation in it, and should be quoted knowing that  
  <sub>ID-12; A_core_accounting_spec.md §A.8.1</sub>
- `OK  ` **check_leontief_inverse** — ‖(I−A)L − I‖ = 1.55e-15 against 2.49e-12 for a matrix with condition number 3. This one is arithmetic and nothing else: it asks whether the inverse was computed, not whether the table adds up. An ill-conditioned system loses digits no source precision can restore  
  <sub>ID-12, CORE_005 ¶36.37, p. 1015</sub>
- `OK  ` **check_sign_preserved** — 0 cell(s) changed sign during balancing; 1 negative(s) in the result against 1 in the seed  
  <sub>UNH_18 ¶18.35, p. 558 — GRAS is sign preserving</sub>
- `OK  ` **check_extreme_coefficients** — 0 technical coefficient(s) above 1 (PROJECT CHOICE); max = 0.439, min = -0.0799
- `OK  ` **check_internal_block_share** — estimated internal block(s) as a share of the absolute value of the whole intermediate matrix: I56 0.07 %. This is the least certain part of the result and is labelled PROXY_ESTIMATED throughout  
  <sub>MVP_0.1 §6.3 — double-proportionality hypothesis</sub>
- `OK  ` **check_zero_row_col** — 0 zero row/column(s) created by balancing. Zero means below 2.948e-07, which is what this source's own precision can distinguish from it. 3 were already zero in the seed and are not attributable to the solver: row L68A, row T97, col T97
- `OK  ` **check_user_constraints_held** — every analyst-pinned cell still holds the value it was given  
  <sub>UNH_18 ¶18.81, p. 569 — GRAS accepts row and column totals only</sub>
- `OK  ` **check_provenance_complete** — 10609 observed, 627 proxy-estimated, 0 balanced-adjustment, 0 user-constrained, of 11236 cells  
  <sub>MVP_0.1 §2.6; A_core_accounting_spec.md §A.1</sub>

> Solver convergence is necessary but **not sufficient** for statistical validity (CORE_006 ¶9.51, p. 288; CORE_012 ¶11.105, pp. 342–343).

---

## Scenario comparison

Output multipliers by subsector. The range is the honest measure of how much the proxy choice matters — of how much it matters, not of how wrong the answer is; see the note under *How far the outside evidence disagrees*.

| Subsector | S1_abs | S2_employment | Range | Range % |
|---|---|---|---|---|
| I561 | 1.848 | 1.848 | 0.000 | 0.0 % |
| I562 | 1.848 | 1.848 | 0.000 | 0.0 % |
| I563 | 1.848 | 1.848 | 0.000 | 0.0 % |

**Main driver of variation:** the cell `G46 -> I561`, which spans 108.2 across scenarios. This is the crude measure of MVP_0.1 §10 — the widest cell, not a sensitivity analysis.

### How far the outside evidence disagrees

Each scenario compared against the allocation keys that were registered and then **not** used to drive it. The spread between the closest and the furthest is the uncertainty this report can actually support.

| Scenario | driven by | closest key | furthest key | keys compared |
|---|---|---|---|---:|
| `S1_abs` | `key_turnover_abs_2023` | `key_employment_bres_2023` 7.5% | `key_purchases_abs_2023` 9.9% | 3 |
| `S2_employment` | `key_employment_bres_2023` | `key_purchases_abs_2023` 6.0% | `key_agva_abs_2023` 15.3% | 3 |

> **Nothing here says which end is right, and the ranking that used to sit in this space was removed for cause.** It marked the scenario that disagreed least as better supported. On the Spanish pilot the key that disagreed MOST — employment, by 58.8 % — turned out to be the closest to the truth once the INE's 110-product supply table settled it, while the driving key was 9.8 points out. Least disagreement measures resemblance to your own inputs, not accuracy. See `validators/run_key_bias.py`.
>
> **What a large disagreement is good for** is telling you where to go looking. In that case a better source existed and was one download away. See `D_open_questions.md` OQ-S-05 and OQ-S-06.
>
> **This spread is not a confidence interval, and it is not much of a floor either.** Measured on 65 splits across five country-years where the office publishes both the parent and its parts: the range contains the true share for 84.0 % of subsectors and for every subsector at once in **49 of 65 splits** — it misses one split in four. And where it does contain the answer it does so across a median **28 points of share**, which excludes almost nothing. Honest about being uncertain; nearly silent about where the answer is.
>
> **A narrow range is not a safer one.** The splits where the range misses are the WIDER ones (median 38.6 points against 27.8), so there is no flag here to act on. Nor is the verdict a property of the sector: of the 13 parents that appear in more than one country-year, the range agrees with itself in 7. Dropping the highest and lowest proxy does not rescue it — coverage falls to 59.7 % while the range is still 12 points wide. See `validators/run_key_spread.py`.
>
> One thing the spread does NOT do is lean reliably one way. Every available proxy sits on the same side of the answer for only **16.0 %** of subsectors. Spanish hospitality, where all seven of the pilot's keys overstate accommodation and the range misses by 0.6 points, is the unusual case and not the pattern — as it also was for the size of the error. See `validators/run_key_bias.py` and `validators/run_real_key.py`.

### How risky was this split, before you made it?

**How many parts you asked for** ranks a split's difficulty, measured on 96 real splits where the office publishes both the parent and its parts. Held out one country at a time it separates in the same direction in all four — BE 7.9 to 22.5 %, FR 8.2 to 11.2 %, HU 5.3 to 7.9 %, SK 4.4 to 19.7 %.

| Split | parent multiplier | parts | comparable splits: median error | worst |
|---|---:|---:|---:|---:|
| `I56` | 1.848 | 3 | 10.6 % | 49.2 % |

> The error columns are what the subsectors' **multipliers** did in comparable splits. They are a band, not a prediction for your table: the screen ranks, and the spread inside each band is wide — the worst column is the worst of 96, not a bound on yours. The cut point is the median of the 96, two parts.
>
> **The parent multiplier column is printed and is no longer used to place you in a band.** Fitted on 68 splits it looked like a second, independent signal; on 96 it ranks at +0.24 and is NEGATIVE in France, and at few parts its two bands come out at 5.4 % and 5.3 % — no separation at all. An earlier version of this report split you four ways on it. See `validators/run_split_screen.py`.
>
> **The band does not depend on your key being right.** Without an input profile, no allocation key can move a subsector's multiplier — the share cancels out of the coefficients, so every key gives the same one. Measured on 638 real published proxies, identical to the answer's own multipliers in 636 of 638 — the two exceptions give a real subsector a share of exactly zero, and the engine refuses those. What the band measures is structure, and your key cannot add to it or subtract from it. See `validators/run_key_invariance.py`.
>
> **Your key sets the sizes, and that is where it costs you.** A share error of a few points is not a subsector a few percent out: the error is relative to a part that may be small, so it is amplified by a median factor of 3.8. Real downloadable proxies are out by a median 7.3 points of share, which leaves the worst subsector's output out by a median **32 %**, and only 77 of 638 put every subsector within 10 % of its true size. See `validators/run_real_key.py`.
>
> **If ANOTHER YEAR of your own table publishes the split, use it and ignore all of this.** The same parent a year earlier misses by **0.7 points**, against 2.8 for the band above and 5.7 for the same parent borrowed from another country. A split's difficulty is a property of the table it is in, not of the sector — which is why another COUNTRY's number is the worst of the three, and why `validators/run_key_carryover.py` finds the same thing from the key's side.
>
> **Asking for more parts does not make each part worse.** A single subsector's error barely moves with the number of parts (r = +0.17); the worst of them does (r = +0.36), because more parts is more draws. If you need one particular subsector, that costs you little. If you need all of them to hold, it costs you the maximum. See `validators/run_split_screen.py`.

### How wrong is this if your allocation key is wrong?

Exactly as wrong as the key, in the sizes — and not at all in the multipliers. The weight scales a subsector's output, value added and purchases together and cancels out of `a_ij = Z_ij / X_j`, so **one per cent of error in the key is one per cent of error in the size and zero in the multiplier**. That is arithmetic, not an estimate, and it needs no simulation.

Per 1 % your key is wrong, in GBP million:

| Subsector | Output | Value added | Purchases | per 1 % of key |
|---|---:|---:|---:|---:|
| `I561` | 54,270 | 30,645 | 23,625 | **543** |
| `I562` | 14,193 | 8,015 | 6,179 | **142** |
| `I563` | 26,347 | 14,877 | 11,469 | **263** |

So a key you believe to within 10 % gives a subsector size you believe to within 10 %, and a multiplier you believe exactly as much as you believe the parent sector's — no more and no less. **The uncertainty the key carries lands entirely on the levels.**

What moves a multiplier is the `profiles` sheet, and it moves it very little: on the project's own fixture, DOUBLING one supplier's intensity moves the multiplier by 0.35 %. If you need subsectors that differ as buyers, that is the lever — and it is a short one. See `validators/run_key_sensitivity.py`.

### Read this before quoting the multipliers

**Every subsector has the same output multiplier, and that is a property of the method, not a finding about the economy.**

Splitting a sector proportionally with a single allocation key gives each subsector a scaled copy of the parent's input structure. If output and intermediate purchases are split by the same weights, the technical coefficients `a_ij = Z_ij / X_j` come out identical for every subsector — the weight cancels — so the multipliers must be identical too. The arithmetic cannot produce anything else.

The disaggregation is still useful: each subsector gets its own output, value added and final demand, and the table stays balanced. But it adds **no information about how the subsectors differ as buyers**. Genuinely different multipliers require genuinely different input structures — a separate proxy for the intermediate columns, survey data on what each subsector actually purchases, or cells set by hand through `Scenario.user_constraints`.

Quoting these multipliers as evidence that hotels and restaurants have similar economic pull would be circular.

---

## How to read this

- Every value produced by the solver has data status `BALANCED`. It is **not** an observation and must never be relabelled as one.
- Solver convergence is **necessary but not sufficient** for statistical validity (CORE_006 ¶9.51, p. 288). A converged run that fails a plausibility check is a failed run.
- **No published source states a numerical tolerance for an accounting identity.** Six were searched and the question is settled: what a balance can be tested against is a property of the table, not of the method. So the floor applied here is derived from your own table's stated precision — an identity summing `n` cells published to `d` decimals cannot be checked more tightly than `0.5·10⁻ᵈ·n`, and below that line 'balanced' and 'not balanced' are the same observation. Every tolerance that remains a genuine choice is labelled `PROJECT CHOICE` where it is used.
- The method was **selected by the sign structure of the table**, not chosen by preference. RAS cannot be applied to a matrix with negative entries (CORE_012 Box 11.3, p. 345); GRAS can (UNH_18 ¶18.35, p. 558), and reduces to RAS when there are none.

---

## Assumption ledger

| ID | Assumption | Source | Confidence | Impact |
|---|---|---|---|---|
| `A-01` | Every subsector inherits the parent's input structure. That is the method's limit, not a choice: with one allocation key the weight cancels in a_ij = Z_ij / X_j, so all three subsectors necessarily share the parent's multiplier. Differentiating them would need purchasing profiles that no published source provides. | Sizes: ONS Annual Business Survey, 'Non-financial business economy, UK: Sections A to S', Table 13 Section I, released 2026-05-26, retrieved 2026-08-09. United Kingdom, SIC 56.1/56.2/56.3 published directly at 3-digit level. || Structures: NOT ESTIMATED. CORE_013 par. B12.14, p. 422 holds that for restaurants and bars specifically the separate input structures cannot be distinguished from the accounts. | strong | the subsector multipliers are the parent's, and should be quoted as such |
| `A-03` | One key splits every block, so each subsector inherits the parent's composition. ABS measured the true composition separately and it differs: value added by up to 8.9 % and purchases by up to 9.9 %, both on event catering. The sizes are right; the composition is approximate. | ONS Annual Business Survey, 'Non-financial business economy, UK: Sections A to S', Table 13 Section I, released 2026-05-26, retrieved 2026-08-09. United Kingdom, SIC 56.1/56.2/56.3 published directly at 3-digit level. | medium | up to 10 % on a subsector's value added and intermediate purchases; none on its size |
| `A-04` | Splitting output, value added and purchases by three separate ABS variables at once is INFEASIBLE and was refused by the engine, not chosen against. Catering earns 16.4 % of the sector's value added on 15.0 % of its output, and only 1.39 % of output is traded inside the sector, so nothing can absorb the difference. | engine feasibility check, src/quadrium/scenarios.py | strong | decides the configuration; see A-03 for what it costs |
| `A-02` | Balancing uses GRAS. The table carries 129 legitimate negative entries, so RAS is undefined on it. | CORE_012 Box 11.3, p. 345; UNH_18 par. 18.35, p. 558 | strong | decisive |


---

*Not every reference here is one you can follow.* `INFORME_PILOTO.md`, `OQ-D-01`, `A_core_accounting_spec.md`, `D_open_questions.md`, `OQ-B-02`, `OQ-S-01`, `MVP_0.1`, `OQ-S-05` and 1 more point into this project's own research record — its open questions, its accounting specification and its method cards. That record is **not** distributed with the software, because it quotes copyrighted manuals at length; `PROVENANCE.md` says so and why. Everything cited as `CORE_nnn`, `UNH_nn` or `SNA_25` is a published source, given by paragraph and page, and every one of those page citations is verified against the source's own text before it ships. The identities `ID-nn` are defined in the public specification.