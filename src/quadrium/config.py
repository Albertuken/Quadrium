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

Everything the workbook cannot express is a project default, and every default
is documented where it lives. Nothing here invents an economic assumption.
"""

from __future__ import annotations

from pathlib import Path

from .io_loader import LoaderError, _open_workbook, load_ine_tio, \
    load_io_table, load_uk_analytical_iot
from .models import (AllocationKey, Assumption, AssumptionLedger,
                     ProxyStrength, Scenario, SplitSpec)

REQUIRED_SHEETS = ("project", "splits")
TABLE_KINDS = ("uk_analytical", "interchange",
               "ine_interior", "ine_total")


class ConfigError(ValueError):
    """Something in the workbook is wrong, said in the analyst's terms."""


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


def load_config(path: Path | str) -> dict:
    """Read a configuration WORKBOOK and return everything `IOProject` needs."""
    path = Path(path)
    sheets = _open_workbook(path)
    missing = [s for s in REQUIRED_SHEETS if s not in sheets]
    if missing:
        raise ConfigError(
            f"{path.name} is missing the sheet(s) {', '.join(missing)}. "
            f"Run `python3 run_quadrium.py --template my_config.xlsx` to get a "
            f"workbook with the right shape and comments in it.")
    meta = {}
    for r in sheets["project"]:
        if r and r[0] is not None and str(r[0]).strip():
            k = str(r[0]).strip()
            if k.startswith("#"):
                continue
            meta[k.lower()] = r[1] if len(r) > 1 else None
    tables = {name: _rows(sheets, name)
              for name in ("splits", "keys", "scenarios", "profiles")}
    return build_config(meta, tables, base_dir=path.parent, label=path.name)


def build_config(meta: dict, tables: dict, base_dir: Path = Path("."),
                 label: str = "<configuration>") -> dict:
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
    project_id = str(_need(meta, "project_id", "project", 0)).strip()
    table_path = Path(str(_need(meta, "table_path", "project", 0)).strip())
    if not table_path.is_absolute():
        table_path = (Path(base_dir) / table_path).resolve()
    kind = str(meta.get("table_kind") or "uk_analytical").strip().lower()
    if kind not in TABLE_KINDS:
        raise ConfigError(f"table_kind {kind!r} must be one of {TABLE_KINDS}")
    if not table_path.exists():
        raise ConfigError(f"table_path points at {table_path}, which does not "
                          f"exist. Paths may be absolute or relative to the "
                          f"config file.")

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
    }
    try:
        table = loaders[kind](table_path)
    except LoaderError as exc:
        raise ConfigError(f"the table could not be loaded:\n{exc}") from None

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
    defaults_taken: list[str] = []
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
        source="MVP_0.1 §6.3 — project convention, no methodological source",
        validated_by="pending analyst review", confidence=ProxyStrength.WEAK,
        impact_on_results="high — the only part of the table with no "
                          "observation behind it"))

    return {"project_id": project_id,
            "title": str(meta.get("title") or f"{project_id} — sector split"),
            "table": table, "splits": splits, "scenarios": scenarios,
            "keys": keys, "ledger": ledger, "source_file": table_path,
            "notes": str(meta.get("notes") or ""),
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
            ("table_path", "../UK_IOAT_2023_domestic_ixi.xlsx"),
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
            "# table_kind: uk_analytical  the ONS workbook (industry x industry)",
            "#             ine_interior  the INE workbook, domestic output",
            "#             ine_total     the INE workbook, total flows",
            "#             interchange   the project's own format.",
            "# table_unbalanced: refuse (default) or residual_column.",
            "#             Only for ine_interior, which does not balance for",
            "#             one product -- see OQ-D-04. Anywhere else it is an error.",
            "#",
            "# Fill in the other sheets, then run:",
            "#     python3 run_quadrium.py <this file>",
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
           "default 0.5 (MVP_0.1 §6.3 — a project convention, not a source).",
           "Two or more scenarios let you see how much the answer depends on",
           "your choices, which is the honest way to present it."])

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
    wb.save(path)
    return path
