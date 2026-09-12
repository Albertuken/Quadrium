"""
Drive the whole engine from a spreadsheet.

WHY A WORKBOOK AND NOT A USER INTERFACE
---------------------------------------
The inputs to a disaggregation are tables of numbers with metadata: which
sectors to divide, the new codes, the proxies with their source and year, the
relative purchasing intensities by supplier. That is what a spreadsheet is for,
and an economist is faster in one than in any form. Forty intensity values are
a column, not forty input boxes.

It is also the honest choice about verification: a workbook-driven run can be
checked end to end by running it, which a screenful of buttons cannot.

THE WORKBOOK
------------
Five sheets. Only `project` and `splits` are required.

`project`   key/value rows: project_id, table_path, table_kind, title, notes.
            `table_kind` is one of:
              `uk_analytical`  the ONS workbook, industry by industry
              `ine_interior`   the INE workbook, domestic output (product by
                               product) — the Spanish counterpart
              `ine_total`      the INE workbook, total flows
              `interchange`    the project's own format
              `eurostat`       fetched from the Eurostat API by country and
                               year, and cached — see below
              `eu_mrio`        one region of the European MRIO (Huang and
                               Koutroumpis 2023), named by `mrio_region`,
                               for `mrio_year` 2008-2018 (default 2018).
                               The archive does not balance and the residue
                               is carried in a labelled column and row.
                               `mrio_employment: yes` attaches Eurostat's
                               employed persons for that region and year
                               as the account `employment`
            `table_unbalanced` (`refuse` by default, or `residual_column`)
            applies to `ine_interior` alone, whose published table does not
            balance for one product — see OQ-D-04. Setting it on any other kind
            is an error rather than something quietly ignored.

`splits`    one row per NEW subsector:
              sector_code | new_code | new_label | key_id
            Rows sharing a `sector_code` form one split. `key_id` names the
            allocation key for that split; blank falls back to the scenario.

`keys`      one row per subsector per key:
              key_id | new_sector_code | value | source | source_year | strength
            `strength` is strong / medium / weak.

            A KEY YOU DO NOT USE IS NOT WASTED. Any key registered here whose
            `key_id` no split or scenario names becomes an automatic external
            check: the report compares the split it produced against what that
            key measures, and prints the gap. If you have employment AND
            turnover, put both in and drive with one — the other buys you an
            error bar, which nothing else in this system can give you.

`scenarios` one row per scenario:
              scenario_id | label | description | internal_block_alpha
            Blank alpha uses the default 1.0 -- CORE_031 eq. (14), the
            outer product of the weights. Raising it concentrates the block
            on its diagonal and the off-diagonal pays for it, so the parent
            cell is conserved either way; published tables sit around 1.5
            (OQ-S-04). If the sheet is missing, one
            scenario named `S1` is created.

`profiles`  one row per (scenario, subsector, supplier) intensity:
              scenario_id | subsector_code | supplier_code | intensity
            1.0 means the parent sector's average. Scenarios absent from this
            sheet simply have no profiles, which is how a "plain" and a
            "profiled" scenario are written side by side.

FETCHING RATHER THAN NAMING A FILE
-----------------------------------
`table_kind: eurostat` replaces `table_path` with a country and a year:

    eurostat_geo       ES, AT, FR … the two-letter code
    eurostat_year      2022
    eurostat_dataset   product_by_product (default) | industry_by_industry
                       | a raw naio_10_* code
    eurostat_variant   domestic (default) | total
    table_path         optional: where to cache. Defaults to
                       data/eurostat/<dataset>_<GEO>_<year>.json beside the
                       configuration.

**A cached file is never re-fetched.** This is the reproducibility rule, and it
is the reason `eurostat.fetch()` and `eurostat.load_iot()` were built as
separate functions in the first place: statistical offices revise, so a
configuration that downloaded on every run would give one answer in January and
another in June with nothing in the output to say why. The first run downloads
and records the URL, the byte count and the SHA-256; every run after it reads
those same bytes and never touches the network. `--refresh` overrides that
deliberately and says what it is doing; `--offline` refuses to fetch at all and
prints the URL so the file can be brought in by hand.

Everything the workbook cannot express is a project default, and every default
is documented where it lives. Nothing here invents an economic assumption.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .io_loader import LoaderError, _open_workbook, load_eu_mrio, \
    load_ine_tio, load_io_table, load_uk_analytical_iot
from .models import (AllocationKey, Assumption, AssumptionLedger,
                     ProxyStrength, Satellite, Scenario, SplitSpec)

REQUIRED_SHEETS = ("project",)
# A workbook describes ONE of two jobs: dividing a sector or estimating a
# region. It needs `splits` for the first and `regionalise` for the second, and
# `splits` was unconditionally required until v1.86 -- which is why
# regionalisation only existed as command-line flags, in a tool whose guide
# opens by promising you will not need Python.
# THREE jobs, not two: `targets` with `table_kind: eurostat_sut` describes a
# projection, which has no splits either. The first version of this check
# listed only the first two and refused every projection workbook.
ONE_OF_SHEETS = ("splits", "regionalise", "targets")
TABLE_KINDS = ("uk_analytical", "interchange",
               "ine_interior", "ine_total", "eurostat", "eurostat_sut",
               "eu_mrio")

# Why a type II closure cannot be built on the European MRIO. Said in two
# places -- the gate and `--plan` -- so it is one string.
_EU_MRIO_NO_TYPE_II = (
    "the European MRIO publishes value added as ONE row, `VA`, with no split "
    "between wages and profits, so there is no row of household income to "
    "close on. Naming `VA` would close the model on profits as if households "
    "received them, and the result would look like an induced effect and not "
    "be one")

# What `--template` seeds into `table_path`. Named here because the refusal
# below has to recognise it: the first thing a new user does is run the
# template unchanged, and the file it points at ships with the SOURCE
# CHECKOUT, so anyone who installed the package cannot have it. Kept as one
# constant so the seed and the message that explains it cannot drift.
TEMPLATE_TABLE_PATH = "../UK_IOAT_2023_domestic_ixi.xlsx"


def _yes(value) -> bool:
    """A spreadsheet cell that means yes, in the forms a user actually types.

    Excel turns some of these into a real bool and leaves others as text, and a
    user writing `si` in a Spanish workbook means the same as one writing
    `TRUE`. An unrecognised value is FALSE and not an error: this switch only
    adds a section to the report, so a typo costs a missing section rather than
    a refused run -- and the report says when the section is absent.
    """
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in (
        "yes", "y", "true", "1", "si", "sí", "on")


class ConfigError(ValueError):
    """Something in the workbook is wrong, said in the analyst's terms."""


def _eurostat_cache_path(meta: dict, base_dir: Path) -> tuple[Path, dict]:
    """Where the download lives, and what to ask for if it is not there yet.

    Returns the cache path and the request it stands for. Nothing here touches
    the network: this only resolves what the workbook asked for into a filename
    and a set of API parameters, so that a configuration can be READ, and its
    mistakes reported, without a connection.
    """
    from .eurostat import DATASETS

    geo = str(_need(meta, "eurostat_geo", "project", 0)).strip().upper()
    if not (len(geo) == 2 and geo.isalpha()):
        raise ConfigError(
            f"eurostat_geo is {geo!r}. It must be a two-letter country code — "
            f"ES, AT, FR, PT. Eurostat answers an unknown code with an empty "
            f"result rather than an error, so this is checked here instead.")
    try:
        year = int(str(_need(meta, "eurostat_year", "project", 0)).strip())
    except ValueError:
        raise ConfigError(
            f"eurostat_year is {meta.get('eurostat_year')!r}, which is not a "
            f"year.") from None

    name = str(meta.get("eurostat_dataset")
               or "product_by_product").strip().lower()
    dataset = DATASETS.get(name, name)
    if not dataset.startswith("naio_10_"):
        raise ConfigError(
            f"eurostat_dataset {name!r} is neither one of "
            f"{', '.join(sorted(DATASETS))} nor a naio_10_* code.")

    variant = str(meta.get("eurostat_variant") or "domestic").strip().lower()
    if variant not in ("domestic", "total"):
        # `imports` is refused for a reason worth repeating here rather than
        # letting the loader raise it after the download: Eurostat publishes no
        # output vector for the imported block, so it is an input table and not
        # a symmetric IOT.
        raise ConfigError(
            f"eurostat_variant {variant!r} must be 'domestic' (the default, "
            f"and what Leontief analysis wants) or 'total'. 'imports' is an "
            f"input table, not a symmetric IOT — Eurostat publishes no output "
            f"vector for it, so the column identity has nothing to close "
            f"against.")

    raw = meta.get("table_path")
    if raw and str(raw).strip():
        path = Path(str(raw).strip())
    else:
        path = Path("data") / "eurostat" / f"{dataset}_{geo}_{year}.json"
    if not path.is_absolute():
        path = (Path(base_dir) / path).resolve()

    return path, {"dataset": dataset, "geo": geo, "year": year,
                  "variant": variant}


def _eurostat_sut_paths(meta: dict, base_dir: Path) -> tuple[Path, dict]:
    """Where the three files of a supply-use system live, and what to ask for.

    A symmetric table is one download. A supply-use SYSTEM is three, and they
    are not interchangeable:

        naio_10_cp15    supply at basic prices, with its valuation columns
        naio_10_cp16    use at purchasers' prices
        naio_10_cp1610  use at BASIC prices, split DOM / IMP

    The third is the one that makes a transformation possible. Without it the
    domestic and imported halves would have to be derived, which means assuming
    every user of a product imports the same share of it -- an economic
    hypothesis, not bookkeeping, and not one this engine makes for anybody.
    """
    from .eurostat import DATASETS

    geo = str(_need(meta, "eurostat_geo", "project", 0)).strip().upper()
    if not (len(geo) == 2 and geo.isalpha()):
        raise ConfigError(
            f"eurostat_geo is {geo!r}. It must be a two-letter country code.")
    try:
        year = int(str(_need(meta, "eurostat_year", "project", 0)).strip())
    except ValueError:
        raise ConfigError(
            f"eurostat_year is {meta.get('eurostat_year')!r}, not a year."
        ) from None

    model = str(meta.get("eurostat_model") or "D").strip().upper()
    if model not in ("A", "B", "C", "D"):
        raise ConfigError(
            f"eurostat_model {model!r} must be one of the four in CORE_013 "
            f"Figure 12.2, p. 378:\n"
            f"  A  product technology            product x product\n"
            f"  B  industry technology           product x product\n"
            f"  C  fixed industry sales          industry x industry\n"
            f"  D  fixed product sales           industry x industry\n"
            f"A and C need a square supply table and may produce negative "
            f"cells; B and D cannot produce them. Which is right is not a "
            f"question the data answers.")

    raw = meta.get("table_path")
    root = Path(str(raw).strip()) if raw and str(raw).strip() \
        else Path("data") / "eurostat"
    if not root.is_absolute():
        root = (Path(base_dir) / root).resolve()
    if root.suffix:                       # a file was named; use its folder
        root = root.parent
    # A supply-use system caches THREE files, so `table_path` names a folder.
    # If something is already there and is not one, say so: the alternative is
    # a FileExistsError from `mkdir` several frames down, which is what a
    # `table_path` shared with a single-file `eurostat` run produced.
    if root.exists() and not root.is_dir():
        raise ConfigError(
            f"table_path is {root}, which exists and is a file. A supply-use "
            f"system caches three downloads, so this names the FOLDER they go "
            f"in — not one of them. Leave it blank for data/eurostat, or point "
            f"it at a directory.")

    files = {name: root / f"{DATASETS[name]}_{geo}_{year}.json"
             for name in ("supply", "use_purchasers", "use_basic")}
    unbalanced = str(meta.get("sut_unbalanced") or "refuse").strip().lower()
    if unbalanced not in ("refuse", "cancelling"):
        raise ConfigError(
            f"sut_unbalanced {unbalanced!r} must be 'refuse' (the default) or "
            f"'cancelling'.\n\n"
            f"`cancelling` admits ONE case: a closing identity out beyond what "
            f"the source's own precision allows, whose residues SUM TO ZERO "
            f"and sit in lines the message names — a boundary between two "
            f"industries rather than a table that fails to add up.\n\n"
            f"No source this project holds currently needs it. It was written "
            f"for Belgium's 2022 pair, +0.8 on L68A and -0.8 on L68B and 0.000 "
            f"on the other 87, which turned out to be INSIDE what Belgium's "
            f"one-decimal printing allows once the precision was read off the "
            f"figures the file actually uses rather than off two anomalous "
            f"cells in 2,829.\n\n"
            f"It does not admit residues that accumulate. Whatever is missing "
            f"from a table as a whole stays missing, and the load stops.")

    to_year = meta.get("project_to_year")
    # NO DEFAULT, AND THAT IS THE POINT.
    #
    # It defaulted to `sut_euro`, which is the worse of the two methods on
    # every test that has been run (`OQ-B-16`), so a user who said nothing got
    # the loser by silence. Changing the default to `sut_ras` would have moved
    # the problem rather than removed it.
    #
    # The two methods take DIFFERENT targets, so the `targets` sheet already
    # says which one the user means: nobody can reach a default by accident,
    # because they had to write `gva` rows or `industry_output` rows to get
    # anywhere. `project_method` is now an OPTIONAL declaration that has to
    # agree with the sheet, and `_project` reads the method off the sheet.
    raw = str(meta.get("project_method") or "").strip().lower()
    if raw and raw not in ("sut_euro", "sut_ras"):
        raise ConfigError(
            f"project_method {raw!r} must be 'sut_euro' or 'sut_ras', or "
            f"left out — the `targets` sheet says which one you mean.\n\n"
            f"They project onto different quantities:\n"
            f"  sut_euro   gva (one per industry, BASIC prices)\n"
            f"             final_use (one per category, PURCHASERS' prices)\n"
            f"             taxes, imports (one row each, totals)\n"
            f"  sut_ras    industry_output (one per industry)\n"
            f"             use_column_totals (one per industry, then one per\n"
            f"                 final-use category — each industry's output\n"
            f"                 LESS its value added)\n"
            f"             taxes, imports (one row each; their sum is the "
            f"total this method balances against)")
    pmethod = raw or None
    if to_year not in (None, ""):
        try:
            to_year = int(str(to_year).strip())
        except ValueError:
            raise ConfigError(
                f"project_to_year is {meta.get('project_to_year')!r}, not a "
                f"year.") from None
    else:
        to_year = None

    return root, {"geo": geo, "year": year, "model": model, "files": files,
                  "took_default_model": not meta.get("eurostat_model"),
                  "project_to_year": to_year, "project_method": pmethod,
                  "unbalanced": unbalanced}


