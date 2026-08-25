#!/usr/bin/env python3
"""
Quadrium — run a disaggregation from a configuration workbook.

No Python required. Fill in a spreadsheet, run one command, read the report.

    quadrium --template my_config.xlsx    # get a blank workbook
    quadrium my_config.xlsx               # run it
    quadrium my_config.xlsx --check       # validate, do not run

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

    if not args.config:
        ap.print_help()
        return 2

    try:
        cfg = load_config(args.config)
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
