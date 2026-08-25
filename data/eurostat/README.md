# `data/eurostat/` — tables fetched through the API, with their provenance

Everything here is **retrieved data**. Each file records the exact request that
produced it, so a result can be re-run against the same bytes.

Fetched with `quadrium.eurostat.fetch()`, which returns this record; loaded
with `load_iot()`, which never touches the network.

---

## `naio_10_cp1700_ES_2022.json`

**What it is.** Symmetric input-output table at basic prices, product by
product, Spain, 2022. JSON-stat 2.0. Carries all three valuation variants in one
response on the `stk_flow` dimension: `TOTAL`, `DOM`, `IMP`.

**Retrieved.** 2026-08-10, 240,702 bytes.
**SHA-256** `32af202af23b9075b014f1aa73a5318c168525cdacfc1b6e774132ffc2ad5e5f`

```
https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/naio_10_cp1700?format=JSON&lang=EN&geo=ES&time=2022&unit=MIO_EUR
```

**Why this file matters beyond being a fixture.** It is Eurostat's rendering of
the INE's own table, and its totals match the INE workbook to the last decimal —
intermediate 1,067,578.0, output 2,664,587.0. But its NPISH consumption of
agricultural products is **7.3**, where the INE workbook's domestic sheet has
**−4,914.3**. That is the defect of `OQ-D-04`, and Eurostat does not carry it.

**For a clean Spanish domestic table, load this rather than
`data/ine/cne_tio_22.xlsx`.** The INE workbook needs
`unbalanced="residual_column"`; this balances to 2.9e-11 with nothing derived.

**65 codes, not 64.** Eurostat serves the whole CPA hierarchy and the loader
derives the product set from which codes carry values, checking they sum to the
published `CPA_TOTAL`. Spain resolves to 65; the INE's own workbook prints 64.
The totals agree exactly, so the difference is where one classification splits a
product the other keeps whole.

**What is NOT in this file.** The method. Eurostat harmonises the format and not
the compilation — see `library/SOURCE_REGISTER.md` §6b for the measurement, and
the module docstring of `src/quadrium/eurostat.py`.

---

## `naio_10_cp1750_IT_2022.json`

**What it is.** Symmetric input-output table at basic prices, **industry by
industry**, Italy, 2022. JSON-stat 2.0, same three `stk_flow` variants.

**Retrieved.** 2026-08-10, 267,142 bytes.
**SHA-256** `0d60b40f24f240b9e4969a310c987808561ac9aa5c1acd572309aa54fc76c395`

```
https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/naio_10_cp1750?format=JSON&lang=EN&geo=IT&time=2022&unit=MIO_EUR
```

**Why Italy and not Spain.** Because Spain does not publish one. **ES, AT, DE
and FR return an empty `value` object for `naio_10_cp1750` in every year
2019–2022**; IT, NL, FI and DK publish. The project's main fixture country has
no industry × industry table at all, so this axis cannot be exercised on Spanish
data and the two fixtures here are necessarily different countries.

**Do not read the two side by side as a comparison of axes.** A `cp1750` table
is a *national* transformation of a *national* supply-use pair, and which of the
five models produced it is not in the response. An Italian ixi table beside a
Spanish pxp table differs by country, by model, and by axis at once.

**No prefix, and it costs something.** `cp1700` indexes products as `CPA_A01`;
`cp1750` indexes industries as `A01`, bare. The prefix had been doing unseen
work — it kept the value-added rows out of the sector set for free. Without it,
selecting on "carries a value" admits `P1`, `P2_ADJ` and `IMP` as though they
were branches of activity: 68 codes summing to 10,096,344.3 against a published
4,124,091.0, **2.4×**. The loader now requires a sector to appear on *both*
axes, which is what distinguishes one. See
`library/validators/run_eurostat_ixi.py`.

**One absent cell that is a real zero.** Italy's `D1` row omits one industry.
Eurostat omits structural zeros and suppressions alike, so the loader fills with
zeros and then reconciles against the row's own published total: 783,597.5
against 783,597.5. It is an industry with no compensation of employees.

**Residuals are rounding, not error.** Italy balances to 0.08 where Spain
balances to 2.9e-11 — cells are published to two decimals, and a 73-term sum is
entitled to 0.365.

