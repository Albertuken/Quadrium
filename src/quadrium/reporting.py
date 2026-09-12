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
                      "`validators/run_key_vintage.py`.",
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

        # How wrong each subsector's SIZE will be, from the key's own weights.
        # Not a fitted screen: a proportional split gives part i an output of
        # `share_i * X_parent`, so an error of e POINTS in that share is an
        # error of `e / share_i` in the part itself. `validators/run_size_screen.py`
        # calibrates the constant and holds out one country at a time.
        out_w = sp.get("weights", {}).get("output")
        if out_w is not None and len(out_w) == len(sp.get("new_codes", [])):
            band = [(c, float(w)) for c, w in zip(sp["new_codes"], out_w)
                    if float(w) > 0]
            if band:
                lines += [
                    "",
                    "**How wrong will each subsector's SIZE be?**", "",
                    "| Subsector | share of the parent | typical | p90 |",
                    "|---|---:|---:|---:|"]
                for code, w in band:
                    lines.append(f"| `{code}` | {w:.1%} | "
                                 f"{7.3 / (w * 100) * 100:.0f} % | "
                                 f"{27.4 / (w * 100) * 100:.0f} % |")
                lines += [
                    "",
                    "> A proportional split gives each part `share x parent "
                    "output`, so an error of *e* **points** in a share is an "
                    "error of `e / share` in that part's own size. The two "
                    "columns put the median and p90 error of a real "
                    "downloadable key — 7.3 and 27.4 points "
                    "(`validators/run_real_key.py`) — through that division. Measured on "
                    "1,583 subsector-and-proxy pairs, the typical column runs "
                    "about 0.65 of the truth and the p90 column contains it "
                    "**92 %** of the time, holding at 88.7 to 92.9 % with each "
                    "country held out.",
                    ">",
                    "> **A small part is where this bites.** A few points of "
                    "key error is the whole of a 5 % subsector. If your key "
                    "came from the office's own published split for another "
                    "year rather than from a proxy, use 1.2 points instead of "
                    "7.3 (`validators/run_key_carryover.py`) and these numbers fall by "
                    "six. See `validators/run_size_screen.py`.", ""]
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

        # TYPE II. The induced effect: wages spent, spending produced, more
        # wages. `UNH_20` para 20.88.
        #
        # Printed as a RATIO beside the type I number rather than as a column
        # of its own, and that is the finding rather than a layout choice.
        # `run_type_ii_multipliers.py` closed the same table three ways: the
        # economy-wide uplift barely moved (1.573, 1.614, 1.612) and the
        # industry spread nearly halved (1.02-3.10 against 1.20-2.31). So the
        # aggregate is firm and a ranking of industries by their type II
        # multiplier rests on a choice the Handbook does not make.
        t2 = d.get("type_ii")
        if t2:
            lines += ["", "*Type II — with households endogenous:*", "",
                      "| Subsector | type I | type II | induced uplift |",
                      "|---|---:|---:|---:|"]
            for i, code in zip(sp["positions"], sp["new_codes"]):
                a, b = d["multipliers"][i], t2["multipliers"][i]
                lines.append(f"| {code} | {a:,.4f} | {b:,.4f} | "
                             f"{(b / a - 1) if a else float('nan'):+.1%} |")
            lines += ["",
                      f"Closed on {', '.join(t2['income_rows'])}, spent as "
                      f"`{t2['household']}`. `UNH_20` ¶20.88: income earned "
                      f"from wages and salaries is spent as household final "
                      f"consumption, which induces more income, and so on to "
                      f"a new equilibrium.",
                      "",
                      f"That column of spending sums to "
                      f"**{t2['propensity']:.3f}** of the income you named — "
                      f"household consumption is not funded by wages alone, "
                      f"and the ratio is the closure this run used.",
                      "",
                      "> **The aggregate uplift is solid; ranking the "
                      "subsectors by it is not.** ¶20.88 names the income "
                      "concept and says nothing about what to divide the "
                      "consumption column by. Closed three ways on the UK "
                      "table — wages alone, wages plus surplus, all of value "
                      "added — the economy-wide ratio moves from 1.573 to "
                      "1.614 to 1.612, and the spread between industries "
                      "nearly halves, from 1.02–3.10 to 1.20–2.31. Read the "
                      "uplift; do not read the order. See "
                      "`validators/run_type_ii_multipliers.py`.",
                      ">",
                      "> **And these subsectors inherit the parent's income "
                      "coefficient**, for the same reason the satellite "
                      "accounts do: the split divided value added by the "
                      "allocation key, so nothing here says one of them pays "
                      "more wages per unit of output than the other."]

        # SATELLITE ACCOUNTS. Employment, emissions, anything per sector in
        # units the table does not use. `UNH_20` eq. (46) `Z = B(I - A)^-1`.
        #
        # Placed inside the split's own section rather than at the end,
        # because the number a reader wants is beside the sector it belongs to
        # -- and because the warning underneath is about THIS split.
        sats = d.get("satellites") or {}
        if sats:
            lines += ["", f"*Satellite accounts, per unit of final demand "
                          f"delivered ({len(sats)} registered):*", ""]
            for name, s in sorted(sats.items()):
                lines += [f"| {name} ({s['unit']}) | direct | total | "
                          f"indirect share |", "|---|---:|---:|---:|"]
                for i, code in zip(sp["positions"], sp["new_codes"]):
                    dir_, tot = s["direct"][i], s["total"][i]
                    share = (1 - dir_ / tot) if tot else float("nan")
                    mark = " *(estimated)*" if code in s["estimated"] else ""
                    lines.append(f"| {code}{mark} | {dir_:,.4f} | "
                                 f"{tot:,.4f} | {share:.1%} |")
                lines += ["", f"Source: {s['source']} ({s['source_year']}). "
                              f"`UNH_20` eq. (46): the total is the direct "
                              f"coefficient carried through the Leontief "
                              f"inverse, so it counts what this sector's "
                              f"suppliers use too."]
                # What the account says about itself -- for Eurostat's
                # regional employment, that a measured count is divided by an
                # estimated output. Beside the numbers, not in an appendix.
                if s.get("notes"):
                    lines += ["", f"Notes on this account: {s['notes']}"]
                if s["undefined"]:
                    lines += ["",
                              f"> {s['undefined']} sector(s) have zero output "
                              f"and therefore no intensity. They are NOT "
                              f"counted as zero — a sector that produced "
                              f"nothing is undefined here, not clean — and "
                              f"they contribute nothing to the totals above, "
                              f"which is the one reading that is safe."]

            # THE ASSUMPTION, WHERE THE NUMBERS ARE.
            eq = [a for a in (d.get("equal_intensity_assumed") or [])
                  if a["sector_code"] == sp["sector_code"]]
            if eq:
                got = sorted({a["satellite"] for a in eq})
                names = ", ".join(got)
                verb = "was" if len(got) == 1 else "were"
                keyname = ", ".join(sorted({k for a in eq for k in a["key"]}))
                lines += ["",
                          f"> **Those subsectors have the SAME intensity as "
                          f"each other, and that is an assumption rather than "
                          f"a finding.** {names} {verb} divided by `{keyname}`, "
                          f"the key that split the output, which says the "
                          f"parts use the same amount per unit of money. For "
                          f"hotels against restaurants that is known to be "
                          f"false: a restaurant employs far more people per "
                          f"euro of turnover than a hotel does.",
                          ">",
                          f"> The parts add to the parent exactly, so the "
                          f"account's own total is untouched. What is "
                          f"estimated is how it divides. **If you have this "
                          f"quantity BY SUBSECTOR, that is the number to "
                          f"use** — the split cannot invent a difference "
                          f"nobody measured."]

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
                      "> **What a profile is worth, measured.** On 96 splits "
                      "where the office publishes both the parent and its "
                      "parts, giving the engine the parts' TRUE input profile "
                      "moves the SEED's multiplier error from a median 7.78 % "
                      "to 3.48 %. **The balancer then gives all of that "
                      "back**: the delivered table is a median 7.79 % against "
                      "7.78 % for using no profile at all, and it beats doing "
                      "nothing in 30 of 56. Balancing adjusts the internal "
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
                      "(r = +0.17 for the parent multiplier, -0.22 for the "
                      "number of parts). See "
                      "`validators/run_input_profiles_backtest.py`."]
        # "THE WEAKEST ASSUMPTION IN THE RESULT" WAS HALF RIGHT AND SAID
        # WRONG. Measured on 68 real splits where the office publishes both
        # the parent and its parts: the estimated block misses the published
        # one by a median of 60.9 %, comfortably the worst-estimated part of a
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
                  "not rest on it.** Measured on 96 splits where the office "
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
        # WHAT A ONE-REGION TABLE LEAVES OUT, when it was cut from a
        # multiregional archive. Read from the table AS LOADED -- the split
        # tables below carry none of it, on purpose -- and said to be that.
        ir = getattr(tbl, "interregional", None) or {}
        if ir.get("share_by_sector"):
            sc = ir.get("survey_check") or {}
            low = (f" And the archive keeps trade at home: where "
                   f"{sc.get('regions')} regional surveys can check it, it "
                   f"records {sc.get('rest_of_country_ratio', 0):.2f} times "
                   f"the purchases a region makes from the rest of its "
                   f"country, so these shares are more likely too low than "
                   f"too high.") if sc else ""
            if sc.get("spillover_median_if_surveyed") is not None:
                low += (f" Moved to what the surveys record, the "
                        f"{ir.get('archive_year', 2018)} archive's "
                        f"median rises from {ir.get('archive_median_pct')} % "
                        f"to {sc['spillover_median_if_surveyed']} %.")
            cf = ir.get("share_by_sector_if_surveyed")
            if ir.get("share_if_surveyed") is not None:
                low += (f" **At the surveys' level of trade** — this region's "
                        f"trade with the rest of its country multiplied by "
                        f"{ir.get('surveyed_factor', 4):g}, every column total "
                        f"held; a counterfactual, not a corrected figure — it "
                        f"would lose **{_fmt(100 * ir['share_if_surveyed'])} "
                        f"%**.")
            yc = ir.get("years_check") or {}
            if yc:
                low += (f" It is the figure for {tbl.year}: across the "
                        f"deposit's eleven years a region's figure moves by a "
                        f"median of {yc.get('region_range_median_pts')} points "
                        f"between its highest and lowest year "
                        f"({yc.get('region_range_p90_pts')} at the 90th "
                        f"percentile), while the archive's median stays "
                        f"between {yc.get('median_min')} % and "
                        f"{yc.get('median_max')} %. Read it as that year's, "
                        f"not as a constant.")
            # The same weighted by the final demand for the region's own
            # products, which is the figure a reader asks for: the sum above
            # counts a unit of demand in every sector alike.
            dem = ir.get("share_of_demand")
            dem_txt = "" if dem is None else (
                f" Weighted by the final demand for this region's own "
                f"products instead, exports included, **{_fmt(100 * dem)} %** "
                f"of the output that demand sets off is produced in other "
                f"regions ({_fmt(100 * ir['share_of_demand_if_surveyed'])} % "
                f"at the surveys' level); the median region's is "
                f"{ir.get('demand_median_pct', '—')} %.")
            prov += [
                "", "### What a one-region table leaves out", "",
                f"This table is one region cut from a multiregional archive, so "
                f"part of what happens when one of its sectors grows runs "
                f"through other regions and comes back. Measured on "
                f"{ir.get('measured_on', 'the archive')}, that part is "
                f"**{_fmt(100 * ir['share'])} %** of this region's output "
                f"multipliers; across the {ir.get('archive_year', 2018)} "
                f"archive the median is "
                f"{ir.get('archive_median_pct', '—')} %. **The multipliers in "
                f"this report come from the one-region table and do not "
                f"contain it.**" + dem_txt + low, "",
                "| sector | | multiplier, full system | runs through other "
                "regions |" + (" at the surveys' level |" if cf else ""),
                "|---|---|---:|---:|" + ("---:|" if cf else "")]
            for i, (c, lab, mf, sh) in enumerate(zip(
                    tbl.sector_codes, tbl.sector_labels,
                    ir.get("multiplier_full", []), ir["share_by_sector"])):
                prov.append(f"| `{c}` | {lab} | {_fmt(mf, 3)} | "
                            f"{_fmt(100 * sh)} % |"
                            + (f" {_fmt(100 * cf[i])} % |" if cf else ""))
            if ir.get("to_regions"):
                prov += ["", "Where it goes, as a share of what leaves: "
                         + ", ".join(f"`{r}` {_fmt(100 * v)} %"
                                     for r, v in ir["to_regions"]) + "."]
            # THE SAME IN JOBS, when the employment came from Eurostat: the
            # loader's columns weighted by jobs per unit of output in every
            # region Eurostat carries (`io_loader.mrio_jobs`).
            jb = ir.get("jobs") or {}
            if jb:
                worst = max(jb.get("unmeasured_by_sector") or [0.0])
                # Regions whose output the archive puts far below their
                # employment: said when they carry a tenth or more of the
                # jobs elsewhere, or when this region is one of them.
                imp = jb.get("implausible") or []
                imp_note = ""
                if jb.get("loaded_implausible"):
                    imp_note += (
                        f" **The archive puts this region's own output far "
                        f"below what its employment implies**: its jobs per "
                        f"unit of output are "
                        f"{jb['loaded_implausible']:.0f} times the median "
                        f"region's, which means the archive's output and this "
                        f"employment are not describing the same place: the "
                        f"employment multipliers above cannot be read with "
                        f"confidence.")
                if imp and (jb.get("from_implausible") or 0) >= 0.10:
                    times = [t for _, t in imp]
                    imp_note += (
                        f" **{_fmt(100 * jb['from_implausible'])} % of the "
                        f"jobs this region's demand creates elsewhere fall in "
                        f"{', '.join(f'`{r}`' for r, _ in imp)}**, whose jobs "
                        f"per unit of output in the archive are "
                        f"{min(times):.0f} to {max(times):.0f} times the "
                        f"median region's: the archive's output and "
                        f"Eurostat's employment are not describing the same "
                        f"place there, so a figure that multiplies one by the "
                        f"other cannot be read with confidence in either "
                        f"direction, and neither can the job figures here, as "
                        f"far as they carry. Until 2026-09-12 this was the "
                        f"archive's own Greek and Finnish labels naming other "
                        f"regions, which the loader now corrects.")
                prov += [
                    "", f"**In jobs.** Weighted by Eurostat's employment for "
                    f"{jb['regions_counted']} of the archive's "
                    f"{jb['regions']} regions, **{_fmt(100 * jb['share'])} %** "
                    f"of this region's employment multipliers runs through "
                    f"other regions ({_fmt(100 * jb['share_if_surveyed'])} % "
                    f"at the surveys' level); across the archive the median "
                    f"is {jb.get('archive_median_pct', '—')} %. The employment "
                    f"multipliers in this report come from the one-region "
                    f"table and do not contain it. Regions without "
                    f"Eurostat's employment hold at most {_fmt(100 * worst)} % "
                    f"of any sector's multiplier here, and count nothing."
                    + ("" if jb.get("share_of_demand") is None else
                       f" Weighted by the final demand for the region's own "
                       f"products, **{_fmt(100 * jb['share_of_demand'])} %** "
                       f"of the jobs it creates are elsewhere "
                       f"({_fmt(100 * jb['share_of_demand_if_surveyed'])} % "
                       f"at the surveys' level); the median region's is "
                       f"{jb.get('demand_median_pct', '—')} %.")
                    + ("" if not jb.get("years_check") else
                       f" It is the figure for {tbl.year}: across the "
                       f"deposit's eleven years a region's figure moves by a "
                       f"median of "
                       f"{jb['years_check']['region_range_median_pts']} "
                       f"points between its highest and lowest year "
                       f"({jb['years_check']['region_range_p90_pts']} at the "
                       f"90th percentile), while the archive's median stays "
                       f"between {jb['years_check']['demand_median_min']} % "
                       f"and {jb['years_check']['demand_median_max']} %.")
                    + imp_note,
                    "",
                    "| sector | jobs through other regions | at the surveys' "
                    "level |", "|---|---:|---:|"]
                for c, a, b in zip(tbl.sector_codes, jb["share_by_sector"],
                                   jb["share_by_sector_if_surveyed"]):
                    prov.append(f"| `{c}` | {_fmt(100 * a)} % | "
                                f"{_fmt(100 * b)} % |")
            prov += ["", "These figures are for the table as loaded, before "
                         "any split. A split changes the region's own block, "
                         "and the archive's inverse is not recomputed for the "
                         "parts, so no subsector below has a figure of its "
                         "own."]
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
                  "resemblance to your own inputs, not accuracy. See "
                  "`validators/run_key_bias.py`.",
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
                  "`validators/run_key_spread.py`.",
                  ">",
                  "> One thing the spread does NOT do is lean reliably one "
                  "way. Every available proxy sits on the same side of the "
                  "answer for only **16.0 %** of subsectors. Spanish "
                  "hospitality, where all seven of the pilot\'s keys "
                  "overstate accommodation and the range misses by 0.6 "
                  "points, is the unusual case and not the pattern — as it "
                  "also was for the size of the error. See "
                  "`validators/run_key_bias.py` and `validators/run_real_key.py`.", ""]

    # ------------------------------------------------------------------
    # OQ-E-03. What the answer would have been under each of the other keys.
    #
    # The section above compares the SHARES an unused key implies. This one
    # re-runs the split under it and reports what came out, which is what the
    # user publishes. Present only when the run asked for it: it costs one full
    # run per candidate key.
    #
    # It prints LEVELS first and multipliers second, and that order is not
    # presentation. The multiplier is invariant to the key -- the weight
    # cancels in `a_ij = Z_ij / X_j` -- so leading with it would show a column
    # of zeros to a reader who would take them for agreement between sources.
    # `validators/run_key_sensitivity.py` had warned about exactly that before
    # this was written.
    #
    # It does NOT rank them, for the same reason the scenario ranking above was
    # removed, and now with a second measurement behind it: on the Spanish case
    # the key an economist would pick on conceptual grounds is +40.8 % out and
    # the loosest conceptual match is the closest at -11.3 %.
    # ------------------------------------------------------------------
    alts = meta.get("key_alternatives")
    if alts:
        lines += ["### What the answer would have been under a different key", "",
                  f"Each split re-run under every other allocation key "
                  f"registered for it, on scenario "
                  f"`{meta.get('key_alternatives_scenario')}`. Not a "
                  f"perturbation: these are the proxies actually registered, "
                  f"and each row is a complete run.", ""]

        # ASKED FOR AND EMPTY IS THE ONE OUTCOME THAT MUST BE SPOKEN.
        #
        # With a single key registered there is nothing to compare against, and
        # the first version printed the heading, the paragraph above, and then
        # stopped. A reader who asked for this section and met a blank one
        # reads it as agreement, or as a switch that did not work. Both are
        # worse than not printing it. Found on 2026-09-07 running the engine
        # from a fresh clone the way a stranger would.
        if not any(a["runs"] for a in alts.values()):
            lines += ["> **Nothing to compare against: only one allocation key "
                      "is registered.** That is not a clean result, it is an "
                      "absent test. This section can only say what a DIFFERENT "
                      "proxy would have given, and there is no different proxy "
                      "here.",
                      ">",
                      "> Registering a second key you do not intend to use is "
                      "the only external check this engine can make, and it "
                      "costs one row per subsector in the `keys` sheet. On the "
                      "one split where the answer is published, eight proxies "
                      "of the same two subsectors spanned **423.8 %** — see "
                      "`validators/run_key_alternatives.py`.", ""]
        for code, a in sorted(alts.items()):
            if not a["runs"]:
                continue
            new_codes = a["new_codes"]
            lines += [f"**`{code}` into {', '.join(f'`{c}`' for c in new_codes)}**",
                      "",
                      "| Key | strength | "
                      + " | ".join(f"{c} level" for c in new_codes)
                      + " | vs the run |",
                      "|---|---|" + "---:|" * (len(new_codes) + 1)]
            driving = ", ".join(f"`{k}`" for k in a["driving"])
            lines.append(
                f"| {driving} — **the one used** | | "
                + " | ".join(f"{x:,.1f}" for x in a["actual_levels"])
                + " | — |")
            for r in sorted(a["runs"], key=lambda r: r["level_gap"][0]):
                lines.append(
                    f"| `{r['key_id']}` | {r['strength']} | "
                    + " | ".join(f"{x:,.1f}" for x in r["levels"])
                    + f" | {_pct(r['level_gap'][0])} |")
            lines += ["",
                      f"Widest disagreement between any two runs: "
                      f"**{a['level_spread_pct']:,.1f} %** of a subsector's "
                      f"size."]

            if a["multiplier_invariant_by_construction"]:
                lines += ["",
                          "> **The multipliers are identical in every one of "
                          "those runs, and that is arithmetic rather than "
                          "agreement.** This scenario carries no input "
                          "profiles, so each subsector gets a scaled copy of "
                          "the parent's input structure and the weight cancels "
                          "in `a_ij = Z_ij / X_j`. A key cannot move a "
                          "multiplier here whatever it says. Read the zero as "
                          "*this choice does not touch that number*, never as "
                          "*my sources agree*."]
            else:
                lines += ["",
                          f"Multipliers move too, by up to "
                          f"**{a['multiplier_spread_pct']:,.2f} %**, because "
                          f"this scenario carries input profiles."]

            for sk in a["skipped"]:
                lines += ["",
                          f"*`{sk['key_id']}` was not run: {sk['reason']}*"]

            lines += ["",
                      "> **Which of these is right cannot be decided from "
                      "inside, and this engine will not pretend otherwise.** "
                      "If a source existed that said which proxy to believe, "
                      "the proxy would not be needed. The one split in this "
                      "project where the answer is published settles what "
                      "guessing costs: on Spanish product 36 the key with the "
                      "best conceptual match — production against output — is "
                      "**+40.8 %** from the truth, and employment, the "
                      "loosest match of the seven, is the closest at "
                      "**-11.3 %**. Ranking by plausibility would have picked "
                      "one of the worst and called it founded. See "
                      "`validators/run_key_alternatives.py`.",
                      ">",
                      "> **Choose one and say why.** The choice belongs in the "
                      "assumption ledger with its argument, where a reader can "
                      "disagree with it. `D_open_questions.md` OQ-E-03.", ""]

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
    # `validators/run_split_backtest.py` scores 68 real splits against tables where the
    # office publishes both the parent and its parts. `validators/run_split_screen.py`
    # then asks what in the COARSE table predicts the result, since the thing
    # that actually drives it — how unlike the parts are — cannot be known
    # without the answer. Seven candidates were tried; on 96 splits ONE
    # survives -- the number of parts. The parent's multiplier ranked at
    # +0.24 and negative in France, so the four-corner table this printed
    # until v1.75 is gone. See run_split_screen.py.
    # the parent's own output multiplier (equivalently, one minus its value
    # added share, r = -0.98 between them) and the number of parts.
    #
    # It ranks, it does not predict a number, and it holds on countries it was
    # not fitted on: leave-one-country-out Spearman +0.52 to +0.76, positive in
    # every fold. The cut point below is the median of those 96 splits.
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
            med, worst = ("5.4 %", "41.6 %") if k <= 2 else ("10.6 %", "49.2 %")
            band.append((code, pm, k, med, worst))
        if band:
            lines += [
                "### How risky was this split, before you made it?", "",
                "**How many parts you asked for** ranks a split's difficulty, "
                "measured on 96 real splits where the office publishes both "
                "the parent and its parts. Held out one country at a time it "
                "separates in the same direction in all four — BE 7.9 to "
                "22.5 %, FR 8.2 to 11.2 %, HU 5.3 to 7.9 %, SK 4.4 to "
                "19.7 %.", "",
                "| Split | parent multiplier | parts | comparable splits: median error | worst |",
                "|---|---:|---:|---:|---:|"]
            for code, pm, k, med, worst in band:
                lines.append(f"| `{code}` | {pm:.3f} | {k} | {med} | {worst} |")
            lines += [
                "",
                "> The error columns are what the subsectors' **multipliers** "
                "did in comparable splits. They are a band, not a prediction "
                "for your table: the screen ranks, and the spread inside each "
                "band is wide — the worst column is the worst of 96, not a "
                "bound on yours. The cut point is the median of the 96, two "
                "parts.",
                ">",
                "> **The parent multiplier column is printed and is no longer "
                "used to place you in a band.** Fitted on 68 splits it looked "
                "like a second, independent signal; on 96 it ranks at +0.24 "
                "and is NEGATIVE in France, and at few parts its two bands "
                "come out at 5.4 % and 5.3 % — no separation at all. An "
                "earlier version of this report split you four ways on it. "
                "See `validators/run_split_screen.py`.",
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
                "> **If ANOTHER YEAR of your own table publishes the "
                "split, use it and ignore all of this.** The same parent a "
                "year earlier misses by **0.7 points**, against 2.8 for the "
                "band above and 5.7 for the same parent borrowed from another "
                "country. A split\'s difficulty is a property of the table it "
                "is in, not of the sector — which is why another COUNTRY\'s "
                "number is the worst of the three, and why "
                "`validators/run_key_carryover.py` finds the same thing from the key\'s "
                "side.",
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
            "short one. See `validators/run_key_sensitivity.py`.", ""]

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
