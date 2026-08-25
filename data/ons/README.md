# `data/ons/` — auxiliary data, with its provenance

Everything in this folder is **retrieved data, not derived data**. Each file
records where it came from, when, and by what query, so that any number the
engine produces can be traced back to a request someone else could repeat.

---

## `NSO_UK_03_FISIM_UK_revisited_2017.pdf`

**What it is.** "Financial intermediation services indirectly measured
(FISIM) in the UK revisited", ONS, 2017-04-24, 51 pages. The article that
documents how FISIM on loans secured on dwellings is allocated to
intermediate consumption by households as owner-occupiers — the exact
economic content of the project's own fixture cell `K64 → L68A` (`OQ-D-02`).

**Source.** ONS methodology article,
`https://www.ons.gov.uk/economy/grossdomesticproductgdp/articles/financialintermediationservicesindirectlymeasuredfisimintheukrevisited/2017-04-24`,
PDF retrieved from the article's own `/pdf` link — an official statistical
office publication, downloaded under the project's standing authorization for
official-source acquisitions (`CLAUDE.md` §"Standing authorizations").

**Retrieved.** 2026-08-13.

**SHA-256** `c546ebac9c52e74df502a25a8fe3e63e647788740a383e58e19b261e43dec5e0`

**Access.** Open, unauthenticated. Crown copyright, ONS standard open licence
for statistical publications.

**Extraction.** `library/extracted/NSO_UK_03_FISIM_UK_revisited_2017.txt`,
107,100 characters across 51 pages. Figures (charts) did not extract as data —
only the surrounding prose is usable; treat as **QUOTE_ONLY**, no paragraph
numbering in the source.

**Why it is here — `OQ-D-02`.** The entry's own v1.20 note names "FISIM
allocation to owner-occupied dwellings" as the one remaining place to look for
an explanation of the project's single unexplained negative cell. This is that
document, read directly rather than named and left unread.

---

## `NSO_UK_04_ONS_supply_use_tables_BB25.xlsx` — the second fixture, and the
## document that closed `OQ-D-02`

*Input-output supply and use tables*, Blue Book 2025 edition, ONS. Supply,
intermediate consumption, final demand, HHFCE and GFCF for **every year from
1997 to 2023** — 135 sheets.

**URL.** `https://www.ons.gov.uk/file?uri=/economy/nationalaccounts/supplyandusetables/datasets/inputoutputsupplyandusetables/current/supublicationtablesbb25.xlsx`

**Retrieved.** 2026-08-13, 3,037,546 bytes.
**SHA-256** `e86439f8a5a3371998c838e8816c9b05af824b830f42b44360f031a720d8e96b`

**Acquired by hand, and that is the point.** `quadrium.acquire` (`M-069`)
refuses `ons.gov.uk`: the site answers **403 to a scripted fetch of
`robots.txt`**, which by convention means disallowed, where a browser gets 404 —
no robots file at all. The engine cannot tell a prohibition from bot detection,
so it stops, and this is exactly the "technical friction around content already
confirmed open" that `CLAUDE.md`'s standing authorisation leaves to a person.
The first document the new capability could not fetch was the one that mattered
most.

**Two things it gives the project.**

1. **`OQ-D-02`, closed.** The unexplained negative — financial services into
   owner-occupiers' housing — is **in the ONS's own published supply-use table**
   at **−20,814**, so it does not come from the transformation, and that is now
   OBSERVED rather than inferred. And the same cell for **27 consecutive years**
   shows it is not a convention: positive every year from 1997 to 2022, crossing
   zero **once**, in 2023.
2. **The real supply-use pair the project has wanted since v1.0.** Six identities
   have been reported NOT APPLICABLE for want of one (`OQ-D-03`,
   `run_uk_diagnostics.py`); two thirds of the CORE_012 diagnostic battery needs
   a genuine SUT and a second year. This has twenty-seven.

---

## `iot/` — the analytical tables, six editions

**What they are.** The UK Input-Output Analytical Tables, **product by
product**, domestic use, basic prices, GBP million. The project's own fixture
`UK_IOAT_2023_domestic_ixi.xlsx` is the industry-by-industry table for the same
2023 edition, and the two agree on total output to the pound: 4,819,806.

