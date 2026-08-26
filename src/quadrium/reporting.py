"""
Reproducible Markdown report (MVP_0.1 §1.12).

Written for an economist reading the result, not for the person who wrote the
code: every number that is an estimate says so, and every tolerance that is a
project choice says so.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from .models import CellLabel, DisaggregationResult, count_label


def _fmt(x, dp=1):
    """Format a number so that "too small to show" never looks like zero.

    `f"{0.04:,.1f}"` is `"0.0"`, which in a table of results is indistinguishable
    from a true zero — the reader is told a sector buys nothing when it buys a
    little. On a table in millions the difference rarely matters; on a
    coefficient at three decimals, or on any table whose unit is smaller, it
    does, and the reader has no way to tell the two cases apart (2026-08-10).

    A value that rounds to zero at the requested precision is shown as
    `<0.05` (or `>-0.05` when negative): the tightest true statement available,
    since anything larger would have rounded to a visible figure.

    NaN stays "—". That is not-computable, which is a third thing again, and
    conflating it with either zero would be the same mistake.
    """
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    v = float(x)
    if v == 0.0:
        return f"{v:,.{dp}f}"
    half = 0.5 * 10.0 ** -dp
    if abs(v) < half:
        return f"<{half:,.{dp + 1}f}" if v > 0 else f">-{half:,.{dp + 1}f}"
    return f"{v:,.{dp}f}"


def _pct(x, dp=1):
    """The same rule for percentages, where it bites harder.

    A corroboration gap of 0.0004 printed "+0.0%", which reads as agreement.
    """
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    v = float(x)
    if v == 0.0:
        return f"{0.0:+.{dp}%}"
    half = 0.5 * 10.0 ** -(dp + 2)
    if abs(v) < half:
        return f"<+{half:.{dp + 1}%}" if v > 0 else f">-{half:.{dp + 1}%}"
    return f"{v:+.{dp}%}"


def provenance_summary(prov: np.ndarray) -> str:
    total = prov.size
    rows = ["| Provenance | Cells | Share | Data status (§A.1) |",
            "|---|---:|---:|---|"]
    status = {CellLabel.OBSERVED: "OBSERVED",
              CellLabel.PROXY_ESTIMATED: "**ESTIMATED**",
              CellLabel.BALANCED_ADJUSTMENT: "**BALANCED**",
              CellLabel.USER_CONSTRAINT: "OBSERVED (analyst-pinned)"}
    for label in CellLabel:
        n = count_label(prov, label)
        rows.append(f"| {label.value} | {n} | {100*n/total:.1f} % | "
                    f"{status[label]} |")
    return "\n".join(rows)


def scenario_section(res: DisaggregationResult) -> str:
    d = res.diagnostics
    b = d["balance_info"]
    codes = res.table.sector_codes
    Z, Y, VA, X = res.table.Z, res.table.Y, res.table.VA, res.table.X

    lines = [f"## Scenario `{res.scenario_id}`", "",
             "### Balancing", "",
             f"- **Method: {b['method']}** — {b['reason']}",
             f"- Converged: {b['converged']}; iterations by split: "
             + ", ".join(f"{k} {v}" for k, v in b["iterations_per_split"].items()),
             f"- Max deviation from target row / column totals: "
             f"{b['max_row_dev']:.3g} / {b['max_col_dev']:.3g}",
             f"- Negatives: {b['n_negative_seed']} in the seed, "
             f"{b['n_negative_result']} in the result, "
             f"**{b['sign_changes']} sign changes**", ""]

    over = d.get("user_constraints_overridden") or []
    if over:
        lines += [
            f"> **{len(over)} cell(s) you pinned were MOVED by the solver.** "
            f"`user_constraints` writes a value; it does not protect it. GRAS "
            f"takes row and column totals and nothing else (UNH_18 ¶18.81, "
            f"p. 569), so a pinned cell inside a rebalanced block cannot be "
            f"held. Those cells are labelled `balanced_adjustment` below, not "
            f"`user_constraint` — they hold the solver's value, not yours.", "",
            "| Cell | you asked for | it holds | moved by |",
            "|---|---:|---:|---:|"]
        for o in over:
            lines.append(f"| `{o['cell']}` | {o['requested']:,.4f} | "
                         f"{o['actual']:,.4f} | {o['moved_by']:+,.4f} |")
        lines += ["",
                  "To hold a cell you need a method that accepts predefined "
                  "interior cells — TRAS or KRAS — which no loaded source "
                  "specifies (`D_open_questions.md` OQ-B-01). On a non-negative "
                  "table `method='RAS'` with `locked_cells` will hold them.", ""]

    for sp in res.splits:
        # The key that DROVE the split gets the same provenance the corroborating
        # keys already got. Before, a `weak` key and a `strong` one looked
        # identical here — id and numbers, nothing else — while the keys that did
        # NOT matter carried their strength and source in full (2026-08-10).
        meta_by_key = sp.get("key_meta", {})
        inherited = sp.get("keys_inherited", {})
        lines += [f"### `{sp['sector_code']}` — {sp['sector_label']}", "",
                  "| Block | Key | Chosen? | Strength | Year | vs table | Weights |",
                  "|---|---|---|---|---|---|---|"]
        stale_here = False
        for block, key_id in sp["keys_used"].items():
            w = ", ".join(f"{x:.3f}" for x in sp["weights"][block])
            km = meta_by_key.get(key_id, {})
            st = km.get("strength", "—")
            if st == "weak":
                st = "**weak**"
            chose = "inherited" if inherited.get(block) else "chosen"
            # The year was printed here from the first version and never
            # compared with the table's own. A 2019 proxy on a 2022 table read
            # as ordinary. The gap now sits in the column next to it.
            yr = km.get("source_year")
            tyr = getattr(getattr(res, "table", None), "year", None)
            if yr is None or tyr is None:
                gap = "—"
            elif int(yr) == int(tyr):
                gap = "same year"
            else:
                stale_here = True
                gap = f"**{int(yr) - int(tyr):+d} yr**"
            lines.append(f"| {block} | `{key_id}` | {chose} | {st} | "
                         f"{km.get('source_year', '—')} | {gap} | {w} |")
        if stale_here:
            lines += ["",
                      "*vs table* — the gap between what the proxy measures and "
                      "what the table measures. **Its cost is not proportional "
                      "to its size.** Measured on the INE's structural business "
                      "survey for the same two subsectors, one year moved the "
                      "output share by 0.6 points between 2018 and 2019 and by "
                      "11.9 between 2019 and 2020; value added moved 21.0 while "
                      "employment moved 1.9 over the same years. Whether a break "
                      "falls inside the gap is something the analyst can know "
                      "and this engine cannot. See "
                      "`library/validators/run_key_vintage.py`.",
                      "",
                      "> **An old ANSWER beats a current proxy, by about four "
                      "to one.** If the office published your split for a "
                      "nearby year, use that year's shares as the key instead "
                      "of any proxy. Measured on the one country that "
                      "publishes three consecutive years at the detail that "
                      "settles it: last year's published split is out by a "
                      "median **1.2 points**, two years back by **2.4**, "
                      "against **4.8 at best** for the ten downloadable "
                      "proxies and 27 at p90. Correcting a proxy by a bias "
                      "measured on a published year was tried and adds "
                      "nothing — it beats plain carry-over in 54 % of splits, "
                      "which is a coin flip, because it is that carry-over "
                      "with extra steps. One country and three years, one of "
                      "them pandemic-affected. See "
                      "`validators/run_key_carryover.py`."]
        va = sp.get("va_rows") or {}
        if va.get("pinned"):
            lines += ["",
                      "**Value-added rows driven separately.** The block total "
                      "still follows the `value_added` key; these rows carry "
                      "their own measurement exactly, and one row absorbs what "
                      "they leave (OQ-B-12).", "",
                      "| VA row | driven by | share |", "|---|---|---|"]
            for row, kid in va["pinned"].items():
                lines.append(f"| {row} | `{kid}` | pinned |")
            shares = ", ".join(f"{s:.2%}" for s in (va.get("residual_shares") or []))
            lines.append(f"| {va.get('residual_row')} | **residual** | {shares} |")
            lines += ["",
                      "*residual* — this row was not measured; it holds the "
                      "difference between the block total and the rows that "
                      "were. Read its share as an outcome of the others, not "
                      "as evidence."]

        srcs = {k: m.get("source") for k, m in meta_by_key.items()}
        if srcs:
            lines += [""] + [f"- `{k}` — {v}" for k, v in sorted(srcs.items())]
        if any(inherited.get(b) for b in sp["keys_used"]):
            lines += ["",
                      "*inherited* — no key was named for that block, so it took "
                      "the output key. That is a default, not a decision by the "
                      "analyst, and it means the block carries whatever the "
                      "output proxy implies rather than a measurement of its own."]
        weak_driving = [b for b, k in sp["keys_used"].items()
                        if meta_by_key.get(k, {}).get("strength") == "weak"]
        if weak_driving:
            lines += ["",
                      f"> **A key marked `weak` is driving "
                      f"{', '.join(weak_driving)}.** Its own author classed it a "
                      f"last resort. Every figure below inherits that."]
        lines += ["",
                  "| Subsector | Output | Intermediate sales | Final demand | "
                  "Value added | Output multiplier |",
                  "|---|---:|---:|---:|---:|---:|"]
        for i in sp["positions"]:
            lines.append(f"| {codes[i]} | {_fmt(X[i])} | {_fmt(Z[i].sum())} | "
                         f"{_fmt(Y[i].sum())} | {_fmt(VA[:, i].sum())} | "
                         f"{_fmt(d['multipliers'][i], 3)} |")

        # External corroboration. Placed immediately under the results table,
        # before headroom and input structures, because it is the only thing on
        # this page that speaks to whether the numbers are RIGHT rather than
        # merely consistent — and a reader who stops after the table should not
        # miss it.
        for c in sp.get("corroboration", []):
            worst = c["max_abs_gap"]
            lines += ["",
                      f"*Corroboration against `{c['key_id']}` "
                      f"({c['strength']}, {c['source_year']}), which did **not** "
                      f"drive this split:*", "",
                      "| Subsector | implied by the split | measured | gap |",
                      "|---|---:|---:|---:|"]
            for r in c["rows"]:
                lines.append(f"| {r['code']} | {r['implied']:.4f} | "
                             f"{r['measured']:.4f} | {_pct(r['gap'])} |")
            lines += ["",
                      f"Largest disagreement **{worst:.1%}**, against the "
                      f"`{c['compared_against_block']}` weights. Every other "
                      f"check in this report asks whether the arithmetic is "
                      f"self-consistent and would pass on any key; this one "
                      f"asks whether an independent measurement agrees. "
                      f"Source: {c['source']}"]

        # WHAT THE CORROBORATION DOES NOT COVER. An allocation key describes how
        # big each subsector is. Input profiles describe what each one BUYS, and
        # no key backs them — they are intensities the analyst typed. So a
        # scenario with profiles gets a corroboration that validates its sizes
        # and is silent about the very thing that makes its multipliers differ.
        #
        # Silence reads as approval. On the UK pilot the profiled scenario came
        # out with the same 9.9 % as the size-only one and looked equally well
        # supported, which it is not (2026-08-10). Scope is now stated wherever
        # the reader meets the number.
        # It fires on the PROFILES, not on the presence of a corroboration.
        # A profiled scenario with no spare keys gets no corroboration at all
        # and would otherwise pass in silence — which is the worse case, not
        # the safer one.
        if sp.get("input_structure", {}).get("differentiated"):
            if sp.get("corroboration"):
                lines += ["",
                          "> **Scope of the corroboration above: sizes only.** "
                          "Those checks compare the subsectors' SHARES against "
                          "independent measurements. They say nothing about the "
                          "input profiles, which is what makes this scenario's "
                          "multipliers differ."]
            else:
                lines += ["", "> **Nothing here verifies these multipliers.**"]
            provs = [sp.get("profile_provenance") for sp in res.splits
                     if sp.get("profile_provenance")]
            if provs:
                # OQ-B-13: a profile used to be a bare dict, so a sourced one and
                # an invented one reached the reader identically labelled. This
                # paragraph was the sentence that was too pessimistic whenever a
                # profile DID have a source.
                for pv in provs:
                    st = pv.get("strength", "—")
                    lines.append(
                        f"> The purchasing patterns are **sourced**: {pv['source']} "
                        f"({st}, {pv.get('source_year', '—')})."
                        + (f" {pv['notes']}" if pv.get("notes") else ""))
                lines += ["> Nothing in the engine can VERIFY a purchasing "
                          "pattern against anything — there is no equivalent of "
                          "the corroboration table for profiles. A source is a "
                          "weaker claim than a check, and it is the one on "
                          "offer."]
            else:
                lines += ["> No allocation key backs a purchasing pattern — "
                          "profiles are intensities the analyst supplied, with "
                          "**no source recorded**, and the engine has no way to "
                          "check one. Read the differentiated multipliers as a "
                          "demonstration of what different input structures do, "
                          "not as an estimate."]
            for sp in res.splits:
                sh = sp.get("profile_shift")
                if not sh or sh.get("neutral"):
                    continue
                lines.append(
                    f"> **The profile on `{sp['sector_code']}` moves subsector "
                    f"SIZE, not only composition** — by {_fmt(sh['max_abs'])} "
                    f"against an internal block of {_fmt(sh['internal_block'])}, "
                    f"{sh['share_of_internal_block']:.1f}x. Intensities are "
                    f"normalised per supplier, which holds each supplier's total "
                    f"sales; nothing then holds each subsector's total where its "
                    f"key put it. `disaggregation.neutralise_profile()` removes "
                    f"the level and keeps the pattern.")

        for sk in sp.get("corroboration_skipped", []):
            lines += ["",
                      f"*Not used to corroborate:* `{sk['key_id']}` — "
                      f"{sk['reason']}. It is registered and it was left out of "
                      f"the comparison on purpose; a weak key disagreeing with "
                      f"a strong one says nothing about the strong one."]

        if sp.get("code_check"):
            lines += ["", f"*Classification:* {sp['code_check']}"]

        # HEADROOM, INCLUDING THE CASE WHERE THERE IS NONE.
        #
        # `headroom_pct` is NaN when the parent trades nothing with itself, and
        # the old code simply omitted the line. That is the silence at its
        # worst: the sector with ZERO budget for differentiated purchasing —
        # the most constrained case there is — produced no constraint text at
        # all, while every less-constrained sector produced one. Absence read
        # as "unconstrained" and meant the exact opposite (2026-08-10).
        hp = sp.get("headroom_pct")
        if hp is not None and hp == hp:                       # not NaN
            lines += ["", f"*Headroom:* the tightest subsector still has "
                          f"{sp['tightest_internal_total']:,.2f} of internal "
                          f"trade left, {hp:.1f} % of this "
                          f"sector's own diagonal of "
                          f"{sp['parent_diagonal']:,.1f}. That margin is the "
                          f"budget any differentiated input structure has to "
                          f"fit inside — a sector that barely trades with "
                          f"itself leaves little room to claim its subsectors "
                          f"buy differently."]
        else:
            lines += ["", f"*Headroom:* **none — this sector trades nothing "
                          f"with itself.** Its own diagonal is "
                          f"{sp.get('parent_diagonal', 0):,.1f}, so there is no "
                          f"internal trade for a differentiated purchasing "
                          f"structure to be carved out of, and no headroom "
                          f"percentage exists to report. This is the most "
                          f"constrained case, not an unconstrained one: any "
                          f"input profile here has a budget of zero."]

        isd = sp.get("input_structure", {})
        if isd.get("differentiated"):
            lines += ["", f"*Input structures:* these subsectors buy "
                          f"**different mixes**, not just different amounts — "
                          f"mean pairwise cosine distance between their "
                          f"technical-coefficient columns is "
                          f"{isd['mean_cosine_distance']:.3f}, largest single "
                          f"coefficient difference "
                          f"{isd['max_abs_difference']:.4f}. Their multipliers "
                          f"differ for an economic reason, not an arithmetic "
                          f"one."]
        elif isd:
            lines += ["", f"*Input structures:* these subsectors buy the "
                          f"**same mix** in different amounts — cosine distance "
                          f"{isd['mean_cosine_distance']:.5f}, effectively "
                          f"zero. Each is a scaled copy of the parent's input "
                          f"structure, so any difference in their multipliers "
                          f"is an artefact of the internal block, not a "
                          f"finding. Supply `input_profiles` to give them "
                          f"genuinely different purchasing patterns.",
                      "",
                      "> **What a profile is worth, measured.** On 54 splits "
                      "where the office publishes both the parent and its "
                      "parts, giving the engine the parts' TRUE input profile "
                      "moves the SEED's multiplier error from a median 9.0 % "
                      "to 3.4 %. **The balancer then gives most of that "
                      "back**: the delivered table is a median 10.6 % against "
                      "10.0 % for using no profile at all, and it beats doing "
                      "nothing in 21 of 35. Balancing adjusts the internal "
                      "block only — correct when a split is proportional, "
                      "since nothing else moves — so a profiled column pushes "
                      "the whole adjustment into the least reliable part of "
                      "the table. The engine also refuses the profiled "
                      "scenario outright in 19 of 54.",
                      ">",
                      "> **Borrowing one from a country that publishes your "
                      "split is a coin flip** — 162 borrowings, better in 78 "
                      "and worse in 84, helping by a median 4.2 points and "
                      "hurting by 3.1. It helps where the split was going "
                      "badly anyway and hurts where it was fine (r = +0.42 "
                      "against the baseline error), which is only knowable "
                      "afterwards; the ex-ante screen does not predict it "
                      "(r = +0.12). See "
                      "`validators/run_input_profiles_backtest.py`."]
        # "THE WEAKEST ASSUMPTION IN THE RESULT" WAS HALF RIGHT AND SAID
        # WRONG. Measured on 68 real splits where the office publishes both
        # the parent and its parts: the estimated block misses the published
        # one by a median of 60.6 %, comfortably the worst-estimated part of a
        # split — and how wrong it is does not predict how wrong the
        # multipliers are, r = +0.03. It is the weakest ASSUMPTION; the result
        # does not rest on it. See `validators/run_internal_block_backtest.py`.
        lines += ["",
                  f"The estimated **internal block** for this sector is "
                  f"{sp['internal_block_share_pct']:.2f} % of the absolute "
                  f"value of the intermediate matrix. It has no direct "
                  f"observation behind it: the original table held a single "
                  f"diagonal cell of {_fmt(sp['original_diagonal'])}, and the "
                  f"split assumes the propensity to trade internally is "
                  f"proportional to each subsector's weight (MVP_0.1 §6.3).",
                  "",
                  "> **It is the weakest assumption here, and the result does "
                  "not rest on it.** Measured on 68 splits where the office "
                  "publishes both the parent and its parts, this block misses "
                  "the published one by a median of **60 %** — the "
                  "worst-estimated part of a split, against 42 % for the "
                  "touched block as a whole. But how wrong it is does not "
                  "predict how wrong the subsectors' multipliers are: "
                  "correlation **+0.03**. Raising `internal_block_alpha` to "
                  "the 1.5 that real blocks show makes the multipliers worse, "
                  "not better, on 37 of those 68. "
                  "See `validators/run_internal_block_backtest.py`.",
                  "",
                  "> One caution about the percentage above: it is the block "
                  "over the **whole** intermediate matrix, which is why it "
                  "reads small. Over this subsector's own input column the "
                  "same block runs from nothing to 56 %, and that is the share "
                  "with anything to do with its multiplier.", ""]

    lines += ["### Cell provenance", "", provenance_summary(res.provenance), "",
              "> **This is a map of what was estimated, not a warning about "
              "your multipliers.** Measured on 68 real splits where the office "
              "publishes both the parent and its parts, the share of the table "
              "a split had to estimate has **no relationship** to how far the "
              "subsectors' multipliers land from the published truth — "
              "correlation −0.01. A split can be 112 % out cell by cell and "
              "still put its multipliers inside 4 %, or be tidy in the cells "
              "and 40 % out in the multipliers. What the multiplier error does "
              "track, at +0.92, is how UNLIKE the parts are: the worst error "
              "is about two thirds of the spread between their true "
              "multipliers, because proportional splitting hands every part "
              "the parent's average structure. See "
              "`validators/run_split_backtest.py`.", "",
              "### Validation", "", res.report.to_markdown(), ""]
    return "\n".join(lines)


def build_report(results: list[DisaggregationResult], meta: dict,
                 table_title: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    first = results[0]
    lines = [f"# {table_title}", "",
             f"Generated {now} · Quadrium 0.1.0 (MVP 0.1)", "",
             f"Sector `{first.table.sector_codes[first.split_index]}`"
             if False else "", ]
    lines = [x for x in lines if x != ""]
    split_desc = "; ".join(f"`{s['sector_code']}` into "
                           f"{', '.join(s['new_codes'])}"
                           for s in first.splits)
    lines += ["",
              f"**{len(results)} scenario(s)** · {len(first.splits)} sector(s) "
              f"divided: {split_desc}", "", "---", ""]

    lines += ["## Original table", ""]

    # WHAT THE LOADER DID TO THE INPUT, said to the person reading the result.
    #
    # The loader makes real decisions on a foreign file: it reads the reference
    # year from the workbook's own metadata rather than its filename, it knows
    # that two of the value-added rows are not value added, and it DISCARDS
    # final-demand columns that are subtotals of other columns — on this
    # project's own fixture that is GBP 259,330 million of double-counted
    # household consumption.
    #
    # All of it was recorded in project.json and none of it reached report.md
    # (2026-08-10). A reader was never told their table had been modified. The
    # machine knew; the human did not, which is the wrong way round.
    tbl = meta.get("original_table")
    if tbl is None:            # older callers; better to say nothing than to
        prov = []              # describe the disaggregated table as the input
    else:
        prov = [f"- **Source:** {tbl.source}",
                f"- **Reference year:** {tbl.year} · **Unit:** {tbl.unit} · "
                f"**Classification:** {tbl.classification}"]
        if getattr(tbl, "notes", None):
            prov.append(f"- **What the loader decided when reading this file:** "
                        f"{tbl.notes}")
        # WHEN THE INPUT IS ITSELF A PRODUCT OF THIS ENGINE.
        #
        # A disaggregated table balances as exactly as a published one, so a
        # reader has no way to tell from the numbers that the "original" here
        # is already an estimate. Said at the top, before any figure, because
        # everything below inherits it: the multipliers in a second-generation
        # table rest on the first generation's allocation key as much as on
        # this run's.
        if getattr(tbl, "derived", False):
            counts = tbl.provenance_counts()
            total = max(sum(counts.values()), 1)
            est = total - counts.get("OBSERVED", 0)
            # "a disaggregation" was the only way in when this was written.
            # A table transformed from a supply-use pair arrives here too, and
            # calling that a disaggregation would misname the one thing the
            # reader most needs to get right. The lineage below says which.
            prov.append(
                f"- ⚠️ **The input table is not a publication.** It is itself "
                f"a product of this engine: **{est} of its {total} "
                f"intermediate cells ({100 * est / total:.1f} %) were already "
                f"estimates before this run began**, and every figure below "
                f"inherits them. What was done to it, oldest first:")
            prov += [f"  {i}. {line}" for i, line
                     in enumerate(tbl.lineage or ["(not recorded)"], start=1)]
    lines += prov + ["", meta["original_report"].to_markdown(), "", "---", ""]

    for res in results:
        lines.append(scenario_section(res))
        lines.append("---\n")

    if meta.get("infeasible"):
        lines += ["## Scenarios that were rejected", ""]
        for inf in meta["infeasible"]:
            lines += [f"### `{inf['scenario_id']}` — {inf['explanation']}", "",
                      inf["detail"], ""]
        lines += ["> A rejected scenario is a **result**, not a malfunction. "
                  "The software refused to produce a table that could not "
                  "exist rather than quietly returning one that looked "
                  "plausible.", "", "---", ""]

    lines += ["## Scenario comparison", "",
              "Output multipliers by subsector. The range is the honest measure "
              "of how much the proxy choice matters — of how much it matters, "
              "not of how wrong the answer is; see the note under *How far the "
              "outside evidence disagrees*.", ""]
    ids = [r.scenario_id for r in results]
    lines.append("| Subsector | " + " | ".join(ids) + " | Range | Range % |")
    lines.append("|---" * (len(ids) + 3) + "|")
    for row in meta["comparison"]:
        vals = " | ".join(f"{row[s]:.3f}" for s in ids)
        lines.append(f"| {row['code']} | {vals} | {row['range']:.3f} | "
                     f"{row['range_pct']:.1f} % |")
    lines += ["",
              f"**Main driver of variation:** the cell `{meta['driver']}`, "
              f"which spans {meta['driver_spread']:,.1f} across scenarios. "
              f"This is the crude measure of MVP_0.1 §10 — the widest cell, not "
              f"a sensitivity analysis.", ""]

    # ------------------------------------------------------------------
    # How far the outside evidence disagrees -- and DELIBERATELY NOT which
    # scenario it favours. This section used to rank scenarios by least
    # disagreement and mark a winner. OQ-S-06 records the case that killed it.
    #
    # On the Spanish pilot the largest disagreement was with the employment key,
    # at 58.8 %, and the report treated that as the headline uncertainty. When
    # the INE's 110-product supply table settled the answer, employment was the
    # CLOSEST of the seven keys -- 2.7 points from the truth -- and the driving
    # key was 9.8 points out. The loudest disagreement was pointing at the right
    # answer.
    #
    # "Disagrees least with the keys it did not use" does not measure being
    # right. It measures how much a result resembles its own inputs.
    # ------------------------------------------------------------------
    rows = []
    for res in results:
        pairs = [(c["key_id"], c["max_abs_gap"], c["compared_against_block"])
                 for sp in res.splits for c in sp.get("corroboration", [])]
        if not pairs:
            continue
        lo = min(pairs, key=lambda x: x[1])
        hi = max(pairs, key=lambda x: x[1])
        driven = ", ".join(sorted({k for sp in res.splits
                                   for k in sp["keys_used"].values()}))
        rows.append((res.scenario_id, driven, lo, hi, len(pairs)))

    if rows:
        lines += ["### How far the outside evidence disagrees", "",
                  "Each scenario compared against the allocation keys that were "
                  "registered and then **not** used to drive it. The spread "
                  "between the closest and the furthest is the uncertainty this "
                  "report can actually support.", "",
                  "| Scenario | driven by | closest key | furthest key | keys compared |",
                  "|---|---|---|---|---:|"]
        profiled = {r.scenario_id for r in results
                    if any(s.get("input_structure", {}).get("differentiated")
                           for s in r.splits)}
        for sid, driven, lo, hi, n in rows:
            note = " · *sizes only*" if sid in profiled else ""
            lines.append(f"| `{sid}` | `{driven}` | `{lo[0]}` {lo[1]:.1%} | "
                         f"`{hi[0]}` {hi[1]:.1%}{note} | {n} |")
        if profiled & {r[0] for r in rows}:
            lines += ["",
                      "*sizes only* — that scenario carries input profiles, and "
                      "no key backs a purchasing pattern. Its figure in this "
                      "column measures the same size key as its unprofiled "
                      "sibling and is **not** evidence for its differentiated "
                      "multipliers."]
        lines += ["",
                  "> **Nothing here says which end is right, and the ranking "
                  "that used to sit in this space was removed for cause.** It "
                  "marked the scenario that disagreed least as better supported. "
                  "On the Spanish pilot the key that disagreed MOST — employment, "
                  "by 58.8 % — turned out to be the closest to the truth once "
                  "the INE's 110-product supply table settled it, while the "
                  "driving key was 9.8 points out. Least disagreement measures "
                  "resemblance to your own inputs, not accuracy.",
                  ">",
                  "> **What a large disagreement is good for** is telling you "
                  "where to go looking. In that case a better source existed "
                  "and was one download away. See `D_open_questions.md` "
                  "OQ-S-05 and OQ-S-06.",
                  ">",
                  "> **This spread is not a confidence interval, and it is "
                  "not much of a floor either.** Measured on 65 splits across "
                  "five country-years where the office publishes both the "
                  "parent and its parts: the range contains the true share "
                  "for 84.0 % of subsectors and for every subsector at once "
                  "in **49 of 65 splits** — it misses one split in four. And "
                  "where it does contain the answer it does so across a "
                  "median **28 points of share**, which excludes almost "
                  "nothing. Honest about being uncertain; nearly silent about "
                  "where the answer is.",
                  ">",
                  "> **A narrow range is not a safer one.** The splits where "
                  "the range misses are the WIDER ones (median 38.6 points "
                  "against 27.8), so there is no flag here to act on. Nor is "
                  "the verdict a property of the sector: of the 13 parents "
                  "that appear in more than one country-year, the range "
                  "agrees with itself in 7. Dropping the highest and lowest "
                  "proxy does not rescue it — coverage falls to 59.7 % while "
                  "the range is still 12 points wide. See "
                  "`run_key_spread.py`.",
                  ">",
                  "> One thing the spread does NOT do is lean reliably one "
                  "way. Every available proxy sits on the same side of the "
                  "answer for only **16.0 %** of subsectors. Spanish "
                  "hospitality, where all seven of the pilot\'s keys "
                  "overstate accommodation and the range misses by 0.6 "
                  "points, is the unusual case and not the pattern — as it "
                  "also was for the size of the error. See "
                  "`run_key_bias.py` and `run_real_key.py`.", ""]

    # If the multipliers do not differ across subsectors, say why, loudly. An
    # economist reading "range 0.0 %" could otherwise take the result as robust,
    # when in fact the method cannot produce any other answer.
    diff_flags = {r.scenario_id:
                  any(s.get("input_structure", {}).get("differentiated")
                      for s in r.splits)
                  for r in results}
    if any(diff_flags.values()) and not all(diff_flags.values()):
        undiff = [s for s, v in diff_flags.items() if not v]
        diff = [s for s, v in diff_flags.items() if v]
        lines += [
            "### Why the multipliers move in some scenarios and not others", "",
            f"In {', '.join(f'`{s}`' for s in undiff)} every subsector has the "
            f"same multiplier. That is arithmetic, not economics: a single "
            f"allocation key gives each subsector a scaled copy of the parent's "
            f"input structure, and the weight cancels in `a_ij = Z_ij / X_j`.",
            "",
            f"In {', '.join(f'`{s}`' for s in diff)} the subsectors were given "
            f"genuinely different purchasing patterns, so their coefficient "
            f"columns differ and the multipliers separate for a reason you can "
            f"defend. **Only those numbers say anything about the subsectors.**",
            "",
            "Note how small the spread is even so. Multipliers are dominated by "
            "the parent sector's overall input intensity; redistributing the "
            "mix within a similar total moves them at the margin. Treat a "
            "difference of a few tenths of a per cent as a direction, not a "
            "measurement.", ""]

    # HOW WRONG IS THIS IF THE KEY IS WRONG -- answered exactly, because the
    # relationship is exact and does not need simulating.
    #
    # The weight scales a subsector's output and everything that moves with it
    # ONE FOR ONE, and leaves the technical coefficients untouched, because it
    # cancels in `a_ij = Z_ij / X_j`. Measured to confirm rather than assumed:
    # on the UK fixture, moving a key from 50/50 to 80/20 moved output from
    # 47,405 to 75,848 and the multiplier not at all -- 1.84800 at every
    # weight, to five decimals.
    #
    # So the honest error bar is arithmetic: one per cent wrong in the key is
    # one per cent wrong in the size, and nothing at all wrong in the
    # multiplier. Reported per subsector, in the table's own units, so it can
    # be read rather than derived.
    first = results[0]
    tbl = first.table
    rows = []
    for split in first.splits:
        for pos, code in zip(split["positions"], split["new_codes"]):
            rows.append((code, float(tbl.X[pos]),
                         float(tbl.VA[:, pos].sum()),
                         float(tbl.Z[:, pos].sum())))
    # HOW RISKY WAS THIS SPLIT, FROM TWO NUMBERS AVAILABLE BEFORE MAKING IT.
    #
    # `run_split_backtest.py` scores 68 real splits against tables where the
    # office publishes both the parent and its parts. `run_split_screen.py`
    # then asks what in the COARSE table predicts the result, since the thing
    # that actually drives it — how unlike the parts are — cannot be known
    # without the answer. Seven candidates; two independent signals survive:
    # the parent's own output multiplier (equivalently, one minus its value
    # added share, r = -0.98 between them) and the number of parts.
    #
    # It ranks, it does not predict a number, and it holds on countries it was
    # not fitted on: leave-one-country-out Spearman +0.52 to +0.76, positive in
    # every fold. The cut points below are the medians of those 68 splits.
    orig = meta.get("original_table")
    if orig is not None and first.splits:
        import numpy as _np
        _A = orig.Z / _np.where(orig.X == 0, 1.0, orig.X)
        _m = _np.linalg.inv(_np.eye(orig.n) - _A).sum(0)
        band = []
        for split in first.splits:
            code = split["sector_code"]
            try:
                pm = float(_m[orig.index_of(code)])
            except Exception:
                continue
            k = len(split["new_codes"])
            hi_m, hi_k = pm > 1.5525, k > 2
            med, worst = {(False, False): ("4.8 %", "14.9 %"),
                          (False, True): ("7.0 %", "23.4 %"),
                          (True, False): ("7.9 %", "41.6 %"),
                          (True, True): ("18.6 %", "48.1 %")}[(hi_m, hi_k)]
            band.append((code, pm, k, med, worst))
        if band:
            lines += [
                "### How risky was this split, before you made it?", "",
                "Two numbers from the table you started with rank a split's "
                "difficulty, measured on 68 real splits where the office "
                "publishes both the parent and its parts: **the parent's own "
                "output multiplier** and **how many parts you asked for**. "
                "They are independent of each other, and together they rank "
                "difficulty on countries they were not fitted on.", "",
                "| Split | parent multiplier | parts | comparable splits: median error | worst |",
                "|---|---:|---:|---:|---:|"]
            for code, pm, k, med, worst in band:
                lines.append(f"| `{code}` | {pm:.3f} | {k} | {med} | {worst} |")
            lines += [
                "",
                "> The error columns are what the subsectors' **multipliers** "
                "did in comparable splits. They are a band, not a prediction "
                "for your table: the screen ranks, and the spread inside each "
                "band is wide. The cut points are the medians of the 68 "
                "(multiplier 1.553, two parts).",
                ">",
                "> **The band does not depend on your key being right.** "
                "Without an input profile, no allocation key can move a "
                "subsector's multiplier — the share cancels out of the "
                "coefficients, so every key gives the same one. Measured on "
                "638 real published proxies, identical to the answer's own "
                "multipliers in 636 of 638 — the two exceptions give a real "
                "subsector a share of exactly zero, and the engine refuses "
                "those. What the band measures is "
                "structure, and your key cannot add to it or subtract from "
                "it. See `validators/run_key_invariance.py`.",
                ">",
                "> **Your key sets the sizes, and that is where it costs "
                "you.** A share error of a few points is not a subsector a "
                "few percent out: the error is relative to a part that may be "
                "small, so it is amplified by a median factor of 3.8. Real "
                "downloadable proxies are out by a median 7.3 points of "
                "share, which leaves the worst subsector's output out by a "
                "median **32 %**, and only 77 of 638 put every subsector "
                "within 10 % of its true size. See "
                "`validators/run_real_key.py`.",
                ">",
                "> If another country publishes your split, you may be "
                "tempted to read its error instead. Measured, that is worse: "
                "the band above misses a held-out case by 3.7 points and the "
                "same parent's error borrowed from other countries by 4.9, "
                "because the spread for one parent varies by a median factor "
                "of 4.6 between countries.",
                ">",
                "> **Asking for more parts does not make each part worse.** "
                "A single subsector's error barely moves with the number of "
                "parts (r = +0.17); the worst of them does (r = +0.36), "
                "because more parts is more draws. If you need one particular "
                "subsector, that costs you little. If you need all of them to "
                "hold, it costs you the maximum. See "
                "`validators/run_split_screen.py`.", ""]

    if rows:
        unit = tbl.unit.split(",")[0]
        lines += [
            "### How wrong is this if your allocation key is wrong?", "",
            "Exactly as wrong as the key, in the sizes — and not at all in the "
            "multipliers. The weight scales a subsector's output, value added "
            "and purchases together and cancels out of `a_ij = Z_ij / X_j`, so "
            "**one per cent of error in the key is one per cent of error in "
            "the size and zero in the multiplier**. That is arithmetic, not an "
            "estimate, and it needs no simulation.", "",
            f"Per 1 % your key is wrong, in {unit}:", "",
            "| Subsector | Output | Value added | Purchases | per 1 % of key |",
            "|---|---:|---:|---:|---:|"]
        for code, x, va, z in rows:
            lines.append(f"| `{code}` | {x:,.0f} | {va:,.0f} | {z:,.0f} | "
                         f"**{x / 100:,.0f}** |")
        lines += [
            "",
            "So a key you believe to within 10 % gives a subsector size you "
            "believe to within 10 %, and a multiplier you believe exactly as "
            "much as you believe the parent sector's — no more and no less. "
            "**The uncertainty the key carries lands entirely on the levels.**",
            "",
            "What moves a multiplier is the `profiles` sheet, and it moves it "
            "very little: on the project's own fixture, DOUBLING one "
            "supplier's intensity moves the multiplier by 0.35 %. If you need "
            "subsectors that differ as buyers, that is the lever — and it is a "
            "short one.", ""]

    across = [row[ids[0]] for row in meta["comparison"]]
    if max(across) - min(across) < 1e-6 and not any(diff_flags.values()):
        lines += [
            "### Read this before quoting the multipliers", "",
            "**Every subsector has the same output multiplier, and that is a "
            "property of the method, not a finding about the economy.**", "",
            "Splitting a sector proportionally with a single allocation key "
            "gives each subsector a scaled copy of the parent's input "
            "structure. If output and intermediate purchases are split by the "
            "same weights, the technical coefficients `a_ij = Z_ij / X_j` come "
            "out identical for every subsector — the weight cancels — so the "
            "multipliers must be identical too. The arithmetic cannot produce "
            "anything else.", "",
            "The disaggregation is still useful: each subsector gets its own "
            "output, value added and final demand, and the table stays "
            "balanced. But it adds **no information about how the subsectors "
            "differ as buyers**. Genuinely different multipliers require "
            "genuinely different input structures — a separate proxy for the "
            "intermediate columns, survey data on what each subsector actually "
            "purchases, or cells set by hand through "
            "`Scenario.user_constraints`.", "",
            "Quoting these multipliers as evidence that hotels and restaurants "
            "have similar economic pull would be circular.", ""]

    lines += ["---", "", "## How to read this", "",
              "- Every value produced by the solver has data status "
              "`BALANCED`. It is **not** an observation and must never be "
              "relabelled as one.",
              "- Solver convergence is **necessary but not sufficient** for "
              "statistical validity (CORE_006 ¶9.51, p. 288). A converged run "
              "that fails a plausibility check is a failed run.",
              "- **No published source states a numerical tolerance for an "
              "accounting identity.** Six were searched and the question is "
              "settled: what a balance can be tested against is a property of "
              "the table, not of the method. So the floor applied here is "
              "derived from your own table's stated precision — an identity "
              "summing `n` cells published to `d` decimals cannot be checked "
              "more tightly than `0.5·10⁻ᵈ·n`, and below that line 'balanced' "
              "and 'not balanced' are the same observation. Every tolerance "
              "that remains a genuine choice is labelled `PROJECT CHOICE` "
              "where it is used.",
              "- The method was **selected by the sign structure of the table**, "
              "not chosen by preference. RAS cannot be applied to a matrix with "
              "negative entries (CORE_012 Box 11.3, p. 345); GRAS can "
              "(UNH_18 ¶18.35, p. 558), and reduces to RAS when there are "
              "none.", ""]
    return "\n".join(lines)
