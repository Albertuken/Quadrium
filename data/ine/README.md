# `data/ine/` — the Spanish input-output table, with its provenance

Everything in this folder is **retrieved data, not derived data**. Each file
records where it came from, when, and by what request, so that any number the
engine produces can be traced back to something someone else could repeat.

---

## `cne_tio_22.xlsx`

**What it is.** The Spanish symmetric input-output table for 2022, **product by
product**, at basic prices, 64 products, in millions of euros at current prices.

**Source.** INE (Instituto Nacional de Estadística), *Contabilidad Nacional
Anual de España, Revisión Estadística 2024* — **Tablas Input-Output 2022**.

**Retrieved.** 2026-08-10, 382,796 bytes.
**SHA-256** `7f466a4026a51d2d6e34da9ce31c4a56cabf14f9f4523c2932fa8386f606366e`

**The request, verbatim, so it can be re-run:**

```
https://www.ine.es/daco/daco42/cne24/cne_tio_22.xlsx
```

The filename pattern is **two digits**, not four: `cne_tio_16.xlsx` …
`cne_tio_22.xlsx` for 2016–2022. A first guess at `cne_tio_2022.xlsx` returns
404. The loader never reads the year from the filename anyway — two digits is
precisely the sort of thing `OQ-D-01` exists to stop it from believing — and
takes it from the workbook's own `Lista_Tablas` sheet instead.

**Vintage.** 2022 is the latest definitive TIO at the time of retrieval. The
2023 table is announced for December 2026.

### What is in the workbook

| Sheet | Contents | Used by the loader |
|---|---|---|
| `Lista_Tablas` | index, and the banner carrying the reference year | year |
| `Tabla1` | IOT at basic prices, **total** flows | `variant="total"`, and every value-added row |
| `Tabla2` | IOT of **domestic** output (*producción interior*) | `variant="interior"` (default) |
| `Tabla3` | IOT of **imports** | the imported-input row of the interior variant |
| `Tabla4`–`Tabla7` | technical coefficients and Leontief inverses, total and domestic | not loaded — used once to confirm the output denominator |
| `Tabla8` | correspondence of the TIO numbering with CPA 2008 / NACE | not loaded |

`Tabla2` carries no value added: the INE splits the framework into total /
domestic / imports, and the primary-input rows live only in `Tabla1`. Value
added belongs to the branch regardless of where its inputs came from, so the
interior variant takes `Z` and final demand from `Tabla2` and its primary
inputs from `Tabla1`, with imported intermediate consumption from the column
sums of `Tabla3`.

### Two traps in the layout

**Subtotals interleaved with their own components.** Five of them, in the
final-demand columns: *Total gasto en consumo final* sits next to the three
components it sums, *Formación bruta de capital* next to its two,
*Total exportaciones* next to its two. Summing the block as printed
double-counts everything. This is the same trap as the UK sheet's `P3 S1`, but
the UK detection rule — *a column whose code is a strict prefix of another's is
a subtotal of it* — cannot reach it, because these columns have no codes, only
Spanish prose. The loader therefore declares the groupings and **checks** each
subtotal against its components before dropping it.

**A product numbered `44 bis`.** The workbook's numeric index row runs 1…64, but
the INE's own product numbering does not: *Alquileres imputados de las viviendas*
is `44 bis`. `Tabla8` maps the *label* numbering to CPA, so that is the one kept
as the sector code.

### A discrepancy in the published data — `OQ-D-04`

The interior table does not satisfy the row identity for one product. Domestic
uses of **agricultural products** fall **4,921.6 million EUR** short of domestic
agricultural output, and uses of *imported* agricultural product exceed recorded
imports by exactly the same amount. The two cancel, which is why `Tabla1`
balances to the last decimal while `Tabla2` does not. No other product deviates
by more than 1 million EUR.

This is in the data, not in the parse. Every block reproduces the INE's own
published `Total demanda intermedia`, `Total demanda final` and `Total empleos`
columns to 1.5e-11 in all three sheets; `Tabla1 = Tabla2 + Tabla3` holds to
7.3e-12; and the denominator implied by the INE's own `Tabla4` and `Tabla5`
coefficients, recovered cell by cell, equals `Producción a precios básicos` in
all 64 branches to difference 0.000.

`load_ine_tio()` refuses the interior table by default. See `OQ-D-04` in
`library/specs/D_open_questions.md` for what would resolve it and for the two
ways past it.

---

## `cne_tio_16.xlsx` … `cne_tio_21.xlsx` — the rest of the published series

**What they are.** The same table, for **2016 to 2021**. Same statistical
revision, same 64 products, same basic prices, same URL pattern. Retrieved
2026-08-25; each file's URL, byte count and SHA-256 are in
`_provenance_2016_2022.json` beside them.

