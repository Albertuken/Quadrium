"""
`IOProject` — the orchestration object (MVP_0.1 §3).

Each project lives in `outputs/<project_id>/`, and everything needed to
reproduce the run from scratch is written there: the original table copied, the
allocation keys, the scenario parameters, the environment, and a hash of the
input file.

Why the hash. A reproducibility folder that records "loaded UK IO 2022.csv" is
worthless the day that file is replaced with a revised vintage and nobody
notices. The hash makes silent substitution detectable.

Why the original table is copied. Reaggregation is checked against it, and a
check against a file that may have moved is not a check.
"""

from __future__ import annotations

import hashlib
import platform
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import __version__
from .export import (write_json, write_provenance_csv, write_table_csv,
                     write_xlsx)
from .models import (AssumptionLedger, CellLabel, IOTable, Scenario,
                     SplitSpec, count_label)
from .reporting import build_report
from .scenarios import run_project


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class IOProject:
    project_id: str
    table: IOTable
    splits: list[SplitSpec]
    scenarios: list[Scenario]
    keys: dict
    title: str = ""
    ledger: AssumptionLedger | None = None
    source_file: Path | None = None
    root: Path = Path("outputs")
    preamble: str = ""

    results: list = field(default_factory=list, init=False)
    meta: dict = field(default_factory=dict, init=False)

    @property
    def dir(self) -> Path:
        return Path(self.root) / self.project_id

    def run(self) -> "IOProject":
        self.results, self.meta = run_project(
            self.table, self.splits, self.scenarios, self.keys)
        return self

    # -- the reproducibility record ----------------------------------------

    def _manifest(self) -> dict:
        src = Path(self.source_file) if self.source_file else None
        return {
            "project_id": self.project_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            # The authoritative list of scenario IDS. A consumer that globs
            # scenarios/*/ should check against this rather than trust the
            # filesystem: the folder is where stale results hide.
            #
            # NOT called "scenarios": this dict already has that key, holding
            # the full scenario objects, and a duplicate key in a dict literal
            # is discarded by Python without a word. The test caught it; the
            # interpreter would never have (2026-08-10).
            "scenario_ids": sorted(res.scenario_id for res in self.results),
            "scenarios_removed_as_stale": sorted(
                getattr(self, "removed_scenarios", [])),
            "quadrium_version": __version__,
            "environment": {
                "python": sys.version.split()[0],
                "numpy": np.__version__,
                "platform": platform.platform(),
            },
            "input": {
                "path": str(src) if src else None,
                # A source can be a FOLDER: a supply-use system is three files, so
        # `table_path` names where they live rather than which one they are.
        # Their individual checksums are recorded by the loader, on the table.
        "sha256": _sha256(src) if src and src.is_file() else None,
                "note": ("The hash exists so that a silently revised input "
                         "vintage is detectable. A reproducibility record that "
                         "names a file without fixing its contents is not one."),
            },
            "table": {
                "table_id": self.table.table_id, "country": self.table.country,
                "year": self.table.year, "unit": self.table.unit,
                "classification": self.table.classification,
                "source": self.table.source, "n_sectors": self.table.n,
                "notes": self.table.notes,
                "negatives": {
                    "Z": int((self.table.Z < 0).sum()),
                    "Y": int((self.table.Y < 0).sum()),
                    "VA": int((self.table.VA < 0).sum()),
                },
            },
            "splits": [
                {
                    "sector_code": s.sector_code,
                    "sector_label": self.table.sector_labels[
                        self.table.index_of(s.sector_code)],
                    "into": dict(zip(s.new_codes, s.new_labels)),
                    "keys_by_block": s.keys_by_block,
                    "input_profiles": s.input_profiles,
                } for s in self.splits
            ],
            "allocation_keys": {
                k.key_id: {
                    "applies_to": k.applies_to, "source": k.source,
                    "source_year": k.source_year, "strength": k.strength.value,
                    "new_sector_codes": k.new_sector_codes,
                    "raw_values": k.raw_values, "weights": k.weights,
                    "notes": k.notes,
                } for k in self.keys.values()
            },
            "scenarios": [
                {
                    "scenario_id": s.scenario_id, "label": s.label,
                    "description": s.description,
                    "keys_by_block": s.keys_by_block,
                    "balancing_method": s.balancing_method,
                    "balancing_tolerance": s.balancing_tolerance,
                    "reaggregation_tolerance_pct": s.reaggregation_tolerance_pct,
                    "internal_block_alpha": s.internal_block_alpha,
                    "locked_cells": s.locked_cells,
                    "user_constraints": s.user_constraints,
                } for s in self.scenarios
            ],
            "outcome": {
                "scenarios_run": [r.scenario_id for r in self.results],
                "scenarios_rejected": self.meta.get("infeasible", []),
                # A rejected scenario never reaches validation, so it
                # cannot be counted as having passed it. Reading only
                # `results` made a run that produced one table out of two
                # indistinguishable, here and in the exit code, from one
                # that produced both.
                "all_passed": (all(r.report.passed for r in self.results)
                               and not self.meta.get("infeasible")),
            },
            "tolerances": (
                "No published source states a numerical tolerance for an "
                "accounting identity, and six were searched: what a balance can "
                "be tested against is a property of the table, not of the "
                "method. The floor applied here is derived from the table's own "
                "stated precision — an identity summing n cells published to d "
                "decimals cannot be checked more tightly than 0.5*10^-d*n. "
                "Tolerances that remain a genuine choice are labelled "
                "PROJECT CHOICE where they are used."),
        }

    def write(self) -> Path:
        """Write everything needed to reproduce and to audit the run."""
        if not self.results:
            raise RuntimeError("call run() before write()")
        d = self.dir
        d.mkdir(parents=True, exist_ok=True)

        # ------------------------------------------------------------------
        # REMOVE SCENARIO FOLDERS THIS RUN DID NOT PRODUCE.
        #
        # write() only ever created directories, never removed them, so a
        # scenario deleted from the configuration left its last results on
        # disk looking current. Found on this project's own pilot: a scenario
        # withdrawn for being misleading was still sitting in outputs/ a day
        # later, indistinguishable from the live ones (2026-08-10). A person
        # reading report.md would not have seen it; anything globbing
        # scenarios/*/ would have.
        #
        # Deletion is confined to directories under this project's own
        # scenarios/ folder, and every removal is announced. Trading a stale
        # result for a silent deletion would be no improvement.
        # ------------------------------------------------------------------
        mine = {res.scenario_id for res in self.results}
        sdir = d / "scenarios"
        self.removed_scenarios = []
        if sdir.exists():
            for old in sorted(p for p in sdir.iterdir() if p.is_dir()):
                if old.name not in mine:
                    shutil.rmtree(old)
                    self.removed_scenarios.append(old.name)

        write_json(self._manifest(), d / "project.json")
        write_table_csv(self.table, d / "original_table.csv")
        if self.ledger:
            write_json({"project_id": self.ledger.project_id,
                        "assumptions": self.ledger.assumptions},
                       d / "assumption_ledger.json")

        for res in self.results:
            sd = d / "scenarios" / res.scenario_id
            sd.mkdir(parents=True, exist_ok=True)
            counts = {lbl.value: count_label(res.provenance, lbl)
                      for lbl in CellLabel}
            total = res.provenance.size
            est = counts.get("proxy_estimated", 0)
            bal = counts.get("balanced_adjustment", 0)
            note = (
                f"{res.table.table_id} - scenario {res.scenario_id}. "
                f"NOT ALL OF THESE NUMBERS ARE OBSERVED.\n"
                f"{est:,} of {total:,} cells ({100*est/total:.1f} %) are "
                f"ESTIMATED from an allocation proxy and {bal:,} "
                f"({100*bal/total:.1f} %) were moved by the balancing solver.\n"
                f"Cell-by-cell status is in provenance.csv in this folder; the "
                f"caveats are in ../../report.md. Quoting a figure from this "
                f"file without them states an estimate as a measurement.")
            write_table_csv(res.table, sd / "table_disaggregated.csv",
                            provenance_note=note)
            write_provenance_csv(res, sd / "provenance.csv")
            write_xlsx(res, sd / "table_disaggregated.xlsx")
            write_json(res.report, sd / "validation_report.json")
            write_json({k: v for k, v in res.diagnostics.items()
                        if k not in ("A", "L")},   # matrices go to CSV, not JSON
                       sd / "diagnostics.json")
            # An uncomputable coefficient is written EMPTY, not zero.
            # nan_to_num turned it into 0.00000000, which reads as "this
            # industry buys nothing from that one" -- a plausible-looking
            # statement -- when it means the ratio could not be formed at all.
            A = res.diagnostics["A"]
            with open(sd / "technical_coefficients.csv", "w",
                      encoding="utf-8") as fh:
                fh.write("# a_ij = Z_ij / X_j. An EMPTY cell means the "
                         "coefficient could not be computed (zero output), "
                         "which is not the same as a coefficient of zero.\n")
                fh.write(",".join(res.table.sector_codes) + "\n")
                for row in A:
                    fh.write(",".join("" if v != v else f"{v:.8f}"
                                      for v in row) + "\n")

        report = build_report(self.results, self.meta,
                              self.title or "Sector split")
        if self.preamble:
            report = report.replace("Quadrium 0.1.0 (MVP 0.1)",
                                    f"Quadrium 0.1.0 (MVP 0.1)\n\n{self.preamble}",
                                    1)
        if self.ledger:
            report += ("\n---\n\n## Assumption ledger\n\n"
                       + self.ledger.to_markdown_table() + "\n")
        (d / "report.md").write_text(report, encoding="utf-8")
        return d

    def summary(self) -> str:
        lines = []
        for name in getattr(self, "removed_scenarios", []):
            lines.append(f"  removed stale scenario folder from a previous "
                         f"run: {name}")
        for res in self.results:
            b, r = res.diagnostics["balance_info"], res.report
            lines.append(
                f"  {res.scenario_id:<16s} {b['method']:<5s} "
                f"conv={b['converged']} it={b['iterations']:<4d} "
                f"reagg={r.reaggregation_error_pct:.2e} % "
                f"signchg={b['sign_changes']} "
                f"-> {'PASS' if r.passed else 'FAIL'} ({r.n_warnings} warn)")
        for inf in self.meta.get("infeasible", []):
            lines.append(f"  {inf['scenario_id']:<16s} REJECTED — "
                         f"{inf['explanation']}")
        return "\n".join(lines)
