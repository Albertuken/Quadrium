# Quadrium

Scientific software for constructing Supply-Use and Input-Output systems —
balancing, projecting, transforming and disaggregating national accounting
tables, with every method traced to the manual that specifies it and verified
against that manual's own printed numbers.

```bash
pip install -e .
python3 run_quadrium.py --help
```

Python ≥ 3.10, `numpy` and `openpyxl`. Nothing else.

## What makes this different from a matrix library

**Every claim in here is checked against a number somebody else published.**
Fifty-six validators run on official data from six statistical offices, and
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
validators/       56 runnable checks against published tables
data/             the tables they run on — see PROVENANCE.md
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