---

## Earlier vintages, fetched for `OQ-B-09`

Retrieved 2026-08-10 with `fetch()`, same API pattern as above with `time`
varied. They exist for one purpose: to measure **how often a published cell
actually changes sign between years**, which `OQ-B-09` had asserted was possible
without ever measuring it.

| file | bytes | SHA-256 |
|---|---|---|
| `naio_10_cp1620_AT_2018.json` | 163,651 | `d0073f51c8bf2409…` |
| `naio_10_cp1620_AT_2020.json` | 163,663 | `d5a9a54c4cab38d7…` |
| `naio_10_cp1630_AT_2018.json` | 165,652 | `608434353d82eeef…` |
| `naio_10_cp1630_AT_2020.json` | 165,537 | `4f14f85186268007…` |
| `naio_10_cp1700_ES_2019.json` | 97,239 | `bca2875bfc7ec1bf…` |
| `naio_10_cp1700_ES_2020.json` | 241,639 | `ca77e9f1b6796774…` |
| `naio_10_cp1700_ES_2021.json` | 241,224 | `cda5a90f1dbb6a69…` |

**What they showed.** Three different answers, two orders of magnitude apart:
the trade-and-transport margins matrix never flips a sign in four years (the
sign there is structural); taxes less subsidies flip 0.24–0.78 % of cells; and
**changes in inventories flip 18–42 % of products, year on year**. See
`library/validators/run_sign_change.py`.

`naio_10_cp1700_ES_2019` is much smaller than the others (6,038 values against
17–18,000): Spain publishes less for that year. Nothing here depends on the
missing part, but do not assume a vintage is complete because its neighbour is.

---

## Supply tables for the diagonality test (`OQ-C-04`)

Retrieved 2026-08-11. CORE_008 Box 5.1, p. 144 claims France redefines until its
supply table is diagonal; these are what that claim was tested against.

| file | bytes | SHA-256 |
|---|---|---|
| `naio_10_cp15_FR_2022.json` | 126,962 | `5272c4b9179ad1fc…` |
| `naio_10_cp15_NL_2022.json` | 70,466 | `296fa16efb645e6e…` |
| `naio_10_cp15_DK_2022.json` | 131,648 | `6de94fc082f76e14…` |
| `naio_10_cp15_NO_2022.json` | 69,873 | `dcd6f227ecf9bf22…` |

France measures **98.4 % diagonal** against a field of 84.6–93.6 %. The claim
holds. Box 5.1's remarks about Denmark, Norway and the Netherlands do **not**
reproduce — see `library/validators/run_supply_compilation.py`, which keeps that
negative finding as a check so it cannot quietly disappear.

---

## Supply and use pairs, and the two countries that publish two levels

Retrieved 2026-08-11 for the France diagonality test (`OQ-C-04`) and the
transformation-model measurement (`OQ-T-03`).

| file | bytes | SHA-256 |
|---|---|---|
| `naio_10_cp15_FR_2022.json` | 126,962 | `5272c4b9179ad1fc…` |
| `naio_10_cp15_NL_2022.json` | 70,466 | `296fa16efb645e6e…` |
| `naio_10_cp15_DK_2022.json` | 131,648 | `6de94fc082f76e14…` |
| `naio_10_cp15_NO_2022.json` | 69,873 | `dcd6f227ecf9bf22…` |
| `naio_10_cp16_ES_2022.json` | 92,761 | `6e23e4d5d4d3bc4c…` |
| `naio_10_cp16_FR_2022.json` | 172,555 | `8a8d121fefb8fb2b…` |
| `naio_10_cp16_NL_2022.json` | 85,158 | `eb6c230f378311a4…` |

**`naio_10_cp15_FR` and `naio_10_cp15_DK` populate BOTH levels of the CPA
hierarchy** — `CPA_B` beside `CPA_B05`…`B09`, `CPA_C10-12` beside `C10`, `C11`,
`C12`; 39 containments each. France's supply table sums to 7,939,582.2 against a
published 6,121,102.4, thirty per cent over, until the aggregates are dropped.
They are the only two of the six here that do this, and finding them corrected a
claim in `library/SOURCE_REGISTER.md` §3 that no country served both levels —
which was an artefact of a filter that could not read prefixed codes. See
`library/validators/run_hierarchy_levels.py`.

