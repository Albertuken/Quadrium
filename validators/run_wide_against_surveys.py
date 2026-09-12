"""
The three-block table's total is robust to the archive's home bias. Where it
lands is not.

WHY THIS WAS MEASURED
-----------------------
`load_eu_mrio_wide` returns a region, the rest of its country and the rest of
the archive, and `run_eu_mrio_wide.py` shows those three blocks reproduce the
full 2,720-unit system. What no check had asked is whether the middle block is
RIGHT, and there is a reason to doubt it: the archive keeps trade at home. On
ten regions whose trade was surveyed it records about a quarter of the
purchases they make from the rest of their country
(`run_mrio_against_surveys.py`; 0.23 at 2010 against 2010,
`run_mrio_same_year.py`). The middle block is built from those same cells, so
it inherits the bias, and the three-block table's own figures had to be
qualified before anything was printed on top of them.

The nine Austrian regions, the archive at 2010 against the surveys at 2010.

WHAT IT FOUND
---------------
**1. Almost all of what the three blocks add is output set off in the rest of
the country**, not feedback returning to the region. Of the multiplier the
three blocks add over a one-region table, a median 81 % lands in the rest of
the country and the remainder in the rest of the archive. What comes BACK to
the region is small: its own multiplier rises a median 0.04 % and at most
0.20 % over the nine -- 1.799 to 1.802. "The feedback a one-region table
omits" was the engine's own wording and it claimed more than the numbers
carry: what a one-region table omits is mostly production elsewhere.

**2. Correcting the home bias barely moves the total.** Give each region the
purchases from the rest of its country that its own survey records, taking the
increase out of what the archive puts at home so every column of A keeps its
total -- the counterfactual of `run_spillover_sensitivity.py`, on three blocks
instead of 2,720 -- and the total multiplier moves a median -0.09 %, between
-0.33 % and +1.04 %. The level is not what the bias distorts.

**3. What it distorts is the split.** The share of the impulse that stays in
the region falls from a median 88.9 % to 72.7 % -- 11.5 points, and 25.6 at
AT32 -- and it falls in nine regions of nine. So a table of three blocks can
be trusted for how much output an impulse sets off, and the line between
"here" and "the rest of the country" is the archive's, which is drawn too far
in favour of here.

WHAT THIS IS NOT
------------------
Not a corrected archive: the counterfactual moves coefficients and is
reported as a bound, not as a better table. And not a claim about the rest of
the archive, which no survey here can check -- the Austrian tables carry the
rest of AUSTRIA, and the third block is everyone else.

Run:
    python3 validators/run_wide_against_surveys.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MRIO = ROOT / "data" / "mrio"
AUSTRIA = MRIO / "truth" / "Austria"
YEAR = 2010
FILES = ("MRIO_2010_272regions.xlsx", "Final_demand_2010.xlsx",
         "TAXSUB_VA_2010.xlsx")
REGIONS = ("AT11", "AT12", "AT13", "AT21", "AT22", "AT31", "AT32", "AT33",
           "AT34")
FAIL: list[str] = []

NOTHING_CHECKED = 3


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def counterfactual(Z, X, S, factor):
    """The region's purchases from the rest of its country, times `factor`.

    The increase comes out of what the region buys from ITSELF, column by
    column, so every column of A keeps its total: the archive's LEVEL of
    intermediate purchases is untouched and only the split between here and
    the rest of the country moves. A column is never given more than the home
    block has to give.
    """
    Z2 = np.array(Z, dtype=float)
    add = Z2[S:2 * S, :S] * (factor - 1.0)
    home = Z2[:S, :S].copy()
    want, have = add.sum(0), home.sum(0)
    take = np.where(have > 0, np.minimum(want, have), 0.0)
    Z2[S:2 * S, :S] += add * np.divide(take, want, out=np.zeros_like(want),
                                       where=want > 0)
    Z2[:S, :S] -= home * np.divide(take, np.where(have > 0, have, 1.0))
    return Z2 / X


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    missing = [f for f in FILES if not (MRIO / f).exists()]
    if missing or not AUSTRIA.exists():
        absent = ", ".join(missing) or "the Austrian surveys"
        print(f"    -- absent from this tree: {absent}. The archive's 2010 "
              f"files are in MRIO.zip, Data/; the URL and SHA-256 are in "
              f"data/mrio/_provenance.json.")
        print("\n" + "=" * 78)
        print("Nothing was checked: the 2010 archive is not in this tree.")
        return NOTHING_CHECKED

    from quadrium.io_loader import load_eu_mrio_wide, read_rokicki_components
    from quadrium.regionalise import EVIDENCE

    print(f"\n    {'region':8}{'stays here':>12}{'rest of ctry':>14}"
          f"{'elsewhere':>11}   |{'survey':>9}{'archive':>9}{'factor':>8}"
          f"   |{'total':>8}{'stays here':>12}")
    print(f"    {'':8}{'% of the impulse':>37}   |"
          f"{'rest-of-country share':>26}   |"
          f"{'counterfactual moves':>20}")
    rows = []
    for region in REGIONS:
        t = load_eu_mrio_wide(MRIO, region, YEAR)
        S = t.n // 3
        L = np.linalg.inv(np.eye(t.n) - t.Z / t.X)
        here, rest_c, away = (L[:S, :S].sum(0), L[S:2 * S, :S].sum(0),
                              L[2 * S:, :S].sum(0))
        total = here + rest_c + away

        one = np.linalg.inv(np.eye(S) - t.Z[:S, :S] / t.X[:S]).sum(0)
        gain = total - one

        # what the archive and the survey each say this region buys from the
        # rest of its country, as a share of its output
        archive_share = t.Z[S:2 * S, :S].sum() / t.X[:S].sum()
        c = read_rokicki_components(AUSTRIA, region)
        survey_share = c["imports"]["rest of country"].sum() / c["X_col"].sum()
        factor = survey_share / archive_share

        L2 = np.linalg.inv(np.eye(t.n)
                           - counterfactual(t.Z, t.X, S, factor))
        here2 = L2[:S, :S].sum(0)
        total2 = L2[:, :S].sum(0)

        rows.append({
            "region": region,
            "here_pct": 100 * float(np.median(here / total)),
            "rest_c_pct": 100 * float(np.median(rest_c / total)),
            "away_pct": 100 * float(np.median(away / total)),
            "rest_c_of_gain": float(np.median(
                rest_c / np.where(gain > 0, gain, np.nan))),
            "feedback_pct": 100 * float(np.median((here - one) / one)),
            "survey": survey_share, "archive": archive_share,
            "factor": factor,
            "total_move_pct": 100 * float(np.median((total2 - total) / total)),
            "here_move_pts": 100 * float(np.median(here2 / total2
                                                   - here / total)),
            "here_pct_survey": 100 * float(np.median(here2 / total2))})
        r = rows[-1]
        print(f"    {region:8}{r['here_pct']:11.1f}%{r['rest_c_pct']:13.1f}%"
              f"{r['away_pct']:10.1f}%   |{r['survey']:8.1%}"
              f"{r['archive']:9.1%}{r['factor']:8.2f}   |"
              f"{r['total_move_pct']:7.2f}%{r['here_move_pts']:11.1f}")
    print()

    med = {k: float(np.median([r[k] for r in rows]))
           for k in rows[0] if k != "region"}

    check("almost all of what the three blocks add is output set off in the "
          "rest of the country",
          med["rest_c_of_gain"] > 0.6,
          f"a median {med['rest_c_of_gain']:.0%} of the multiplier they add "
          f"over a one-region table lands there, the rest further away")
    check("and what returns to the region itself is small, so `feedback` "
          "claimed more than the numbers carry",
          med["feedback_pct"] < 0.5
          and max(r["feedback_pct"] for r in rows) < 1.0,
          f"the region's own multiplier rises a median "
          f"{med['feedback_pct']:.2f} %, at most "
          f"{max(r['feedback_pct'] for r in rows):.2f} % over the nine")
    check("the archive keeps this trade at home here too, as it does on the "
          "whole deposit",
          all(r["archive"] < r["survey"] for r in rows),
          f"the archive's share of output bought from the rest of the country "
          f"is a median {med['archive']:.1%} against the surveys' "
          f"{med['survey']:.1%}, lower in {len(rows)} of {len(rows)}")
    check("giving each region the purchases its own survey records barely "
          "moves the total multiplier",
          abs(med["total_move_pct"]) < 0.5
          and max(abs(r["total_move_pct"]) for r in rows) < 2.0,
          f"a median {med['total_move_pct']:+.2f} %, at most "
          f"{max(abs(r['total_move_pct']) for r in rows):.2f} % — the level is "
          f"not what the bias distorts")
    check("but it moves where the impulse lands, in every region",
          all(r["here_move_pts"] < 0 for r in rows)
          and med["here_move_pts"] < -5,
          f"the share that stays in the region falls a median "
          f"{-med['here_move_pts']:.1f} points, "
          f"{-min(r['here_move_pts'] for r in rows):.1f} at the worst, from "
          f"a median {med['here_pct']:.1f} % to "
          f"{med['here_pct_survey']:.1f} %")

    ev = EVIDENCE.get("wide_vs_surveys") or {}
    if ev:
        want = {"regions": len(rows),
                "rest_of_country_of_gain": round(med["rest_c_of_gain"], 2),
                "feedback_pct": round(med["feedback_pct"], 2),
                "total_move_pct": round(med["total_move_pct"], 2),
                "here_pct": round(med["here_pct"], 1),
                "here_pct_survey": round(med["here_pct_survey"], 1)}
        wrong = {k: (v, ev.get(k)) for k, v in want.items() if ev.get(k) != v}
        check("and the engine quotes these figures and no others",
              not wrong,
              "EVIDENCE['wide_vs_surveys'] is the measurement" if not wrong
              else "; ".join(f"{k}: measured {m}, quoted {q}"
                             for k, (m, q) in wrong.items()))

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: " + ", ".join(FAIL))
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
