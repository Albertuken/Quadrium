# `data/mrio/` — regional tables with both sides of interregional trade

Everything in this folder is **retrieved data, not derived data**, taken from one
open archive and recorded with its URL, byte count and hash so any number the
engine produces from it can be traced back to something someone else could
repeat.

It is here for one reason. Every measurement this project had about
regionalisation rested on a single region — Catalonia — and a measurement from
one case is an anecdote with a decimal point. These are the other cases.

---

## The archive

**What it is.** The technical-validation set of *European multi regional input
output data for 2008–2018*, which publishes MRIO tables for 272 European NUTS-2
regions. The validation set is the part that is **not** estimated: survey or
government regional tables that the authors checked their estimates against.

**Source.** Huang, S. et al., *European multi regional input output data for
2008–2018*, **Scientific Data 10** (2023). Deposited on Zenodo, record
[7875024](https://zenodo.org/records/7875024).

**Reuse terms.** Data **CC BY 4.0**; the code inside the archive is **MIT** (see
`LICENSE`). Both permit redistribution with attribution, which is why this folder
can exist in a public repository when `data/idescat/` cannot.

**Retrieved.** 2026-09-01, 317,055,869 bytes.
**SHA-256** `9db930f2438f27179b0f4d99a7f54b6d45b134b964a98234326c6c4925201e27`

**The request, verbatim, so it can be re-run:**

```
https://zenodo.org/records/7875024/files/MRIO.zip?download=1
```

A `HEAD` on that URL returns 504; a ranged `GET` works. `_provenance.json`
records the method used.

---

## What is here, and what is not

**Here:** `truth/`, the validation set — 844 kB, the publishers' own bytes.

**Not here:** the eleven `MRIO_YYYY_272regions.xlsx` workbooks, 33 MB each. They
are re-obtainable from the URL above and the project gitignores them in both
repositories. `run_mrio_axis_scale.py`, which uses the 2018 one, runs privately
for that reason and is not in this repository — a validator that could not run
was removed rather than left to pass vacuously.

---

## `truth/Austria/AT11.csv` … `AT34.csv`

**What it is.** Nine **survey-based** regional input-output tables, one per
Austrian NUTS-2 region, 56 sectors square, with six final-demand columns and,
below the sectors, labour by occupation, capital, land, taxes and two import
rows.

**Source.** Rokicki, Bartlomiej, et al., *Survey-based versus algorithm-based
multi-regional input–output tables within the CGE framework — the case of
Austria*, **Economic Systems Research 33(4)**: 470–491 (2021), as distributed in
the archive above.

**Why these and not others.** They carry the shape Catalonia has and almost
nothing else does: **both sides of interregional trade, by sector**. Column
`61 EXPROC` is what the region sells to the rest of Austria; row `71 ROCimp` is
what it buys. Without both sides the assumptions of a regionalisation method
cannot be scored.

**Two things a reader should know before using them**, both checked in
`run_austria_regional.py`:

1. **The import rows run the full width of the table.** Read across the
   intermediate columns only, the nine regions' interregional imports come to
   75,338 against exports of 180,079 — **58 % short**. Read across the whole
   width they come to 180,079, to one part in a million, because a closed
   national MRIO cannot do otherwise.

2. **Row output is not column output.** Both balance identities hold against
   their own total — rows to 2.1 and columns to 4.9 on AT13, against a file
   floor of 0.028 — but the two totals differ by up to **6,730 for one sector**:
   Trade sells 11,156 and buys 17,886. The differences sum to 3.3 across all 56,
   so it is a redistribution and not a hole. `load_rokicki_austria` therefore
   **refuses** to return them as symmetric tables;
   `read_rokicki_components` returns the parts and makes the caller say which
   total it is using.

---

## `truth/Finland/io_reg_2014.xlsx` and `truth/Scotland/UKM-.xlsx`

**Present, and deliberately unused.** `run_regional_truth_survey.py` records why,
because the reason is not that a fit came out badly.

**Scotland** is a bare 10-sector intermediate matrix with no output vector and no
final demand. A coefficient needs a denominator.

**Finland** has four usable NUTS-2 sheets (`FI1B`, `FI1C`, `FI1D`, `FI19`;
`FI20` is empty and the NUTS-3 sheets do not partition the country) whose row
identities close exactly. But its tables are **total-flow, not domestic**: the
intermediate share sits at 0.45 of output against Austria's 0.23 and does not
rise with region size, and a fitted FLQ runs to the boundary — delta = 0, where
it collapses onto CILQ — while still undershooting by 7 % to 30 %. The quotient
family can only scale down; here it would have to scale up. That is not a bad
calibration, it is the wrong object.

The irony is on the record: Finland is where the FLQ's delta was calibrated, but
on Statistics Finland's 1995 regional tables, which are not these.