---

## `sbs_i561_i562_i563_turnover_2018_2020.json` and `..._employment_2018_2020.json`

**What they are.** Structural Business Statistics, dataset `sbs_na_1a_se_r2`
("Annual detailed enterprise statistics for services"), turnover (`V12110`) and
persons employed (`V16110`), for the three NACE Rev. 2 groups inside division 56
— `I561` restaurants and mobile food service, `I562` event catering and other
food service, `I563` beverage serving — eleven EU countries (BE, CZ, DE, ES,
FR, IT, NL, AT, PL, PT, SE), 2018–2020.

**Retrieved.** 2026-08-13, via the Eurostat REST API,
`https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sbs_na_1a_se_r2`,
querying `nace_r2=I561,I562,I563`, `indic_sb=V12110` or `V16110`, the eleven
`geo` codes above, `sinceTimePeriod=2018`.

**SHA-256** turnover `a1f291cf623f8a6e2b1922c23d53a39c5311e62fa8e870e02c816e950fc7613b`;
employment `936474397f5d9b8edf5e3d746c88c0f240e66734fdeedf88c1d66e9190a5d38c`.

**Why 2020 is the last year.** `sbs_na_1a_se_r2` is capped at 2005–2020 by
Eurostat's own design — a discontinued vintage of the series, not a live feed
that stopped responding. That ceiling happens to include the one year this data
was fetched for: 2019→2020, the pandemic break.

**Why it was fetched — `OQ-B-14`.** A third and fourth test of the entry's
finding (levels volatile, shares steady, breaks catastrophic — measured on
Spain, then partly on the UK), across eleven countries at once instead of one
more at a time. The result **refines rather than repeats** the earlier finding:
see `run_key_vintage_eurostat.py` and the entry.

---

## `NACE2_to_NACE21_correspondence_v1.06.xlsx`

**What it is.** Eurostat's own official correspondence table between NACE
Rev. 2 and NACE Rev. 2.1, version 1.06 (2026-07-21), 1,600 rows: for every
NACE Rev. 2 position, which Rev. 2.1 position(s) it maps to, at what type of
correspondence (1:1, 1:n, n:1, n:m), and the shared content where the mapping
is not clean.

**Retrieved.** 2026-08-13, from Eurostat's public working-group repository on
CIRCABC — `Standards Working Group` → `Classifications` → `NACE and CPA` →
`NACE review` → `NACE Rev. 2.1 explanatory notes and correspondence tables` →
`NACE Rev. 2.1 correspondence tables` → `... V.1.06`, a folder explicitly
marked "Esta carpeta es pública" (this folder is public), accessible as an
anonymous guest. Downloaded via CIRCABC's own REST endpoint,
`https://circabc.europa.eu/rest/download/438307b0-a515-41b8-b2ec-fc260fa553ea`
— found by inspecting the page's element references after the shortlink
`CORE_030`'s introductory guidelines cite (`europa.eu/!f6H9nX`) resolved to
this folder rather than a direct file.

**SHA-256** `ef2851a4de1eab213fe03e1748af09344a2351670256dfa1a37c7cf20352cd2b`

**Why it was fetched — `OQ-S-01`.** Closes the caveat `run_uk_classification.py`
had carried since v1.44: NACE's own detailed structure, read from `CORE_030`,
is Rev. 2.1, one revision newer than the Rev. 2 the project's UK and Spanish
fixtures use. This table gives the exact difference per code rather than a
general caveat: `56.1`, `56.2`, `56.3` and `69.1` map 1:1 with no content lost;
`56.4` traces entirely to Rev. 2's `79.9`/`79.90` (not a split of the existing
three groups, closing the division-56 exhaustiveness question outright); `35.1`
genuinely splits into Rev. 2.1's `35.1` and a new `35.4`, so `D351`'s existence
stands but its boundary does not carry over unchanged. See
`run_uk_classification.py` and the entry.


---

## The six-pack — `naio_10_pyp16`, and the two years beside it

**Fetched 2026-08-13** with `quadrium.eurostat.fetch()`, for the four
CORE_012 diagnostics that had never had data: `ID-16`, `D3`, `D5` and `D2d`.

