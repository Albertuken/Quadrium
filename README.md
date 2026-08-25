# Quadrium

Scientific software for constructing Supply-Use and Input-Output systems —
balancing, projecting, transforming and disaggregating national accounting
tables, with every method traced to the manual that specifies it and verified
against that manual's own printed numbers.

```bash
pip install -e .
quadrium --help
```

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
Sixty-four validators run on official data from six statistical offices, and
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
validators/       64 runnable checks against published tables
data/             the tables they run on — see PROVENANCE.md
docs/             the user guide
examples/         four worked pilots
tests/            40 unit tests
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
