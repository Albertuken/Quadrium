# What this run was, and what came out

A finished run, published so it can be read **before installing anything**.
`report.md` beside this file is the engine's verbatim output; this page says
what was asked, what it was given, and what to look at first.

## The question

The ONS publishes a UK analytical input-output table for 2023 with 104
industries, and one of them is `I56`, *food and beverage service activities* —
restaurants, event catering and bars, in a single row and a single column. If
what you care about is bars, or is restaurants, that table cannot answer you:
the three are one sector in it.

**The question is how much of that sector is each of the three, and what their
tables look like separately.**

## What it was given

| | |
|---|---|
| Table | ONS 2023 analytical IOT, 104 industries, industry-by-industry, domestic use, basic prices |
| Sector divided | `I56` into `I561` restaurants, `I562` event catering, `I563` beverage serving |
| Proxy, scenario 1 | ONS Annual Business Survey turnover for SIC 56.1 / 56.2 / 56.3, published directly at three digits — **strong** |
| Proxy, scenario 2 | ONS Business Register and Employment Survey employment — **medium**, and Great Britain rather than the UK |

**Both proxies are real.** This is not an illustration: the split rests on
figures the office published, and the two scenarios exist so you can see whether
the answer depends on which one you believe.

## What came out

| Subsector | Output | Value added | Output multiplier |
|---|---:|---:|---:|
| `I561` restaurants | 54,270.3 | 30,645.2 | 1.848 |
| `I562` event catering | 14,193.1 | 8,014.5 | 1.848 |
| `I563` beverage serving | 26,346.6 | 14,877.3 | 1.848 |

GBP million, 2023, basic prices. Both scenarios passed every check; nothing was
rejected.

## The three things to look at, and one is the point

**1. The multipliers are identical, and that is not a result — it is a
statement of what was not attempted.** The sizes come from a real survey; the
input structures do not. Each subsector is a scaled copy of the parent's
purchasing pattern, cosine distance effectively zero, so any difference between
their multipliers would be an artefact of the balancing rather than a finding.
The report says so where the number appears, not in a footnote.

Making them genuinely different needs an input profile, and the report carries
what that is worth: on 96 splits where the office publishes both the parent and
its parts, a TRUE input profile moves the seed's multiplier error from a median
7.78 % to 3.48 % — **and the balancer gives all of it back**, delivering 7.79 %
against 7.78 % for using no profile at all. That is measured, and it is why the
published run does not use one.

**2. A block took a default, and the report names it as a default.** No key was
registered for the intermediate-input block, so it inherited the output key.
That is not a decision anybody made, and the distinction between *chosen* and
*defaulted* is exactly what an assumption ledger exists to keep.

**3. It was corroborated against a proxy it did not use.** A second strong key —
approximate gross value added from the same survey — was registered and
deliberately not used to drive the split, so the report can compare what the
split implies against what that key measures. That comparison is the only
external check this kind of work admits, and it is in the report as a table with
a gap column.

## What is in the folder

| | |
|---|---|
| `report.md` | the run, verbatim: checks, both scenarios, the corroboration, the ledger in prose |
| `assumption_ledger.json` | every assumption as data, for a later reader who is not reading prose |
| `project.json` | what was run, with what, under which version |
| `original_table.csv` | the parent table as the loader read it |
| `scenarios/` | the resulting tables, one folder per scenario |

## Reproducing it

From a checkout, with nothing else installed:

```bash
python3 examples/uk_food_beverage.py
```

The example's docstring says what is real in it and what is illustrative. The
ONS table is in the repository; nothing is downloaded.