def _project(sut, req: dict, targets: list, defaults: list):
    """Move a supply-use pair to a later year, onto totals from the `targets`
    sheet.

    THE SHEET IS FOUR KINDS OF ROW, and each is a different shape of fact:

        gva         one row per industry, its code, value added at BASIC prices
        final_use   one row per final-use category, at PURCHASERS' prices
        taxes       one row, the total
        imports     one row, the total

    The price bases are not decoration. The method carries taxes as a row of
    the use table, so a final-use target has to include them; getting that
    wrong does not fail loudly, it runs to the iteration ceiling with every
    value-added deviation reading 1.00003, which looks like success. What tells
    the two apart is projecting a pair onto its OWN totals and requiring the
    pair back -- exactly, in one iteration, which is what happens when the
    bases are right.
    """
    import numpy as np

    VOCAB = {"sut_euro": ("gva", "final_use", "taxes", "imports"),
             "sut_ras": ("industry_output", "use_column_totals",
                         "taxes", "imports")}
    SHARED = ("taxes", "imports")

    kinds = []
    for n, r in enumerate(targets, start=2):
        kind = str(_need(r, "kind", "targets", n)).strip().lower()
        known = {k for v in VOCAB.values() for k in v}
        if kind not in known:
            raise ConfigError(
                f"targets row {n}: kind {kind!r} is not one of "
                f"{', '.join(sorted(known))}.")
        kinds.append(kind)

    # THE SHEET SAYS WHICH METHOD, BECAUSE ONLY THE SHEET KNOWS WHAT YOU HAVE.
    #
    # `gva` and `final_use` belong to SUT-EURO, `industry_output` and
    # `use_column_totals` to SUT-RAS, and `taxes` and `imports` to both. A
    # sheet carrying rows of one distinctive set has already chosen. The
    # question a user can answer is "what do I know about the later year?",
    # not "which of two methods from chapter 18 do I want", and this is the
    # place that difference shows up.
    seen = set(kinds)
    votes = {m: seen & (set(v) - set(SHARED)) for m, v in VOCAB.items()}
    chosen = [m for m, hit in votes.items() if hit]
    if len(chosen) != 1:
        lines = "\n".join(
            f"      {m:<9} {', '.join(k for k in VOCAB[m] if k not in SHARED)}"
            for m in VOCAB)
        raise ConfigError(
            ("the `targets` sheet mixes the two projection methods' rows: "
             + ", ".join(sorted(seen)) if len(chosen) > 1 else
             "the `targets` sheet carries no rows that say which projection "
             "method you mean")
            + f".\n\n  What do you know about {req['project_to_year']}?\n"
            + lines
            + "\n      both      taxes, imports\n\n"
            + "  Write the rows for what you have. There is no default: "
              "`sut_ras` is the better\n  of the two on every test run "
              "(OQ-B-16) but it needs industry outputs, and\n  picking one "
              "for you would be choosing what you measured.")
    method = chosen[0]
    if req.get("project_method") and req["project_method"] != method:
        raise ConfigError(
            f"project_method says {req['project_method']!r} and the `targets` "
            f"sheet carries {', '.join(sorted(votes[method]))}, which is what "
            f"{method!r} takes.\n\nLeave `project_method` out and the sheet "
            f"decides, or make the two agree.")
    wanted = VOCAB[method]
    by_kind: dict = {}
    for n, (r, kind) in enumerate(zip(targets, kinds), start=2):
        try:
            value = float(r.get("value"))
        except (TypeError, ValueError):
            raise ConfigError(
                f"targets row {n}: value {r.get('value')!r} is not a number."
            ) from None
        by_kind.setdefault(kind, []).append(
            (str(r.get("code") or "").strip(), value))

    for kind in wanted:
        if kind not in by_kind:
            raise ConfigError(
                f"the `targets` sheet has no {kind!r} row(s). A "
                f"`{method}` projection needs all four: "
                f"{', '.join(wanted)}.")

    def vector(kind, codes, what):
        given = dict(by_kind[kind])
        missing = [c for c in codes if c not in given]
        extra = [c for c in given if c not in codes]
        if missing or extra:
            raise ConfigError(
                f"the {kind!r} targets do not match this pair's {what}.\n"
                + (f"  missing: {', '.join(missing[:8])}"
                   + ("…" if len(missing) > 8 else "") + "\n" if missing else "")
                + (f"  not in the table: {', '.join(extra[:8])}"
                   + ("…" if len(extra) > 8 else "") if extra else ""))
        return np.array([given[c] for c in codes], float)

    live_a = [c for c, g in zip(sut.activity_codes, sut.g) if g > 0]

    if method == "sut_ras":
        # SUT-RAS is given industry output and use column totals and imposes
        # them, rather than approaching value added iteratively. Wired here
        # because leaving the better method reachable only from Python is the
        # same "built, verified and unreachable" fault the engine keeps finding
        # in itself. See OQ-B-16 and `run_projection_backtest.py`.
        cols = list(live_a) + list(sut.Y_labels)
        projected = sut.project(
            method="sut_ras", year=req["project_to_year"],
            taxes=by_kind["taxes"][0][1], imports=by_kind["imports"][0][1],
            industry_output=vector("industry_output", live_a,
                                   "industries with output"),
            use_column_totals=vector("use_column_totals", cols,
                                     "use columns (industries then "
                                     "final-use categories)"))
        print(f"    Projected {sut.year} -> {req['project_to_year']} by "
              f"sut_ras: output {sut.q.sum():,.0f} -> "
              f"{projected.q.sum():,.0f} "
              f"({100 * (projected.q.sum() / sut.q.sum() - 1):+.2f} %)")
        return projected

    gva = vector("gva", sut.activity_codes, "industries") \
        if len(by_kind["gva"]) == len(sut.activity_codes) \
        else vector("gva", live_a, "industries with output")
    if len(gva) == len(live_a) and len(live_a) != len(sut.activity_codes):
        full = np.zeros(len(sut.activity_codes))
        full[[i for i, g in enumerate(sut.g) if g > 0]] = gva
        gva = full
        defaults.append(
            f"the gva targets cover the {len(live_a)} industries with output "
            f"and not the {len(sut.activity_codes)} in the table; the rest "
            f"were taken as zero, which is what they already are")

    projected = sut.project(
        gva=gva, final_use=vector("final_use", list(sut.Y_labels),
                                  "final-use categories"),
        taxes=by_kind["taxes"][0][1], imports=by_kind["imports"][0][1],
        method="sut_euro", year=req["project_to_year"])
    print(f"    Projected {sut.year} -> {req['project_to_year']} by "
          f"{method}: output "
          f"{sut.q.sum():,.0f} -> {projected.q.sum():,.0f} "
          f"({100 * (projected.q.sum() / sut.q.sum() - 1):+.2f} %)")
    return projected


def _load_eurostat_sut(req: dict, offline: bool, refresh: bool,
                       defaults: list, targets: list):
    """Fetch or read the three files, then transform by the named model."""
    import json

    from .eurostat import EurostatError, fetch, load_sut

    if req["took_default_model"]:
        defaults.append(
            "no `eurostat_model` was named, so model D (fixed product sales "
            "structure) was used. CORE_013 par. 12.76, p. 393 recommends it "
            "for rectangular tables and it cannot produce negative cells, but "
            "IT IS STILL A CHOICE ABOUT SECONDARY PRODUCTION and the four "
            "models give four different tables from the same data")

    for name, path in req["files"].items():
        side = path.with_suffix(path.suffix + ".provenance")
        if path.exists() and not refresh:
            continue
        if offline:
            raise ConfigError(
                f"--offline was given and {path.name} is not cached yet. A "
                f"supply-use system needs all three of "
                f"{', '.join(p.name for p in req['files'].values())}.")
        try:
            rec = fetch(name, req["geo"], req["year"], path)
        except EurostatError as exc:
            raise ConfigError(
                f"the Eurostat download failed on {name}:\n{exc}\n\n"
                f"A supply-use system needs all three files; nothing was "
                f"transformed.") from None
        side.write_text(json.dumps(rec, indent=2))
        print(f"    Downloaded {rec['dataset']} {req['geo']} {req['year']} — "
              f"{rec['bytes']:,} bytes, SHA-256 {rec['sha256'][:16]}…")

    try:
        sut = load_sut(req["files"]["supply"], req["files"]["use_purchasers"],
                       req["files"]["use_basic"],
                       unbalanced=req.get("unbalanced", "refuse"))
    except EurostatError as exc:
        raise ConfigError(f"the supply-use pair could not be built:\n{exc}"
                          ) from None

    print(f"    Supply-use: {sut.V.shape[0]} products x {sut.V.shape[1]} "
          f"activities, {sut.q.sum():,.0f} {sut.unit}")
    for chunk in (sut.notes or "").split("CLOSURE:")[1:]:
        for part in chunk.strip().rstrip(".").split("; "):
            if part.startswith("ADMITTED"):
                # Split on the marker, not on the first colon: the note
                # itself contains one, inside `sut_unbalanced: cancelling`.
                marker = "`sut_unbalanced: cancelling`: "
                body = part.split(marker, 1)[-1] if marker in part else part
                defaults.append(
                    "`sut_unbalanced: cancelling` was set, and it admitted a "
                    "real discrepancy — " + body)
            else:
                defaults.append("the source's closing identities lean rather "
                                "than cancel — " + part)

    if req.get("project_to_year"):
        sut = _project(sut, req, targets, defaults)
    try:
        table = sut.to_iot(req["model"])
    except (ValueError, ArithmeticError) as exc:
        raise ConfigError(
            f"model {req['model']} could not transform this system:\n{exc}"
        ) from None
    print(f"    Transformed by model {req['model']} -> {table.n} sectors, "
          f"{int((table.Z < 0).sum())} negative cell(s) in Z")

    # THE THREE FILES, ON THE TABLE. A supply-use system has no single source
    # file to checksum, so the manifest records none; the provenance has to
    # travel with the table instead, or a reader cannot tell which vintage of
    # which download produced the figures they are holding.
    stamps = []
    for name, path in req["files"].items():
        side = path.with_suffix(path.suffix + ".provenance")
        try:
            rec = json.loads(side.read_text())
            # `.get`, not `[...]`, and for a reason found on 2026-08-26: a
            # sidecar written by hand rather than by `fetch()` used the key
            # `retrieved` where this reads `retrieved_at`, and the whole run
            # died with `KeyError: 'retrieved_at'` after the table had loaded,
            # transformed and projected. A provenance stamp is a note about
            # the data; a missing field in it must degrade the note, not kill
            # the run. `run_provenance_sidecars.py` now checks the fields too.
            stamps.append(f"{rec.get('dataset', path.name)} "
                          f"{str(rec.get('retrieved_at', 'date unrecorded'))[:10]} "
                          f"{str(rec.get('sha256', ''))[:16]}…")
        except (ValueError, OSError):
            stamps.append(f"{path.name} (no provenance sidecar)")
    table.notes = ((table.notes or "") + " Built from " + "; ".join(stamps)
                   + ".").strip()
    return table


