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
| **ONS (United Kingdom)** | `data/ons/`, `UK_IOAT_2023_domestic_ixi.xlsx` — the analytical input-output tables and the Blue Book supply-use tables, 1997–2023 | Open Government Licence v3.0, Crown copyright |
| **INE (Spain)** | `data/ine/` — symmetric tables and supply-use tables, 2016–2022 | INE reuse conditions, attribution required |
| **UNSD** | `data/unsd/` — the NACE↔ISIC correspondence | United Nations, attribution required |

**Attribution, as the publishers ask for it.** Contains public sector
information licensed under the Open Government Licence v3.0. Source: Eurostat;
Office for National Statistics; Instituto Nacional de Estadística; United
Nations Statistics Division. Neither the publishers nor this project's author
endorse any use made of the results.

## What is deliberately NOT here

The methodological library — verbatim chapter text of the UN Handbook on Supply
and Use Tables, the 2025 SNA, the Eurostat 2008 manual and the OECD-EU handbook
— is **not in this repository and will not be**. Those are copyrighted
publications; the project holds them privately, cites them by paragraph and
page, and redistributes none of them.

That is why six validators are missing from this repository: `check_citations`,
`run_handbook_chapters`, `run_iot_provenance`, `run_p2_sweep`, `run_card_schema`
and `run_key_from_report` all read that library. They run privately against it.
Nothing here fails for their absence — a validator that could not run was
removed rather than left to pass vacuously.