**`naio_10_pyp16` is "Use table at purchasers' prices (previous years
prices)"** — the middle value of the six-pack (CORE_012 Figure 11.2, p. 325),
`v[t, p_{t-1}]`. With `naio_10_cp16` for `t` and for `t-1` the triple is
complete:

    v[t, p_t]        naio_10_cp16   2022
    v[t, p_{t-1}]    naio_10_pyp16  2022
    v[t-1, p_{t-1}]  naio_10_cp16   2021

| file | bytes | SHA-256 | size |
|---|---:|---|---|
| `naio_10_pyp16_AT_2022.json` | 183,706 | `7b4c93384218af09…` | 5,644 values |
| `naio_10_cp16_AT_2021.json` | 189,592 | `8185481c68e7e8ac…` | 6,040 values |
| `naio_10_pyp16_ES_2022.json` | 85,196 | `2146be1599f6de42…` | 5,652 values |
| `naio_10_cp16_ES_2021.json` | 92,410 | `a8903c6b29fc0533…` | 5,771 values |

**Austria and Spain**, because both publish `pyp16` and both already had a
current-price use table here.

⚠ **`LE` in these tables is "Closing balance sheet", not labour input.** A first
pass at `D4` (labour productivity) took it for employment and flagged 48 Spanish
industries at up to 284 %. The row is a balance sheet; the flags were an
artefact of the join. `D4` stays NOT APPLICABLE and needs a labour dataset and a
deliberate decision about the statistical unit — see `run_six_pack.py`.

⚠ **The Laspeyres/Paasche precondition cannot be checked from these files.**
CORE_012 ¶11.17, p. 323 holds the volume-term identities only under that
pairing, and nothing in the data states which pairing Eurostat used.


---

## Labour input — `nama_10_a64_e`, for `D4`

**Fetched 2026-08-13.** `D4` (labour productivity, CORE_012 ¶11.20, p. 323) had
reported NOT APPLICABLE since v1.1 because **no Eurostat supply-use table
carries labour input**. This is where it lives: *Employment by detailed industry
(NACE Rev. 2), national accounts*, `na_item=EMP_DC` (domestic concept), in both
`THS_HW` (thousand hours worked) and `THS_PER` (thousand persons).

National-accounts employment against national-accounts GVA is the same framework
on both sides, which is what the source means by "calculated on the same basis".

| file | bytes | SHA-256 |
|---|---:|---|
| `nama_10_a64_e_AT_2021_THS_HW.json` | 10,958 | `886f7987366f…` |
| `nama_10_a64_e_AT_2021_THS_PER.json` | 10,944 | `4ea4c9213e49…` |
| `nama_10_a64_e_AT_2022_THS_HW.json` | 10,962 | `9322ba9c8915…` |
| `nama_10_a64_e_AT_2022_THS_PER.json` | 10,946 | `e1998440135e…` |
| `nama_10_a64_e_ES_2021_THS_HW.json` | 11,027 | `32406b1f0527…` |
| `nama_10_a64_e_ES_2021_THS_PER.json` | 11,017 | `68ce86785f7e…` |
| `nama_10_a64_e_ES_2022_THS_HW.json` | 11,030 | `89edb73d9057…` |
| `nama_10_a64_e_ES_2022_THS_PER.json` | 11,018 | `a1def28649b9…` |

**The NACE codes differ from the SUT's and the mapping is stated, not assumed.**
The SUT writes `C31_32`, `J59_60`, `M74_75`; this cube writes `C31_C32`,
`J59_J60`, `M74_M75`. `U` is `U99`. **`L68B` is DERIVED as `L68 − L68A`** and
labelled as derived. 63 of 65 industries match; `L68A` (owner-occupiers'
housing, zero labour by construction) and `U` are dropped rather than guessed.

⚠ **This is the dataset the `LE` row was mistaken for.** `LE` in
`naio_10_cp16` is *Closing balance sheet*; a pass that took it for employment
flagged 48 Spanish industries at up to 284 %, plausibly and wrongly. See
`run_labour_productivity.py`.

---

## `naio_10_cp1700_PT_2020.json` — the first source that rounds to two decimals