def _load_eurostat(path: Path, req: dict, offline: bool, refresh: bool):
    """Load the table, downloading it first if it is not already here.

    THE RULE IS THAT A CACHED FILE IS NEVER RE-FETCHED. A statistical office
    revises; a configuration that downloaded on every run would answer one way
    in January and another in June, with nothing in the output to say why, and
    the whole point of this engine is that a number can be traced back to
    something someone else could repeat. So the first run downloads and records
    the URL, the byte count and the SHA-256 in a sidecar; every run after it
    reads exactly those bytes and never opens a socket.

    `refresh` overrides that on purpose and says so. `offline` refuses to
    download at all and prints the URL, which is what a machine behind a
    firewall — or an air-gapped review of someone else's result — needs.
    """
    import json

    from .eurostat import EurostatError, fetch, load_iot

    # NOT `.json`. The sidecar sits beside its table, and `data/eurostat/` is
    # globbed for `*.json` by more than one validator, each of which would then
    # try to read a provenance record as a JSON-stat cube. `run_uk_classification`
    # did exactly that on 2026-08-25, five minutes after the first sidecar was
    # written, and died on `KeyError: 'id'`.
    side = path.with_suffix(path.suffix + ".provenance")

    if path.exists() and not refresh:
        note = None
        if side.exists():
            try:
                rec = json.loads(side.read_text())
                note = (f"Eurostat {rec.get('dataset')} {req['geo']} "
                        f"{req['year']}, {req['variant']} variant. Downloaded "
                        f"{str(rec.get('retrieved_at', ''))[:10]}, "
                        f"{rec.get('bytes')} bytes, SHA-256 "
                        f"{str(rec.get('sha256', ''))[:16]}…. Read from the "
                        f"local cache; the network was not used.")
            except (ValueError, OSError):
                note = None
        if note is None:
            # Still say it came from the cache — that is the fact the reader
            # needs either way — and then say what is missing rather than
            # letting the absence pass as if nothing were.
            note = (f"Eurostat {req['dataset']} {req['geo']} {req['year']}, "
                    f"{req['variant']} variant. Read from the local cache "
                    f"({path.name}); the network was not used. NO PROVENANCE "
                    f"SIDECAR was found beside it, so when it was downloaded, "
                    f"from what URL, and with what checksum are not recorded.")
        return _tag(load_iot(path, req["variant"]), note)

    if offline:
        raise ConfigError(
            f"--offline was given and {path} is not cached yet.\n\n"
            f"Either drop --offline, or fetch it once by hand:\n"
            f"    {_eurostat_url(req)}\n"
            f"and save the response as that file.")

    # WHAT THE OLD FILE HELD, read before it is overwritten.
    #
    # A re-download that changes the SHA-256 has NOT necessarily changed a
    # number. Measured on this project's own cache on 2026-08-25: the Spanish
    # symmetric table fetched on 2026-08-10 and again fifteen days later hashed
    # differently, and all 17,957 values were identical -- what moved was
    # Eurostat's own `updated` stamp and an `extension` block. Hashing the raw
    # bytes is the right integrity check because it is conservative, but it
    # answers "are these the same bytes", not "are these the same figures", and
    # only the second question is the analyst's. So `--refresh` compares.
    previous = None
    if refresh and path.exists():
        try:
            previous = json.loads(path.read_text()).get("value")
        except (ValueError, OSError):
            previous = None

    try:
        rec = fetch(req["dataset"], req["geo"], req["year"], path)
    except EurostatError as exc:
        raise ConfigError(
            f"the Eurostat download failed:\n{exc}\n\n"
            f"Nothing was written. The cache path was {path}.") from None
    side.write_text(json.dumps(rec, indent=2))

    verb = "Re-downloaded" if refresh else "Downloaded"
    print(f"    {verb} {rec['dataset']} {req['geo']} {req['year']} — "
          f"{rec['bytes']:,} bytes, {rec['n_values']:,} values")
    print(f"    cached at {path}")
    print(f"    SHA-256 {rec['sha256']}")
    if refresh:
        print("    --refresh replaced a file that was already here. The "
              "figures below are the new ones.")
        if previous is None:
            print("    The previous file could not be read for comparison, so "
                  "whether any figure moved is unknown.")
        else:
            now = json.loads(path.read_text()).get("value") or {}
            moved = [k for k in set(previous) | set(now)
                     if previous.get(k) != now.get(k)]
            if not moved:
                print(f"    {len(now):,} values, NONE of them changed. The "
                      f"checksum moved and the data did not — Eurostat "
                      f"restamps a release without revising it.")
            else:
                worst = max(moved, key=lambda k: abs((now.get(k) or 0)
                                                     - (previous.get(k) or 0)))
                print(f"    {len(moved):,} of {len(now):,} values CHANGED. "
                      f"Largest move: {previous.get(worst)} -> "
                      f"{now.get(worst)}. Any earlier result from this "
                      f"configuration was computed on different figures.")
    return _tag(load_iot(path, req["variant"]),
                f"Eurostat {rec['dataset']} {req['geo']} {req['year']}, "
                f"{req['variant']} variant. Downloaded "
                f"{str(rec.get('retrieved_at', 'date unrecorded'))[:10]} from "
                f"{rec.get('url', 'url unrecorded')}, "
                f"{rec.get('bytes', '?')} bytes, SHA-256 "
                f"{str(rec.get('sha256', ''))[:16]}….")


def _eurostat_url(req: dict) -> str:
    from .eurostat import API
    return (API.format(dataset=req["dataset"])
            + f"&geo={req['geo']}&time={req['year']}&unit=MIO_EUR")


def _tag(table, note: str):
    """Put the download's provenance where the report will print it.

    The reader of a result has to be able to see which file it came from and
    when it arrived, and `notes` is the field the report already surfaces under
    'What the loader decided when reading this file'.
    """
    table.notes = f"{table.notes} {note}".strip() if table.notes else note
    return table


# Eurostat's regional employment, on the A10 grouping the European MRIO uses.
EMPLOYMENT_DATASET = "nama_10r_3empers"

# THE ARCHIVE'S CODES THAT EUROSTAT SERVES UNDER ANOTHER CODE, FOR THE SAME
# TERRITORY. The archive codes Greece on NUTS 2010 and France and Poland on
# NUTS 2013; Eurostat serves NUTS 2024. Every pair below is a chain of steps
# that Eurostat's own correspondence tables call a new code ("code change",
# "recoded") and nothing else. Held here rather than read from those tables at
# run time, so an installed engine needs no spreadsheet of Eurostat's;
# `run_mrio_eurostat_codes.py` rebuilds the list from the tables in
# `data/nuts/` and fails if the two disagree.
MRIO_EUROSTAT_CODE = {
    # Greece needs no entry: the archive's Greek labels do not describe their
    # own rows, and `io_loader.MRIO_RELABEL` replaces them with the codes
    # Eurostat serves (`run_mrio_labels.py`).
    # NUTS 2013 -> 2016, "recoded" (FR24 "recoded and relabelled")
    "FR21": "FRF2", "FR22": "FRE2", "FR23": "FRD2", "FR24": "FRB0",
    "FR25": "FRD1", "FR26": "FRC1", "FR30": "FRE1", "FR41": "FRF3",
    "FR42": "FRF1", "FR43": "FRC2", "FR51": "FRG0", "FR52": "FRH0",
    "FR53": "FRI3", "FR61": "FRI1", "FR62": "FRJ2", "FR63": "FRI2",
    "FR71": "FRK2", "FR72": "FRK1", "FR81": "FRJ1", "FR82": "FRL0",
    "FR83": "FRM0",
    "PL11": "PL71", "PL31": "PL81", "PL32": "PL82", "PL33": "PL72",
    "PL34": "PL84",
}

# THE ARCHIVE'S REGIONS WHOSE BORDER EUROSTAT HAS SINCE MOVED, in what the
# tables say. Eurostat recalculates its series on the new borders, so no code
# it serves is the archive's territory, and nothing is fetched for them.
MRIO_REDRAWN = {
    # PL12 is not here: the archive prints that code over PL91's rows, which
    # Eurostat publishes (`io_loader.MRIO_RELABEL`, `run_mrio_labels.py`).
    "NL31": "NUTS 2024 moved its border with Zuid-Holland; Eurostat serves "
            "Utrecht as NL35",
    "NL33": "NUTS 2024 moved its border with Utrecht; Eurostat serves "
            "Zuid-Holland as NL36",
    "PT16": "NUTS 2024 gave part of it to the new PT1D (Oeste e Vale do "
            "Tejo); Eurostat serves Centro as PT19",
    "PT17": "NUTS 2024 split it into PT1A (Grande Lisboa) and PT1B "
            "(Península de Setúbal)",
    "PT18": "NUTS 2024 gave part of it to the new PT1D (Oeste e Vale do "
            "Tejo); Eurostat serves Alentejo as PT1C",
}


def _no_employment_reason(region: str, geo: str, year: int) -> str:
    """Why Eurostat answered with nothing, said as what it is.

    The United Kingdom's regions are not in the release at all: measured on
    2026-09-11, none of its NUTS-2 codes carried a 2018 figure, so no code can
    supply one. Any other code reaching here is the one this engine takes to
    be Eurostat's for the territory, and the release has other regions, so
    what is missing is that year's figure for it.
    """
    if region.startswith("UK"):
        return ("Eurostat's release carries no region of the United Kingdom: "
                "measured on 2026-09-11, none of its NUTS-2 codes had a 2018 "
                "figure, so no code can supply one.")
    return (f"{geo} is the code this engine takes to be Eurostat's for that "
            f"territory (`run_mrio_eurostat_codes.py` checks every region of "
            f"the 2018 archive), and the {year} release carries other regions "
            f"but no figure under it: what is missing is that year's figure "
            f"for this territory, not the code.")


def _mrio_employment(meta: dict, table, table_path, base_dir, offline: bool,
                     refresh: bool) -> tuple:
    """Employment for one region of the European MRIO, from Eurostat.

    WHY
    ----
    The archive's ten sectors are Eurostat's A10 grouping, code for code, and
    Eurostat's regional accounts publish employed persons by NUTS-2 region on
    that same grouping: `nama_10r_3empers`, thousand persons, `wstatus=EMP`.
    So an employment account for an MRIO region does not have to be typed in.
    Checked on 2026-09-11 for Catalonia in 2018: the ten sectors add up to the
    3,562.6 Eurostat publishes as the total.

    ONE FILE PER YEAR, EVERY REGION (326 KB for 2018). This region's row is
    the account; everyone's rows weight the loader's columns to say how much
    of the region's employment multipliers runs through other regions
    (`io_loader.mrio_jobs`). Returns the account and that share.

    Cached by the rule `_load_eurostat` states: a kept download is never
    fetched again, `refresh` fetches it on purpose, `offline` refuses and
    prints the URL.

    WHICH CODE
    -----------
    The archive codes Greece on NUTS 2010 and France and Poland on NUTS 2013,
    and Eurostat serves NUTS 2024. Where Eurostat's correspondence tables call
    every step a new code for the same territory, the region is fetched under
    the code Eurostat serves (`MRIO_EUROSTAT_CODE`) and the account says so.

    WHAT IT REFUSES
    ----------------
    A region whose border moved (`MRIO_REDRAWN`): one territory's employment
    over another's output is a multiplier of neither, so the code is not
    translated and nothing is fetched. A region the release carries nothing
    for -- every one of the United Kingdom's.

    A sector with no figure, because absent is not zero -- the rule
    `build_satellites` states. And sectors that do not add up to the total
    Eurostat publishes beside them, beyond the rounding of its own figures.
    """
    import json

    from .eurostat import API, EurostatError, _Cube, _rounding_tol, fetch

    region = str(meta.get("mrio_region") or "").strip()
    year = int(table.year)
    if region in MRIO_REDRAWN:
        raise ConfigError(
            f"Eurostat publishes no employment for {region} as the archive "
            f"draws it: {MRIO_REDRAWN[region]}.\n\n"
            f"A region whose border moved is not the same territory, and one "
            f"territory's employment over another's output is a multiplier of "
            f"neither, so the code is not translated and nothing was fetched. "
            f"Give the figures yourself in a `satellites` sheet, account name "
            f"`employment`, one row per sector; the sheet's figures are used.")
    # The code Eurostat serves for the archive's territory: the archive's own,
    # or a later one for the same territory.
    geo = MRIO_EUROSTAT_CODE.get(region, region)
    path = (Path(base_dir) / "data" / "eurostat"
            / f"{EMPLOYMENT_DATASET}_ALL_{year}.json")
    side = path.with_suffix(path.suffix + ".provenance")
    url = (API.format(dataset=EMPLOYMENT_DATASET)
           + f"&time={year}&unit=THS&wstatus=EMP")

    if path.exists() and not refresh:
        try:
            rec = json.loads(side.read_text())
            how = (f"downloaded {str(rec.get('retrieved_at', ''))[:10]}, "
                   f"SHA-256 {str(rec.get('sha256', ''))[:16]}…, read from "
                   f"the local cache without using the network")
        except (ValueError, OSError):
            how = (f"read from the local cache ({path.name}) without using "
                   f"the network. NO PROVENANCE SIDECAR was found beside it, "
                   f"so when it was downloaded and with what checksum are not "
                   f"recorded")
    elif offline:
        raise ConfigError(
            f"--offline was given and the employment for {region} {year} is "
            f"not kept here yet ({path}).\n\n"
            f"Either drop --offline, or fetch it once by hand:\n"
            f"    {url}\n"
            f"and save the response as that file.")
    else:
        try:
            rec = fetch(EMPLOYMENT_DATASET, None, year, path, unit="THS",
                        wstatus="EMP")
        except EurostatError as exc:
            if "returned no values" in str(exc):
                raise ConfigError(
                    f"Eurostat publishes no regional employment for {year}: "
                    f"{EMPLOYMENT_DATASET} answered with no values for any "
                    f"region, which is what it does for a year not yet "
                    f"published.\n\nGive the figures yourself in a "
                    f"`satellites` sheet, account name `employment`, one row "
                    f"per sector. The sheet's figures are used and nothing is "
                    f"fetched.") from None
            raise ConfigError(
                f"the Eurostat download of employment failed:\n{exc}\n\n"
                f"Nothing was written. The cache path was {path}.") from None
        side.write_text(json.dumps(rec, indent=2))
        print(f"    Downloaded {EMPLOYMENT_DATASET}, every region, {year} — "
              f"{rec['bytes']:,} bytes")
        print(f"    cached at {path}")
        how = (f"downloaded {str(rec.get('retrieved_at', ''))[:10]}, SHA-256 "
               f"{str(rec.get('sha256', ''))[:16]}…")

    try:
        cube = _Cube(json.loads(path.read_text()))
    except (ValueError, OSError) as exc:
        raise ConfigError(
            f"{path.name} could not be read as a Eurostat response: "
            f"{str(exc)[:200]}\n\nFetch it again with --refresh.") from None

    def _employment_cell(code):
        try:
            return cube.at(nace_r2=code, geo=geo, time=str(year))
        except EurostatError as exc:
            raise ConfigError(
                f"{path.name} holds more than one category of a dimension "
                f"this reads as fixed ({exc}). The download it expects is "
                f"employed persons alone, `wstatus=EMP`, in thousands, for one "
                f"region and one year; fetch it again with --refresh.") \
                from None

    values = {c: _employment_cell(c) for c in table.sector_codes}
    if (all(v is None for v in values.values())
            and _employment_cell("TOTAL") is None):
        raise ConfigError(
            f"Eurostat publishes no employment for {region} in {year}: the "
            f"kept release ({path.name}) has no figure for {geo}.\n\n"
            f"{_no_employment_reason(region, geo, year)}\n\n"
            f"Give the figures yourself in a `satellites` sheet, account name "
            f"`employment`, one row per sector. The sheet's figures are used "
            f"and nothing is fetched.")
    missing = [c for c, v in values.items() if v is None]
    if missing:
        raise ConfigError(
            f"{path.name} has no figure for {', '.join(missing)} ({region}, "
            f"{year}).\n\nAn absent figure is not taken as zero: zero says "
            f"the sector employs nobody, and an absent cell says only that "
            f"Eurostat did not publish it. Give the account yourself in a "
            f"`satellites` sheet, account name `employment`, with a value for "
            f"every sector; the sheet's figures are used and nothing is "
            f"fetched.")
    got = sum(values.values())
    total = _employment_cell("TOTAL")
    if total is None:
        checked = ("Eurostat's total was not in the download, so the sectors "
                   "were not checked against it.")
    else:
        tol = _rounding_tol(len(values) + 1, list(values.values()) + [total])
        if abs(got - total) > tol:
            raise ConfigError(
                f"the {len(values)} sectors of {path.name} do not add up to "
                f"the total Eurostat publishes beside them: {got:,.1f} against "
                f"{total:,.1f} thousand persons, {got - total:+,.1f} apart, "
                f"where the rounding of its own figures allows {tol:,.2f}. "
                f"They are the archive's own grouping and should tile the "
                f"total; fetch the file again with --refresh.")
        checked = (f"The {len(values)} sectors add up to the {total:,.1f} "
                   f"Eurostat publishes as the total.")

    served = ("" if geo == region else
              f" Eurostat serves the archive's {region} as {geo}: the same "
              f"territory under a later NUTS code, by Eurostat's own "
              f"correspondence tables (`run_mrio_eurostat_codes.py`).")
    sat = Satellite(
        name="employment", unit="thousand persons",
        values=[values[c] for c in table.sector_codes],
        source=(f"Eurostat {EMPLOYMENT_DATASET}, employed persons, {geo}"
                + ("" if geo == region else f" (the archive's {region})")),
        source_year=year,
        notes=(f"Eurostat's employed persons for {geo} in {year} "
               f"(`wstatus=EMP`), {how}.{served} {checked} The employment is "
               f"measured; the output each multiplier divides it by is the "
               f"MRIO's, which the archive estimates, so the multiplier pairs "
               f"a measured figure with an estimated one and is no firmer "
               f"than the estimate. Per unit of output means per million US "
               f"dollars, the archive's unit."))

    # HOW MUCH OF THOSE MULTIPLIERS RUNS THROUGH OTHER REGIONS, IN JOBS. The
    # same file carries every region, so the loader's columns for this region
    # are weighted by jobs per unit of output wherever Eurostat has them. A
    # neighbour without them counts nothing, and the report says how much of
    # the multiplier that is -- it is not refused.
    from .io_loader import mrio_jobs
    from .regionalise import EVIDENCE

    def employment_of(code):
        if code in MRIO_REDRAWN or code.startswith("UK"):
            return None
        g = MRIO_EUROSTAT_CODE.get(code, code)
        try:
            v = [cube.at(nace_r2=s, geo=g, time=str(year))
                 for s in table.sector_codes]
        except EurostatError:
            return None
        return None if any(x is None for x in v) else v

    jobs = mrio_jobs(table_path, region, year, employment_of)
    jobs["archive_median_pct"] = EVIDENCE["employment_spillover_pct"]["median"]
    jobs["demand_median_pct"] = EVIDENCE["demand_spillover_pct"]["jobs_median"]
    # How far that figure moves across the deposit's years, so the report can
    # say it is the loaded year's (`run_employment_years.py`).
    jobs["years_check"] = dict(EVIDENCE.get("employment_by_year") or {})
    # If the archive puts this region's own output far below its employment,
    # the account's multipliers inherit it, and the account says so.
    if jobs.get("loaded_implausible"):
        sat.notes = (f"{sat.notes} The archive's output for {region} and this "
                     f"employment are not describing the same place: its jobs "
                     f"per unit of output are "
                     f"{jobs['loaded_implausible']:.0f} times the median "
                     f"region's (`run_demand_spillovers.py`), so the "
                     f"multipliers this account gives cannot be read with "
                     f"confidence.")
    return sat, jobs


