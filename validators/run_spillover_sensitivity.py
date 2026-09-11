"""
How far below the truth is 11.7 %? Move the archive's trade with the rest of
the country to what surveys record, and measure again.

WHAT WAS KNOWN
----------------
`run_mrio_spillovers.py` measured on the European MRIO that a single-region
table omits a median 11.7 % of the output multiplier.
`run_mrio_against_surveys.py` then found that, where surveys can check it, the
archive records 0.25 times the purchases a region makes from the rest of its
country and 2.06 times those from itself, with the total about right. So 11.7 %
is a floor. This measures how far above the floor the answer plausibly sits.

WHAT IS DONE, AND WHAT IT IS NOT
----------------------------------
A counterfactual on the coefficients, not a corrected archive. For every
purchasing sector of every region, the intermediate inputs it buys are split
three ways: from its own region (o), from the rest of its own country (c), and
from regions of other countries (f). f is left alone and o + c is held fixed,
so every column of A keeps its total and the archive's LEVEL of intermediate
purchases is untouched. Only the split between home and the rest of the
country moves, and the extra trade is spread over the partners the archive
already has, in the archive's proportions -- so the archive's view of WHO
trades with whom stands, and only how much is changed.

Two settings:

  ratio   c multiplied by 4 in every region, the inverse of the median survey
          ratio 0.25. Each region keeps its own position in the spread
  own     for each of the ten surveyed regions, one factor on c chosen so the
          REGION's purchases from the rest of the country reach the share of
          domestic purchases its own survey records

A column whose purchases from the rest of the country are zero is left as it
is: there is no partner to spread them over, and inventing one is not this
file's to do. A column is never given more than it buys. The thirteen regions
with no interregional trade at all are excluded, as in
`run_mrio_spillovers.py`.

THE FIRST VERSION GOT THE SETTING WRONG, AND IT SHOWED
--------------------------------------------------------
It imposed the survey's split on every COLUMN, and on every region the median
split. The spread closed instead of rising (p90 41.5 % to 39.4 %) and two of
the ten surveyed regions came out LOWER than the archive -- Catalonia 16.4 % to
14.8 %. Setting each purchasing sector to the region's average moved trade
back home in exactly the sectors the archive already sent furthest, Catalonia's
primary sector at 53.9 % among them: it homogenised the sectors instead of
moving trade out. The split is a statement about a region, so it is applied as
one factor per region, and the archive's pattern across sectors stands.

WHAT IT FINDS
---------------
                                 p10     median    p90
    as the archive has it        2.1 %   11.7 %   41.5 %
    rest of country x 4          4.7 %   21.6 %   61.4 %

**Roughly double.** And each of the ten surveyed regions, given its own
survey's split, loses more to the rest of its country than the archive says --
ten of ten, Catalonia 27.8 % against the 16.4 % the report prints, the
Austrian regions 26 % to 46 % against 14 % to 30 %.

That is a range with a floor and a plausible level, not a corrected figure:
the partners, and each sector's share of the region's trade, are still the
archive's, and nobody has measured those.

Run:
    python3 validators/run_spillover_sensitivity.py
"""
from __future__ import annotations

import importlib.util
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MRIO = ROOT / "data" / "mrio"
AUSTRIA = MRIO / "truth" / "Austria"
IDESCAT = ROOT / "data" / "idescat" / "mioc2021ts64.xlsx"
S = 10
SURVEYED = ("AT11", "AT12", "AT13", "AT21", "AT22",
            "AT31", "AT32", "AT33", "AT34")
FAIL: list[str] = []

