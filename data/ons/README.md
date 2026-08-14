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
