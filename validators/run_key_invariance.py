"""
The allocation key buys sizes and nothing else, and that is exact.

TWO HALVES THAT HAD NEVER BEEN JOINED
---------------------------------------
`run_real_key.py` scores a key an analyst can actually download — Eurostat's
structural business statistics — against the office's own answer: **median 7.9
points of share error, p90 28.8, worst 70.2**, and no proxy reliably best.

`run_split_backtest.py` scores what a split costs when the key is exactly
RIGHT: **7.8 % median error in the subsectors' multipliers**.

One measures the key, the other measures the structure, and nobody had run a
real key through the engine and scored the delivered table. `run_real_key.py`
asserted the answer in prose — "the multiplier is not moved by it at all" —
without a check behind it. This is the check, and the assertion is true in a
stronger sense than it was stated.

MEASURED: 372 REAL KEYS, END TO END
-------------------------------------
The same 39 splits x up to 10 published proxies across FR 2021, BE 2022 and
HU 2022, each run twice — once with the proxy, once with the published answer:

    key error                      median   7.90 pp   p90  28.76
    subsector SIZE, perfect key    median   0.00 %
    subsector SIZE, real key       median  31.28 %    p90 111.08
    subsector MULTIPLIER, perfect  median   8.19 %
    subsector MULTIPLIER, real     median   8.19 %    p90  23.36

    real minus perfect, multipliers: identical to 1e-6 in 372 of 372

Not close. **Identical.** And the correlation between the key's error and the
multiplier error is r = +0.036, against r = +0.691 for the key's error and the
size error.

IT IS AN IDENTITY, NOT A REGULARITY
-------------------------------------
Without an input profile, a proportional split gives every part the parent's own
column of technical coefficients: `A[i, part] = s·Z[i, parent] / (s·X[parent])`,
and the share cancels. The output multiplier obeys `m_j = 1 + Σ_i m_i·A[i,j]`,
which reads columns only, and the parts' contribution to any column is
`Σ_a m_a·s_a·A[parent,j] = m_parent·A[parent,j]` — the shares sum to one and
cancel again. So the key leaves the multiplier recursion untouched.

Checked directly on France, two keys as far apart as they can be made — every
part equal, against parts weighted 1, 4, 9, 16 — over 13 splits:

    largest relative difference in any subsector multiplier:  6.3e-16

Machine precision. The 372 real proxies land on the same identity from the
other direction.

**With an input profile it is false**, and that is the boundary: the same test
with one profiled part moves multipliers by 9.9e-02. A profile is the only way
a key reaches structure. `OQ-B-17` measured what a profile is worth after
balancing — a wash — so on what the engine ships today, the key reaches sizes
and stops.

WHAT THE KEY DOES BUY, AND IT IS WORSE THAN THE POINTS SUGGEST
----------------------------------------------------------------
A share error of 7.9 points is not a 7.9 % subsector. The size error is
relative to a part that may be small, so the points are amplified by a median
factor of **3.8, p90 9.7**:

    key error       n    worst part's size error: median    p90
    under 5 pp     128                            13.8 %   33.8 %
    5 to 15 pp     147                            31.0 %   68.2 %
    over 15 pp      97                            88.1 %  163.8 %

Only **45 of 372** real keys put every subsector within 10 % of its true size.

WHAT THIS CHANGES
-------------------
The report's risk bands (`run_split_screen.py`) are printed with the caveat
"with the size key exactly right". That caveat understates them: the bands hold
for ANY key, because the key cannot move what they measure. What the user needs
warning about is the other column — the sizes — and the report was not saying
that at all.

Run:
    python3 validators/run_key_invariance.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_real_key import CASES, COARSE, DATA, PROXIES, reader  # noqa: E402

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}"
          + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def multipliers(Z, X):
    A = Z / np.where(X == 0, 1.0, X)
    return np.linalg.inv(np.eye(len(X)) - A).sum(0)


def main() -> int:
    from quadrium.disaggregation import split_sector
    from quadrium.eurostat import _covers, load_iot
    from quadrium.models import (AllocationKey, IOTable, ProxyStrength,
                                 Scenario, SplitSpec)

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    def aggregate(t, parent, idx):
        pos, s = idx[0], set(idx)
        keep = [i for i in range(t.n) if i not in s]
        order = ([i for i in keep if i < pos] + [None]
                 + [i for i in keep if i > pos])
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
            VA_labels=list(t.VA_labels), X=M @ t.X, source=t.source,
            retrieved_at=t.retrieved_at)

    def splits_of(fine, coarse):
        for parent in coarse.sector_codes:
            kids = [c for c in fine.sector_codes
                    if c != parent and _covers(parent, c)]
            if len(kids) < 2:
                continue
            idx = [fine.sector_codes.index(c) for c in kids]
            if idx != list(range(idx[0], idx[0] + len(idx))) \
                    or fine.X[idx].min() <= 0:
                continue
            yield parent, kids, idx

    def scored(agg, fine, parent, kids, idx, vals, year, profiles=None):
        """Run one split with one key; return (multiplier err, size err)."""
        keys = {"k": AllocationKey(
            key_id="k", applies_to="output", new_sector_codes=kids,
            raw_values=list(vals), source="scored against the answer",
            source_year=year, strength=ProxyStrength.MEDIUM)}
        spec = SplitSpec(parent, kids, kids, keys_by_block={"output": "k"})
        sc = Scenario(scenario_id="s", label="s",
                      input_profiles=profiles or {})
        try:
            r = split_sector(agg, parent, kids, kids, sc, keys, spec)
        except Exception:
            return None
        if list(r["codes"]) != list(fine.sector_codes):
            return None
        Z, X = np.asarray(r["Z"]), np.asarray(r["X"])
        return multipliers(Z, X), X

    coarse = load_iot(DATA / COARSE)

    # 1 -- the identity, on two keys made as different as they can be.
    #
    # Not a proxy against the truth: two ARBITRARY keys against each other. If
    # the multiplier depended on the key at all, this would show it.
    fr = DATA / "naio_10_cp1700_FR_2021.json"
    check("there is a table that publishes both a parent and its parts",
          fr.exists(), "FR 2021 at 89 products")
    if not fr.exists():
        return 0
    fine = load_iot(fr)

    flat, prof = [], []
    for parent, kids, idx in splits_of(fine, coarse):
        agg = aggregate(fine, parent, idx)
        k = len(kids)
        equal = np.ones(k)
        skewed = np.arange(1, k + 1, dtype=float) ** 2
        others = {c for c in agg.sector_codes
                  if c != parent and c in fine.sector_codes}
        one_profiled = {kids[0]: {c: 1.7 for c in others}}
        for tag, profiles, into in (("flat", None, flat),
                                    ("profiled", one_profiled, prof)):
            a = scored(agg, fine, parent, kids, idx, equal, 2021, profiles)
            b = scored(agg, fine, parent, kids, idx, skewed, 2021, profiles)
            if a is None or b is None:
                continue
            ma, mb = a[0][idx], b[0][idx]
            into.append(float(np.abs(ma - mb).max()
                              / max(float(np.abs(ma).max()), 1e-12)))

    print()
    print(f"    two keys as far apart as they can be made, over "
          f"{len(flat)} splits:")
    print(f"      {'no input profile':<28}largest relative difference "
          f"{max(flat):.1e}")
    print(f"      {'one part profiled':<28}"
          f"{'':<27}{max(prof):.1e}")
    check("without a profile the key cannot move a multiplier at all",
          max(flat) < 1e-12,
          f"{max(flat):.1e} — machine precision, not a small effect. A "
          f"proportional split gives every part the parent's own column of "
          f"coefficients (the share cancels in Z/X) and the multiplier "
          f"recursion m_j = 1 + sum_i m_i A[i,j] reads columns only. It is an "
          f"identity")
    check("and a profile is the only thing that lets it",
          max(prof) > 1e-4,
          f"{max(prof):.1e} with a single profiled part. That is the boundary "
          f"of the result above — and OQ-B-17 measured what a profile is worth "
          f"once the balancer has had it: a wash")

    # 2 -- and 372 real, downloadable keys land on the same identity.
    rows = []
    for geo, year, f in CASES:
        sbs = DATA / f"sbs_ovw_act_{geo}_{year}.json"
        if not (DATA / f).exists() or not sbs.exists():
            continue
        t = load_iot(DATA / f)
        at, _ = reader(sbs)
        m_true = multipliers(t.Z, t.X)
        for parent, kids, idx in splits_of(t, coarse):
            agg = aggregate(t, parent, idx)
            truth_share = t.X[idx] / t.X[idx].sum()
            perfect = scored(agg, t, parent, kids, idx, t.X[idx], year)
            if perfect is None:
                continue

            def err(res):
                m, X = res
                return (float((np.abs(m[idx] - m_true[idx])
                               / m_true[idx] * 100).max()),
                        float((np.abs(X[idx] - t.X[idx])
                               / t.X[idx] * 100).max()))

            m_p, x_p = err(perfect)
            for code, label in PROXIES:
                vals = [at(nace_r2=c, indic_sbs=code) for c in kids]
                if any(v is None for v in vals):
                    continue
                v = np.array(vals, float)
                if v.sum() <= 0 or (v < 0).any():
                    continue
                real = scored(agg, t, parent, kids, idx, v, year)
                if real is None:
                    continue
                m_r, x_r = err(real)
                rows.append((float(np.abs(v / v.sum() - truth_share).max()
                                   * 100), m_p, m_r, x_p, x_r))

    check("and there are real published proxies to run through it",
          len(rows) >= 200,
          f"{len(rows)} key-and-split pairs from structural business "
          f"statistics across {len(CASES)} countries")
    if len(rows) < 200:
        return 1 if FAIL else 0

    kp = np.array([r[0] for r in rows])
    mp = np.array([r[1] for r in rows])
    mr = np.array([r[2] for r in rows])
    xp = np.array([r[3] for r in rows])
    xr = np.array([r[4] for r in rows])

    print()
    print(f"    {'key error':<32}median {np.median(kp):>7.2f} pp  "
          f"p90 {np.percentile(kp, 90):>6.2f}")
    print(f"    {'subsector SIZE, perfect key':<32}"
          f"median {np.median(xp):>7.2f} %")
    print(f"    {'subsector SIZE, real key':<32}median {np.median(xr):>7.2f} % "
          f"  p90 {np.percentile(xr, 90):>6.2f}")
    print(f"    {'subsector MULTIPLIER, perfect':<32}"
          f"median {np.median(mp):>7.2f} %")
    print(f"    {'subsector MULTIPLIER, real key':<32}"
          f"median {np.median(mr):>7.2f} %   p90 {np.percentile(mr, 90):>6.2f}")

    same = int((np.abs(mr - mp) < 1e-6).sum())
    check("a real key delivers the SAME multipliers as the published answer",
          same == len(rows),
          f"identical to 1e-6 in {same} of {len(rows)}. The 7.8 % a split "
          f"costs is structural and the key does not add to it")
    check("the key's error predicts the size error and not the multiplier",
          abs(float(np.corrcoef(kp, mr)[0, 1])) < 0.15
          and float(np.corrcoef(kp, xr)[0, 1]) > 0.5,
          f"r = {np.corrcoef(kp, xr)[0, 1]:+.3f} against the size error, "
          f"r = {np.corrcoef(kp, mr)[0, 1]:+.3f} against the multiplier")

    # 3 -- what the key does buy, and why the points understate it
    print()
    amp = xr / np.where(kp == 0, np.nan, kp)
    print(f"    {'key error':<16}{'n':>5}{'size error: median':>22}{'p90':>9}")
    for lo, hi, lbl in ((0, 5, "under 5 pp"), (5, 15, "5 to 15 pp"),
                        (15, 1e9, "over 15 pp")):
        m = (kp >= lo) & (kp < hi)
        if not m.any():
            continue
        print(f"    {lbl:<16}{int(m.sum()):>5}{np.median(xr[m]):>20.1f} %"
              f"{np.percentile(xr[m], 90):>8.1f} %")
    check("a point of key error costs more than a point of subsector",
          float(np.nanmedian(amp)) > 2.0,
          f"a median factor of {np.nanmedian(amp):.1f}, p90 "
          f"{np.nanpercentile(amp, 90):.1f} — the error is relative to a part "
          f"that may be small, so 7.9 points of share is a median "
          f"{np.median(xr):.0f} % on the worst part")
    within = int((xr < 10).sum())
    check("and few real keys get every subsector close",
          within < len(rows) * 0.25,
          f"{within} of {len(rows)} put every subsector within 10 % of its "
          f"true size")

    print()
    print("    The key is a levels instrument. Structure comes from the")
    print("    split itself, and the only thing that lets a key reach it is")
    print("    an input profile.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