def _rows(sheets: dict, name: str) -> list[dict]:
    """Sheet -> list of dicts keyed by the header row, blank rows dropped."""
    if name not in sheets:
        return []
    raw = [r for r in sheets[name] if r and any(c is not None for c in r)]
    if not raw:
        return []
    head = [str(c).strip().lower() if c is not None else "" for c in raw[0]]
    out = []
    for r in raw[1:]:
        # A row whose first cell starts with '#' is a comment. The template
        # writes its instructions underneath the data in exactly that form, so
        # the sheet explains itself without the explanation becoming data.
        if r and r[0] is not None and str(r[0]).lstrip().startswith("#"):
            continue
        row = {h: (r[i] if i < len(r) else None)
               for i, h in enumerate(head) if h}
        if any(v is not None and str(v).strip() != "" for v in row.values()):
            out.append(row)
    return out


def _need(row: dict, field: str, sheet: str, n: int):
    v = row.get(field)
    if v is None or str(v).strip() == "":
        raise ConfigError(f"sheet '{sheet}', row {n}: '{field}' is empty and "
                          f"is required")
    return v


def _strength(v, sheet: str, n: int) -> ProxyStrength:
    s = str(v).strip().lower()
    if s not in ("strong", "medium", "weak"):
        raise ConfigError(f"sheet '{sheet}', row {n}: strength {v!r} must be "
                          f"strong, medium or weak. It is not decoration — a "
                          f"weak proxy makes the whole split weak, and the "
                          f"report says so.")
    return ProxyStrength(s)


def load_config(path: Path | str, *, offline: bool = False,
                refresh: bool = False) -> dict:
    """Read a configuration WORKBOOK and return everything `IOProject` needs.

    `offline` refuses any network access; `refresh` forces a re-fetch of a
    cached download. Both are no-ops unless `table_kind` is `eurostat`.
    """
    path = Path(path)
    sheets = _open_workbook(path)
    missing = [s for s in REQUIRED_SHEETS if s not in sheets]
    if missing:
        raise ConfigError(
            f"{path.name} is missing the sheet(s) {', '.join(missing)}. "
            f"Run `python3 run_quadrium.py --template my_config.xlsx` to get a "
            f"workbook with the right shape and comments in it.")
    if not any(s in sheets and _rows(sheets, s) for s in ONE_OF_SHEETS):
        raise ConfigError(
            f"{path.name} says which table to use and then nothing to do with "
            f"it. Fill in `splits` to divide a sector, `regionalise` to "
            f"estimate a region from it, or `targets` to project a supply-use "
            f"pair. A workbook with none of the three describes no job.")
    meta = {}
    for r in sheets["project"]:
        if r and r[0] is not None and str(r[0]).strip():
            k = str(r[0]).strip()
            if k.startswith("#"):
                continue
            meta[k.lower()] = r[1] if len(r) > 1 else None
    tables = {name: _rows(sheets, name)
              for name in ("splits", "keys", "scenarios", "profiles",
                           "targets", "satellites")}

    # `regionalise` is key/value like `project`, not a table of rows: the job
    # has one set of parameters, not one per sector.
    reg = {}
    for r in sheets.get("regionalise", []):
        if r and r[0] is not None and str(r[0]).strip():
            k = str(r[0]).strip()
            # `#` is a comment; `key` is the template's own header row, which
            # the first version read as a setting called "key" and so treated
            # an untouched template as a regionalisation with nothing in it.
            if k.startswith("#") or k.lower() in ("key", "sector_code"):
                continue
            reg[k.lower()] = r[1] if len(r) > 1 else None
    if reg:
        return build_regionalisation(meta, reg, base_dir=path.parent,
                                     label=path.name, offline=offline,
                                     refresh=refresh)
    return build_config(meta, tables, base_dir=path.parent, label=path.name,
                        offline=offline, refresh=refresh)


def _load_declared_table(meta: dict, base_dir, tables: dict, offline: bool,
                         refresh: bool, defaults_taken: list):
    """The table the `project` sheet names, however it names it.

    Extracted at v1.86 so a regionalisation reads its national table exactly
    the way a split reads the table it divides -- including `table_kind:
    eurostat`, which the command-line route cannot do at all. Two ways of
    naming the same table would have been two places to fix a loader.
    """
    kind = str(meta.get("table_kind") or "uk_analytical").strip().lower()
    if kind not in TABLE_KINDS:
        raise ConfigError(f"table_kind {kind!r} must be one of {TABLE_KINDS}")

    # `mrio_region` names one region of the European MRIO and means nothing to
    # any other kind. Refused rather than ignored, for the reason given for
    # `table_unbalanced` below: a setting that was silently dropped cannot be
    # told apart from one that was applied.
    mrio_region = str(meta.get("mrio_region") or "").strip()
    if mrio_region and kind != "eu_mrio":
        raise ConfigError(
            f"mrio_region={mrio_region!r} applies only to table_kind "
            f"'eu_mrio', not {kind!r}. Refusing rather than ignoring a "
            f"setting you would never see was ignored.")
    if kind == "eu_mrio" and not mrio_region:
        raise ConfigError(
            "table_kind 'eu_mrio' needs `mrio_region`: the archive holds 272 "
            "regions and a table is one of them. Add a row to the `project` "
            "sheet with its NUTS-2 code, for example\n"
            "\n    mrio_region    ES51\n"
            "\nfor Catalonia. A code the archive does not have is refused with "
            "the list of that country's regions.")
    # `mrio_year` the same way: one kind only, and a year or nothing. Empty is
    # 2018, the year this project measured the archive on, and the run says
    # so; a year outside the deposit is the loader's to refuse.
    raw_year = meta.get("mrio_year")
    mrio_year = 2018
    if raw_year not in (None, ""):
        if kind != "eu_mrio":
            raise ConfigError(
                f"mrio_year={raw_year!r} applies only to table_kind "
                f"'eu_mrio', not {kind!r}. Refusing rather than ignoring a "
                f"setting you would never see was ignored.")
        try:
            mrio_year = int(float(str(raw_year).strip()))
        except ValueError:
            raise ConfigError(
                f"mrio_year {raw_year!r} is not a year. The archive holds "
                f"2008 to 2018; leave the row empty for 2018.") from None
    elif kind == "eu_mrio":
        defaults_taken.append(
            "mrio_year is empty: the 2018 table, the year this project "
            "measured the archive on")
    # `mrio_employment` too, and checked HERE, before the table is opened, so
    # the refusal names the setting and not whatever the path turns out to be.
    # The download itself waits for `build_config`, which knows whether the
    # workbook already gives the account.
    raw_emp = str(meta.get("mrio_employment") or "").strip()
    if raw_emp and kind != "eu_mrio":
        raise ConfigError(
            f"mrio_employment={raw_emp!r} applies only to table_kind "
            f"'eu_mrio', not {kind!r}: it fetches Eurostat's employment for a "
            f"region of the European MRIO. For another table give the account "
            f"in a `satellites` sheet. Refusing rather than ignoring a setting "
            f"you would never see was ignored.")
    if (raw_emp and not _yes(raw_emp)
            and raw_emp.lower() not in ("no", "n", "false", "0", "off")):
        defaults_taken.append(
            f"mrio_employment is {raw_emp!r}, which is not a yes; no "
            f"employment account was fetched")

    # `eurostat` names a country and a year instead of a file, and `table_path`
    # becomes where the download is KEPT rather than where it already is. So
    # the existence check below cannot apply to it: on a first run the file is
    # supposed to be missing.
    if kind == "eurostat_sut":
        table_path, fetch_note = _eurostat_sut_paths(meta, base_dir)
    elif kind == "eurostat":
        table_path, fetch_note = _eurostat_cache_path(meta, base_dir)
    else:
        raw = str(_need(meta, "table_path", "project", 0)).strip()
        table_path = Path(raw)
        if not table_path.is_absolute():
            table_path = (Path(base_dir) / table_path).resolve()
        fetch_note = None
        if not table_path.exists():
            # The commonest first failure there is, and until 2026-09-06 the
            # message treated it as a typo. It is not: the workbook still
            # holds the value `--template` seeded, and that value resolves
            # ONLY inside a source checkout. The note explaining that sits in
            # grey at the foot of the sheet, which is where it was put on the
            # belief that a user would read it before running. The project's
            # first outside tester did not, and neither will anyone else --
            # so it is said HERE, where they are actually looking.
            if raw == TEMPLATE_TABLE_PATH:
                raise ConfigError(
                    f"table_path still holds the value --template wrote:\n"
                    f"    {raw}\n"
                    f"which resolves to {table_path} and is not there.\n"
                    f"\nThat is not a broken install. The seeded table ships "
                    f"with the SOURCE CHECKOUT of this project, and you "
                    f"installed the package, so you do not have it. Nothing "
                    f"in the workbook has been filled in yet.\n"
                    f"\nTo see which tables you DO have:\n"
                    f"    quadrium --sources\n"
                    f"and if you know the sector but not the table:\n"
                    f"    quadrium --find <CODE> --geo <XX>\n"
                    f"Either one prints the `project` rows to paste in.")
            raise ConfigError(f"table_path points at {table_path}, which does "
                              f"not exist. Paths may be absolute or relative "
                              f"to the config file.")

    # `table_unbalanced` means something for exactly one kind. A workbook that
    # sets it anywhere else is refused rather than quietly ignored: an analyst
    # who typed `residual_column` and got a silent `refuse` would have no way of
    # telling, and an analyst who typed it on a table that balances would think
    # they had authorised something they had not.
    unbalanced = str(meta.get("table_unbalanced") or "refuse").strip().lower()
    if unbalanced not in ("refuse", "residual_column"):
        raise ConfigError(f"table_unbalanced {unbalanced!r} must be 'refuse' "
                          f"(the default) or 'residual_column'")
    if unbalanced != "refuse" and kind != "ine_interior":
        raise ConfigError(
            f"table_unbalanced={unbalanced!r} applies only to "
            f"table_kind 'ine_interior', not {kind!r}. Refusing rather than "
            f"ignoring a setting you would never see was ignored.")

    loaders = {
        "uk_analytical": lambda p: load_uk_analytical_iot(p),
        "interchange": lambda p: load_io_table(p),
        "ine_interior": lambda p: load_ine_tio(p, "interior", unbalanced),
        "ine_total": lambda p: load_ine_tio(p, "total"),
        "eu_mrio": lambda p: load_eu_mrio(p, mrio_region, mrio_year),
        "eurostat": lambda p: _load_eurostat(p, fetch_note, offline, refresh),
        "eurostat_sut": lambda p: _load_eurostat_sut(
            fetch_note, offline, refresh, defaults_taken,
            tables.get("targets", [])),
    }
    try:
        table = loaders[kind](table_path)
    except LoaderError as exc:
        # A refusal that names the problem and not the remedy dead-ends the
        # user, and this one had a remedy sitting in the sheet they already
        # have open. The INE's interior table genuinely does not balance
        # (OQ-D-04) and `table_unbalanced` exists for exactly that; until
        # 2026-09-05 nothing said so, so the documented Spanish route stopped
        # at the first command with no way forward. Named here rather than in
        # the loader because the key is a WORKBOOK key: the loader is also
        # called from Python, where the argument is already visible.
        if (kind == "ine_interior" and unbalanced == "refuse"
                and "does not balance" in str(exc)):
            raise ConfigError(
                f"the table could not be loaded:\n{exc}\n"
                f"\nThis table is known not to balance, and it is not a "
                f"defect in your copy: the INE publishes it that way for one "
                f"product (OQ-D-04). You can carry the difference instead of "
                f"stopping, by adding one row to the `project` sheet:\n"
                f"\n    table_unbalanced    residual_column\n"
                f"\nThat puts the difference in a labelled RESIDUAL column "
                f"that travels into every report, so it is visible rather "
                f"than absorbed into a cell that would read as observed. It "
                f"is a disclosure, NOT a repair — the residual is computed "
                f"here and the INE never published it. Leave the key off and "
                f"this refusal is the right answer.") from None
        raise ConfigError(f"the table could not be loaded:\n{exc}") from None
    return table, table_path, kind