```
https://www.ine.es/daco/daco42/cne24/cne_tio_16.xlsx
...
https://www.ine.es/daco/daco42/cne24/cne_tio_21.xlsx
```

The matching `cne_tod_YY.xlsx` supply-use files for 2016–2021 are here too,
under the same URL pattern and recorded in the same sidecar. Every one of the
fourteen files reproduces its recorded SHA-256.

### The INE publishes this workbook in two shapes

Five of these six years refused to load until 2026-08-25, with

```
the INE workbook's layout no longer matches the one this loader hard-codes.
failed check: Tabla1 == Tabla2 + Tabla3 (intermediate block)
off by 29,086.9212
```

Nothing about the layout was wrong. The loader knew one shape and the office
publishes two. Every difference is the older vintage carrying **less**, never
carrying the same thing somewhere else:

| | 2016–2020 | 2021–2022 |
|---|---|---|
| sheets | 5 | 9 |
| `Tabla2` | technical coefficients | IOT of **domestic** output |
| `Tabla3` | Leontief inverse | IOT of **imports** |
| domestic/imports split | **not published** | published |
| `Importaciones de la UE` / `de terceros países` | labels printed, rows empty | populated |
| exports | one column, `Total exportaciones` | split UE / third countries |
| `Total demanda final` | column 76 | column 78 |

So `variant="interior"` is not merely unsupported for 2016–2020 — **the domestic
table does not exist to be read**. `load_ine_tio` now says that, and says what
loading `variant="total"` instead would cost: an imported input is treated as if
it had been produced in Spain, which overstates domestic effects.

The three consequences in the loader are `_ine_vintage()`, which reads each
file's own `Lista_Tablas` to decide which shape it is holding;
`_ine_columns()`, which reads header row 7 to pick the column map; and the
import-split check, which is skipped when both component rows are empty rather
than failing a populated row against a blank one. **The shape is read from what
the workbook prints, not inferred from the year in its name** — a third shape
would be refused, not mismapped.

Note what exports do between the two: in the older files `Total exportaciones`
is a **leaf**, in the newer ones a **subtotal** of two columns. That is why the
older column map has one subtotal group fewer rather than a group of one. A
subtotal checked against itself checks nothing, and would have hidden the
two-column offset in everything to its right.

### What the seven years say

| year | output at basic prices | shape |
|---:|---:|---|
| 2016 | 1,969,898 | total only |
| 2017 | 2,077,118 | total only |
| 2018 | 2,171,029 | total only |
| 2019 | 2,255,859 | total only |
| 2020 | **2,030,323** | total only |
| 2021 | 2,280,636 | split |
| 2022 | 2,664,587 | split |

Rising to 2019, falling in 2020, recovering after: the Spanish economy's actual
shape, which is the strongest evidence available that the older column map is
right. A loader that had quietly mismapped a column does not produce a pandemic.

Locked in by `library/validators/run_ine_series.py`.

---

## `cne_tod_22.xlsx` — **the file that should have been loaded first**

**What it is.** The Spanish **supply and use tables** for 2022 — the statistical
source from which the input-output table is derived.

**Source.** INE, *Contabilidad Nacional Anual de España, Revisión Estadística
2024* — Tablas de Origen y Destino 2022.
**Retrieved.** 2026-08-10, 345,069 bytes.
**SHA-256** `86cbcbf046432c9eacee9935bc55fa2052fbc7feea249fb468c43ee403cad7e9`

```
https://www.ine.es/daco/daco42/cne24/cne_tod_22.xlsx
```

**Why it matters more than its billing.** `OQ-S-05` opened on the INE's own
statement that it compiles at 91 products and publishes at 64, and asked whether
the honest next step for Spain was a data request. It was not. **Two of these
tables are published at 110 products by 81 branches** and were downloadable all
along — **in this edition**. The 2016–2020 files are 65 x 64, and the
qualification matters more than it looks: see the next section.

| sheet | contents | detail |
|---|---|---|
| `Tabla1` | supply at basic prices, with the transformation to purchasers' prices | **110 x 81** |
| `Tabla2` | use at purchasers' prices | **110 x 81** |
| `Tabla3` | use at basic prices | 64 x 64 |
| `Tabla4` | use of **domestic** output at basic prices | 64 x 64 |
| `Tabla5` | use of imports (CIF) | 64 x 64 |
| `Tabla8` / `Tabla9` | CPA 2008 / CNAE 2009 correspondences | — |

So there are four levels of detail in the Spanish system, not two: 110 products
in the purchasers'-price supply and use tables, 64 in the basic-price ones, 91
as the IOT's working level, 64 as the IOT published.

