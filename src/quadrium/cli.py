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
        print(f"\n  Put this in the `project` sheet:\n")
        for line in s.config_lines():
            print(f"      {line}")
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
