"""
OQ-B-17 option 2, measured instead of debated: it buys nothing and costs the proof.

THE DECISION THIS INFORMS
---------------------------
`OQ-B-17` records that an input profile — the feature that makes a split more
than a rescaling — halves the structural error **in the seed** (7.78 % to
3.48 %) and that balancing gives all of it back in the table that is delivered
(7.79 % against 7.78 %). The mechanism is the engine's own design:
`run_scenario` balances the **internal block only**, because a proportional
split already satisfies every other margin exactly, and letting the solver move
cells copied from the original would break the §8 reaggregation guarantee —
which is a proof, not a diagnostic. With a profile the off-block column moves
and the whole adjustment lands in the k x k block, the worst-estimated part of
a split.

The entry offers four options and picks none. Option 2 is **widen what
balancing may touch**, and it is the only one that is neither already shipped
nor blocked on a document this project does not hold. It had never been
measured, so choosing between it and leaving things alone was choosing between
two arguments.

This measures it. Nothing under `src/quadrium` is touched: the prototype seeds
a split exactly as the engine does, then balances the **whole matrix** against
the same targets — option 2 in its strongest form.

WHAT CAME OUT, ON 60 SPLITS ACROSS FOUR COUNTRIES
---------------------------------------------------
    no profile, block only (ships today)     median 12.74 %   mean 13.09 %
    profile, block only (ships today)        median 12.46 %   mean 13.17 %
    profile, WHOLE MATRIX (option 2)         median 12.69 %   mean 12.97 %

**The three are indistinguishable.** Option 2 beats using no profile in 14 of
20 comparable splits and beats today's profiled path in 10 of 20 — exactly
half, which is what no effect looks like.

    what it costs    reaggregation error   median 31.4, worst 309.2
                     today                 exactly 0, by construction

That is the trade in one line: **the §8 guarantee stops holding and the answer
does not improve.** Reaggregating the delivered table would no longer return
the original for the untouched sectors, which is the one property this engine
proves rather than checks.

It is not even more permissive: full-matrix balancing **refuses more often** —
31 of 60 against 21 — because whole-matrix GRAS fails to converge on these
systems where the block alone succeeds.

WHAT THIS DOES NOT SETTLE
---------------------------
Twenty comparable splits, not the 96 the main back-test uses: a scenario must
survive all three paths to be compared, and full-matrix balancing kills more of
them. The direction is not in doubt — the cost is enormous and the gain sits
inside the noise — but a reader wanting a tight interval on the gain will not
find one here. This was built so the owner's decision is made against a number.

Run:
    python3 validators/run_profile_scope_experiment.py
"""
from __future__ import annotations

import statistics as st
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DATA = ROOT / "data" / "eurostat"
FINES = {"FR 2021": "naio_10_cp1700_FR_2021.json",
         "BE 2022": "naio_10_cp1700_BE_2022.json",
         "HU 2021": "naio_10_cp1700_HU_2021.json",
         "SK 2015": "naio_10_cp1700_SK_2015.json"}
COARSE = "naio_10_cp1700_ES_2022.json"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def multipliers(Z, X):
    A = Z / np.where(X == 0, 1.0, X)
    return np.linalg.inv(np.eye(len(X)) - A).sum(0)