**What it is.** Portugal's symmetric input-output table for 2020, product by
product, at basic prices, in millions of euros at current prices. 18,098
values, 65 products after aggregates are dropped.

**Source.** Eurostat, `naio_10_cp1700`.

```
https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/naio_10_cp1700?format=JSON&lang=EN&geo=PT&time=2020&unit=MIO_EUR
```

**Retrieved.** 2026-08-25, 248,255 bytes.
**SHA-256** `6a0134601ddaa753d120e6918269cd2ac266b173efe3d93f9dbbebd1724bf926`

**Why it is here, and it is not for Portugal.** It was fetched as the first
blind test of `table_kind: eurostat` — a country the project had never touched,
chosen for no reason but that. It printed to **two decimals** where Spain prints
to one, and that one difference broke four consecutive gates, each of which had
passed every fixture the project held until then:

| Gate | Refused Portugal at | What the source's own rounding permits |
|---|---|---|
| `validate_original` balance | 2.6e-05 | 0.37 |
| GRAS margin consistency | 1.1e-05, then 0.02 | 1.3 |
| `check_margins_attained` | 0.033 | 0.12 |
| `check_reaggregation` | 1e-06 % | 0.035 in 350,000 |

Every one of those tolerances was either a flat project constant or a figure
inferred from numbers the engine had computed rather than read. `OQ-B-02`
closed at v1.57 establishing that the bound must come from the publisher's own
precision; four gates had never adopted it, and nothing showed because every
fixture the project held either printed one decimal or closed exactly.

**Spain 2020 fails the same first gate**, on a max deviation of 0.1 against a
tolerance of 1.5e-04 — so this was never a Portuguese problem.

`run_eurostat_config.py` holds the whole chain.

---

## `naio_10_cp1610_{ES,AT}_2022.json` — use at basic prices, split DOM / IMP

**What they are.** The use table at **basic prices**, with a `stk_flow`
dimension of `TOTAL` / `DOM` / `IMP` — what each industry and each final-demand
category buys, separated into what was produced at home and what was imported.

**Source.** Eurostat, `naio_10_cp1610`.

```
https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/naio_10_cp1610?format=JSON&lang=EN&geo=ES&time=2022&unit=MIO_EUR
```

**Retrieved.** 2026-08-25.
`ES` 233,977 bytes, SHA-256 `31ddd6d35db5e27688268810cf7bd35aa0709a7b16e71b777a5b2c13b0e21af8`
`AT` 538,767 bytes, SHA-256 `73db41d501896c3b4ed6ebd57f0057e3eac3a1d08dc0c0d1af69e8df4eb614cd`

**Why they are here.** They are what makes a SUT→IOT transformation possible.
`naio_10_cp16` is at purchasers' prices and undivided; the four models of
CORE_013 need the domestic and imported halves separately, because in a Leontief
system domestic demand pulls domestic output and imported demand leaves the
economy. **Deriving that split would impose import proportionality** — every
user of a product importing the same share of it — which is an economic
hypothesis rather than bookkeeping. Eurostat publishes it, so it is read.

Both identities were verified on load, and they close:

| | Spain (1 decimal) | Austria (2 decimals) |
|---|---|---|
| `U_dom.rows + Y_dom.rows = q` | 0.0000 | 0.10 |
| `U_imp.rows + Y_imp.rows = imports` | 0.0000 | 0.06 |
| `U.cols + taxes + VA.cols = g` | 0.0000 | 0.11 |

Austria's residues sit against a rounding floor of 0.34 for a 68-term sum.

`run_sut_to_iot.py` holds the whole path.

---

## What `--find` reports, and one country that does not load

`catalogue.available_years()` asks Eurostat which years a country populates,
per dataset, and caches the answer beside the data as
`_availability_<GEO>.json`.

**The years come from the VALUE map, not from the `time` dimension.** That
dimension lists the years a *dataset* spans, and reading it directly reported 35
years to 2024 for Germany — so `--find` printed a configuration naming 2024,
which fails, because Eurostat answers 200 with an empty result for a year a
country does not publish. It is the same "listed is not available" trap as
`CPA_I55` in the Spanish symmetric table, in a third place.

