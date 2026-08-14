"""
`OQ-C-02`: the unit definitions were in the library all along, unread.

The entry has said since v1.0 that the establishment is the recommended unit
(CORE_003 ¶15.26, p. 483; CORE_005 ¶36.44, p. 1016) "but its definition, and the
rules for partitioning multi-product enterprises, are not in the loaded set", and
pointed at CORE_001 as the next source to load. **CORE_001 was already extracted**
— `library/extracted/CORE_001_SNA2025_CH06_...txt`, ten pages, paragraphs
6.1–6.57. The question was open for want of reading a file that was on disk.

Read now, and written up as `B_method_cards/M-058`. This file measures the two
things in it that can be measured.

TEST 1 — THE ALLOCATION KEY IS NOW SOURCED, AND THE THREE OPTIONS DISAGREE
--------------------------------------------------------------------------
CORE_001 ¶6.44, p. 200 says an ancillary unit's output "should be allocated
across them using an appropriate indicator such as the **output, value added or
labour input** of these establishments". That is the first sourced statement in
this library about what may serve as an allocation key; the engine's keys have
carried a `PROJECT CHOICE` label since v0.1 and three of them no longer need it.

The source names three and ranks none. They do not agree. On the pilot's own
pair — UK I55 accommodation × I56 food service — the weight on I55 is 0.2867 by
output, 0.3056 by value added and 0.2490 by labour input. Across 965 UK sibling
pairs the spread between them has a **median of 9.0 percentage points**.

**That is not measurement error.** All three are indicators the standard calls
appropriate, so the spread is the width of a range the SNA deliberately leaves
open — a lower bound on the uncertainty attributable to key choice alone, and
wider than most of the refinements this project has made.

TEST 2 — THE ONE BRIGHT LINE, AND WHAT IT PREDICTS
---------------------------------------------------
CORE_001 ¶6.26 and ¶6.28, p. 198: "when a vertically integrated enterprise spans
two or more sections of the ISIC, at least one establishment should preferably be
distinguished within each section." Everything else in the chapter is judgement;
this names a boundary in the classification and says do not cross it. Vertical
chains *inside* a section are therefore left intact inside one unit, and their
intra-chain deliveries stay inside one industry.

Measured: industries buy from their own ISIC section 2.1–3.1× more than that
section's share of total supply implies, in about 88 % of industries, in all
three fixtures.

**This is consistent with the rule and does not prove it.** Real supply chains
cluster inside sections for ordinary technological reasons, and this measurement
cannot separate the two causes. It is recorded as a magnitude, not as a
mechanism. It does bear on `OQ-S-04`, which found the diagonal of a two-sector
block sitting at ~1.5× the outer product and could not explain it: delineation
is now a candidate explanation with a rank-1 source behind it, and still only a
candidate.

Run:
    python3 validators/run_statistical_units.py
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def _uk():
    p = ROOT / "UK_IOAT_2023_domestic_ixi.xlsx"
    if not p.exists():
        return None
    import run_uk_iot as uk
    t = uk.load_iot(p)
    return (t["Z"], [str(c).strip() for c in t["codes"]],
            {"output (P1)": t["x"], "value added (B1G)": t["gva"],
             "labour input (D1)": t["compensation"]})


def _section_concentration(Z, codes):
    """How far intermediate purchases lean towards the buyer's own section."""
    sec = np.array([str(c)[0] if c else "?" for c in codes])
    col, supply = Z.sum(0), Z.sum(1)
    total = supply.sum()
    out = []
    for j in range(Z.shape[1]):
        if col[j] <= 0:
            continue
        m = sec == sec[j]
        base = supply[m].sum() / total
        if base > 0:
            out.append((Z[m, j].sum() / col[j]) / base)
    return np.array(out)


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    uk = _uk()
    if uk is None:
        print("  UK fixture absent; test 1 needs it")
    else:
        Z, codes, keys = uk
        i, j = codes.index("I55"), codes.index("I56")
        w = {}
        for name, v in keys.items():
            a, b = float(v[i]), float(v[j])
            w[name] = a / (a + b)
        print("    CORE_001 ¶6.44's three keys on the pilot's own pair, "
              "UK I55 × I56:")
        for name, ww in w.items():
            print(f"      {name:<20} weight on I55 = {ww:.4f}")
        lo, hi = min(w.values()), max(w.values())
        check("the three sourced keys disagree on the pilot's own pair",
              hi - lo > 0.02,
              f"{100 * (hi - lo):.1f} percentage points between "
              f"{min(w, key=w.get)} and {max(w, key=w.get)}; the engine "
              f"defaults to output, at {w['output (P1)']:.4f}")

        # And what that does to a cell, which is what an analyst sees.
        P = Z[i, i] + Z[i, j] + Z[j, i] + Z[j, j]
        cells = {n: ww * ww * P for n, ww in w.items()}
        spread = max(cells.values()) - min(cells.values())
        check("and it moves the internal block's diagonal by 40 %",
              spread / np.mean(list(cells.values())) > 0.3,
              f"{min(cells.values()):,.1f} to {max(cells.values()):,.1f} £m on "
              f"a parent cell of {P:,.1f}, at alpha = 1")

        # The distribution, so the pilot pair is not taken for the whole story.
        sec = [c[0] if c else "?" for c in codes]
        spreads = []
        for a, b in itertools.combinations(range(len(codes)), 2):
            if sec[a] != sec[b]:
                continue
            ws = []
            for v in keys.values():
                p_, q_ = float(v[a]), float(v[b])
                if p_ + q_ <= 0 or p_ < 0 or q_ < 0:
                    ws = None
                    break
                ws.append(p_ / (p_ + q_))
            if ws:
                spreads.append(max(ws) - min(ws))
        spreads = np.array(spreads)
        check("across 965 sibling pairs the median disagreement is 9 points",
              8.0 < 100 * np.median(spreads) < 10.0,
              f"median {100 * np.median(spreads):.1f} pp, p90 "
              f"{100 * np.percentile(spreads, 90):.1f} pp, above 5 pp in "
              f"{100 * (spreads > 0.05).mean():.0f} % of pairs — a range the "
              f"standard leaves open, not an error")

    # ---- test 2 -----------------------------------------------------------
    print()
    print("    Purchases from the buyer's own ISIC section, against that "
          "section's\n    share of total supply (¶6.26/¶6.28, p. 198):")
    from quadrium.eurostat import load_iot
    results = {}
    if uk:
        results["UK 104"] = _section_concentration(uk[0], uk[1])
    for fname, label in (("naio_10_cp1750_IT_2022.json", "Italy ixi 65"),
                         ("naio_10_cp1700_ES_2022.json", "Spain pxp 65")):
        p = ROOT / "data" / "eurostat" / fname
        if p.exists():
            t = load_iot(p, variant="domestic")
            results[label] = _section_concentration(t.Z, t.sector_codes)
    for label, r in results.items():
        print(f"      {label:<14} n={r.size:>4}  median {np.median(r):>5.2f}×  "
              f"above 1 in {100 * (r > 1).mean():.0f} % of industries")

    check("every fixture shows purchases leaning to the buyer's own section",
          all(np.median(r) > 1.5 for r in results.values()) and results,
          "medians " + ", ".join(f"{l} {np.median(r):.2f}×"
                                 for l, r in results.items()))
    check("and it is consistent across countries and both axes",
          len(results) >= 3
          and all((r > 1).mean() > 0.8 for r in results.values()),
          "≥80 % of industries in each — but real supply chains also cluster "
          "inside sections, and this cannot separate the two causes. Recorded "
          "as a magnitude, not as a mechanism")

    print()
    print("    What CORE_001 does NOT settle, from `M-058`:")
    print("      ¶6.15, p. 196 — how close 'nearly as important' is. No ratio.")
    print("      ¶6.44, p. 200 — which of the three keys to prefer. No ranking.")
    print("      ¶6.27, p. 198 — the uniform operating-surplus rate is offered")
    print("                      as 'one possibility', not prescribed.")
    print()
    print("    And ¶6.36, p. 199: the SNA could not agree which unit a supply")
    print("    and use table should rest on, and put it on the research agenda.")
    print("    The unit behind a published table is a national choice that the")
    print("    data does not record — the same finding as SOURCE_REGISTER §6b,")
    print("    reached from a rank-1 source instead of from an API.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
