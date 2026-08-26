# Quadrium — user guide

You have an input-output table. One of its sectors is too coarse for the
question you are asking: "hospitality" when you care about restaurants, "food
products" when you care about dairy. You want to divide it into subsectors,
keep the table balanced, and be able to say afterwards which numbers you
measured and which ones you assumed.

That is what this does. No Python: you fill in a spreadsheet and run one
command.

**Contents**

0. [Which table do I even need?](#0-which-table-do-i-even-need)
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

## 0. Which table do I even need?

You probably did not start with a table. You started with a sector — "I want to
look at restaurants" — and the first real question is whether anyone publishes
it separately for your country.

```bash
quadrium --find I55 --geo ES
```

```
  I55 — split

  No ES table here separates I55. The finest that contains it is
  eurostat:naio_10_cp1700:ES:2022, where it sits inside `I` (Accommodation
  and food services). That is the sector to divide, and dividing it is what
  this engine does — bring a proxy that measures the parts. UK publishes it
  separately, which tells you the split is a real distinction and NOT that
  you may borrow their figures.

  Put this in the `project` sheet:

      table_kind       eurostat
      eurostat_geo     ES
      eurostat_year    2022
      eurostat_dataset product_by_product

  and divide `I` in the `splits` sheet.
```

Four answers are possible:

| Answer | What it means |
|---|---|
| **load** | Someone publishes it as a sector of its own. You do not need this tool for that sector — take the table and read the row. |
| **split** | It exists only inside a coarser sector, which is named. That coarser sector is what you divide, and this is the case the engine is built for. |
| **publisher has it** | Your office publishes the code, but only as part of a set whose pieces do not add up to their parent — so taking them would lose whatever was not published. It exists; it is not loadable. Do not estimate it with a proxy without looking at the file first. |
| **none** | No table on disk covers the code. Check it against the classification, or fetch a table that might carry it. |

If nothing for your country is on disk, it asks Eurostat which years that
country actually publishes — per dataset, cached afterwards — and prints the
configuration rows to paste.

**And it tells you whether it loads.** Every country's newest table of each kind
was loaded once and the result recorded, so `--find` names the verdict rather
than warning you in general terms:

```
      symmetric table  2020   REFUSED — incomplete: the table's codes do not
                                        sum to the total it prints
      the pair         2020   REFUSED — incomplete
```

That is evidence about the year it names and not a prediction about the others,
and the output says so. Carrying is not loading: the engine checks the
publisher's own identities and refuses a table whose books do not close within
its own printed precision.

Some countries have no route at all. Germany publishes neither a symmetric table
nor use at basic prices to Eurostat, so its pair cannot be transformed either —
the domestic/imported split would have to be assumed. The adviser says so rather
than offering a configuration that would fail.

`--geo` is not optional in spirit. Without it nothing is recommended, only
listed by country — because a finer table for another economy is not a better
source for your question, it is an answer to a different one.

```bash
quadrium --sources
```

lists every table on disk, how many sectors each distinguishes, and how much
detail the publisher publishes that is nonetheless not loadable.

Where a publisher serves both a code and its components — France transmits
`C10`, `C11` and `C12` alongside `C10-12` — **the engine keeps the components**,
provided their published totals add up to the parent's. It checks that
arithmetically rather than trusting the notation, because a publisher may serve
only some of an aggregate's pieces, and taking those would silently lose the
rest. France's supply-use pair therefore loads at 89 products by 88 industries
rather than 65 by 65. It also lists the
sources that **measure** sectors rather than being tables — candidate
allocation keys for the split you are about to do — and says when one of them
covers only part of the sector you asked about, which means it cannot drive
that split on its own.

Two things it counts carefully, because both are easy to get wrong:

- **Sectors are the codes that carry data, not the codes that are listed.**
  Eurostat's metadata lists the whole CPA hierarchy whether a country publishes
  at that level or not. Spain's symmetric table lists `CPA_I55` and `CPA_I56`
  and populates neither.
- **Resolution is not comparability.** It ranks by how many sectors a table
  distinguishes, which is the only thing it can see. Two tables with the same
  classification and the same count were not necessarily made the same way.

---

## 1. Install

Python 3.10 or later. Two dependencies, both ordinary: `numpy` 1.24 or later
and `openpyxl` 3.1 or later. Those floors are tested, not asserted — CI installs
exactly them on one leg, and the latest on two more.

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

**If the year you want has no symmetric table, use the supply-use pair.** Most
offices publish supply and use before, and more often than, symmetric tables:
Spain has 22 years of the symmetric table and 35 of the pair, and the most
recent year exists only as a pair. Set `table_kind: eurostat_sut` with the same
country and year, plus one more key:

| `eurostat_model` | Axis | Can produce negative cells? |
|---|---|---|
| `A` product technology | product × product | yes |
| `B` industry technology | product × product | no |
| `C` fixed industry sales | industry × industry | yes |
| `D` fixed product sales *(default)* | industry × industry | no |

**That key is a real decision and not a formatting option.** A supply-use pair
is what the data is collected as; a symmetric table is what an assumption about
secondary production turns it into. On Spain 2022, models A and D differ by
5,629 million EUR in their widest cell from identical inputs. The report names
the model that produced your table, and if you leave the key blank it tells you
a default was taken.

**And you can move the pair to a later year before splitting it.** If you have
a detailed pair for one year and only aggregates for a later one — which is the
normal situation between benchmark years — add `project_to_year` and a
`targets` sheet:

| kind | code | value |
|---|---|---|
| `gva` | one row per industry | value added, at **basic** prices |
| `final_use` | one row per category | totals, at **purchasers'** prices |
| `taxes` | — | total taxes less subsidies on products |
| `imports` | — | total imports |

The price bases are not decoration. The method carries taxes as a row of the
use table, so a final-use target must include them. Get it wrong and it does
not fail loudly: it runs to its iteration ceiling and reports every value-added
deviation as 1.00009, which reads like success. Get it right and projecting a
pair onto its own totals returns that pair exactly, in one iteration — which is
the test to run if you ever doubt your targets.

The method stops when every aggregate is within one per cent of its target,
which is the Handbook's own rule. Your totals are approached, not attained, and
the report says how closely. Real pairs take **hundreds to thousands of
iterations** to get there — 356 for Spain 2021 → 2022, 2,835 for Italy — where
the Handbook's own worked example takes three. A run that does not reach the
rule now refuses rather than returning a table that says it converged.

**What a projection is for, and what it costs.** The projected table is
consistent with the totals you supplied and the base year is not: Spain's 2021
value added is 10.8 % below 2022's, so if you need a table that adds up to 2022,
the 2021 table is not an option however good it is. That consistency is what you
are buying.

You are not buying a better estimate of the structure. Projecting eight
countries forward, over horizons of one to twelve years, and scoring the result
against the table their offices later published — **61 tests, and the projected
cells came out further from the truth than the base year's own in every one**,
on technical coefficients, which have no scale in them, and against a baseline
that scales the base year by a single number the projection was itself given.
The gap widens with the horizon rather than closing. Sixty-one tests are one
method and one publisher, and no manual claims otherwise, but do not read
"projected to 2026" as "a better picture of 2026 than the latest published
table".

### Which method — and the question is really "what do you know?"

There are two methods and **no default**. The `targets` sheet decides which one
runs, because the two need different things from you:

| what you have for the later year | `kind` rows to write | method |
|---|---|---|
| value added by industry, final use by category | `gva`, `final_use`, `taxes`, `imports` | `sut_euro` |
| **industry output** by industry, use column totals | `industry_output`, `use_column_totals`, `taxes`, `imports` | `sut_ras` |

`use_column_totals` is one row per industry and then one per final-use
category. For an industry it is that industry's output **less** its value
added; for a final-use category it is the same figure `final_use` would carry.

You can put `project_method` in the `project` sheet if you want to say it out
loud, but it has to agree with the rows. If it disagrees, or the sheet mixes
the two, or it carries only `taxes` and `imports`, the engine stops and asks
what you know rather than picking for you.

**Why there is no default.** `sut_ras` is the better of the two on every test
run: it beats `sut_euro` in all 61 back-tests against tables the offices later
published, and in **54 of 54** when both are handed exactly the same
information. It also hits your industry-output targets exactly, because it is
given them, where `sut_euro` approaches value added iteratively and on Spain
2021 → 2022 overshoots the published total by 3.6 %. But it needs industry
outputs, and if you do not have them the answer is not for the engine to invent
them. Defaulting to either one would be choosing what you measured.

**What a projection is worth depends on that same thing.** With a real
measurement of the later year's industry output, `sut_ras` beats leaving the
base year alone in 60 of 61 tests. With only value added and final use it wins
18 of 54, and `sut_euro` wins none — on that information a projection buys
consistency with your totals rather than a better picture of the structure. The
6.6 points between the two is what knowing next year's industry output is
worth.

**And SUT-EURO may simply refuse.** 29 of those 61 runs did not reach the Handbook's
1 % rule in 5,000 iterations — some are only slow (Czechia converges at 18,423)
and some cannot get there at all: if an industry's value added changes sign
between your base year and your target, the method scales by ratios and cannot
cross zero. Hungary's air transport went from −96.7 to +28.3 between 2021 and
2022. The refusal names the industry, both figures, and which of the two cases
you are in.

**If the pair does not close.** The engine checks the publisher's own
identities before loading anything, against a bound derived from that
publisher's printed precision, and refuses a pair that misses it — naming the
lines that failed and saying whether their residues cancel.

That bound is the whole game, and getting it right is not the same as deriving
it. Belgium's 2022 pair was refused for a 0.8 discrepancy against a bound of
0.465, and the bound was wrong: Belgium publishes to **one** decimal, with two
cells out of 2,829 carrying a second, and the engine was reading the precision
off those two. One decimal over 92 summed cells cannot distinguish anything
below 4.6. The pair loads.

The residue is still worth knowing and the report still prints it — +0.8 on
`L68A`, −0.8 on `L68B`, 0.000 on the other 87, a boundary between two halves of
one sector rather than a table that fails to add up. Where a residue is
genuinely beyond the source's precision and still cancels like that,
`sut_unbalanced: cancelling` admits that shape and only that shape; residues
that accumulate still stop the load. Whatever it admits is recorded in the
report and carried forward, so every later check accounts for it rather than
blaming the engine.

The engine downloads three files for this — supply, use at purchasers' prices,
and use at basic prices split into domestic and imported. That third one is why
the split is read rather than assumed: deriving it would mean supposing every
user of a product imports the same share of it, which is an economic
hypothesis, not bookkeeping.

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

**If your country's newest table refuses, try an earlier year.** `--find` with
`--geo` prints what happened when each route was last loaded, and for three
countries the answer is "the newest refuses and an earlier one loads" — France's
2022 symmetric table is refused for sparse final demand and its 2010, 2016 and
2021 load. The adviser names the year and puts it in the configuration it
prints. For seven other countries every year tried refuses, and it says that
too, rather than handing you a configuration that will fail.

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
| `ine_interior` | The Spanish INE workbook, domestic output — **2021 and 2022 only** |
| `ine_total` | The Spanish INE workbook, total flows — **2016 to 2022** |
| `interchange` | This project's own format — see Route C |

The Spanish restriction is the publisher's, not the loader's: before 2021 the
INE does not publish the domestic/imports split at all, so there is no domestic
table to read. The same edition boundary runs through the Spanish supply-use
files (§3, Route A note): 2021 and 2022 come at 110 products by 81 activities,
2016 to 2020 at 65 by 64, where accommodation and food service are still one
product. Point `ine_interior` at a 2016–2020 file and the engine says so
and tells you that `ine_total` will load instead — at the cost of treating an
imported input as if it had been produced in Spain, which overstates domestic
effects. All seven years are in `data/ine/`; change only the `table_path`.

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

Leave `internal_block_alpha` blank for the default of **1.0**, which is the
sourced rule (CORE_031 eq. 14: the block is the outer product of the weights).
It governs how much of the parent sector's trade with itself stays inside each
subsector rather than crossing between them.

The default was 0.5 until v1.12, on the intuition that a subsector buys from
itself *less* than proportionality implies. Measured on 1,403 sibling pairs in
three published tables, the diagonal of a real two-sector block is about **1.5×**
the outer product and the off-diagonal about 0.1× — the intuition had the sign
backwards. It is not set to 1.5 either: that is this project's measurement, not
a source, and substituting it would be the same mistake in the other direction.
Raise it if you have reason to, and the report will say what you raised it to.

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

**How wrong is this if your key is wrong?** Exactly as wrong as the key in the
sizes, and not at all in the multipliers. The weight scales a subsector's
output, value added and purchases together and cancels out of the technical
coefficients, so a key you believe to within 10 % gives sizes you believe to
within 10 % and a multiplier you believe exactly as much as the parent
sector's. The report prints what 1 % of key error costs, per subsector, in your
table's own units. It is arithmetic, not a simulation.

**Are input profiles worth the trouble?** A profile is how you tell the engine
that your subsectors buy different things; without one they inherit the parent's
purchasing pattern. Measured on 54 splits against the office's own answer, the
answer is more awkward than it looks.

Supplying the parts' **true** profile moves the multiplier error from a median
9.0 % to **3.4 %** — in the seed. Then the balancer gives most of it back: the
table you actually get is a median **10.6 %**, against 10.0 % for using no
profile at all. It still edges out doing nothing in 21 of 35, by margins the
medians do not show. And the engine **refuses the profiled scenario outright in
19 of 54**.

The reason is the engine's own design, and it is sound as far as it goes:
balancing adjusts the internal block and nothing else, because a proportional
split already satisfies every other margin and letting the solver touch copied
cells would break the reaggregation guarantee. Give it a profile and the moved
column has to be absorbed somewhere, and that somewhere is the one block the
measurements show is worst estimated.

**Borrowing a profile from a country that publishes your split is a coin flip**:
better in 78 of 162 borrowings and worse in 84. It helps where the split was
going badly anyway and hurts where it was already fine, and there is no test you
can run beforehand to know which you are in — the risk screen above predicts the
level of error, not whether borrowing will reduce it. So source a real profile if
you can, and treat a borrowed one as a scenario to compare rather than an
improvement.

**Which proxy should the key come from?** Measured on 66 splits over five
country-years against the office's own answer, using the ten variables
Eurostat's structural business statistics publish: **no proxy is reliably
best.** Value of output and turnover have the best medians (4.8 and 5.1 points
of error in a subsector's share) but win a split outright 7 and 8 times out of
66, and the most frequent winner — purchases, at 12 — is still under a third.
The winner is scattered across all ten. Output value beats employment head to
head in 37 of 64, a coin flip.

Expect **5 to 8 points** of error from a real key, with a long tail — p90 is 27
points and the worst case here was 71. Pick for the conceptual match, register
the others, and read the spread: since no proxy is reliably best, that spread is
the honest thing to look at.

Read it knowing what it is. Over 65 splits with the answer published beside
them, the range across the proxies contains the true share for every subsector
at once in **49 of 65 splits** — it misses one in four — and where it does
contain the answer it spans a median **28 points of share**. It is honest about
being uncertain and says almost nothing about where the answer is. A narrow
range is not a safer one: the splits where it misses are the wider ones. Treat
it as evidence that you do not know, not as an interval you can quote.

**Before any of that, check whether the answer is already published for another
year.** If your office publishes the split you need for a nearby year, use that
year's shares as the key and ignore the proxies entirely. On the one country
that publishes three consecutive years at the detail that settles it, last
year's published split is out by a median **1.2 points** and two years back by
**2.4**, against **4.8 at best** for the ten proxies and 27 at p90 — about four
to one in favour of an older answer over a current proxy. The engine already
records the key's `source_year` and says when it differs from the table's; what
was missing was the size of the trade.

The clever version — measure the proxy's bias in the published year and subtract
it in yours — was tried and does not earn its complexity. It beats plain
carry-over in 54 % of splits, a coin flip, because subtracting "proxy minus
truth" is a laundered way of using the published year. One country, three years,
one of them pandemic-affected; the cost doubles from a one-year to a two-year
gap, which is the shape to expect rather than a law. See
`validators/run_key_carryover.py`.

Two practical notes. National-accounts employment (`nama_10_a64_e`) is the first
thing most people reach for and it **cannot be used**: it is published at exactly
the aggregation of the table you are splitting. The detail only exists in
business statistics, which count enterprises where the table counts products —
that mismatch is not a shortcut, it is the only road there is.

**How risky is this split, before you make it?** Two numbers from the table you
already have rank the difficulty: **the parent's own output multiplier** and
**how many parts you are asking for**. They are independent of each other, and
fitted on three countries they rank a fourth they were never fitted on
(Spearman +0.52 to +0.76, positive in every fold). Cut both at the median of the
68 measured splits:

| parent multiplier | parts | median error | worst |
|---|---|---:|---:|
| low | few | 4.8 % | 14.9 % |
| low | many | 7.0 % | 23.4 % |
| high | few | 7.9 % | 41.6 % |
| high | many | **18.6 %** | 48.1 % |

The report prints which band your split falls in. **It ranks; it does not
predict your number** — the spread inside each band is wide. And if another
country publishes your split, reading its error instead is worse, not better:
the band misses a held-out case by 3.7 points and the borrowed number by 4.9,
because one parent's spread varies by a median factor of 4.6 between countries.

**And how wrong is it if your key is RIGHT?** That is a different question and
it has been measured. Several countries publish a table where the office gives
both a parent and its parts, so a split can be scored against the real answer.
Across 68 such splits in 4 countries, **with the size key exactly right**, the
subsectors' multipliers land a median of 7.8 % from the published truth, and 15
of the 68 are out by more than 15 %. A perfect key does not buy a right answer:
the parts inherit the parent's average input structure and they do not have it.

What that error tracks is how **unlike** the parts are — the worst error is
about two thirds of the spread between their true multipliers, correlation
+0.92. Some sectors divide cleanly wherever you look (`J59_60`, `Q87_88`, `I`,
`J62_63`, all under 7 % median spread) and some do not (`C10-12`, `B`,
`N80-82`, `F`, 20 % to 35 %). You cannot read your own number off another
country — for the same parent the biggest country spread is typically 4.6 times
the smallest — but the ordering mostly holds, so a country that publishes your
split will tell you whether the sector is a safe one.

**Cell provenance.** Every cell of the new table is counted into one of four
statuses:

| Status | What it means |
|---|---|
| `OBSERVED` | Copied from the source table, untouched |
| `ESTIMATED` | Produced by your proxy |
| `BALANCED` | Produced by the solver to make the table add up |
| `user_constraint` | A value you pinned by hand |

**Read this as a map of what was estimated, not as a warning about your
multipliers.** On those same 68 splits, how much of the table a split had to
estimate has *no* relationship to how far the multipliers land from the truth —
correlation −0.01. A split can be badly wrong cell by cell and put its
multipliers inside 4 %, or be tidy in the cells and 40 % out.

A `BALANCED` figure is not an observation and must never be relabelled as one.
In a typical split, around 90 % of cells are untouched and 10 % come from your
key — which is a useful reminder that a disaggregation is a local operation,
not a new table.

**The Leontief checks.** Four of them, and they are about the multipliers the
report prints — a multiplier is a column sum of the Leontief inverse, so these
are checks on the number you are most likely to quote.

| Check | What it asks |
|---|---|
| `check_leontief_productive` | Is the spectral radius of the coefficient matrix below 1? Above it, multipliers are not large — they are undefined. |
| `check_leontief_identity` | Do `Ax + y = x` and `Ly = x` hold, within your source's own printed precision? |
| `check_leontief_inverse` | Was the inverse actually computed, given how well conditioned the system is? |
| `check_leontief_nonnegative` | Does the inverse contain negative entries? |

The last one deserves a note, because it warns rather than fails and it fires on
real published tables. A negative cell in the inverse says that more final
demand for one product *lowers* output of another. It follows from negative
cells in the table itself, which are legitimate — the ONS's own analytical table
has one, financial services into imputed rents, and that single cell produces 19
negatives in the inverse, all in one column. The multiplier for that column is
1.0828, which is 1.1705 minus 0.0877. The check names the column, so you know
which one multiplier to treat carefully rather than distrusting all of them.

**Validation.** Eleven or so further checks per scenario, each printing the
deviation it measured and, where it comes from one, citing the manual paragraph
and page.
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
