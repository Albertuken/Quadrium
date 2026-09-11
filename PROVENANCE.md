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
| **Eurostat** | `data/eurostat/` — supply, use, valuation and symmetric tables (`naio_10_*`), employment by industry (`nama_10_a64_e`), regional employment (`nama_10r_3empers`), structural business statistics; `data/nuts/` — the NUTS 2010→2013, 2013→2016, 2016→2021 and 2021→2024 correspondence tables | Commission reuse policy: reuse permitted with attribution |
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
tree, and seven more — `run_automation_limits`, `run_core082_acquisition`,
`run_eurostat_negatives`, `run_h_approach`, `run_topdown_procedure`,
`run_type_ii_multipliers` and `run_tolerance_absent` — quote chapter text from
the methodological library, which is the first group's reason applied to a file
rather than to a validator: the chapter cannot travel, so here they read
nothing.

`run_mrio_axis_scale` was in the private group until 2026-09-06, on the
reasoning that a validator with nothing to run against should be removed rather
than shipped broken. The reasoning was sound and the file was the wrong one:
five of the validators above import it, so the tree it was removed from had no
state in which they worked — without the workbook they returned early, and with
it they died on the missing import. All six read the same file, so all six
ship.

### And until 2026-09-06 they said it and then passed anyway

The paragraph above used to end by claiming that each of them "exits without
asserting anything", and that a check quietly returning success on evidence it
never saw is the failure this project keeps finding in itself. The first half
was true and the second was not honoured. They named the missing file, printed
`All checks passed.`, and exited 0 — so `./check.sh` counted all thirteen among
its passing validators, and its summary line could not distinguish a validator
that had measured 2,720 region-sectors from one that had opened no file. The
sentence describing the fault was three lines from the code committing it.

The fix is that **a validator which read nothing exits 3**, prints
`Nothing was checked: <file> is absent.` in place of a verdict, and is counted
apart:

```
2 validator(s) CHECKED NOTHING. They are not counted as passing:
    run_mrio_spillovers.py           data/mrio/MRIO_2018_272regions.xlsx is absent.
    run_reachability.py              library/tools/sweep_reachability.py is absent.

106 validators passed in 121s; 2 checked nothing.
```

Exit 3 is **not** a failure, and making it one would be the opposite error. A
checkout that does not hold the workbook is the normal, supported state of this
repository; `./check.sh` still exits 0 on it and CI runs on exactly such a tree.
The distinction being drawn is between *checked and passed* and *did not
check* — a statement about what evidence was in front of the validator, not
about whether the code is correct.

Two neighbouring cases are deliberately **not** in this group, because the
difference is the whole point. `run_grit_cell_ranking` skips one source-text
check when GRIT II's private extraction is absent and then runs its entire
arithmetic battery on two economies instead of three: it measured something, so
it passes and says how much it had. `run_mrio_nuts_join` has both shapes in one
file — without the NUTS correspondence tables it checks nothing and exits 3,
while with the tables and without the workbook it verifies the correspondence,
reports that the composition against the archive is what it could not reach, and
passes on the five checks it actually ran. A partial run is a result. A run with
no inputs is not.

A validator that could not run and could not say so is still removed instead —
the rule for the two groups above, and the reason this third group exists at all
is that these can say so, and can name the one download that would make them
run.