**The filter has to name a category that exists on the axis it names.** The
`cp1700` probe asked `prd_use=CPA_TOTAL`, and `CPA_TOTAL` is the total on the
*available* axis — the use axis's total is `TU`. Eurostat answers 200 with an
empty result either way, so the probe reported that **no country publishes a
symmetric product-by-product table**, and a claim that Germany had no route to
one was written into four documents before a sweep of 28 countries showed every
single one reading zero. Spain publishes nine years and Germany thirteen.

Measured 2026-08-25 across 28 countries, once the probe asked properly. Every
one publishes supply and use; what differs is the rest:

| | `cp1700` | `cp1750` | `cp1610` | newest transformable pair |
|---|---|---|---|---|
| **DE** | 13 yr | none | **none** | **none** |
| **ES** | 9 yr | none | 13 yr | 2022 |
| **DK** | none | 18 yr | 18 yr | 2022 |
| **CZ** | 9 yr | 9 yr | 34 yr | 2024 |
| **BG** | 1 yr | none | 1 yr | 2010 |

**Germany is the one country whose pair cannot be transformed** — it publishes
no use table at basic prices, so the domestic/imported split would have to be
assumed. Its symmetric table is reachable.

**Belgium's 2022 pair was refused until 2026-08-26**, on the industry column
identity: intermediate consumption plus value added missing output by **0.80**
against the **0.46** its precision was said to allow. The refusal was wrong, and
the bound was the reason. Belgium publishes to **one** decimal — 2,553
one-decimal figures, 274 whole numbers and **two** cells with a second decimal,
out of 2,829 — and `printed_decimals` was asking which precision *represents*
99.95 % of the values, which those two cells decide. One decimal over 92 summed
cells cannot distinguish anything below 4.6. The pair loads.

---

## `naio_10_cp15/cp16/cp1610_BE_2022.json` — the pair that was refused

**What they are.** Belgium's 2022 supply-use system, 89 products by 89
industries. Retrieved 2026-08-25; URLs, byte counts and SHA-256 in the
`.provenance` sidecar beside each file.

**Why they are here, and it is not for Belgium.** They are the fixture for
`run_sut_closure.py`, and they carry three things no other pair here does.

**One.** The closing identity fails, and fails in exactly two cells:

| industry | residue |
|---|---|
| `L68A` imputed rents of owner-occupied dwellings | **+0.800** |
| `L68B` other real estate services | **−0.800** |
| the other 87 | 0.000 |

Sum exactly 0.000. A boundary between two halves of one sector, not a table
that fails to add up — and `L68A` is the same sector that produces all 19
negative cells in the UK analytical table's Leontief inverse, and the subject
of `OQ-D-02`.

It is **inside** what one decimal allows, so the pair loads and the residue is
reported rather than refused. That is not a relaxation: 0.8 across 92
one-decimal cells is what one decimal cannot distinguish, and the finding —
where the residue sits and that it cancels — survives intact. Where a residue
is genuinely beyond a source's precision and still cancels this way,
`sut_unbalanced: cancelling` admits that shape and only that shape, and records
what it admitted. Nothing in this folder needs it now; `run_sut_closure.py`
exercises it on a fixture built to.

**Two.** `B06`, crude petroleum and natural gas, has **zero domestic output and
20,342 of imports**, of which 20,238 goes to `C19`, refining. Belgium imports
all its crude and refines it. It is the first wholly imported product in this
data folder, and it found a real defect: `to_iot` dropped such products from the
product axis — correctly, since no domestic industry makes them and every model
divides by that output — and dropped their imported use with them, taking
20,210 out of C19's column.

**Three.** It is the first pair here that is rectangular *after* masking, 85
products against 84 industries, so models A and C refuse it and B and D do not.

Austria, Spain, France and the Netherlands were the control that made Belgium's
0.8 look like a failure: they pass the same check exactly. What separates them
is that Austria prints two decimals and Belgium one, which is the thing the
bound is supposed to notice and did not.

---

## Five tables the engine will not load, kept as fixtures

Retrieved 2026-08-25 in a sweep of every EU country plus Norway, most recent
year each. **Eighteen of twenty-eight load and are sound** — spectral radius
0.33 to 0.65, row residues at the rounding scale. These five do not, for four
distinct reasons, and each refusal is correct. The live count for both routes
is in `_verdicts.json`, which `run_docs_current.py` checks `library/INDEX.md`
against; a count in prose beside a count in a file is a count that will
disagree, and these two already had.

