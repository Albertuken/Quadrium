#!/usr/bin/env python3
"""
Quadrium — run a disaggregation from a configuration workbook.

No Python required. Fill in a spreadsheet, run one command, read the report.

    quadrium --template my_config.xlsx    # get a blank workbook
    quadrium my_config.xlsx               # run it
    quadrium my_config.xlsx --check       # validate, do not run
    quadrium my_config.xlsx --offline     # refuse to download anything

A configuration can name a file, or it can name a country and a year and let
the engine fetch the table from Eurostat. A fetched table is cached with its
SHA-256 and never downloaded twice, so the second run of a configuration reads
the same bytes as the first.

From a checkout, without installing: `python3 run_quadrium.py …` does the same.

Exit code 0 means every scenario passed validation. Anything else means read
the message: the errors are written for an economist, not for a programmer, and
they say which subsector or which proxy is the problem.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Relative imports would do here, but the absolute ones keep this file
# runnable as a script from a checkout as well as importable from an
# install; `run_quadrium.py` at the repository root puts `src/` on the
# path and calls `main` below.
from quadrium.config import ConfigError, load_config, write_template  # noqa: E402
from quadrium.project import IOProject  # noqa: E402
from quadrium.scenarios import ScenarioInfeasible  # noqa: E402


def _describe(cfg: dict) -> None:
    t = cfg["table"]
    print(f"Table   : {t.table_id} — {t.country} {t.year}, {t.n} sectors")
    print(f"          {t.unit}")
    print(f"          balance verified on load; negatives: "
          f"Z={int((t.Z < 0).sum())} Y={int((t.Y < 0).sum())} "
          f"VA={int((t.VA < 0).sum())}")
    for s in cfg["splits"]:
        i = t.index_of(s.sector_code)
        print(f"Split   : {s.sector_code} ({t.sector_labels[i].strip()[:38]}) "
              f"-> {', '.join(s.new_codes)}")
    for k in cfg["keys"].values():
        print(f"Key     : {k.key_id} [{k.strength.value}] "
              + ", ".join(f"{c} {w:.1%}" for c, w
                          in zip(k.new_sector_codes, k.weights)))
    for sc in cfg["scenarios"]:
        n = sum(len(v) for v in sc.input_profiles.values())
        print(f"Scenario: {sc.scenario_id} — {sc.label}"
              + (f" ({n} input intensities)" if n else " (no input profiles)"))



def _warn_about_substance(cfg: dict) -> None:
    """Say what is WEAK about a configuration that is structurally VALID.

    `--check` parses the workbook and confirms the table balances. A reader
    takes "valid" for "ready", and the two are not the same: a split driven by
    a key its own author marked `weak` parses perfectly. The engine already
    knew — it printed `[weak]` next to the key — and then said "valid" without
    connecting the two (2026-08-10).

    Everything here is a caution, never an error. It changes no exit code.
    """
    notes = []
    for note in cfg.get("defaults_taken", []):
        notes.append(f"a default was taken: {note}")
    weak = sorted(k.key_id for k in cfg["keys"].values()
                  if getattr(k.strength, "value", str(k.strength)) == "weak")
    if weak:
        notes.append(
            f"the key(s) {', '.join(weak)} are marked WEAK by whoever "
            f"registered them. Every figure a split driven by one produces "
            f"inherits that, and no check in this system will object")
    profiled = sorted(s.scenario_id for s in cfg["scenarios"]
                      if getattr(s, "input_profiles", None))
    if profiled:
        notes.append(
            f"scenario(s) {', '.join(profiled)} carry input profiles. No "
            f"allocation key backs a purchasing pattern, so the differentiated "
            f"multipliers they produce are demonstrations, not estimates")
    spare = [k.key_id for k in cfg["keys"].values()]
    if len(spare) < 2:
        notes.append(
            "only one allocation key is registered, so nothing can corroborate "
            "the split. Registering a second key you do NOT use turns it into "
            "an external check — the only kind this system can make")
    if not notes:
        return
    print("\nValid is not the same as well founded:")
    for n in notes:
        print(f"  - {n}")


def _catalogue(args) -> int:
    """`--sources` and `--find`, which need no configuration and no network."""
    from quadrium.catalogue import advise, scan

    sources = scan(args.data)
    if not sources:
        print(f"No loadable table found under {args.data.resolve()}.\n"
              f"Nothing is wrong: this looks in `data/eurostat/`, `data/ine/` "
              f"and for `UK_IOAT_*.xlsx`. A configuration with "
              f"`table_kind: eurostat` fetches one without any of them.",
              file=sys.stderr)
        return 1

    if args.sources:
        tables = [s for s in sources if s.kind == "table"]
        proxies = [s for s in sources if s.kind == "proxy"]

        print(f"{len(tables)} table(s) you can load and split\n")
        print(f"  {'source':56s}{'sectors':>8}{'discarded':>11}")
        for s in tables:
            more = f"{len(s.finer)}" if s.finer else "—"
            print(f"  {s.source_id:56s}{s.resolution:>8}{more:>11}")

        if any(s.finer for s in tables):
            print("\n  `discarded` is detail the PUBLISHER publishes and this "
                  "engine drops: where\n  a country serves both a code and its "
                  "components, the loader keeps the coarser\n  tiling. "
                  "`--find CODE --geo XX` says when that affects the sector "
                  "you want.")

        if proxies:
            print(f"\n{len(proxies)} source(s) that measure sectors — "
                  f"candidate allocation keys\n")
            print(f"  {'source':56s}{'sectors':>8}  countries")
            for s in proxies:
                geos = (",".join(s.geos[:5]) + ("…" if len(s.geos) > 5 else "")
                        ) if s.geos else "—"
                print(f"  {s.source_id:56s}{s.resolution:>8}  {geos}")

        print("\n  Sectors counted are the codes that CARRY DATA. Eurostat "
              "lists the whole CPA\n  hierarchy in its metadata whether a "
              "country publishes at that level or not:\n  Spain's symmetric "
              "table lists CPA_I55 and CPA_I56 and populates neither.")
        print("\n  Resolution is the only thing this ranks by, and it is NOT "
              "comparability.\n  Eurostat harmonises the format and neither "
              "harmonises nor records the method.")
        return 0

    a = advise(args.find, sources, args.geo)
    print(f"\n  {a['target']} — {a['action'].replace('_', ' ')}\n")
    for line in _wrap(a["why"], 74):
        print(f"  {line}")

    # NOTHING ON DISK FOR THAT COUNTRY IS A TRUE ANSWER AND A USELESS ONE.
    # On a fresh install the catalogue holds whatever shipped, so the first
    # question a new user asks -- about their own country -- lands here. What
    # they need next is which years exist, which is one small query per
    # dataset and is cached afterwards.
    if a["action"] == "none" and args.geo and not args.offline:
        _availability(args, a)

    # The verdict belongs on EVERY answer that names a country, not only on
    # the branch that found nothing on disk. A user whose table IS here is the
    # one who most needs to know it refuses: Ireland's and Sweden's are in this
    # checkout precisely because they do.
    if args.geo:
        _verdicts(args.geo.strip().upper(), args.data)

    if a["action"] == "choose_country":
        print(f"\n  {'country':>9}  verdict     finest table")
        for g, h in sorted(a["by_geo"].items()):
            where = (h["container"] or "—") if h["verdict"] != "SEPARATE" \
                else a["target"]
            print(f"  {g:>9}  {h['verdict']:<10}  {h['source'].source_id} "
                  f"({where})")
        print(f"\n  Add --geo XX to get a recommendation.")
        return 0

    if a["best"] and a["action"] in ("load", "split"):
        s = a["best"]["source"]
        note = _year_advice(s, args.geo, args.data) if args.geo else ""
        print(f"\n  Put this in the `project` sheet:\n")
        for line in s.config_lines():
            if note and line.startswith("eurostat_year"):
                line = line.split()[0] + f"    {note[0]}"
            print(f"      {line}")
        if note:
            print(f"\n  {note[1]}")
        if a["action"] == "split":
            print(f"\n  and divide `{a['best']['container']}` in the `splits` "
                  f"sheet.")

    for pr in a.get("proxies", [])[:4]:
        print()
        head = ("A key that measures its parts:" if pr["tiles"] else
                "Related, but NOT a key for this split:")
        print(f"  {head}")
        print(f"      {pr['source'].source_id}")
        print(f"      measures {', '.join(pr['parts'])}")
        if not pr["tiles"]:
            print(f"      — these are parts of {', '.join(pr['covers'])}, not "
                  f"of `{a['best']['container']}`. They cover one")
            print(f"        piece of it and say nothing about the rest, so "
                  f"they cannot drive this split.")
    if a.get("proxies"):
        print("\n  A proxy is a candidate, not a recommendation. Whether "
              "employment is the\n  right key is a judgement about the "
              "sectors — two subsectors share a\n  headcount far more evenly "
              "than they share an output.")
    return 0


def _availability(args, a) -> None:
    """What Eurostat actually carries for a country whose tables are not here.

    Every count comes from the VALUE map and not from the `time` dimension,
    which lists the years a dataset spans rather than the years a country
    populates. Read the wrong one and this printed a configuration naming 2024
    for Germany, which fails: Eurostat answers 200 with an empty result for a
    year a country does not publish. Advice you have not run is not advice.
    """
    from quadrium.catalogue import available_years
    from quadrium.eurostat import DATASETS

    geo = args.geo.strip().upper()
    print(f"\n  Asking Eurostat what it carries for {geo}…")
    years = available_years(geo, Path(args.data) / "data" / "eurostat",
                            refresh=args.refresh)
    if not years:
        print(f"  Nothing came back for {geo}. Either it is not a code "
              f"Eurostat knows,\n  or the network is not there. `--offline` "
              f"skips this question entirely.")
        return

    taken = str(years.pop("_taken", ""))[:10]
    labels = {"product_by_product": "symmetric, product x product",
              "industry_by_industry": "symmetric, industry x industry",
              "supply": "supply", "use_purchasers": "use, purchasers' prices",
              "use_basic": "use, basic prices, split DOM / IMP"}
    print(f"\n  {'dataset':<22}{'years':>7}  range")
    for name in ("product_by_product", "industry_by_industry", "supply",
                 "use_purchasers", "use_basic"):
        ys = years.get(name)
        row = f"{len(ys):>7}  {ys[0]}–{ys[-1]}" if ys else f"{'—':>7}  none  "
        print(f"  {DATASETS[name]:<22}{row}  {labels[name]}")
    print(f"\n  (years a country POPULATES, not the years the dataset spans; "
          f"asked {taken},\n  cached, and `--refresh` asks again)")

    sym_kind = ("product_by_product" if years.get("product_by_product")
                else "industry_by_industry" if years.get("industry_by_industry")
                else None)
    pair = years.get("supply") and years.get("use_purchasers")
    transformable = pair and years.get("use_basic")

    if sym_kind:
        ys = years[sym_kind]
        print(f"\n  A symmetric table, most recent {ys[-1]}:\n")
        for line in ("table_kind       eurostat",
                     f"eurostat_geo     {geo}",
                     f"eurostat_year    {ys[-1]}",
                     f"eurostat_dataset {sym_kind}"):
            print(f"      {line}")

    if transformable:
        newest = min(years["supply"][-1], years["use_purchasers"][-1],
                     years["use_basic"][-1])
        extra = ("" if sym_kind and years[sym_kind][-1] >= newest
                 else f"  — and {newest} exists ONLY as a pair")
        print(f"\n  Or the supply-use pair, most recent {newest}{extra}:\n")
        for line in ("table_kind       eurostat_sut",
                     f"eurostat_geo     {geo}",
                     f"eurostat_year    {newest}",
                     "eurostat_model   D"):
            print(f"      {line}")

    if not sym_kind and not transformable:
        print(f"\n  {geo} HAS NO ROUTE TO A SYMMETRIC TABLE HERE, and that is "
              f"the answer,\n  not a failure to look. Eurostat carries no "
              f"symmetric table for it, and")
        if pair:
            print(f"  the supply-use pair it does carry has no "
                  f"`{DATASETS['use_basic']}` —\n  use at basic prices split "
                  f"into domestic and imported. Without that\n  split a "
                  f"transformation would have to assume every user of a "
                  f"product\n  imports the same share of it, which is an "
                  f"economic hypothesis this\n  engine will not make for you.")
            print(f"\n  The pair still loads, and every supply-use identity "
                  f"still holds on it.\n  What it cannot do is become a "
                  f"symmetric table. For that, {geo}'s own\n  statistical "
                  f"office is the place to look — Eurostat is not the only\n"
                  f"  publisher, only the harmonised one.")
        else:
            print(f"  it carries no usable supply-use pair either.")


def _year_advice(source, geo: str, data_root):
    """Do not print a configuration for a year that is known to refuse.

    The recommendation names whatever file happens to be cached, and for
    Ireland that was its 2020 symmetric table — 50 % short of its own printed
    total, refused at every year tried. Handing a user a configuration for it
    and letting the refusal explain itself later is not advice.

    Returns `(year, sentence)` when the recommended year refuses and something
    can be said about it, or `""` when the recommendation stands as it is.
    """
    import json

    route = "symmetric" if getattr(source, "dataset", "") in (
        "naio_10_cp1700", "naio_10_cp1750") else "pair"
    if getattr(source, "table_kind", "") != "eurostat":
        return ""
    try:
        rec = json.loads((Path(data_root) / "data" / "eurostat"
                          / "_verdicts.json").read_text()).get(geo.upper())
    except (OSError, ValueError, AttributeError):
        return ""
    e = (rec or {}).get(route) or {}
    if not e or e.get("verdict") == "loads" or e.get("year") != source.year:
        return ""
    good = sorted(y for y, v in (e.get("also_tried") or {}).items()
                  if v == "loads")
    if good:
        return (good[-1],
                f"{source.year} is refused for this country — {e['cause']} — "
                f"so the year above is {good[-1]}, the newest that was tried "
                f"and loaded"
                + (f" (also {', '.join(good[:-1])})" if len(good) > 1 else "")
                + ".")
    tried = sorted(e.get("also_tried") or {})
    return (source.year,
            f"**{source.year} is refused for this country** — {e['cause']}: "
            f"{e['detail']}"
            + (f", and so {'is' if len(tried) == 1 else 'are'} "
               f"{', '.join(tried)}" if tried else "")
            + ". The configuration above is what you would write if it "
              "loaded; it will refuse, and say why.")


def _verdicts(geo: str, data_root) -> None:
    """What the newest table of each kind actually did, when it was checked.

    "Eurostat carries this, which is not a promise it loads" was a fair caveat
    while nothing better was known. The sweep of 2026-08-25 loaded every
    country's newest table by both routes, so the verdict can be named instead
    of hedged.

    EVIDENCE, NOT PREDICTION. Each line says which year was checked, and which
    others were. That caveat used to be the whole of this docstring and it was
    load-bearing: **three of the ten symmetric refusals turned out to be about
    the year and not the country.** France's 2022 table is refused for sparse
    final demand and its 2010, 2016 and 2021 tables load — twelve usable years
    behind a verdict that said "France refuses". Slovakia and Croatia are the
    same. Ireland, Lithuania, Luxembourg, Malta, Norway, Poland and Sweden
    refuse in every year tried, which is a different fact and now a stated one.

    Years not tried are still not claimed either way.
    """
    import json

    f = Path(data_root) / "data" / "eurostat" / "_verdicts.json"
    try:
        rec = json.loads(f.read_text()).get(geo)
    except (OSError, ValueError):
        rec = None
    if not rec:
        print(f"\n  Whether any of this LOADS has not been checked for {geo}. "
              f"Carrying is not\n  loading: the engine verifies the "
              f"publisher's own identities and refuses a\n  table whose books "
              f"do not close within its own printed precision.")
        return

    print(f"\n  And what happened when they were last loaded:\n")
    for key, label in (("symmetric", "symmetric table"), ("pair", "the pair")):
        e = rec.get(key)
        if not e:
            continue
        year = e.get("year")
        also = e.get("also_tried") or {}
        good = sorted(y for y, v in also.items() if v == "loads")
        bad = sorted(y for y, v in also.items() if v != "loads")
        if e["verdict"] == "loads":
            print(f"      {label:16s} {year}   LOADS")
        elif e["verdict"] == "not published":
            print(f"      {label:16s}  —     {e['cause']}, {e['detail']}")
        else:
            print(f"      {label:16s} {year}   REFUSED — {e['cause']}: "
                  f"{e['detail']}")
        # A refusal at the newest year is not a refusal of the country, and
        # saying so is the difference between France having no table and
        # France having twelve.
        if good:
            print(f"      {'':16s}        but {', '.join(good)} "
                  f"{'LOADS' if len(good) == 1 else 'LOAD'} — set the year in "
                  f"your configuration")
        elif bad and e["verdict"] not in ("loads", "not published"):
            verb = "does" if len(bad) == 1 else "do"
            print(f"      {'':16s}        and so {verb} {', '.join(bad)}")
    print(f"\n  Checked on the years named and on those only — evidence, not "
          f"a\n  prediction about the rest.")


def _wrap(text: str, width: int) -> list[str]:
    import textwrap
    return textwrap.wrap(text, width) or [""]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Run an IO disaggregation from a configuration workbook.")
    ap.add_argument("config", nargs="?", type=Path,
                    help="the .xlsx configuration workbook")
    ap.add_argument("--template", type=Path, metavar="PATH",
                    help="write a blank workbook to PATH and exit")
    ap.add_argument("--check", action="store_true",
                    help="validate the configuration and the table, then stop")
    ap.add_argument("--outputs", type=Path, default=Path("outputs"),
                    help="where project folders are written "
                         "(default: ./outputs)")
    ap.add_argument("--sources", action="store_true",
                    help="list every table on disk this engine can load, and "
                         "how many sectors each distinguishes")
    ap.add_argument("--find", metavar="CODE",
                    help="say where a sector code is available, and if "
                         "nowhere, which coarser code to split")
    ap.add_argument("--geo", metavar="XX",
                    help="the country --find is asking about. Without it "
                         "nothing is recommended, because a finer table for "
                         "another economy answers a different question")
    ap.add_argument("--data", type=Path, default=Path("."),
                    help="where --sources and --find look (default: .)")
    ap.add_argument("--offline", action="store_true",
                    help="never touch the network. A table_kind that would "
                         "need a download fails, naming the URL to fetch by "
                         "hand")
    ap.add_argument("--refresh", action="store_true",
                    help="re-download a cached table even though it is "
                         "already here. Statistical offices revise, so this "
                         "can change your results — it says so when it does")
    args = ap.parse_args(argv)

    if args.template:
        p = write_template(args.template)
        print(f"Template written to {p}")
        print("Fill it in — every sheet carries its own instructions — then:")
        # The installed user has no run_quadrium.py. Echo whatever
        # they actually typed -- a clean-venv install test is what
        # found this telling them to run a file they do not have.
        print(f"    {Path(sys.argv[0]).name} {p}")
        return 0

    if args.sources or args.find:
        return _catalogue(args)

    if not args.config:
        ap.print_help()
        return 2

    if args.offline and args.refresh:
        print("--offline and --refresh contradict each other: one forbids the "
              "network, the other requires it.", file=sys.stderr)
        return 2

    try:
        cfg = load_config(args.config, offline=args.offline,
                          refresh=args.refresh)
    except ConfigError as exc:
        print(f"Configuration problem in {args.config}:\n\n{exc}\n",
              file=sys.stderr)
        return 1

    _describe(cfg)
    # Printed on BOTH paths. Warning only under --check would mean the run that
    # actually produces numbers is the quieter of the two.
    _warn_about_substance(cfg)
    if args.check:
        print("\nConfiguration and table are valid. Nothing was run "
              "(--check).")
        return 0

    project = IOProject(
        project_id=cfg["project_id"], table=cfg["table"], splits=cfg["splits"],
        scenarios=cfg["scenarios"], keys=cfg["keys"], ledger=cfg["ledger"],
        title=cfg["title"], source_file=cfg["source_file"], root=args.outputs,
        preamble=cfg["notes"] or "")
    try:
        project.run().write()
    except ScenarioInfeasible as exc:
        print(f"\nEvery scenario was rejected.\n\n{exc.detail}\n",
              file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"\n{exc}\n", file=sys.stderr)
        return 1

    print()
    print(project.summary())
    print(f"\nReport : {project.dir / 'report.md'}")
    print(f"Folder : {project.dir}")
    rejected = project.meta.get("infeasible", [])
    if rejected:
        # Not a malfunction, and the report says so -- but not a clean run
        # either, and the exit code is what a script reads. Counting only
        # `results` returned 0 for a run that produced one table out of two.
        print(f"\n{len(rejected)} scenario(s) were REJECTED before they could "
              f"be balanced: {', '.join(r['scenario_id'] for r in rejected)}. "
              f"The numbers you gave them describe an economy that cannot "
              f"exist; the report says which figure is the problem, under "
              f"'Scenarios that were rejected'.", file=sys.stderr)
    ok = (all(r.report.passed for r in project.results) and not rejected)
    if not all(r.report.passed for r in project.results):
        print("\nAt least one scenario FAILED validation. Read the report "
              "before using any number from it.", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
