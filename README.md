# Quadrium

Scientific software for constructing Supply-Use and Input-Output systems —
balancing, projecting, transforming and disaggregating national accounting
tables, with every method traced to the manual that specifies it and verified
against that manual's own printed numbers.

```bash
pip install -e .
quadrium --help
```

## See what it produces before installing anything

**[`outputs/uk_food_beverage/report.md`](outputs/uk_food_beverage/report.md)** is
a finished run, published on purpose: the ONS 2023 analytical table with its
hospitality sector divided into three, using real ABS turnover for the sizes.
Verbatim output — the whole folder is there, including the disaggregated table,
the provenance of every cell and the assumption ledger. Regenerate it with
`python3 examples/uk_food_beverage.py`.

Read it before deciding whether this is worth installing. That is what it is
there for.

*One thing you will notice in it.* The report cites its sources by paragraph and
page — `CORE_012 ¶11.66, pp. 333–334` and the like — and those are published
manuals. It also carries pointers like `MVP_0.1 §6.3` and `OQ-S-05` into this
project's own research record, which is **not** in this repository and is not
meant to be readable by you. `PROVENANCE.md` says why. They are left in rather
than stripped, because the run is verbatim and editing it would make it
something other than what the engine produced.

For an EU country you do not even need a table: name the country and the year
in the configuration and the engine fetches it from Eurostat, caches it with
its SHA-256, and never downloads it again.

And you do not need to know which table first:

```bash
quadrium --find I55 --geo ES
```

answers whether anyone publishes accommodation separately for Spain — nobody
does; it sits inside `I`, and that is the sector to divide — and hands back the
configuration rows to paste.

If the year you want has no symmetric table, name the supply-use pair instead
and say which of the four transformation models to apply. Spain publishes 22
years of the symmetric table and 35 of the pair, and 2024 exists only as a
pair.

Python ≥ 3.10, `numpy` and `openpyxl`. Nothing else.

**New here?** [`docs/GUIDE.md`](docs/GUIDE.md) takes you from an empty folder to
a disaggregated, balanced table with an audit trail — including how to bring in
a table from any statistical office, not just the two whose workbooks are read
natively. No Python: you fill in a spreadsheet and run one command.

## What makes this different from a matrix library

**Every claim in here is checked against a number somebody else published.**
Ninety-nine validators run on official data from seven statistical offices, and
they are the documentation: each one states what it is testing, cites the
paragraph and page it comes from, and prints the deviation it measured.

```bash
for v in validators/run_*.py; do python3 "$v"; done
```

Some of what they establish:

| | |
|---|---|
| **GRAS** reproduces every printed intermediate of the UN Handbook's own worked example, iterations 1 and 2 | `validators/run_gras_austria.py` |
| **SUT-RAS** reproduces the printed vectors of iterations 1, 2, 3 and 20, and the converged table to within half a cell | `validators/run_sut_ras_austria.py` |
| The four **SUT→IOT transformation models** reproduce the Handbook's tables exactly, and behave on signs as its Figure 12.2 says they do | `validators/run_handbook_transformations.py` |
| Six accounting **identities hold exactly in all 27 published years** of the UK supply-use tables, and value added is preserved from the SUT into the analytical IOT across two tables | `validators/run_uk_sut_identities.py` |
| The **valuation matrices** total their supply columns to 0.0000 on 65 products, three years | `validators/run_valuation_matrices.py` |
| A result **read back and split again** keeps its provenance: withholding it would relabel 12 of 36 cells from estimate to observation, with the numbers unchanged | `validators/run_export_roundtrip.py` |
| Every balance tolerance is **derived from the publisher's own printed precision**. Four gates used flat constants instead, and refused two of three real published tables over residues 10–100× inside what their rounding permits | `validators/run_eurostat_config.py` |
| **Nineteen of twenty-seven** published EU symmetric tables load and are sound; the eight that refuse do so for four distinct reasons, and all eight refusals are correct — Ireland's 2020 table prints a total twice what its own codes carry | `validators/run_eu_sweep.py` |
| A refused table is **diagnosed, not just measured**: Belgium's pair is +0.8 on `L68A` and −0.8 on `L68B` and 0.000 on the other 87 — a boundary between two halves of one sector, which "off by 0.8000" could not say | `validators/run_sut_closure.py` |
| Availability is read from the **value map, not the `time` dimension** — which said Germany had data to 2024 and produced a configuration that fails. Germany in fact has no route to a symmetric table through Eurostat at all | `validators/run_availability.py` |
| The **allocation key moves sizes one-for-one and multipliers not at all** — 1.84800 at every weight from 50/50 to 80/20, so the error bar is arithmetic and a perturbation study would have reported zero and been read as robustness | `validators/run_key_sensitivity.py` |
| A pair **projected onto its own totals returns itself exactly**, in one iteration — the test that showed final-use targets belong at purchasers' prices, where the wrong basis merely fails to converge while reporting 1.00009 | `validators/run_projection.py` |
| A **multiplier is checked against the inverse it comes from**: one negative cell in the ONS table produces 19 in the Leontief inverse, all in one column, whose multiplier of 1.0828 is 1.1705 minus 0.0877 | `validators/run_leontief_check.py` |
| A **supply-use pair transforms** into a symmetric table by any of CORE_013's four models, closing both identities to float64 noise on Spain and to hundredths on Austria, which prints two decimals | `validators/run_sut_to_iot.py` |
| The catalogue counts the codes that **carry data**, not the codes a publisher lists. Spain's symmetric table lists `CPA_I55` and `CPA_I56` among 121 categories and populates neither; 9 of 10 countries on disk cannot separate hotels from restaurants | `validators/run_catalogue.py` |

## Two ideas the engine is built on

**A tolerance is derived from the problem, not chosen.** A table published to
`d` decimals cannot have an `n`-term identity checked more tightly than
`0.5·10⁻ᵈ·n`, whatever anyone would like; and a solver handed row and column
totals that do not sum alike is being asked for a table that does not exist, so
its residual is bounded below by the inconsistency of the request.
`quadrium.precision` computes both. Measured across 18 identity observations
from six offices, a flat constant is wrong in one direction or the other on
half of them.

**Negatives are not errors.** Margins sum to zero through offsetting negatives,
subsidies are negative taxes, and inventory changes go both ways. GRAS is used
precisely because it can neither create nor destroy a sign. Any routine here
that assumed non-negative cells would be wrong about official data, and the
validators say so on the project's own fixtures.

## Layout

```
src/quadrium/     the engine: loaders, solvers, transformation, disaggregation,
                  balancing, validation, reporting
validators/       99 runnable checks against published tables
data/             the tables they run on — see PROVENANCE.md
docs/             the user guide
outputs/          one finished run, published so it can be read without
                  installing anything
examples/         four worked pilots
tests/            55 unit tests
```

## What is not here

The methodological library — verbatim chapters of the UN, Eurostat, OECD and
SNA manuals — is copyrighted and stays private. See **PROVENANCE.md**, which
also names the six validators that read it and are therefore absent. Everything
present runs.

## Licence

MIT for the software. The data keeps its publishers' terms — Eurostat, ONS
(Open Government Licence v3.0), INE and UNSD — recorded per file in
PROVENANCE.md.