**Source.** ONS, *UK input-output analytical tables: product by product*.
Retrieved 2026-08-25; every file's URL, byte count and SHA-256 are in
`iot/_provenance.json` beside them.

```
https://www.ons.gov.uk/file?uri=/economy/nationalaccounts/supplyandusetables/datasets/ukinputoutputanalyticaltablesdetailed/2023/iot2023product.xlsx
```

| file | reference year | products | output |
|---|---:|---:|---:|
| `iot_pxp_1719.xlsx` | 2019 | 105 | 3,824,433 |
| `iot_pxp_2020.xlsx` | 2020 | 105 | 3,609,108 |
| `iot_pxp_2021.xlsx` | 2021 | 105 | **refused, see below** |
| `iot_pxp_2022.xlsx` | 2022 | 105 | 4,548,357 |
| `iot_pxp_2022revised.xlsx` | 2022 | 104 | 4,610,060 |
| `iot_pxp_2023.xlsx` | 2023 | 104 | 4,819,806 |

### Two things that are not constant across editions

**The classification.** The 2023 edition merged `CPA_C254` (weapons and
ammunition) into `CPA_C25`, so 2016–2022 are 105 × 105 and 2023 is 104 × 104.
The 2022 *revised* tables adopt the merged classification too, which is how the
same reference year comes at two different sizes.

**The axis.** The product-by-product workbook labels its axis `CPA` /
`Product`; the industry-by-industry one says `SIC` / `Industry`, with no prefix
on the codes at all.

`load_uk_analytical_iot` navigated by fixed row and column numbers until
2026-08-25, so it read one of the nine published editions correctly and the
other eight one line out of true — and then reported the result as the *data*
failing:

```
iot_pxp_2022.xlsx does not balance and will not be loaded.
  worst row: CPA_F41, F42 & F43 off by 406,662.169 (Construction)
```

That file balances exactly. Both axes are now found by the `_T` total the sheet
prints at the end of each block, every primary-input row by the label beside it,
and the row codes are required to equal the column codes before a number is
read. The derivation is checked against the ONS's own printed `_T`, `TU` and
`GVA` lines, so a block located one line out fails as the loader's mistake and
not as an accusation against the office.

### The precision of these files, which is two precisions

The intermediate block is **full precision** — under 0.6 % of its cells are
whole numbers — and **final demand, output and total use are every one of them
integers**, in all six editions. The interior is unrounded; the margins are
rounded to whole millions.

That matters because the detectable floor of the row identity is set by the
rounded terms, not the unrounded ones: nine final-demand integers and one
output integer at half a unit each is **5.0**. Pooling all the blocks gives
99.1 % unrounded, `printed_decimals` answers `None`, and the identity is judged
at float64 accumulation — 2e-07, twenty-five million times too tight. See
`OQ-B-02` and `precision.assertable_tolerance_mixed`.

It went unnoticed because the ONS's rounded margins happen to be mutually
consistent in four editions of six.

### `iot_pxp_2021.xlsx` — refused, and it is the data

83 of 105 rows disagree with their own printed total, mostly by ±1 to ±3, and
`CPA_D351` (electricity, transmission and distribution) by **259**: total use
89,244 against output 88,985. 259 rounding units is not rounding. The 2022
revised tables, by contrast, are out by one unit on `CPA_G46` and one on
`CPA_G47`, cancelling — one rounding unit doing what rounding units do — and
they load.

### What a revision costs

The ONS published 2022 twice, a year apart. Output rises 1.36 % and the **output
multipliers move by a median of 2.0 %, a mean of 2.4 % and up to 14.8 %**; 70 of
the 103 shared products move by more than 1 %. Basic pharmaceutical products go
from 1.7166 to 1.4625. Both editions remain productive — spectral radius 0.569
and 0.574 — so the revision moves the answer without breaking the framework.

That is the number to hold next to any disaggregation this engine produces.

Locked in by `library/validators/run_uk_editions.py`.
