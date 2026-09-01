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
| **Eurostat** | `data/eurostat/` — supply, use, valuation and symmetric tables (`naio_10_*`), employment by industry (`nama_10_a64_e`), structural business statistics | Commission reuse policy: reuse permitted with attribution |
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
privately. And `run_mrio_axis_scale` reads a 33 MB workbook that neither
repository tracks.

Nothing here fails for any of those absences — a validator that could not run
was removed rather than left to pass vacuously, which is the same rule in both
cases.
