# `data/unsd/` — auxiliary data, with its provenance

Everything in this folder is **retrieved data, not derived data**. Each file
records where it came from, when, and by what query, so that any number the
engine produces can be traced back to a request someone else could repeat.

---

## `NACE2_ISIC4.txt`

**What it is.** The official correspondence table between NACE Rev. 2 (the EU
industrial classification) and ISIC Rev. 4 (the UN's), down to the four-digit
class level. 997 lines, header `"NACE2code","NACE2part","ISIC4code","ISIC4part"`.

**Source.** UN Statistics Division, Classifications Section — the freely
downloadable correspondence table collection at
`unstats.un.org/unsd/classifications/Econ`.

**Retrieved.** 2026-08-11, from
`https://unstats.un.org/unsd/classifications/Econ/tables/ISIC/NACE2_ISIC4/NACE2_ISIC4.txt`,
with explicit authorisation from the project owner.

**SHA-256** `1220d7f920783418b82d0da6d35cf90a31d69efae47e41835417f5a3bdd5ebfe`

**Access.** Open, unauthenticated, plain text — a UN classifications-office
publication, not a paywalled work. No licence restriction beyond ordinary
attribution.

**Why it is here — `OQ-S-01` and `M-052`.** RACE (`M-052`, from CORE_026)
converts a table from one classification to another using a **generic
correspondence table `G`** — which categories of the old classification may map
to which of the new. The method half of `OQ-S-01` was closed at v1.4; the
correspondence *content* was the remaining binding item, described in the entry
as "a download and a parse; it needs no source we lack." This is that download.

**What it does NOT resolve.** It maps *between* NACE Rev. 2 and ISIC Rev. 4 — it
says nothing about whether a given NACE or SIC code exists at all, or whether a
set of subdivisions exhausts their parent. That is a different gap
(`CORE_030_NACE_Rev2_1_Detailed_Structure.txt`, extracted the same day, answers
it with one caveat: it is Rev. 2.1's structure, one revision newer than the
Rev. 2 that the project's UK and Spanish fixtures are built on — see that
extraction's own note and `run_uk_classification.py`).
