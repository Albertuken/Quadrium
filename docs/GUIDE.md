# Quadrium — user guide

You have an input-output table. One of its sectors is too coarse for the
question you are asking: "hospitality" when you care about restaurants, "food
products" when you care about dairy. You want to divide it into subsectors,
keep the table balanced, and be able to say afterwards which numbers you
measured and which ones you assumed.

That is what this does. No Python: you fill in a spreadsheet and run one
command.

**Contents**

1. [Install](#1-install)
2. [Run the worked example](#2-run-the-worked-example-five-minutes)
3. [Use your own table](#3-use-your-own-table)
4. [Fill in the configuration workbook](#4-fill-in-the-configuration-workbook)
5. [Run it](#5-run-it)
6. [Read the report](#6-read-the-report)
7. [Split a second sector, later](#7-split-a-second-sector-later)
8. [When it refuses](#8-when-it-refuses)
9. [What it will not do](#9-what-it-will-not-do)

---

## 1. Install

Python 3.10 or later. Two dependencies, both ordinary: `numpy` and `openpyxl`.

```bash
pip install quadrium
```

From a checkout instead:

```bash
pip install -e .
```

Check it worked:

```bash
quadrium --help
```

If `quadrium` is not found, your Python scripts directory is not on `PATH`.
`python3 -m quadrium.cli --help` does the same thing and always works.

---

## 2. Run the worked example (five minutes)

The repository ships a complete configuration and a real table: the ONS
industry-by-industry analytical table for the United Kingdom, 2023, 104
industries. It divides accommodation and food services into five subsectors
under two different scenarios.

```bash
quadrium configs/ejemplo.xlsx
```

You should see it describe what it is about to do, warn you about what is weak
in the configuration, run, and finish with a path to a report. Open
`outputs/<project_id>/report.md`.

**The proxies in that example are invented.** The table is real; the split is
illustrative, and the report says so at the top and in the assumption ledger.
It exists so you can see the shape of a result before you commit real data to
it.

---

## 3. Use your own table

There are two routes, and which one you take depends on where your table came
from.

### Route A — let the engine fetch it

If your country is in the EU, you do not need a file at all. Name the country
and the year and the engine downloads the table from Eurostat:

| Key | Value |
|---|---|
| `table_kind` | `eurostat` |
| `eurostat_geo` | `ES`, `PT`, `AT` … the two-letter code |
| `eurostat_year` | `2022` |
| `eurostat_dataset` | `product_by_product` (default) or `industry_by_industry` |
| `eurostat_variant` | `domestic` (default) or `total` |

The first run downloads it, prints the URL, the size and the SHA-256, and saves
it under `data/eurostat/`. **Every run after that reads those same bytes and
never touches the network.** That is deliberate: statistical offices revise, and
a configuration that re-downloaded on every run would give one answer in
January and another in June with nothing in the output to say why.

- `--refresh` downloads again on purpose, and then tells you **how many figures
  actually changed**. Often none: Eurostat restamps a release without revising
  it, so the checksum moves and the data does not.
- `--offline` refuses to fetch anything and prints the URL, so you can bring
  the file in by hand.

One caveat worth knowing before you plan a project around it. Eurostat
harmonises the **format**, not the method: the same dataset codes and the same
classification for every member state, with no record of how each office got
there. The UK uses a hybrid of two transformation models chosen per cell, Spain
a hybrid chosen per secondary production, Austria product technology with
manual correction above 15 million euros. Three tables that look alike were not
made alike, and any comparison across countries that does not say so is
comparing the format.

### Route B — a format the loader already knows

Set `table_kind` in the configuration workbook to one of:

| `table_kind` | What it reads |
|---|---|
| `uk_analytical` | The ONS analytical workbook, industry × industry |
| `ine_interior` | The Spanish INE workbook, domestic output |
| `ine_total` | The Spanish INE workbook, total flows |
| `interchange` | This project's own format — see Route C |

These loaders do more than parse. They know, for instance, that the first two
value-added rows of the ONS table are imports and taxes on products rather than
value added, and that the reference year must be read from the Menu sheet and
never from the filename. What each loader decided is printed in your report
under **What the loader decided when reading this file**, so you can check it
made the right call.

### Route C — any other table, via the interchange format

Any table can be brought in by rewriting it into one workbook with two sheets.
This is deliberately plain: no fixed cell positions, blocks are found by their
labels.

**Sheet `table`**, in this order:

- Row 1: a header row. Cell A1 is ignored; then one column per sector, headed
  by its code; then one column per final-demand category, headed by its name.
- Then one row per sector, labelled in column A with **the same codes as the
  header, in the same order, with no gaps**. This is not a formality: nothing
  else marks where the sectors stop, so the loader finds the sector block by
  matching those labels against the header one for one, and stops at the first
  row that does not match.
- Then one row per value-added component (compensation of employees, gross
  operating surplus, taxes less subsidies on production, and so on), labelled
  in column A. At least one is required — without value added a column does
  not add up to output.
- Then a final row labelled `Output` or `Total output`.

**Sheet `metadata`**, as key/value rows. Five keys are required and the loader
refuses the file without them:

| Key | Example |
|---|---|
| `country` | `Portugal` |
| `year` | `2022` |
| `unit` | `EUR million, current prices, basic prices` |
| `classification` | `CPA 2.1 (82 products)` |
| `source` | `INE Portugal, Contas Nacionais, matriz simétrica 2022` |

Optional: `table_id`, `notes`, and `label_<code>` for each sector to give it a
readable name.

Why the refusal on missing metadata: a table without its price basis and its
classification cannot be used safely. Basic prices and purchasers' prices give
different multipliers, and nothing in the numbers tells you which you have.

**The loader will check that your table balances** — output equals the sum down
each column, and the sum along each row equals output — before doing anything
else. If it does not balance, it says so and stops, rather than quietly
producing a result. See §7.

---

## 4. Fill in the configuration workbook

```bash
quadrium --template my_config.xlsx
```

That writes a blank workbook with five sheets. Every sheet carries its own
instructions at the bottom, in grey. What follows is the same thing with more
room to explain.

### Sheet `project`

Five key/value rows.

| Key | What to put |
|---|---|
| `project_id` | A short name. It becomes the output folder. |
| `table_path` | Absolute, or **relative to the configuration file itself** — not to where you run the command. |
| `table_kind` | One of the five above. |
| `title` | The title at the top of the report. |
| `notes` | Free text, printed under the title. Use it for the caveat you want a reader to see first. |

### Sheet `splits` — what you are dividing

One row per **new** subsector.

| sector_code | new_code | new_label | key_id |
|---|---|---|---|
| I56 | I561 | Restaurants and mobile food service | k56 |
| I56 | I562 | Event catering | k56 |
| I56 | I563 | Beverage serving activities | k56 |

Rows sharing a `sector_code` form one split. You can divide several sectors in
one run: add rows with another `sector_code`. Their internal blocks are
disjoint and each split preserves the other's row and column totals, so the
result does not depend on the order you list them in.

### Sheet `keys` — the proxy that decides the sizes

This is the sheet that does the real work, and the one your result will live or
die by.

| key_id | new_sector_code | value | source | source_year | strength |
|---|---|---|---|---|---|
| k56 | I561 | 720000 | ONS BRES, employment by SIC 56.1 | 2023 | strong |
| k56 | I562 | 120000 | ONS BRES, employment by SIC 56.2 | 2023 | strong |
| k56 | I563 | 380000 | ONS BRES, employment by SIC 56.3 | 2023 | medium |

`value` is relative — turnover, employment, floor space, whatever you have.
It is normalised for you, so you do not need shares.

`strength` is `strong`, `medium` or `weak`, and **a key is recorded at its
weakest row**, because a split resting on one weak proxy is a weak split. This
is not decoration: the strength travels into the report, into the assumption
ledger, and into the warning the tool prints before it runs.

Write the real source. It is printed in the report, and in six months it is the
only thing that will tell you what you did.

**Register a second key you do not intend to use.** If two independent proxies
— say employment and turnover — give similar shares, that is the only external
check this system can make on your split. If they disagree, you have learned
something before publishing rather than after. With one key registered, the
tool will tell you nothing can corroborate the result.

### Sheet `scenarios` — how many answers you want

| scenario_id | label | description | internal_block_alpha |
|---|---|---|---|
| S1_plain | Size only | Every subsector inherits its parent's purchasing pattern. | |
| S2_profiled | Differentiated inputs | Subsectors buy different mixes. | |

Leave `internal_block_alpha` blank for the default of 0.5. It governs how much
of the parent sector's trade with itself stays inside each subsector versus
crossing between them, and it is a project convention, not something any
manual states.

Run at least two scenarios. The spread between them is the honest measure of
how much your answer depends on your own choices, and the report computes it
for you.

### Sheet `profiles` — making the subsectors genuinely different

| scenario_id | subsector_code | supplier_code | intensity |
|---|---|---|---|
| S2_profiled | I563 | C1101T1106 & C12 | 2.1 |
| S2_profiled | I563 | C101 | 0.45 |
| S2_profiled | I561 | C101 | 1.35 |

`intensity` is relative to the parent sector's average purchase from that
supplier. `1.0` is the average, `2.1` means it buys 2.1 times as intensively,
`0.45` less than half. In the example, bars buy far more beverages and far less
meat than the parent average.

**Without this sheet every subsector ends up with the same multiplier.** That
is arithmetic, not economics: a single allocation key gives each subsector a
scaled copy of the parent's input structure, and the scale cancels out of
`a_ij = Z_ij / X_j`. Only a differentiated purchasing pattern makes them
different as buyers.

There is a ceiling on how far you can push it, set by how much the parent
sector trades with itself. The report prints the headroom you had, and an
impossible set is rejected with a section of its own: which subsector was left
needing to buy a negative amount, and the parent's own budget it had to fit
inside — what share of that sector's output goes to final demand, what share is
value added, and how much of it is trade within the sector at all.

---

## 5. Run it

Check first, without running anything:

```bash
quadrium my_config.xlsx --check
```

This parses the workbook, loads the table, verifies it balances, and prints
what it would do. Then it prints a section headed **"Valid is not the same as
well founded"**, which is where it tells you that your key is marked weak, or
that only one key is registered, or that your profiled scenario produces
demonstrations rather than estimates. Those are cautions. They never change the
exit code, and they are printed on the real run too.

Then:

```bash
quadrium my_config.xlsx
```

Outputs go to `./outputs/<project_id>/`. Use `--outputs somewhere/else` to put
them elsewhere.

**Exit code 0 means every scenario passed validation.** Anything else means
read the message — including the case where one scenario produced a good table
and another was rejected, which is a partial result rather than a failure but
is not a clean run either.

---

## 6. Read the report

`outputs/<project_id>/report.md`, alongside `original_table.csv`,
`assumption_ledger.json`, `project.json`, and one folder per scenario holding
the disaggregated table.

The report has seven parts. In order of how much they should worry you:

**Scenario comparison.** Output multipliers for every subsector under every
scenario, and the range between them. This is the first thing to look at,
because the range tells you how much of your result is your own assumptions.
The report also names the single cell that drives most of the variation.

**Cell provenance.** Every cell of the new table is counted into one of four
statuses:

| Status | What it means |
|---|---|
| `OBSERVED` | Copied from the source table, untouched |
| `ESTIMATED` | Produced by your proxy |
| `BALANCED` | Produced by the solver to make the table add up |
| `user_constraint` | A value you pinned by hand |

A `BALANCED` figure is not an observation and must never be relabelled as one.
In a typical split, around 90 % of cells are untouched and 10 % come from your
key — which is a useful reminder that a disaggregation is a local operation,
not a new table.

**Validation.** Eleven or so checks per scenario, each printing the deviation
it measured and, where it comes from one, citing the manual paragraph and page.
They cover proxy coverage, key vintage against the table's reference year,
solver convergence, whether the margins were attained, whether cells that
involve no split sector are still exactly what they were, whether reaggregating
the subsectors reproduces the original, whether any cell changed sign, extreme
coefficients, and the size of the estimated internal block.

**Balancing.** Which solver was used and why. The method is chosen by the sign
structure of your table, not by preference: RAS is undefined on a matrix with
negative entries, GRAS is not, and GRAS reduces to RAS when there are no
negatives. Negative cells are normal in official data — subsidies are negative
taxes, inventory changes go both ways — and are not errors.

**Per-split detail.** For each divided sector: the keys considered, which was
chosen, its strength and vintage, how it compares against the table's own
totals, the resulting weights, and the headroom in the internal block.

**How to read this.** Four standing cautions, the most important being that
solver convergence is necessary but not sufficient. A run that converges and
fails a plausibility check is a failed run.

**Assumption ledger.** Every assumption the run rests on, with its source,
confidence and impact. Also written as `assumption_ledger.json` so you can
carry it into whatever you publish.

---

## 7. Split a second sector, later

You divided hospitality. A month on you want to divide food manufacturing in
the same table. You do not have to redo the first split: the workbook the
engine writes, `scenarios/<id>/table_disaggregated.xlsx`, can be read straight
back in.

Point a new configuration at it:

| Key | Value |
|---|---|
| `table_path` | `../outputs/my_project/scenarios/S1_plain/table_disaggregated.xlsx` |
| `table_kind` | `interchange` |

That file carries the numbers twice on purpose. The sheets `Z`, `FinalDemand`,
`ValueAdded` and `Output` are laid out for a person, shaded by provenance. The
sheets `table` and `metadata` hold the same figures in the format the loader
reads. Both are written in one pass from the same arrays, so they cannot
disagree.

**What travels with it, and why that matters more than the numbers.** A
disaggregated table balances exactly as well as a published one. Nothing in the
figures reveals that two thirds of its cells came from an allocation key rather
than a survey, so if the provenance did not travel, the second run would stamp
every cell it did not touch as an observation, and by the third generation a
table of pure inference would report itself as pure measurement.

So the `Provenance` sheet is read back too, and the new report opens with a
warning naming the share of cells that were already estimates and the chain of
splits that produced them, oldest first. On the small test fixture, twelve of
thirty-six cells would be quietly promoted from estimate to observation by one
trip through a file if this did not happen.

Two practical consequences:

- **Do not delete or edit the `Provenance` and `metadata` sheets.** A file
  without them still loads, and still balances, and will silently claim to be a
  publication.
- **Each generation reaggregates onto the one before it**, exactly. You can
  always sum the subsectors back and recover the table you started from, at any
  point in the chain.

There is no limit on the number of generations, but there is a judgement: every
split multiplies the assumptions, and the second generation's multipliers rest
on the first generation's key as much as on your new one. Two generations is
usually the point at which it is worth asking whether one run with both splits
would be more defensible — it uses the same original table for both, and the
report then shows them side by side.

---

## 8. When it refuses

The tool stops rather than producing a number it cannot defend. The messages
are written for an economist and name the subsector or the proxy at fault.

| What you see | What it means | What to do |
|---|---|---|
| `Configuration problem in …` | A sheet is missing, a code does not exist in the table, a key does not cover every subsector, weights do not resolve. | The message names the sheet and the row. |
| The table does not balance on load | Your table's row sums, column sums and output do not agree within the tolerance derived from its own printed precision. | This is usually a real defect in the file: a subtotal column counted twice, or a block pasted in at the wrong offset. |
| One or more scenarios `REJECTED` | Those profiles imply an economy that does not exist — typically a subsector left needing to buy a negative amount from its siblings, because it was given a larger share of inputs than its share of output can absorb. | Nothing about the solver can fix this, and no tolerance will. The report names the subsector and prints the parent's own ratios. Move the keys closer together or soften the intensities. |
| `Every scenario was rejected` | The same thing, for all of them. Nothing is written. | As above. |
| `no sector rows found` / `appear below the sector block` | An interchange file whose row labels do not line up with its header. | See §3, Route C: same codes, same order, contiguous. |
| `the Provenance sheet has N data rows for M sectors` | A re-read result whose provenance grid no longer matches its table, usually after hand-editing. | A grid that does not match is worse than none, because it mislabels rather than leaves unlabelled. Delete the sheet or correct it. |
| A validation check `FAIL`s but the run finishes | The table was produced but something about it is implausible. | Read that check before using any number. The exit code is non-zero. |

On tolerances: a table published to `d` decimals states each cell as a stand-in
for a true figure in a band of width `10⁻ᵈ`, so an identity summing `n` such
cells cannot be checked more tightly than `0.5·10⁻ᵈ·n`, whatever anyone would
prefer. Below that line "balanced" and "not balanced" are the same
observation. The engine computes that floor from your table's own precision
rather than applying a constant. Where a genuine project choice remains, the
report labels it `PROJECT CHOICE`.

This matters more than it sounds. Publishers differ: Portugal prints its
symmetric table to two decimals and Spain to one, from the same Eurostat
dataset under the same regulation, and the same country differs between years.
A table that rounds does not close its own accounts exactly — its row and
column totals disagree by hundredths — and that residue is inherited by
everything computed from it. The report states, next to each check that used
it, how much of its tolerance was the source's own unclosed books rather than
anything this run did. Where your source closes exactly, that allowance is
zero and nothing is relaxed.

---

## 9. What it will not do

- **Multi-region tables.** Single-region only.
- **Regional disaggregation.** Sectors, not territories.
- **Environmental or employment extensions.** Monetary flows only.
- **Invent your proxy.** The split is only as good as the key you bring, and
  the tool's main contribution is refusing to let you forget that.

---

## Where the numbers come from

Every method here is implemented from a published manual, and the code cites it
by paragraph and page: `CORE_012 ¶11.66, pp. 333–334` is the United Nations
*Handbook on Supply and Use Tables and Input-Output Tables* (2018), and
`UNH_18 ¶18.35, p. 558` is its chapter 18. Those citations appear in the
validators, in the code, and in your report.

References of the form `OQ-B-02` point to the project's own research register,
which records questions the sources did not settle and how each was resolved.
The register is not part of the public repository. Where one is cited in a
message, the message states the conclusion as well as the reference.

The `validators/` directory is the real documentation. Each script states what
it tests, cites where it comes from, and prints the deviation it measured
against official data — GRAS against the Handbook's own worked iterations, the
four transformation models against its printed tables, six accounting
identities across 27 published years of UK supply-use tables. They run in
seconds:

```bash
for v in validators/run_*.py; do python3 "$v"; done
```
