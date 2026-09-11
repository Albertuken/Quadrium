# `data/nuts/` — Eurostat's NUTS correspondence tables

Four tables, one per revision of the NUTS classification, each downloaded from
Eurostat's NUTS history page (`https://ec.europa.eu/eurostat/web/nuts/history`)
with its URL, byte count and SHA-256 in the `.provenance.json` beside it and in
`library/SOURCE_REGISTER.md` §7.

| file | revision | sheets read |
|---|---|---|
| `NUTS2010-NUTS2013.xls` | 2010 → 2013 | `NUTS2010-NUTS2013`, `Correspondence NUTS-2` |
| `NUTS2013-NUTS2016.xlsx` | 2013 → 2016 | `NUTS2013-NUTS2016`, `Correspondence NUTS-2` |
| `NUTS2021.xlsx` | 2016 → 2021 | `Changes detailed NUTS 2016-2021`, `Changes NUTS-2` |
| `NUTS2021-NUTS2024.xlsx` | 2021 → 2024 | `NUTS2021- NUTS2024`, `Changes NUTS-2` |

The 2016-to-2021 changes are not a file of their own: they are sheets of the
NUTS 2021 classification. The 2010 table is the old `.xls` format and is read
with `xlrd`, which is a checking dependency and not an engine one; without it
the validators say which step they could not read.

## What they are for

**The European MRIO's region codes are four vintages.** Greece is on NUTS 2010,
France and Poland on NUTS 2013, Hungary, Ireland and Lithuania on NUTS 2016,
and Croatia on NUTS 2021 (HR02, HR05 and HR06 are the 2021 split of HR04).
Eurostat's regional data are served on NUTS 2024.

Each table's NUTS-2 change sheet says, code by code, whether a change was a new
code for the same territory ("recoded", "code change") or something else — a
boundary shift, a split, a merge. Only the first kind is translated.

- `run_mrio_nuts_join.py` uses the first two to identify the vintages of the
  archive's own labels.
- `run_mrio_eurostat_codes.py` follows every region through all four and
  rebuilds the two lists the engine holds for `mrio_employment`:
  `config.MRIO_EUROSTAT_CODE` (35 regions that kept their territory: 21 French,
  9 Greek, 5 Polish) and `config.MRIO_REDRAWN` (PL12, split in 2016; NL31,
  NL33, PT16, PT17 and PT18, redrawn in 2024).

The engine does not read these files at run time. The two lists are constants,
so an installed engine needs none of this; the validator is what keeps the
lists and the published tables in agreement.