| file | why |
|---|---|
| `naio_10_cp1700_IE_2020.json` | **50.46 % short**: 51 codes carry values and the published total counts 104 |
| `naio_10_cp1750_NO_2023.json` | **1.25 % short**, same shape |
| `naio_10_cp1700_LU_2022.json` | **no `P1` output vector published at all** |
| `naio_10_cp1700_HR_2021.json` | final demand has holes at **every** level — 29 products with no capital formation, 12 with no exports |
| `naio_10_cp1700_SE_2023.json` | its own output vector disagrees with its own total-use column for **61 of 65 products** |

**All eight refusals are limits of the data, not of the engine**, and that was
established rather than assumed — three of the four causes looked like loader
gaps until each was traced. Sweden is the clearest: `G46`, wholesale trade, is
published with an output of 67,091.2 and a total use of 67,481.6, 390.5 apart.
Spain and Portugal agree to 0.00 on every product, which is the control that
makes the number readable: without it, 390.5 could as easily have been this
engine's arithmetic. No tolerance reconciles two figures a source publishes for
the same quantity.

**Ireland's 2020 table accounts for barely half of the total it prints.** That
is what a country whose sectors are dominated by a few firms looks like once
confidentiality has been applied — and loading it would understate that economy
by 362,158 without saying so.

Until this sweep all five refused with the same sentence: *"the set still mixes
levels or still carries a row that is not a sector"* — one hypothesis stated as
a conclusion, and wrong five times out of five. A set that mixes levels
OVERSHOOTS by a factor; Italy's was 2.4×, which is what that branch was written
for. An incomplete one UNDERSHOOTS. The message now measures which and says so.

`run_eu_sweep.py`.


---

## `naio_10_cp15/cp16/cp1610_CZ_2024.json` — the trio that found a defect

Retrieved 2026-08-25. Czechia's 2024 supply-use system, 89 × 89, the newest
transformable pair Eurostat carries for anyone.

It is here because it refused to load, and the reason was ours. The final-demand
columns were chosen from `cp16` and then read out of `cp1610` by the same names,
and **the two files do not agree on which components they publish**: Czechia
gives exports as `P6`, not as the `P6_B0`/`P6_D0` split that `cp16` carries. The
missing names read as zero, and the domestic rebuild came out **50,837 short**.
Estonia was 2,267 short for the same reason.

Columns are now chosen to satisfy every file that will be read with them.
Czechia loads at 89 × 89 and transforms into 87 sectors with a column residue of
0.111.

Across all 28 countries, **13 supply-use pairs load and transform**. The other
15 are limits of the data — nine incomplete, two with final demand too sparse to
assemble, Sweden's own output/total-use disagreement, Bulgaria 3.24 outside its
bound, Belgium's closing identity, and Germany, which publishes no basic-price
use table.

---

## `naio_10_cp15/cp16/cp1610_BG_2010.json` — two files that disagree

Retrieved 2026-08-25. Bulgaria's 2010 supply-use system, the only year it
publishes a use table at basic prices.

It was the last refusal across both sweeps with no explanation: a cross-check
out by **3.24** against a bound of 0.365 — nine times the bound and trivial in
absolute terms, which is exactly the shape of thing that gets waved through.

It is the data. For `R90-92`, arts and entertainment:

| file | figure |
|---|---|
| `naio_10_cp15` | domestic product output **793.37** |
| `naio_10_cp1610` | domestic total use **790.11** |

Two figures the same source publishes, for the same country, year and product,
**3.26 apart**. Every other Bulgarian product agrees to 0.01, and Spain agrees
to **0.0000** on all 65 of its own — which is the control that makes 3.26
readable rather than suspicious of this engine. No tolerance reconciles two
published numbers.

With this, **every refusal across both sweeps is explained and every one is the
data.** `run_eu_sweep.py`.

---

## Five files kept because they are the years that WORK