**What that settled for the pilot.** At 110 products, `73. Servicios de
alojamiento` (CPA 55) and `74. Servicios de comidas y bebidas` (CPA 56) are
separate, and their outputs are 30,717.7 and 97,548.8 — summing to 128,266.5,
the output of product 36 in the 64-product IOT, **to the last decimal**. The
split the pilot spent its effort estimating is published — **for 2021 and 2022.
For 2016 to 2020 it is not**, and product 36 is a single undivided
`Servicios de alojamiento y de comidas y bebidas`.

---

## `cne_tod_16.xlsx` … `cne_tod_21.xlsx` — and the same two shapes again

The supply-use workbook changes edition in the same year and the same
direction:

| | 2016–2020 | 2021–2022 |
|---|---|---|
| supply and use | **65 products x 64 activities** | 110 x 81 |
| basic-price, domestic and import use tables | not published | 64 x 64 |
| import origin, EU / third countries | not published | published |
| exports | one leaf column | subtotal of two |
| accommodation and food service | **one product** | two |

`load_ine_tod` had been written against `cne_tod_22.xlsx` and did not refuse the
older five — it raised a bare `IndexError` from inside a list comprehension.
Three things it had hard-coded are not constant:

1. **The two sheets of one workbook start in different columns.** In the older
   files the supply sheet has no leading blank column and the use sheet does. A
   single `first_col` reads the older supply table one column to the left of
   where it is.
2. **The activity index row is not 1, 2, 3, …** It carries `44a` — imputed
   rents of owner-occupied dwellings, split out of real estate — where the label
   column two rows below writes `44 bis.`. Two conventions for one thing, in one
   file. A run that accepts only the next integer stops at 44 and reads a
   65-activity table as a 44-activity one, which stays rectangular and is caught
   by nothing but an identity.
3. **Exports are a leaf, not a subtotal**, as in the symmetric workbook.

Every position is now found by the label the INE prints. The final-demand
subtotals are named; their *components* are not — they are whatever columns lie
between one subtotal and the next, which is how one rule reads a vintage that
splits exports in two and one that does not — and each inference is checked
against the subtotal it was inferred from before the subtotal is dropped.

### The cross-check that makes all of it readable

The supply table's total output and the input-output table's total output agree
**to 0.0000 in every one of the seven years**:

| year | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 |
|---|---|---|---|---|---|---|---|
| output | 1,969,898 | 2,077,118 | 2,171,029 | 2,255,859 | 2,030,323 | 2,280,636 | 2,664,587 |

These are two workbooks, compiled and published separately, read by two
different loaders through two different column maps. Trade and transport margins
sum to zero economy-wide in all seven, which is `ID-19` — the identity an
analytical input-output table cannot be asked at all, because its margins have
already been reallocated.

Locked in by `library/validators/run_ine_series.py`.

---

## `eee_hosteleria_cnae55_56_2018_2024.csv`

**What it is.** Operating-account variables plus employment and sales by
geographic destination, for **CNAE 55** (accommodation), **CNAE 56** (food and
beverage service) and their parent **I** (hostelería), for **2018–2024**, 224
rows. Every allocation key and every input profile in
`examples/es_hosteleria.py` comes from the 2022 rows.

The other six years are not decoration. They are the only place the project
holds the same proxy for the same two subsectors over a run of years, which is
what made it possible to **measure** what a stale key costs instead of guessing
— see `library/validators/run_key_vintage.py` and `OQ-B-14`.

**Source.** INE, **Estadística Estructural de Empresas: Sector Servicios**
(operation 130), tables **76815** (resultados de explotación), **76811**
(principales magnitudes) and **76816** (cifra de negocios por destino
geográfico de las ventas).

**Retrieved.** 2026-08-10.
**SHA-256** `21d5196cf0af2b48547474668ecc1dbcc93d2609f855c2f93c61fd1de78aba45`

**The requests, verbatim, so they can be re-run:**

```
https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/76815?nult=20
https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/76811?nult=20
https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/76816?nult=20
```

The `?nult=` is not decoration. Without a query string the endpoint answers 301
with an empty body, and the documented `tv=<group>:<value>` filter answers 500
on these three tables — so the whole table is fetched and filtered locally. The
activity identifiers are `21896` (I), `17585` (55) and `17586` (56), from
`VALORES_GRUPOSTABLA/76815/156554`.

**Why the file carries shares and not just levels.** The survey is on an
**enterprise/CNAE** basis and the table is on a **product/CPA** basis. The
survey's `valor de la producción` for hostelería is 92,401 million EUR against
the product's 128,266: it sees 72 %. Levels from this file must never be written
into the table; only ratios are usable, and even those carry the assumption that
the 28 % the survey does not see divides between 55 and 56 the same way. That is
assumption A-01 of the pilot.

**Internal consistency, checked on extraction.** For all sixteen variables,
CNAE 55 + CNAE 56 reproduces the published parent I to the last unit (deviations
of 0 or ±1 thousand EUR, which is rounding).
