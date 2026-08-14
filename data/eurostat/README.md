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