`naio_10_cp1700_FR_2021.json`, `naio_10_cp1700_SK_2015.json` and Croatia's 2010
trio (`cp15`, `cp16`, `cp1610`). Retrieved 2026-08-26; URL, bytes and SHA-256
in the `.provenance` sidecar beside each.

The sweep of 2026-08-25 checked each country's **newest** table and recorded a
verdict, with the caveat — in the record itself — that a verdict is about the
year checked and not a prediction about the others. Tried on three other years
per refusing country on 2026-08-26:

| route | refuses at the newest year | of which some other year loads |
|---|---:|---|
| symmetric | 10 | **3** — FR, HR, SK |
| supply-use pair | 14 | **2** — HR, PT |

France publishes thirteen years of symmetric tables. Its 2022 is refused for
sparse final demand and 2010, 2016 and 2021 all load — so "France refuses" was
a statement about one file. Slovakia's 2020 publishes no output vector and its
2010 and 2015 are fine. Croatia refuses at 2021 on both routes and loads at 2010
on both.

The reach is **21 of 28 countries by the symmetric route and 16 of 28 by the
pair**, at some year, provided the user is told which — which `--find` now is.

The other seven and twelve refuse in every year tried. Ireland is 50 % short of
its own printed total in 2010, 2011, 2015 and 2020 alike. That is structural,
and it is now measured rather than assumed.

About ninety files were fetched for this and are not kept. These five are, because
they are the evidence for the claim, and a claim whose evidence lives in a
temporary directory is a claim on trust. `library/validators/run_year_axis.py`
re-derives it from them.

### And the defect the probe found

Malta's 2010 supply table was refused with *"the 65 populated products sum to
27,583.1 against a published total supply of 27,583.0: the set mixes levels of
the CPA hierarchy and would double count."* **0.1 on 27,583.**

The comparison was `1e-6 * published` — relative, and defended in a comment as
measured, because Austria 2022 lands 0.03 from its own printed total and an
absolute `1e-3` would refuse it. But rounding error grows with the number of
terms and the precision they are printed to, not with the size of the economy:
Austria survived that rule by being fifteen times larger than Malta. Both of
`load_sut`'s tiling checks now derive the bound the way the rest of the module
does, and both say whether the set OVERSHOOTS (mixes levels) or falls SHORT
(incomplete) instead of asserting the first.

Malta is still refused, on the industry axis, 20.08 % short — correctly, and now
for the reason that is true.

---

## `naio_10_cp15/cp1610_ES_2021.json` — the year before, so a projection can be scored

Retrieved 2026-08-26; URL, bytes and SHA-256 in the `.provenance` sidecars.
`naio_10_cp16_ES_2021.json` was already here.

With these two, Spain has **two consecutive projectable pairs on identical
axes**, which is what a back-test needs: project 2021 onto 2022's published
value added, final use, taxes and imports, then compare cell by cell with the
2022 the office actually published.

Until this was run, the projection had been checked only against UNH_18
Box 18.7's printed iterations — which tests that the code implements the
chapter, not that the chapter's answer is good.

**Two defects fell out immediately.** The iteration ceiling was 200, taken from
a fixture that converges in three; real pairs need 356 (ES), 561 and 1,617
(AT), 1,703 (NL) and 2,835 (IT). And the projected table's own note said
"Converged in N iteration(s)" whether it had converged or not — at the 200
ceiling Austria was still 9.4 % from its target and the note reported success.

**And the measurement, which is not flattering.** Scored against the published
2022, on domestic intermediate use:

| | levels | coefficients (per 1000) |
|---|---:|---:|
| projected | 34.0 % | 2.117 |
| base year unchanged | 29.4 % | 2.029 |
| base year scaled | 28.8 % | 2.029 |

The projection is further from the published table than the base year left
alone — and the same holds for Austria, Italy and the Netherlands, and on
technical coefficients, which have no scale in them. It is not the project's
own damping choice either: sweeping `ε` from 0.3 to 1.0 moves the iteration
count and not the answer.

That is not a verdict on the method. The projected pair **is consistent with
2022's aggregates and the base year is not** — Spain's 2021 value added is
10.8 % below 2022's — so anyone needing a table that adds up to known later-year
totals cannot use the base year at all. The consistency is the product; this is
its price, and now it is a number.

`library/validators/run_projection_backtest.py`.
