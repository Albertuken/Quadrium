# Where the data came from, and under what terms

Everything under `data/` and the workbook at the repository root is **official
statistics**, fetched by this project and recorded with its URL, byte count and
SHA-256. No file here is derived, cleaned or re-keyed: they are the publishers'
own bytes, so any result in this repository can be re-checked against the
source.

Each directory carries its own `README.md` with the per-file record — request
URL, retrieval date, size, hash, and what the file was fetched for.

| Source | What | Reuse terms |
|---|---|---|
| **Eurostat** | `data/eurostat/` — supply, use, valuation and symmetric tables (`naio_10_*`), employment by industry (`nama_10_a64_e`), structural business statistics; `data/nuts/` — the NUTS 2010→2013 and 2013→2016 correspondence tables | Commission reuse policy: reuse permitted with attribution |
| **ONS (United Kingdom)** | `data/ons/`, `UK_IOAT_2023_domestic_ixi.xlsx` — the analytical input-output tables (six editions, 2019–2023) and the Blue Book supply-use tables, 1997–2023 | Open Government Licence v3.0, Crown copyright |
| **INE (Spain)** | `data/ine/` — symmetric tables and supply-use tables, 2016–2022 | INE reuse conditions, attribution required |
| **UNSD** | `data/unsd/` — the NACE↔ISIC correspondence | United Nations, attribution required |
| **Zenodo / Scientific Data** | `data/mrio/truth/` — survey-based regional input-output tables for nine Austrian NUTS-2 regions, plus Finnish and Scottish regional tables | Data CC BY 4.0; code MIT |

**Attribution, as the publishers ask for it.** Contains public sector
information licensed under the Open Government Licence v3.0. Source: Eurostat;
Office for National Statistics; Instituto Nacional de Estadística; United
Nations Statistics Division. Neither the publishers nor this project's author
endorse any use made of the results.

The regional tables under `data/mrio/` are redistributed under CC BY 4.0 from
Huang, S. et al., *European multi regional input output data for 2008–2018*,
Scientific Data 10 (2023), Zenodo record 7875024. The Austrian tables within it
are from Rokicki, Bartlomiej, et al., *Survey-based versus algorithm-based
multi-regional input–output tables within the CGE framework — the case of
Austria*, Economic Systems Research 33(4): 470–491 (2021). Unmodified: the files
are the archive's own bytes.

## What is deliberately NOT here

The methodological library — verbatim chapter text of the UN Handbook on Supply
and Use Tables, the 2025 SNA, the Eurostat 2008 manual and the OECD-EU handbook
— is **not in this repository and will not be**. Those are copyrighted
publications; the project holds them privately, cites them by paragraph and
page, and redistributes none of them.

That is why several validators are missing from this repository.
`check_citations`, `run_handbook_chapters`, `run_iot_provenance`, `run_p2_sweep`,
`run_card_schema` and `run_key_from_report` all read that library.
`run_docs_current` and `run_box183_provenance` audit documents that live only in
the private tree.

Two more are missing for a different reason, and it is data rather than
copyright. The Catalan tables (IDESCAT) are not redistributed here because their
reuse terms have not been read, which is the owner's call and not a technical
one — so `run_regionalisation_crosshauling`, `run_idescat_catalonia`,
`run_es_cat_bridge`, `run_charm_heterogeneity` and `run_flq_delta` run
privately.

A third group is here and **says out loud that it cannot run**, which is a
different answer from the two above and is stated rather than left to be
inferred. `run_mrio_axis_scale`, `run_mrio_nuts_join`, `run_mrio_side_join`,
`run_mrio_real_output`, `run_mrio_spillovers` and
`run_spillover_predictability` all read the 33 MB European MRIO workbook.
Neither repository tracks it, and the reason is its size rather than its
licence: it is CC BY 4.0 and could be redistributed, but the archive holds
eleven such workbooks and git is the wrong place for them. It is one download
away for anyone — Huang & Koutroumpis, Zenodo record 7875024 — and the URL,
byte count and SHA-256 are in `data/mrio/_provenance.json`.
With the workbook in `data/mrio/`, all six run and reproduce what they report.
`run_reachability` reads a record taken by a tool that lives in the private
tree. Each of them, run without its instrument, reports **which instrument it
does not have** and exits without asserting anything.

`run_mrio_axis_scale` was in the private group until 2026-09-06, on the
reasoning that a validator with nothing to run against should be removed rather
than shipped broken. The reasoning was sound and the file was the wrong one:
five of the validators above import it, so the tree it was removed from had no
state in which they worked — without the workbook they returned early, and with
it they died on the missing import. All six read the same file, so all six
ship.

That is not the same as passing vacuously and the distinction is the point: a
check that quietly returns success on evidence it never saw is the failure this
project keeps finding in itself, so each of these names the missing file and
what it would have established. A validator that could not run and could not
say so was removed instead — the rule for the two groups above.