def build_config(meta: dict, tables: dict, base_dir: Path = Path("."),
                 label: str = "<configuration>", *, offline: bool = False,
                 refresh: bool = False) -> dict:
    """Build a run from plain Python data, with no spreadsheet involved.

    `meta` is the `project` sheet as a dict; `tables` maps 'splits', 'keys',
    'scenarios' and 'profiles' to lists of row-dicts with the same column names
    the workbook uses.

    WHY THIS EXISTS SEPARATELY FROM THE WORKBOOK.
    A configuration is a declarative description of a run: which table, which
    sectors, which proxies with which sources, which scenarios. A human writes
    that in a spreadsheet. A program — a connector to a statistical institute,
    a script, or a model asked to set up a run — writes the same thing as data.
    Keeping the two entry points on one code path means both get identical
    validation and identical error messages, so a machine-written configuration
    cannot take a shortcut a human-written one could not.

    Every check below is deliberately the same for both. In particular a
    generated configuration still has to name a real source and a real strength
    for every proxy: there is no path into this engine that produces a number
    without saying where it came from.
    """
    meta = {str(k).strip().lower(): v for k, v in (meta or {}).items()}
    # Declared here rather than beside the scenarios below, because the loaders
    # take defaults too and the analyst must hear about those as well.
    defaults_taken: list[str] = []
    project_id = str(_need(meta, "project_id", "project", 0)).strip()
    table, table_path, kind = _load_declared_table(
        meta, base_dir, tables, offline, refresh, defaults_taken)

    # ---- type II closure and satellite accounts ------------------------
    #
    # ADD OR REPLACE, NEVER ERASE. Both of these used to assign
    # unconditionally, and `build_satellites` returns {} for an empty sheet.
    # So: split a table with an employment account, export it, point a new
    # workbook at the file as `table_kind: interchange` to divide a second
    # sector -- and the account the FILE carried was wiped, because the new
    # workbook did not repeat the sheet.
    #
    # That is the fourth appearance of one shape in three days and the only
    # one that destroys the user's own work on the route `docs/GUIDE.md`
    # documents. A workbook that says nothing about an account is not asking
    # for it to be deleted.
    #
    # The workbook still WINS where it speaks: an account it declares replaces
    # the file's account of that name, because a user who typed a figure means
    # it. Removing one is a deliberate act and there is no way to do it by
    # omission -- write the file without it, or say so in the sheet.
    from_file = dict(getattr(table, "satellites", None) or {})
    from_book = build_satellites(tables.get("satellites", []), table)
    # EUROSTAT'S EMPLOYMENT, for a region of the European MRIO, goes between
    # the two: the archive carries no accounts, and the workbook still wins for
    # the reason above -- so when it declares the account, nothing is fetched.
    from_eurostat = {}
    if kind == "eu_mrio" and _yes(meta.get("mrio_employment")):
        if "employment" in from_book:
            defaults_taken.append(
                "mrio_employment asks for Eurostat's employment and the "
                "`satellites` sheet declares an `employment` account; the "
                "sheet's figures are used and nothing was fetched")
        else:
            sat, jobs = _mrio_employment(meta, table, table_path, base_dir,
                                         offline, refresh)
            from_eurostat["employment"] = sat
            table.interregional["jobs"] = jobs
    kept = sorted(set(from_file) - set(from_book))
    replaced = sorted(set(from_file) & set(from_book))
    table.satellites = {**from_file, **from_eurostat, **from_book}
    if kept:
        defaults_taken.append(
            f"the satellite account(s) {', '.join(kept)} came with the table "
            f"and this workbook does not mention them; they are kept, not "
            f"dropped")
    if replaced:
        defaults_taken.append(
            f"the satellite account(s) {', '.join(replaced)} came with the "
            f"table AND are declared here; the workbook's figures are used")

    # The label lookup in `_type_ii_spec` would ACCEPT `VA` here, because the
    # row exists -- it is simply not income. So the refusal is by kind.
    if kind == "eu_mrio" and (
            str(meta.get("type_ii_income_rows") or "").strip()
            or str(meta.get("type_ii_household_column") or "").strip()):
        raise ConfigError(
            f"a type II closure cannot be built on this table: "
            f"{_EU_MRIO_NO_TYPE_II}. Remove both type_ii rows; the type I "
            f"results and any satellite accounts are unaffected.")
    spec = _type_ii_spec(meta, table)
    if spec:
        table.type_ii = spec
    elif getattr(table, "type_ii", None):
        defaults_taken.append(
            "the type II closure came with the table and this workbook does "
            "not mention it; it is kept, and the report says which rows it "
            "closes on")

    # ---- keys ---------------------------------------------------------
    grouped: dict[str, list[dict]] = {}
    for n, r in enumerate(tables.get("keys", []), start=2):
        grouped.setdefault(str(_need(r, "key_id", "keys", n)).strip(),
                           []).append((n, r))
    keys = {}
    for key_id, entries in grouped.items():
        codes, values, srcs, yrs, strengths = [], [], [], [], []
        for n, r in entries:
            codes.append(str(_need(r, "new_sector_code", "keys", n)).strip())
            try:
                values.append(float(_need(r, "value", "keys", n)))
            except (TypeError, ValueError):
                raise ConfigError(f"sheet 'keys', row {n}: value "
                                  f"{r.get('value')!r} is not a number") from None
            srcs.append(str(_need(r, "source", "keys", n)).strip())
            yrs.append(int(_need(r, "source_year", "keys", n)))
            strengths.append(_strength(_need(r, "strength", "keys", n),
                                       "keys", n))
        order = ["strong", "medium", "weak"]
        weakest = max(strengths, key=lambda s: order.index(s.value))
        keys[key_id] = AllocationKey(
            key_id=key_id, applies_to="output", new_sector_codes=codes,
            raw_values=values, source=srcs[0], source_year=yrs[0],
            # A key is only as strong as its weakest row: a split resting on
            # one weak proxy is a weak split, whatever the other rows say.
            strength=weakest,
            notes=(f"from {label}"
                   + ("; rows disagree on source, the first is recorded"
                      if len(set(srcs)) > 1 else "")))

    # ---- splits -------------------------------------------------------
    by_sector: dict[str, dict] = {}
    for n, r in enumerate(tables.get("splits", []), start=2):
        sector = str(_need(r, "sector_code", "splits", n)).strip()
        entry = by_sector.setdefault(sector, {"codes": [], "labels": [],
                                              "keys": set(), "rows": []})
        entry["codes"].append(str(_need(r, "new_code", "splits", n)).strip())
        entry["labels"].append(str(r.get("new_label")
                                   or entry["codes"][-1]).strip())
        k = r.get("key_id")
        if k is not None and str(k).strip():
            entry["keys"].add(str(k).strip())
        entry["rows"].append(n)
    if not by_sector:
        raise ConfigError("sheet 'splits' has no rows: nothing to divide")

    splits = []
    for sector, e in by_sector.items():
        try:
            table.index_of(sector)
        except KeyError:
            raise ConfigError(
                f"sheet 'splits' rows {e['rows']}: sector {sector!r} is not in "
                f"the loaded table. Check the code against the table's own "
                f"classification ({table.classification}).") from None
        if len(e["keys"]) > 1:
            # Silently taking one of them would make the result depend on row
            # order, which is exactly the kind of thing that never gets noticed.
            raise ConfigError(
                f"split '{sector}' names more than one allocation key "
                f"({', '.join(sorted(e['keys']))}) across its rows. One split "
                f"takes one key. Use separate splits, or leave key_id blank on "
                f"all but one row.")
        e["key"] = next(iter(e["keys"]), None)
        if e["key"] and e["key"] not in keys:
            raise ConfigError(
                f"split '{sector}' names key '{e['key']}', which is not in the "
                f"'keys' sheet. Available: {', '.join(sorted(keys)) or 'none'}")
        if e["key"]:
            kk = keys[e["key"]]
            if sorted(kk.new_sector_codes) != sorted(e["codes"]):
                raise ConfigError(
                    f"split '{sector}' lists subsectors {e['codes']} but key "
                    f"'{e['key']}' covers {kk.new_sector_codes}. Every "
                    f"subsector needs a weight and every weight needs a "
                    f"subsector.")
        splits.append(SplitSpec(
            sector_code=sector, new_codes=e["codes"], new_labels=e["labels"],
            keys_by_block={"output": e["key"]} if e["key"] else {}))

    # ---- profiles, grouped by scenario ---------------------------------
    profiles: dict[str, dict] = {}
    all_new = {c for s in splits for c in s.new_codes}
    for n, r in enumerate(tables.get("profiles", []), start=2):
        sid = str(_need(r, "scenario_id", "profiles", n)).strip()
        sub = str(_need(r, "subsector_code", "profiles", n)).strip()
        sup = str(_need(r, "supplier_code", "profiles", n)).strip()
        if sub not in all_new:
            raise ConfigError(
                f"sheet 'profiles', row {n}: subsector {sub!r} is not created "
                f"by any split. Created: {', '.join(sorted(all_new))}")
        try:
            table.index_of(sup)
        except KeyError:
            raise ConfigError(f"sheet 'profiles', row {n}: supplier {sup!r} is "
                              f"not a sector of the loaded table") from None
        try:
            val = float(_need(r, "intensity", "profiles", n))
        except (TypeError, ValueError):
            raise ConfigError(f"sheet 'profiles', row {n}: intensity "
                              f"{r.get('intensity')!r} is not a number") from None
        profiles.setdefault(sid, {}).setdefault(sub, {})[sup] = val

    # ---- scenarios -----------------------------------------------------
    # DEFAULTS TAKEN ARE COLLECTED AND REPORTED, not applied quietly. A sheet
    # that is absent and a sheet whose NAME was mistyped are the same thing to
    # this loader, and the second is a mistake the analyst would never see: the
    # run succeeds, on a configuration they did not write (2026-08-10).
    scen_rows = list(tables.get("scenarios", []))
    if not scen_rows:
        scen_rows = [{"scenario_id": "S1", "label": "Default"}]
        defaults_taken.append(
            "no 'scenarios' sheet (or it was empty), so ONE scenario named 'S1' "
            "was created with alpha 0.5. If you wrote a scenarios sheet, check "
            "its name is exactly 'scenarios' — a mistyped sheet name looks "
            "identical to an absent one from here")
    if not tables.get("profiles"):
        defaults_taken.append(
            "no 'profiles' sheet, so every subsector buys the same mix as its "
            "parent and all subsectors of a split share its multiplier")
    if not tables.get("keys"):
        defaults_taken.append(
            "no 'keys' sheet, so the split has no allocation key of its own")
    scenarios = []
    for n, r in enumerate(scen_rows, start=2):
        sid = str(_need(r, "scenario_id", "scenarios", n)).strip()
        alpha = r.get("internal_block_alpha")
        scenarios.append(Scenario(
            scenario_id=sid, label=str(r.get("label") or sid).strip(),
            description=(str(r["description"]).strip()
                         if r.get("description") else None),
            internal_block_alpha=(float(alpha) if alpha not in (None, "")
                                  else 0.5),
            input_profiles=profiles.get(sid, {})))
    named = {s.scenario_id for s in scenarios}
    orphan = set(profiles) - named
    if orphan:
        raise ConfigError(
            f"sheet 'profiles' names scenario(s) {sorted(orphan)} that the "
            f"'scenarios' sheet does not define. A profile with no scenario "
            f"would be silently ignored, which is worse than an error.")

    # ---- ledger --------------------------------------------------------
    ledger = AssumptionLedger(project_id=project_id)
    for key in keys.values():
        ledger.add(Assumption(
            assumption_id=f"KEY-{key.key_id}",
            description=f"Subsectors split by '{key.key_id}' with weights "
                        + ", ".join(f"{c} {w:.1%}" for c, w
                                    in zip(key.new_sector_codes, key.weights)),
            applies_to="allocation", source=key.source,
            validated_by="declared in the configuration workbook",
            confidence=key.strength,
            impact_on_results=("high — a weak proxy makes the whole split weak"
                               if key.strength is ProxyStrength.WEAK
                               else "medium")))
    for sid, prof in profiles.items():
        ledger.add(Assumption(
            assumption_id=f"PROFILE-{sid}",
            description=f"Scenario '{sid}' gives {len(prof)} subsector(s) "
                        f"purchasing intensities that differ from their "
                        f"parent's average.",
            applies_to="input structure",
            source="analyst judgement, declared in the configuration workbook",
            validated_by="NOT VALIDATED — no source states these intensities",
            confidence=ProxyStrength.WEAK,
            impact_on_results="this is what makes the subsectors' multipliers "
                              "differ; without it they are identical by "
                              "construction"))
    ledger.add(Assumption(
        assumption_id="ALPHA",
        description="Trade among new subsectors is estimated by double "
                    "proportionality, damped on the diagonal by alpha.",
        applies_to="internal block",
        source="CORE_031 (Wolsky 1984, via Zhao 2014) eq. (14) at the "
               "default alpha=1.0; a raised alpha is a project choice with "
               "no source",
        validated_by="library/validators/check_wolsky_internal_block.py "
                     "reproduces eq. (14) to 5.6e-17 and eq. (15) to 0.0",
        confidence=ProxyStrength.WEAK,
        impact_on_results="high — the only part of the table with no "
                          "observation behind it"))

    return {"project_id": project_id,
            "title": str(meta.get("title") or f"{project_id} — sector split"),
            "table": table, "splits": splits, "scenarios": scenarios,
            "keys": keys, "ledger": ledger, "source_file": table_path,
            "notes": str(meta.get("notes") or ""),
            # OQ-E-03. A workbook key rather than a flag alone, because the
            # guide's first promise is that the spreadsheet can express
            # everything: a feature reachable only from the command line breaks
            # it, which is how regionalisation was found doing the same thing.
            "key_alternatives": _yes(meta.get("key_alternatives")),
            "defaults_taken": defaults_taken}