# Exit code 3, not 0. `check.sh` counts it as SKIPPED rather than as a pass:
# this validator opened no file and measured nothing, and a run that says
# "All checks passed" on evidence it never saw is the fault the suite exists
# to catch. It is not a failure -- a tree without the workbook still exits 0.
NOTHING_CHECKED = 3


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def spillover(A, R):
    """Per unit: the share of its output multiplier outside its own region."""
    L = np.linalg.inv(np.eye(len(A)) - A)
    m = L.sum(0)
    intra = np.empty_like(m)
    for r in range(R):
        sl = slice(r * S, (r + 1) * S)
        intra[sl] = L[sl, sl].sum(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(m > 0, (m - intra) / m, np.nan), L


def moved(Z, regions, targets):
    """Z with each targeted region's home/rest-of-country split moved.

    `targets` maps a region's index to ("ratio", k) or ("split", s). A split
    is one factor for the whole region, never one per column: see the
    docstring for what the per-column version did. Returns the new Z and the
    number of columns that could not move because they buy nothing from the
    rest of their country.
    """
    Zn = Z.copy()
    stuck = 0
    for r, (how, v) in targets.items():
        cols = slice(r * S, (r + 1) * S)
        own = slice(r * S, (r + 1) * S)
        same = [j for j, q in enumerate(regions)
                if q[:2] == regions[r][:2] and j != r]
        rows_c = np.concatenate([np.arange(j * S, (j + 1) * S) for j in same]) \
            if same else np.array([], int)
        O = Zn[own, cols]
        C = Zn[rows_c, cols] if len(rows_c) else np.zeros((0, S))
        o, c = O.sum(0), C.sum(0)
        d = o + c
        k = v if how == "ratio" else (
            v * d.sum() / c.sum() if c.sum() > 0 else 1.0)
        c_new = np.minimum(c * k, d)
        stuck += int(((c == 0) & (d > 0)).sum())
        o_new = d - c_new
        with np.errstate(invalid="ignore", divide="ignore"):
            fo = np.where(o > 0, o_new / o, 1.0)
            fc = np.where(c > 0, c_new / c, 1.0)
        Zn[own, cols] = O * fo
        if len(rows_c):
            Zn[rows_c, cols] = C * fc
    return Zn, stuck


def main() -> int:
    warnings.filterwarnings("ignore")
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    if not ((MRIO / "_mrio2018_cache.npz").exists()
            or (MRIO / "MRIO_2018_272regions.xlsx").exists()) \
            or not (MRIO / "Final_demand_2018.xlsx").exists() \
            or not AUSTRIA.is_dir():
        print("    -- the MRIO block or the Austrian survey tables are absent.")
        print("\n" + "=" * 78)
        print("Nothing was checked: the archive is not in this tree.")
        return NOTHING_CHECKED

    from quadrium.io_loader import read_rokicki_components
    from quadrium.regionalise import EVIDENCE

    spec = importlib.util.spec_from_file_location(
        "axis", ROOT / "validators" / "run_mrio_axis_scale.py")
    axis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(axis)
    Z, labels = axis.load_Z()
    _, fh, FD = axis.load_side(axis.FD, "rows")
    X = FD[:, fh.index("TOTAL")]
    regions = list(dict.fromkeys(l.split("-", 1)[0] for l in labels))
    R = len(regions)
    denom = np.where(X > 0, X, np.inf)

    # ---- the survey splits: purchases from the rest of the country as a
    # share of domestic purchases (own region + rest of country)
    split = {}
    for r in SURVEYED:
        c = read_rokicki_components(AUSTRIA, r)
        own, roc = c["Z"].sum(), c["imports"]["rest of country"].sum()
        split[r] = roc / (own + roc)
    if IDESCAT.exists():
        from quadrium.io_loader import load_idescat_mioc
        t = load_idescat_mioc(IDESCAT)
        roc = next(row.sum() for lab, row in zip(t.VA_labels, t.VA)
                   if "resta d'Espanya" in lab)
        split["ES51"] = roc / (t.Z.sum() + roc)
    s_med = float(np.median(list(split.values())))

    # ---- the islands, excluded exactly as run_mrio_spillovers.py does
    island = np.array([
        (Z[r * S:(r + 1) * S, :].sum()
         - Z[r * S:(r + 1) * S, r * S:(r + 1) * S].sum()) < 1e-9
        and (Z[:, r * S:(r + 1) * S].sum()
             - Z[r * S:(r + 1) * S, r * S:(r + 1) * S].sum()) < 1e-9
        for r in range(R)])
    live = [r for r in range(R) if not island[r]]

    base, L0 = spillover(Z / denom, R)
    keep = np.repeat(~island, S) & np.isfinite(base)

    # One factor, written once, in the engine's EVIDENCE: the loader uses it
    # for a region's own figure and this file for the archive-wide range.
    factor = EVIDENCE.get("spillover_share_pct_survey", {}).get("factor", 4.0)
    Z_ratio, stuck_r = moved(Z, regions,
                             {r: ("ratio", factor) for r in live})
    col_err = float(np.abs(Z_ratio.sum(0) - Z.sum(0)).max())
    check("every column of A keeps its total, so only the split moved",
          col_err < 1e-6 * float(Z.sum(0).max()),
          f"largest change in a column total {col_err:.2e}; "
          f"{stuck_r} column(s) buy nothing from the rest of their country and "
          f"stay as they are")
    # The loader computes the same counterfactual for the region it returns,
    # with its own implementation. Two codes, one answer, or the region's
    # figure and the range it is read against are not the same experiment.
    try:
        from quadrium.io_loader import _mrio_move_to_country
        Z_eng = _mrio_move_to_country(Z, regions, {r: factor for r in live})
        same = bool(np.allclose(Z_eng, Z_ratio, rtol=0,
                                atol=1e-9 * float(Z.max())))
        detail = ("the loader's implementation gives this file's matrix, cell "
                  "for cell")
    except ImportError as exc:
        same, detail = False, f"the engine has no implementation: {exc}"
    check("and the engine moves the trade exactly as this file does",
          same, detail)

    ratio, L1 = spillover(Z_ratio / denom, R)
    check("and the counterfactual system still has an inverse with no "
          "negative cell", int((L1 < 0).sum()) == 0,
          "the column totals are the archive's, so the system stays "
          "productive")

    def pct(v):
        return np.percentile(v[keep], [10, 50, 90]) * 100

    p0, p1 = pct(base), pct(ratio)
    print()
    print(f"    {'':34}{'p10':>8}{'median':>9}{'p90':>8}")
    print(f"    {'as the archive has it':34}{p0[0]:>7.1f}%{p0[1]:>8.1f}%"
          f"{p0[2]:>7.1f}%")
    print(f"    {'rest of country x 4':34}{p1[0]:>7.1f}%{p1[1]:>8.1f}%"
          f"{p1[2]:>7.1f}%")
    print()

    check("the archive's own figure is reproduced first, so the comparison "
          "starts from the published one",
          round(float(p0[1]), 1) == EVIDENCE["spillover_share_pct"]["median"],
          f"median {p0[1]:.1f} % against the {EVIDENCE['spillover_share_pct']['median']} % "
          f"the engine prints")
    check("and moving trade to the rest of the country raises it, across the "
          "whole spread", all(p1[i] > p0[i] for i in range(3)),
          f"p10 {p0[0]:.1f} → {p1[0]:.1f} %, median {p0[1]:.1f} → "
          f"{p1[1]:.1f} %, p90 {p0[2]:.1f} → {p1[2]:.1f} %")

    # ---- each surveyed region under its OWN survey split
    print(f"    {'region':8}{'survey split':>14}{'archive':>10}{'own split':>11}")
    rise = []
    for name, s in split.items():
        k = regions.index(name)
        Zk, _ = moved(Z, regions, {k: ("split", s)})
        sl = slice(k * S, (k + 1) * S)
        E = np.zeros((len(Z), S))
        E[np.arange(k * S, (k + 1) * S), np.arange(S)] = 1.0
        Lk = np.linalg.solve(np.eye(len(Z)) - Zk / denom, E)
        mk = Lk.sum(0)
        a1 = float((mk - Lk[sl].sum(0)).sum() / mk.sum())
        m0 = L0[:, sl].sum(0)
        a0 = float((m0 - L0[sl, sl].sum(0)).sum() / m0.sum())
        rise.append((name, a0, a1))
        print(f"    {name:8}{100 * s:>13.1f}%{100 * a0:>9.1f}%{100 * a1:>10.1f}%")
    print()
    higher = sum(a1 > a0 for _, a0, a1 in rise)
    check("each surveyed region, given its own survey's split, loses more to "
          "the rest of its country than the archive says",
          higher == len(rise),
          f"higher in {higher} of {len(rise)}")

    ev = EVIDENCE.get("spillover_share_pct_survey") or {}
    if len(split) == 10 or not ev:
        want = {"p10": round(float(p1[0]), 1),
                "median": round(float(p1[1]), 1),
                "p90": round(float(p1[2]), 1),
                "surveyed_higher": higher}
        check("and the engine quotes the range, not a rounded memory of it",
              all(abs(ev.get(k, -1) - v) < 1e-9 for k, v in want.items()),
              f"regionalise.EVIDENCE['spillover_share_pct_survey'] is "
              f"{ev or 'absent'}; measured {want}")
    else:
        print(f"    -- {len(split)} of 10 surveyed regions are here; the "
              f"engine's range is not re-derived from a smaller base")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED:")
        for f in FAIL:
            print(f"  - {f}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