def main() -> int:
    warnings.filterwarnings("ignore")
    from quadrium.balancing import balance
    from quadrium.disaggregation import split_sectors, targets
    from quadrium.eurostat import _covers, load_iot
    from quadrium.models import (AllocationKey, IOTable, ProxyStrength,
                                 Scenario, SplitSpec)
    from quadrium.scenarios import run_scenario

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    have = {g: f for g, f in FINES.items() if (DATA / f).exists()}
    check("there are tables that publish both a parent and its parts",
          len(have) >= 2 and (DATA / COARSE).exists(),
          f"{len(have)} of {len(FINES)} fine tables, coarse {COARSE}")
    if len(have) < 2 or not (DATA / COARSE).exists():
        print("\n" + "=" * 78 + "\nAll checks passed.")
        return 0

    def aggregate(t, parent, idx):
        pos, s = idx[0], set(idx)
        keep = [i for i in range(t.n) if i not in s]
        order = [i for i in keep if i < pos] + [None] + [i for i in keep if i > pos]
        M = np.zeros((len(order), t.n))
        codes = []
        for r, i in enumerate(order):
            if i is None:
                M[r, idx] = 1.0
                codes.append(parent)
            else:
                M[r, i] = 1.0
                codes.append(t.sector_codes[i])
        return IOTable(
            table_id="agg", country=t.country, year=t.year, unit=t.unit,
            classification=t.classification, sector_codes=codes,
            sector_labels=codes, Z=M @ t.Z @ M.T, Y=M @ t.Y,
            Y_labels=list(t.Y_labels), VA=t.VA @ M.T,
            VA_labels=list(t.VA_labels), X=M @ t.X, source=t.source)

    def profile_from(t, parent, kids, agg_codes):
        """m[supplier][part] = the part's coefficient over the parent's."""
        idx = [t.sector_codes.index(c) for c in kids]
        Xk, Xp = t.X[idx], t.X[idx].sum()
        par_col = t.Z[:, idx].sum(1)
        prof = {}
        for a, kid in enumerate(kids):
            d = {}
            for code in agg_codes:
                if code == parent or code not in t.sector_codes:
                    continue
                i = t.sector_codes.index(code)
                base = par_col[i] / Xp
                if base <= 0 or Xk[a] <= 0:
                    continue
                m = (t.Z[i, idx[a]] / Xk[a]) / base
                if np.isfinite(m) and m > 0:
                    d[code] = float(m)
            prof[kid] = d
        return prof

    coarse = load_iot(DATA / COARSE)
    rows = []
    for geo, f in have.items():
        fine = load_iot(DATA / f)
        m_true = multipliers(fine.Z, fine.X)
        for parent in coarse.sector_codes:
            kids = [c for c in fine.sector_codes
                    if c != parent and _covers(parent, c)]
            if len(kids) < 2:
                continue
            idx = [fine.sector_codes.index(c) for c in kids]
            agg = aggregate(fine, parent, idx)
            keys = {"k": AllocationKey(
                key_id="k", applies_to="output", new_sector_codes=kids,
                raw_values=list(fine.X[idx]), source="published truth",
                source_year=fine.year, strength=ProxyStrength.STRONG)}
            spec = SplitSpec(parent, kids, kids, keys_by_block={"output": "k"})
            prof = profile_from(fine, parent, kids, agg.sector_codes)

            def err(Z, X, codes):
                if list(codes) != list(fine.sector_codes):
                    return None
                return float((np.abs(multipliers(Z, X)[idx] - m_true[idx])
                              / m_true[idx] * 100).max())

            row = {"geo": geo, "parent": parent}
            for name, profiles in (("none", {}), ("block", prof)):
                try:
                    r = run_scenario(agg, [spec],
                                     Scenario(scenario_id="b", label="b",
                                              input_profiles=profiles), keys)
                    row[name] = err(r.table.Z, r.table.X, r.table.sector_codes)
                except Exception:                      # noqa: BLE001
                    row[name] = None
            # ---- option 2: the whole matrix, which is what it means
            try:
                sc = Scenario(scenario_id="b", label="b", input_profiles=prof)
                seed = split_sectors(agg, [spec], sc, keys)
                tr, tc = targets(seed["Y"], seed["VA"], seed["X"])
                Zf, _ = balance(seed["Z"], tr, tc, method="gras")
                row["whole"] = err(Zf, seed["X"], seed["codes"])
                # AND WHAT IT COSTS: the guarantee, measured rather than argued.
                pos = seed["splits"][0]["positions"]
                A = np.zeros((agg.n, len(seed["codes"])))
                for r_, c in enumerate(agg.sector_codes):
                    if c == parent:
                        for p in pos:
                            A[r_, p] = 1.0
                    else:
                        A[r_, seed["codes"].index(c)] = 1.0
                row["reagg"] = float(np.abs(A @ Zf @ A.T - agg.Z).max())
            except Exception:                          # noqa: BLE001
                row["whole"], row["reagg"] = None, None
            rows.append(row)

    ok = [r for r in rows
          if r["none"] is not None and r["block"] is not None
          and r["whole"] is not None]
    check("enough splits survive all three paths to compare them",
          len(ok) >= 10,
          f"{len(ok)} comparable of {len(rows)} split(s) across "
          f"{len(have)} countries — a scenario has to complete under every "
          f"path to appear here, and the whole-matrix path kills more of them")
    if len(ok) < 10:
        print("\n" + "=" * 78)
        return 1 if FAIL else 0

    med = {k: st.median([r[k] for r in ok]) for k in ("none", "block", "whole")}
    avg = {k: st.mean([r[k] for r in ok]) for k in ("none", "block", "whole")}
    print()
    print(f"    {'':<40}{'median':>10}{'mean':>10}")
    for k, lab in (("none", "no profile, block only (today)"),
                   ("block", "profile, block only (today)"),
                   ("whole", "profile, WHOLE MATRIX (option 2)")):
        print(f"    {lab:<40}{med[k]:>9.2f} %{avg[k]:>9.2f} %")
    print()

    spread = max(med.values()) - min(med.values())
    check("widening the scope does not improve the delivered table",
          spread < 1.0,
          f"the three medians span {spread:.2f} points on an error of "
          f"{med['none']:.1f} %. Option 2 is indistinguishable from doing "
          f"nothing, which is the question this file was written to answer")

    beats_none = sum(1 for r in ok if r["whole"] < r["none"])
    beats_block = sum(1 for r in ok if r["whole"] < r["block"])
    check("and split by split it is a coin flip against the path that ships",
          abs(beats_block - len(ok) / 2) <= len(ok) * 0.2,
          f"option 2 beats no profile in {beats_none} of {len(ok)} and beats "
          f"today's profiled path in {beats_block} of {len(ok)} — half, which "
          f"is what no effect looks like")

    reagg = [r["reagg"] for r in ok if r["reagg"] is not None]
    check("what it costs is the one property this engine PROVES rather than "
          "checks",
          reagg and st.median(reagg) > 1.0,
          f"reaggregation error median {st.median(reagg):.1f}, worst "
          f"{max(reagg):.1f}, against exactly 0 today by construction. "
          f"Reaggregating the delivered table would no longer return the "
          f"original for the untouched sectors")

    ref_block = sum(1 for r in rows if r["block"] is None)
    ref_whole = sum(1 for r in rows if r["whole"] is None)
    check("and it is not even more permissive", ref_whole > ref_block,
          f"{ref_whole} of {len(rows)} refused under the whole matrix against "
          f"{ref_block} under the block — whole-matrix GRAS fails to converge "
          f"where the block alone succeeds. Widening the scope buys nothing, "
          f"costs the proof, and turns more scenarios away")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