def write_template(path: Path | str) -> Path:
    """Write a workbook the analyst can fill in, with the comments inside it."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    path = Path(path)
    wb = openpyxl.Workbook()
    bold = Font(bold=True)
    head = PatternFill("solid", fgColor="DDEBF7")
    note = Font(italic=True, color="808080")

    def sheet(name, header, rows, notes):
        ws = wb.create_sheet(name)
        for j, h in enumerate(header, start=1):
            c = ws.cell(row=1, column=j, value=h)
            c.font, c.fill = bold, head
            ws.column_dimensions[c.column_letter].width = max(16, len(h) + 4)
        for i, row in enumerate(rows, start=2):
            for j, v in enumerate(row, start=1):
                ws.cell(row=i, column=j, value=v)
        r = len(rows) + 3
        for line in notes:
            ws.cell(row=r, column=1,
                    value=(f"# {line}" if line else "#")).font = note
            r += 1
        return ws

    ws = wb.active
    ws.title = "project"
    for i, (k, v) in enumerate([
            ("project_id", "my_first_split"),
            # Relative to THIS workbook, and it resolves only if the
            # workbook was written inside a checkout. Someone who installed the
            # package does not have that file; the note beside the field says
            # so and sends them to --sources, which lists what they do have.
            ("table_path", TEMPLATE_TABLE_PATH),
            ("table_kind", "uk_analytical"),
            ("title", "My sector split"),
            ("notes", "")], start=1):
        ws.cell(row=i, column=1, value=k).font = bold
        ws.cell(row=i, column=2, value=v)
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 46
    for i, line in enumerate([
            "#",
            "# table_path may be absolute, or relative to THIS file.",
            "# The seeded value points at a table that ships with the SOURCE",
            "# CHECKOUT. If you installed the package you do not have it: run",
            "#     quadrium --sources",
            "# to list every table this engine can load on your machine, and",
            "#     quadrium --find <CODE> --geo <XX>",
            "# if you know the sector but not the table.",
            "# table_kind: uk_analytical  the ONS workbook (industry x industry)",
            "#             ine_interior  the INE workbook, domestic output",
            "#             ine_total     the INE workbook, total flows",
            "#             interchange   the project's own format, and what",
            "#                           this engine writes -- point at a",
            "#                           result to split a second sector.",
            "#             eurostat      symmetric IOT, downloaded by",
            "#                           country and year.",
            "#             eurostat_sut  supply-use pair, downloaded and",
            "#                           TRANSFORMED into a symmetric table.",
            "#             eu_mrio       one region of the European MRIO",
            "#                           (Huang & Koutroumpis 2023). Point",
            "#                           table_path at the archive's Data",
            "#                           folder and add mrio_region, e.g. ES51.",
            "#                           mrio_year picks 2008-2018 (default",
            "#                           2018). mrio_employment sí attaches",
            "#                           Eurostat's employed persons for that",
            "#                           region and year.",
            "#",
            "# For table_kind: eurostat, delete table_path (or use it to say",
            "# where to cache) and add instead:",
            "#     eurostat_geo       ES        two-letter country code",
            "#     eurostat_year      2022",
            "#     eurostat_dataset   product_by_product | industry_by_industry",
            "#     eurostat_variant   domestic | total",
            "#",
            "# For table_kind: eurostat_sut, the same geo and year, and:",
            "#     eurostat_model     A | B | C | D   (default D)",
            "#   A product technology       product x product, may go negative",
            "#   B industry technology      product x product, cannot",
            "#   C fixed industry sales     industry x industry, may go negative",
            "#   D fixed product sales      industry x industry, cannot",
            "# The four are four assumptions about secondary production and",
            "# give four different tables from the same data. CORE_013",
            "# Figure 12.2, p. 378.",
            "# The first run downloads and records the URL and SHA-256; every",
            "# run after it reads those same bytes offline. --refresh forces a",
            "# new download and warns that your results may move.",
            "# key_alternatives: yes to re-run each split under every OTHER",
            "#             allocation key registered for it, and print what",
            "#             each one would have given. Off by default: it",
            "#             costs one full run per key. It never says which",
            "#             is right -- see OQ-E-03.",
            "# type_ii_income_rows / type_ii_household_column: close the",
            "#             model on households and get the INDUCED effect",
            "#             too (UNH_20 20.88). Name the value-added row(s)",
            "#             that hold wages, and the final-demand column",
            "#             households spend. Both or neither. Optional.",
            "# table_unbalanced: refuse (default) or residual_column.",
            "#             Only for ine_interior, which does not balance for",
            "#             one product -- see OQ-D-04. Anywhere else it is an error.",
            "#",
            "# Fill in the other sheets, then run:",
            "#     quadrium <this file>",
            "# (from a checkout, without installing: python3 run_quadrium.py)",
    ], start=7):
        ws.cell(row=i, column=1, value=line).font = note

    sheet("splits", ["sector_code", "new_code", "new_label", "key_id"],
          [["I56", "I561", "Restaurants and mobile food service", "k56"],
           ["I56", "I562", "Event catering", "k56"],
           ["I56", "I563", "Beverage serving activities", "k56"]],
          ["One row per NEW subsector. Rows sharing sector_code form one split.",
           "You may divide several sectors: just add rows with another",
           "sector_code. key_id names the allocation key in the 'keys' sheet."])

    sheet("keys", ["key_id", "new_sector_code", "value", "source",
                   "source_year", "strength"],
          [["k56", "I561", 720000, "ONS BRES (REPLACE — illustrative)", 2023,
            "weak"],
           ["k56", "I562", 120000, "ONS BRES (REPLACE — illustrative)", 2023,
            "weak"],
           ["k56", "I563", 380000, "ONS BRES (REPLACE — illustrative)", 2023,
            "weak"]],
          ["The proxy that decides how big each subsector is. Values are",
           "relative; they are normalised for you.",
           "strength: strong / medium / weak. A key is recorded at its WEAKEST",
           "row, because a split resting on one weak proxy is a weak split.",
           "Write the real source. It goes into the report and the ledger."])

    sheet("scenarios", ["scenario_id", "label", "description",
                        "internal_block_alpha"],
          [["S1_plain", "Size only",
            "No input profiles: every subsector inherits its parent's "
            "purchasing pattern.", None],
           ["S2_profiled", "Differentiated input structures",
            "Subsectors buy different mixes.", None]],
          ["One row per scenario. Leave internal_block_alpha blank for the",
           "default 1.0 — CORE_031 eq. (14), the outer product of the",
           "weights, which conserves the parent cell exactly. It was 0.5",
           "until v1.12, on an intuition measurement showed was backwards.",
           "Two or more scenarios let you see how much the answer depends on",
           "your choices, which is the honest way to present it."])

    sheet("satellites", ["name", "unit", "sector_code", "value", "source",
                         "source_year"],
          [],
          ["Employment, emissions, water -- anything measured per sector in",
           "units the table does not use. UNH_20 eq. (46). Optional: leave",
           "the sheet empty and nothing changes.",
           "",
           "One row per (account, sector). Several accounts live here at",
           "once, told apart by `name`.",
           "",
           "VALUES ARE TOTALS, not per unit of output: the whole quantity",
           "for that sector. The coefficient is derived for you.",
           "",
           "It must cover EVERY sector of your table. A sector left out is",
           "refused rather than taken as zero -- zero says the sector has",
           "none of this, and an absent row says only that nobody wrote it",
           "down. Write an explicit 0 where you mean zero.",
           "",
           "When a sector is split, its account is split by the SAME key,",
           "which assumes the subsectors have equal intensity. That is",
           "false for hotels against restaurants and the report says so."])

    sheet("profiles", ["scenario_id", "subsector_code", "supplier_code",
                       "intensity"],
          [["S2_profiled", "I563", "C1101T1106 & C12", 2.1],
           ["S2_profiled", "I563", "C101", 0.45],
           ["S2_profiled", "I561", "C101", 1.35]],
          ["How intensively each subsector buys from each supplier, RELATIVE",
           "to the parent sector's average. 1.0 = the average, 2.1 = buys",
           "2.1 times as intensively, 0.45 = less than half.",
           "",
           "WITHOUT this sheet every subsector gets a scaled copy of its",
           "parent's input structure, and they all end up with the SAME",
           "multiplier — arithmetic, not economics. This sheet is what makes",
           "them genuinely different as buyers.",
           "",
           "There is a limit: how far you can push it is bounded by how much",
           "the parent sector trades with itself. The report prints the",
           "headroom, and an impossible set is rejected with an explanation."])

    path.parent.mkdir(parents=True, exist_ok=True)
    # The other job this workbook can describe. Left EMPTY of values on
    # purpose: a workbook with both `splits` and `regionalise` filled in
    # describes two jobs, and the loader takes the regionalisation. The
    # comments say what to put here when that is what you want.
    sheet("regionalise", ["key", "value"], [], [
        '',
        "LEAVE THIS SHEET EMPTY unless you want to estimate a REGION's",
        'table from a national one, instead of dividing a sector.',
        '',
        'Fill in three keys in column A, their values in column B:',
        'method          SLQ | CILQ | RLQ | FLQ   (default FLQ)',
        "delta           the FLQ's convexity parameter, 0 <= d < 1.",
        'REQUIRED for FLQ and there is no default:',
        'measured across ten regions in two countries',
        'it runs from 0.14 to 0.60, median 0.26, so a',
        'default would be a guess wearing a number.',
        'activity_path   a CSV, `sector_code,regional` and optionally',
        '`,national`, one row per sector of the table',
        'named on the `project` sheet. Output or',
        'employment; without the third column the',
        "table's own output is used, which is right",
        'only when the second column is output too.',
        '',
        'The table comes from the `project` sheet, as it does for a split,',
        'so `table_kind: eurostat` works here too. It must be the DOMESTIC',
        "table: a total-flow one regionalises the country's imports as",
        'though they were local supply, and nothing downstream catches it.',
        '',
        'Every run prints what the method is known to get wrong -- the',
        'family overstates local multipliers, and cross-hauling is not',
        'reproduced in any amount anyone chose. There is no way to',
        'suppress that, and the absence of one is deliberate.',
    ])

    wb.save(path)
    return path


def read_activity(path: Path | str, table) -> tuple:
    """The region's activity by sector, against the table it will be scaled from.

    Shared by the workbook route and the command-line one, so the two cannot
    drift into different refusals for the same mistake. Returns
    `(Q_region, Q_national, national_from)`.
    """
    import csv as _csv

    path = Path(path)
    if not path.exists():
        raise ConfigError(f"activity_path points at {path}, which does not "
                          f"exist. Paths may be absolute or relative to the "
                          f"config file.")
    rows = list(_csv.reader(path.open()))
    head = [str(c).strip().lower() for c in (rows[0] if rows else [])]
    if head[:2] != ["sector_code", "regional"]:
        raise ConfigError(
            f"{path.name} must start with a header row reading "
            f"`sector_code,regional` and optionally `,national`. Regional "
            f"activity is output or employment; without the third column the "
            f"table's own output is used, which is only right when the second "
            f"column is output too.")
    has_national = len(head) > 2 and head[2] == "national"

    seen = {str(r[0]).strip(): r for r in rows[1:] if r and str(r[0]).strip()}
    missing = [c for c in table.sector_codes if c not in seen]
    extra = [c for c in seen if c not in table.sector_codes]
    if missing or extra:
        raise ConfigError(
            f"{path.name} and the table do not describe the same sectors.\n"
            f"  in the table but not the file: "
            f"{', '.join(missing[:8]) or 'none'}{' …' if len(missing) > 8 else ''}\n"
            f"  in the file but not the table: "
            f"{', '.join(extra[:8]) or 'none'}{' …' if len(extra) > 8 else ''}\n"
            f"Align the classifications; do not pad.")
    try:
        q_reg = np.array([float(seen[c][1]) for c in table.sector_codes])
        q_nat = (np.array([float(seen[c][2]) for c in table.sector_codes])
                 if has_national else table.X.copy())
    except (ValueError, IndexError) as exc:
        raise ConfigError(f"{path.name} has a value that is not a number: "
                          f"{exc}") from None
    return q_reg, q_nat, ("file" if has_national else "table output")


def build_regionalisation(meta: dict, reg: dict, base_dir: Path = Path("."),
                          label: str = "<configuration>", *,
                          offline: bool = False,
                          refresh: bool = False) -> dict:
    """A regionalisation described by a workbook rather than by flags.

    The `project` sheet already says which table to use and how to load it, so
    this sheet only says what to do with it -- which is why `table_kind:
    eurostat` works here and does not on the command line.
    """
    meta = {str(k).strip().lower(): v for k, v in (meta or {}).items()}
    defaults_taken: list[str] = []
    project_id = str(_need(meta, "project_id", "project", 0)).strip()
    # Before the load, which on this kind parses a 35 MB workbook to find out
    # something the `project` sheet already says.
    if str(meta.get("table_kind") or "").strip().lower() == "eu_mrio":
        raise ConfigError(
            "table_kind 'eu_mrio' is already a REGIONAL table: one region's "
            "own block of the European MRIO. Regionalising it would apply a "
            "location quotient to a table that already describes a region, "
            "and estimate a region of a region. Use it directly with `splits`, "
            "or regionalise from a national table.")
    table, table_path, kind = _load_declared_table(
        meta, base_dir, {}, offline, refresh, defaults_taken)

    method = str(reg.get("method") or "FLQ").strip().upper()
    if method not in ("SLQ", "CILQ", "RLQ", "FLQ"):
        raise ConfigError(f"method {method!r} on the `regionalise` sheet must "
                          f"be SLQ, CILQ, RLQ or FLQ")
    delta = reg.get("delta")
    if delta is not None and str(delta).strip() != "":
        try:
            delta = float(delta)
        except (TypeError, ValueError):
            raise ConfigError(f"delta {delta!r} is not a number") from None
    else:
        delta = None

    ap = reg.get("activity_path")
    if not ap or not str(ap).strip():
        raise ConfigError(
            "the `regionalise` sheet needs `activity_path`: a CSV of the "
            "region's activity by sector. There is nothing to scale the "
            "national table by without it.")
    ap = Path(str(ap).strip())
    if not ap.is_absolute():
        ap = (Path(base_dir) / ap).resolve()
    q_reg, q_nat, national_from = read_activity(ap, table)

    return {"kind": "regionalise", "project_id": project_id,
            "title": str(meta.get("title") or f"{project_id} — regionalisation"),
            "table": table, "source_file": table_path, "table_kind": kind,
            "method": method, "delta": delta,
            "Q_region": q_reg, "Q_national": q_nat,
            "national_activity_from": national_from,
            "activity_file": ap,
            "notes": str(meta.get("notes") or ""),
            "defaults_taken": defaults_taken}


# ---------------------------------------------------------------------------
# What this workbook still needs, ALL of it, in one pass
# ---------------------------------------------------------------------------

def plan_workbook(path: Path | str) -> dict:
    """Every gap in a configuration workbook at once, in plain language.

    WHY THIS EXISTS, AND IT IS A DEFECT BEFORE IT IS A FEATURE
    ------------------------------------------------------------
    `load_config` raises on the FIRST problem, which is right for a gate and
    wrong for a person. The owner ran a fresh template on 2026-09-06 and was
    told the table file did not exist. Fix that and the next run says there is
    no split; fix that and it says there is no key. Three sittings to learn
    what one screen could have said, and he is an economist who does not use a
    terminal -- which is the user `docs/GUIDE.md` opens by promising to serve.

    So this reads the workbook LENIENTLY and reports everything: what is
    missing, what is inconsistent, and what still holds the value `--template`
    seeded. It never raises on the content it is describing. A workbook so
    broken it cannot be opened at all is the one thing it cannot survive, and
    it says so rather than pretending.

    AND IT IS THE HALF OF THE CONTRACT THE ENGINE OWES AN ASSISTANT
    ----------------------------------------------------------------
    A language model cannot be inside this engine: `pyproject.toml` promises
    numpy and openpyxl, the run has to be deterministic, and a workbook must
    give the same numbers on any day for the DOI to mean anything. So the
    understanding of *"divide Spanish hospitality into hotels and
    restaurants"* happens OUTSIDE, and what the engine owes in return is an
    exact statement of what it needs. That is this, and `--plan --json` is the
    same statement for a machine.

    Nothing here computes, fetches or writes. It reads a file and describes it.

    Returns `{"ready": bool, "gaps": [...], "have": {...}, "path": str}`.
    Each gap carries `sheet`, `what`, `why` and `fix`, and `severity` is
    `"blocking"` -- the run cannot start -- or `"weak"`, which is a run that
    starts and produces something nobody should publish.
    """
    path = Path(path)
    gaps: list[dict] = []

    def gap(sheet, what, why, fix, severity="blocking"):
        gaps.append({"sheet": sheet, "what": what, "why": why, "fix": fix,
                     "severity": severity})

    try:
        sheets = _open_workbook(path)
    except Exception as exc:                              # noqa: BLE001
        return {"ready": False, "path": str(path), "have": {},
                "gaps": [{"sheet": "-", "what": "the file cannot be opened",
                          "why": str(exc), "fix": "quadrium --template "
                                                  "my_config.xlsx writes a "
                                                  "fresh one",
                          "severity": "blocking"}]}

    for s in REQUIRED_SHEETS:
        if s not in sheets:
            gap(s, f"the sheet `{s}` is not in the workbook",
                "every configuration says which table to use, and that is "
                "where it says it",
                "start from `quadrium --template my_config.xlsx`")

    meta = {}
    for r in sheets.get("project", []):
        if r and r[0] is not None and str(r[0]).strip():
            k = str(r[0]).strip()
            if k.startswith("#"):
                continue
            meta[k.lower()] = r[1] if len(r) > 1 else None

    rows = {name: _rows(sheets, name)
            for name in ("splits", "keys", "scenarios", "profiles", "targets",
                         "satellites")}
    reg = {}
    for r in sheets.get("regionalise", []):
        if r and r[0] is not None and str(r[0]).strip():
            k = str(r[0]).strip()
            if k.startswith("#") or k.lower() in ("key", "sector_code"):
                continue
            reg[k.lower()] = r[1] if len(r) > 1 else None

    kind = str(meta.get("table_kind") or "").strip().lower()
    job = ("regionalise" if reg else
           "project" if rows["targets"] else
           "split" if rows["splits"] else None)

    # ---- the table -------------------------------------------------------
    if not kind:
        gap("project", "`table_kind` is empty",
            "the engine cannot read a file without being told whose format it "
            "is; every office writes its own",
            f"one of {', '.join(TABLE_KINDS)}")
    elif kind not in TABLE_KINDS:
        gap("project", f"`table_kind` is {kind!r}, which is not a kind",
            "a typo here reads as a format nobody publishes",
            f"one of {', '.join(TABLE_KINDS)}")

    raw_path = str(meta.get("table_path") or "").strip()
    if kind in ("eurostat", "eurostat_sut"):
        for need in ("eurostat_geo", "eurostat_year"):
            if not str(meta.get(need) or "").strip():
                gap("project", f"`{need}` is empty",
                    "the engine downloads the table by country and year, and "
                    "cannot guess either",
                    "`quadrium --find <CODE> --geo <XX>` prints the rows to "
                    "paste, including the years that country populates")
    elif not raw_path:
        gap("project", "`table_path` is empty",
            "nothing says which file holds the table",
            "an absolute path, or one relative to this workbook. "
            "`quadrium --sources` lists what is loadable on this machine")
    elif raw_path == TEMPLATE_TABLE_PATH:
        gap("project", "`table_path` still holds the value --template wrote",
            "that file ships with the SOURCE CHECKOUT of this project; if you "
            "installed the package you do not have it, and nothing in this "
            "workbook has been filled in yet",
            "`quadrium --sources` to see what you do have, or "
            "`quadrium --find <CODE> --geo <XX>` if you know the sector")
    else:
        p = Path(raw_path)
        if not p.is_absolute():
            p = (path.parent / p).resolve()
        if not p.exists():
            gap("project", f"`table_path` points at {p}, which is not there",
                "paths are absolute, or relative to THIS workbook — not to "
                "where you run the command",
                "`quadrium --sources` lists what is loadable here")

    mrio_region = str(meta.get("mrio_region") or "").strip()
    if kind == "eu_mrio" and not mrio_region:
        gap("project", "`mrio_region` is empty",
            "the European MRIO holds 272 regions and a table is one of them",
            "its NUTS-2 code, for example ES51 for Catalonia; a code the "
            "archive does not have is refused with that country's list")
    elif mrio_region and kind != "eu_mrio":
        gap("project", f"`mrio_region` is set with table_kind {kind!r}",
            "it names a region of the European MRIO and applies to `eu_mrio` "
            "alone", "remove the row, or change the kind")
    raw_year = str(meta.get("mrio_year") or "").strip()
    if raw_year and kind != "eu_mrio":
        gap("project", f"`mrio_year` is set with table_kind {kind!r}",
            "it picks a year of the European MRIO and applies to `eu_mrio` "
            "alone", "remove the row, or change the kind")
    elif raw_year:
        try:
            bad = int(float(raw_year)) not in range(2008, 2019)
        except ValueError:
            bad = True
        if bad:
            gap("project", f"`mrio_year` is {raw_year!r}",
                "the archive holds 2008 to 2018, one table per year",
                "a year in that range, or leave it empty for 2018")
    raw_emp = str(meta.get("mrio_employment") or "").strip()
    if raw_emp and kind != "eu_mrio":
        gap("project", f"`mrio_employment` is set with table_kind {kind!r}",
            "it fetches Eurostat's employment for a region of the European "
            "MRIO and applies to `eu_mrio` alone",
            "remove the row, or give the account in a `satellites` sheet")
    if kind == "eu_mrio" and job == "regionalise":
        gap("regionalise", "a regionalisation of an `eu_mrio` table",
            "that table already describes one region; a location quotient on "
            "it would estimate a region of a region",
            "use it with `splits`, or regionalise from a national table")

    t2_rows = str(meta.get("type_ii_income_rows") or "").strip()
    t2_col = str(meta.get("type_ii_household_column") or "").strip()
    if kind == "eu_mrio" and (t2_rows or t2_col):
        gap("project", "a type II closure is configured on the European MRIO",
            _EU_MRIO_NO_TYPE_II, "remove both type_ii rows")
    elif bool(t2_rows) != bool(t2_col):
        gap("project",
            f"`type_ii_{'household_column' if t2_rows else 'income_rows'}` is "
            f"empty and the other is not",
            "a type II closure needs both: income that is never spent, or "
            "spending funded by nothing, is half a loop",
            "name the value-added row(s) holding wages AND the final-demand "
            "column households spend, or remove both")
    elif t2_rows:
        gap("project", "a type II closure is configured",
            "the aggregate uplift is solid but RANKING subsectors by their "
            "type II multiplier is not: closed three ways on the UK table the "
            "economy-wide ratio moves 1.573 to 1.612 while the spread between "
            "industries nearly halves",
            "read the uplift, not the order. The report says which closure "
            "produced the numbers", severity="weak")

    unb = str(meta.get("table_unbalanced") or "refuse").strip().lower()
    if unb not in ("refuse", "residual_column"):
        gap("project", f"`table_unbalanced` is {unb!r}",
            "it has two legal values and a third reads as a setting that was "
            "ignored", "`refuse` (the default) or `residual_column`")
    elif unb != "refuse" and kind != "ine_interior":
        gap("project", f"`table_unbalanced` is set with table_kind {kind!r}",
            "it applies to `ine_interior` alone, whose published table does "
            "not balance for one product",
            "remove the row, or change the kind")

    # ---- the job ---------------------------------------------------------
    if job is None:
        gap("splits", "the workbook says which table to use and nothing to "
                      "do with it",
            "`splits` divides a sector, `regionalise` estimates a region, "
            "`targets` projects a supply-use pair. A workbook with none of "
            "the three describes no job",
            "fill in ONE of them")

    if job == "split":
        by_parent: dict = {}
        for r in rows["splits"]:
            by_parent.setdefault(str(r.get("sector_code") or "").strip(),
                                 []).append(r)
        for parent, rs in by_parent.items():
            if not parent:
                gap("splits", "a row has no `sector_code`",
                    "the rows of one split are the rows that share a parent",
                    "the code of the sector being divided, as the TABLE "
                    "writes it")
                continue
            if len(rs) < 2:
                gap("splits", f"`{parent}` has {len(rs)} subsector",
                    "dividing something into one piece is not a "
                    "disaggregation",
                    "at least two rows sharing this `sector_code`")
            for r in rs:
                if not str(r.get("new_code") or "").strip():
                    gap("splits", f"a row of `{parent}` has no `new_code`",
                        "the new subsector needs a name to be reported under",
                        "any code you choose; it does not have to exist "
                        "anywhere")

        named = {str(r.get("key_id") or "").strip()
                 for r in rows["splits"] if str(r.get("key_id") or "").strip()}
        have_keys = {str(r.get("key_id") or "").strip()
                     for r in rows["keys"] if str(r.get("key_id") or "").strip()}
        if not rows["keys"]:
            gap("keys", "no allocation key is registered",
                "the key decides how big each subsector is, and it is the "
                "sheet the result lives or dies by",
                "one row per subsector: key_id, new_sector_code, value, "
                "source, source_year, strength. `quadrium --find <CODE> "
                "--geo <XX>` prints them filled in where a source exists")
        for k in sorted(named - have_keys):
            gap("keys", f"`splits` names the key `{k}` and `keys` does not "
                        f"define it",
                "the split would have nothing to divide by",
                f"add rows with key_id `{k}`")

        illustrative = [r for r in rows["keys"]
                        if "REPLACE" in str(r.get("source") or "").upper()]
        if illustrative:
            gap("keys", f"{len(illustrative)} key row(s) still say REPLACE in "
                        f"their source",
                "those are the template's invented numbers; a split driven by "
                "them is a demonstration and the report will say so",
                "your own figures, with the real source written beside them",
                severity="weak")

        for r in rows["keys"]:
            s = str(r.get("strength") or "").strip().lower()
            if s and s not in ("strong", "medium", "weak"):
                gap("keys", f"`strength` is {s!r}",
                    "strength travels into the report and the ledger, so it "
                    "cannot be free text",
                    "strong, medium or weak")

        # Only when there IS one. Reported beside "no allocation key is
        # registered" it contradicted it in the same screen, which is the
        # kind of thing that makes a reader stop trusting the whole report.
        if rows["keys"] and len({k for k in have_keys if k}) < 2:
            gap("keys", "only one allocation key is registered",
                "a second key you do NOT use is the only external check this "
                "engine can make. On the one split where the answer is "
                "published, eight proxies of the same two subsectors spanned "
                "423.8 %",
                "register a second, with a different source, and leave it "
                "undriven", severity="weak")

        # Satellites are optional, so an empty sheet is not a gap. What IS
        # a gap is a sheet with rows in it that cannot become an account.
        if rows["satellites"]:
            names = {str(r.get("name") or "").strip()
                     for r in rows["satellites"]}
            if "" in names:
                gap("satellites", "a row has no `name`",
                    "several accounts share this sheet and the name is what "
                    "tells them apart",
                    "employment, co2, water — whatever you are measuring")
            for r in rows["satellites"]:
                if not str(r.get("unit") or "").strip():
                    gap("satellites",
                        f"{str(r.get('name') or '?')} has a row with no `unit`",
                        "a multiplier of 1.4 means nothing without one, and it "
                        "is printed everywhere the numbers are",
                        "persons, kt CO2e, cubic metres")
                    break
            gap("satellites",
                f"{len(names - {''})} account(s) will be split by the same key "
                f"as the output",
                "which says the subsectors have equal intensity — the same "
                "jobs per euro, the same tonnes per euro. For hotels against "
                "restaurants that is known to be false",
                "if you hold this quantity BY SUBSECTOR, that is the number "
                "to use; the split cannot invent a difference nobody measured",
                severity="weak")

        if not rows["profiles"]:
            gap("profiles", "no input profiles",
                "without them every subsector gets a scaled copy of the "
                "parent's purchasing pattern, so they all come out with the "
                "SAME multiplier — arithmetic, not economics",
                "leave it empty if sizes are all you need; the report says so "
                "either way", severity="weak")

    if job == "project":
        # The third job, and it had nothing here until 2026-09-08 -- so a
        # projection was the one workbook `--plan` said was fine while
        # `load_config` still refused it. A planner that covers two jobs of
        # three is worse than none for whoever runs the third.
        if kind != "eurostat_sut":
            gap("project", f"there are `targets` rows and table_kind is "
                           f"{kind or 'empty'!r}",
                "a projection moves a supply-use PAIR onto later totals; "
                "there is no pair to move in a symmetric table",
                "`table_kind: eurostat_sut`, with the same geo and year")
        if not str(meta.get("project_to_year") or "").strip():
            gap("project", "`project_to_year` is empty",
                "the targets say what the later year looks like and nothing "
                "says which year that is",
                "the year you are projecting TO, as a number")
        else:
            try:
                int(str(meta.get("project_to_year")).strip())
            except ValueError:
                gap("project",
                    f"`project_to_year` is "
                    f"{str(meta.get('project_to_year'))!r}, not a year",
                    "it is read as a number and compared against the pair's "
                    "own year", "four digits")

        VOCAB = {"gva", "final_use", "taxes", "imports", "industry_output",
                 "use_column_totals"}
        EURO, RAS = {"gva", "final_use"}, {"industry_output",
                                           "use_column_totals"}
        seen = set()
        for n, r in enumerate(rows["targets"], start=2):
            k = str(r.get("kind") or "").strip().lower()
            if not k:
                gap("targets", f"row {n} has no `kind`",
                    "the kind is what says which aggregate this row pins",
                    f"one of {', '.join(sorted(VOCAB))}")
            elif k not in VOCAB:
                gap("targets", f"row {n}: `kind` is {k!r}",
                    "an unknown kind is a target the method never applies, "
                    "and the run would approach totals you did not set",
                    f"one of {', '.join(sorted(VOCAB))}")
            else:
                seen.add(k)
        if seen & EURO and seen & RAS:
            gap("targets", "the sheet mixes the two methods' targets",
                f"`{', '.join(sorted(seen & EURO))}` belong to SUT-EURO and "
                f"`{', '.join(sorted(seen & RAS))}` to SUT-RAS; the sheet is "
                f"what chooses the method, so naming both chooses neither",
                "keep the pair that matches what you actually know")
        if seen and not (seen & EURO or seen & RAS):
            gap("targets", "only shared targets are given",
                "`taxes` and `imports` belong to both methods and settle "
                "nothing on their own, so nothing here picks a method",
                "add `gva` and `final_use`, or `industry_output` and "
                "`use_column_totals`")
        if "final_use" in seen:
            gap("targets", "`final_use` is at PURCHASERS' prices and `gva` at "
                           "BASIC prices",
                "the price bases are not decoration: the method carries taxes "
                "as a row of the use table, so a final-use target must include "
                "them. Get it wrong and it does not fail loudly — it runs to "
                "its iteration ceiling and reports every deviation as 1.00009, "
                "which reads like success",
                "check the basis of the totals you pasted. Projecting a pair "
                "onto its OWN totals returns that pair exactly, in one "
                "iteration, and is the test to run if you doubt them",
                severity="weak")

    if job == "regionalise":
        for need, why, fix in (
                ("activity_path",
                 "the method needs one thing about the region: its output or "
                 "employment by sector",
                 "a CSV with `sector_code,regional`"),
                ("method",
                 "which location quotient is a methodological choice with "
                 "measured consequences",
                 "SLQ, CILQ, RLQ or FLQ")):
            if not str(reg.get(need) or "").strip():
                gap("regionalise", f"`{need}` is empty", why, fix)
        if str(reg.get("method") or "FLQ").strip().upper() == "FLQ" \
                and not str(reg.get("delta") or "").strip():
            gap("regionalise", "`delta` is empty and the method is FLQ",
                "measured across ten regions in two countries it runs from "
                "0.14 to 0.60, so a default would be a guess wearing a number",
                "a value in [0, 1). The report prints what a blind choice "
                "costs")

    blocking = [g for g in gaps if g["severity"] == "blocking"]
    return {"ready": not blocking, "path": str(path), "gaps": gaps,
            "have": {"table_kind": kind or None, "job": job,
                     "splits": len(rows["splits"]), "keys": len(rows["keys"]),
                     "scenarios": len(rows["scenarios"]),
                     "profiles": len(rows["profiles"])}}


def build_satellites(rows: list[dict], table) -> dict:
    """Turn the `satellites` sheet into accounts aligned to the table's sectors.

    One row per (account, sector): `name | unit | sector_code | value |
    source | source_year`. Several accounts live in one sheet, told apart by
    `name`, because employment and emissions are the same shape and a sheet
    each would be four sheets before anyone had two accounts.

    A SECTOR THE SHEET DOES NOT MENTION IS REFUSED, NOT TAKEN AS ZERO
    -------------------------------------------------------------------
    Zero is a measurement. "This industry emits nothing" and "nobody wrote
    down what this industry emits" are different statements and only one of
    them is in the data. Filling the gap silently would put the first in a
    report on the strength of the second, and every multiplier below it would
    inherit that.

    So the sheet has to cover every sector of the table, and writing an
    explicit `0` is how you say you mean zero. That is the opt-in, and it lives
    in the sheet where a reader can see it rather than in a flag they cannot.
    """
    if not rows:
        return {}

    by_name: dict = {}
    for n, r in enumerate(rows, start=2):
        name = str(r.get("name") or "").strip()
        if not name:
            raise ConfigError(
                f"satellites row {n} has no `name`. The sheet holds several "
                f"accounts and the name is what tells them apart.")
        code = str(r.get("sector_code") or "").strip()
        if not code:
            raise ConfigError(f"satellites row {n} ({name}) has no "
                              f"`sector_code`.")
        try:
            value = float(r.get("value"))
        except (TypeError, ValueError):
            raise ConfigError(
                f"satellites row {n} ({name}, {code}): `value` is "
                f"{r.get('value')!r}, not a number.") from None
        acc = by_name.setdefault(name, {"values": {}, "unit": "",
                                        "source": "", "source_year": 0})
        if code in acc["values"]:
            raise ConfigError(
                f"satellites: {name!r} gives {code} twice. Two figures for one "
                f"sector is a choice somebody has to make, and it is not this.")
        acc["values"][code] = value
        for field_, key in (("unit", "unit"), ("source", "source"),
                            ("source_year", "source_year")):
            got = r.get(key)
            if got not in (None, ""):
                acc[field_] = got

    out = {}
    for name, acc in by_name.items():
        missing = [c for c in table.sector_codes if c not in acc["values"]]
        if missing:
            raise ConfigError(
                f"satellite {name!r} covers {len(acc['values'])} of the "
                f"table's {table.n} sectors. {len(missing)} are absent: "
                f"{', '.join(missing[:8])}"
                f"{' …' if len(missing) > 8 else ''}.\n\n"
                f"They are not taken as zero. Zero is a measurement — it says "
                f"the sector has none of this — and an absent row says only "
                f"that nobody wrote it down. Filling the gap here would put "
                f"the first in your report on the strength of the second, and "
                f"every multiplier below it would carry that.\n\n"
                f"Write an explicit 0 for the sectors you mean to be zero.")
        extra = [c for c in acc["values"] if c not in set(table.sector_codes)]
        if extra:
            raise ConfigError(
                f"satellite {name!r} gives values for {len(extra)} code(s) the "
                f"table does not have: {', '.join(extra[:8])}"
                f"{' …' if len(extra) > 8 else ''}. Check them against the "
                f"table's own classification ({table.classification}).")
        if not str(acc["unit"]).strip():
            raise ConfigError(
                f"satellite {name!r} has no `unit`. A multiplier of 1.4 means "
                f"nothing without one, and it is printed everywhere the "
                f"numbers are.")
        try:
            year = int(str(acc["source_year"]).strip() or 0)
        except ValueError:
            year = 0
        out[name] = Satellite(
            name=name, unit=str(acc["unit"]).strip(),
            values=[acc["values"][c] for c in table.sector_codes],
            source=str(acc["source"]).strip() or "not stated",
            source_year=year)
    return out


def _type_ii_spec(meta: dict, table) -> dict:
    """Which value-added rows are income and which final-demand column is
    household spending, resolved against this table's own labels.

    `UNH_20` ¶20.88 names the concept — wages and salaries — and no more. Which
    row of a particular table holds them is a fact about that table, so the
    workbook says it and this checks it. Nothing is guessed: a label the table
    does not have is refused with the labels it does have, because the
    alternative is closing the model on the wrong row and reporting the result
    as an induced effect.
    """
    rows = str(meta.get("type_ii_income_rows") or "").strip()
    col = str(meta.get("type_ii_household_column") or "").strip()
    if not rows and not col:
        return {}
    if not rows or not col:
        raise ConfigError(
            "a type II closure needs BOTH `type_ii_income_rows` and "
            "`type_ii_household_column`. One without the other describes half "
            "a loop: income that is never spent, or spending funded by "
            "nothing.")

    want = [r.strip() for r in rows.split(";") if r.strip()]
    have_va = list(table.VA_labels)
    missing = [r for r in want if r not in have_va]
    if missing:
        raise ConfigError(
            f"`type_ii_income_rows` names {', '.join(missing)}, which this "
            f"table does not have. Its value-added rows are: "
            f"{'; '.join(have_va)}.\n\n"
            f"Closing on the wrong row does not fail — it returns a number "
            f"that looks like an induced effect and is not one.")
    if col not in list(table.Y_labels):
        raise ConfigError(
            f"`type_ii_household_column` is {col!r}, which this table does "
            f"not have. Its final-demand columns are: "
            f"{'; '.join(table.Y_labels)}.")
    return {"income_rows": want, "household": col}
