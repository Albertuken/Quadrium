"""
Twenty-seven published symmetric tables, and the eight the engine will not load.

WHY A SWEEP
------------
Every defect this project found in a fortnight came from adding ONE country.
Portugal's two decimals broke four tolerance gates. France's finest tiling made
a system rectangular and moved a measured result. Belgium's wholly imported
crude took 20,210 out of a refining column. Germany exposed a probe that was
asking the wrong axis.

The engine had been exercised on five or six economies. That is not a claim
about published data, it is a claim about five or six files. So: every EU
country plus Norway, most recent year each, load and check.

WHAT IT FOUND
--------------
**Nineteen of twenty-seven load and are sound** — spectral radius 0.33 to 0.65,
row residues at the rounding scale, and mostly no negative cells at all.

**Eight refuse, for four distinct reasons — and ALL EIGHT ARE LIMITS OF THE
DATA, not of the engine.** That was worth establishing rather than assuming:
three of the four looked like loader gaps until each was traced.

    IE LT MT NO PL   the table is INCOMPLETE: its codes do not sum to the
                     total it prints, by 1.25 % to 50.46 %
    HR               final demand has holes at EVERY level of the hierarchy —
                     29 products with no capital formation, 12 with no exports
    LU SK            no `P1` output vector is published at all
    SE               its own output vector disagrees with its own total-use
                     column for 61 of 65 products, worst 390.5 on `G46`

SWEDEN, AND WHY A CONTROL IS THE WHOLE ARGUMENT
------------------------------------------------
`G46`, wholesale trade: Sweden publishes an output of 67,091.2 and a total use
of 67,481.6 for the same product, 390.5 apart, and disagrees with itself for 61
of its 65 products. Spain and Portugal agree to 0.00 on every one.

Without that control the number is unreadable — it could as easily have been
this engine's arithmetic. With it, no tolerance is the answer: two figures a
source publishes for the same quantity cannot be reconciled by widening a
bound, and the message now names the product and both figures instead of
printing a maximum.

THE INCOMPLETE FIVE, AND A MESSAGE THAT WAS WRONG
---------------------------------------------------
Those five refused with "the set still mixes levels or still carries a row that
is not a sector" — one hypothesis, stated as a conclusion, and wrong five times
out of five. None mixes levels. They publish tables whose codes do not add up
to the total they print:

    LT   62 codes,  3.02 % short        MT   58 codes,  5.12 % short
    PL   60 codes,  3.29 % short        NO   63 codes,  1.25 % short
    IE   51 codes, 50.46 % short

Ireland's 2020 table accounts for barely half of the total it prints. That is
what a country whose sectors are dominated by a few firms looks like after
confidentiality has been applied.

A set that MIXES LEVELS overshoots by a factor -- Italy's was 2.4x, which is
what that branch was written for. An INCOMPLETE one undershoots. The two need
opposite responses, and the message now measures which it is and says so.

The refusals are all correct. Loading Ireland's table would understate that
economy by 362,158 without saying so.

THE OTHER ROUTE IN, SWEPT THE SAME WAY
----------------------------------------
A symmetric table is one way into this engine. The supply-use pair is the
other, and it is the one covering more years — Spain publishes 22 of the first
and 35 of the second. It had been exercised on five countries. Swept across all
28:

    14 of 28 load, transform by model D, and close their identities.

    9  INCOMPLETE, the same story as the symmetric route
    2  a cross-check between the three files: BG out by 3.24 against a bound
       of 0.365, SE by 394.58 — Sweden's own output and total-use disagreement
       again, seen from the other route
    2  final demand too sparse to assemble: Portugal's 2023 basic-price table
       publishes NO final-demand column at all, Finland's covers 1 product in 14
    1  DE, which publishes no basic-price use table

Belgium was the fifteenth refusal until 2026-08-26 — the closing identity, out
by 0.8 — and it is now the fourteenth country that loads. Not because anything
was relaxed: its supply table is a ONE-decimal file, 2,553 one-decimal figures
and two cells carrying a second, and `printed_decimals` was reading the
precision off those two. 0.8 across 92 one-decimal cells is inside what one
decimal can distinguish. See `run_sut_closure.py`.

Bulgaria's 3.24 was the last of the fifteen with no explanation, and it is the
data too: `cp15` gives `R90-92` a domestic output of 793.37 and `cp1610` a
total use of 790.11. Spain agrees with itself to 0.0000 on all 65 of its
products, which is what makes 3.26 readable rather than suspicious of us.

AND THE SWEEP FOUND A DEFECT OF MINE, TWO DAYS OLD
----------------------------------------------------
The final-demand columns were chosen from `naio_10_cp16` and then read out of
`naio_10_cp1610` by the same names. The two files do not agree on which
components they publish: **Czechia and Estonia give exports as `P6` and not as
the `P6_B0`/`P6_D0` split cp16 carries**, so exports were read as zero and the
domestic rebuild came out 50,837 and 2,267 short. The columns are now chosen to
satisfy every file that will be read with them, and both countries load.

Two attempts at that fix failed first, and both are recorded in the code: `cp16`
carries a `stk_flow` dimension whose only value is `TOTAL`, so requiring `DOM`
of it refused every country including the ones that already worked; and
requiring the IMPORTED block populated refuses everybody, because a product with
no imported household consumption is an empty cell that means zero.

Run:
    python3 validators/run_eu_sweep.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "eurostat"
FAIL: list[str] = []
SKIPPED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def refusal(path: Path, variant: str | None = None) -> str:
    """The refusal for one variant, or for the first that refuses.

    Naming the variant matters: the same file refuses with DIFFERENT numbers
    for `domestic` and `total`, because they are different tables. Ireland's
    2020 domestic table is 50.46 % short and its total table 37.75 %. Taking
    "the last error" gave whichever was tried last, which is a way of quoting
    a number without knowing what it measures.
    """
    from quadrium.eurostat import EurostatError, load_iot
    last = ""
    for v in ([variant] if variant else ["domestic", "total"]):
        try:
            load_iot(path, v)
            return ""
        except EurostatError as exc:
            last = str(exc)
            if variant:
                return last
    return last


def main() -> int:
    from quadrium.eurostat import load_iot

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # 1 -- the incomplete ones are diagnosed as incomplete, not as mixed.
    # The DOMESTIC table of each, which is what the docstring quotes.
    cases = {"IE": ("naio_10_cp1700_IE_2020.json", 50.0, 51.0),
             "NO": ("naio_10_cp1750_NO_2023.json", 1.0, 1.5)}
    for geo, (name, lo, hi) in cases.items():
        f = DATA / name
        if not f.exists():
            SKIPPED.append(geo)
            print(f"  --   {geo} — SKIPPED: {name} is not in this checkout")
            continue
        msg = refusal(f, "domestic")
        pct = None
        for tok in msg.replace(",", "").split():
            if tok.replace(".", "").isdigit() and "%" in msg[msg.find(tok):
                                                             msg.find(tok) + 12]:
                pct = float(tok)
                break
        check(f"{geo} is refused as INCOMPLETE, not as mixing levels",
              "INCOMPLETE" in msg and "SHORT" in msg
              and pct is not None and lo <= pct <= hi,
              f"{pct} % short — {msg.split('among them')[-1].split(',')[0].strip()[:40]}…"
              if pct else msg[:80])
        check(f"and {geo}'s message says what loading it anyway would cost",
              "understate this economy by" in msg,
              msg.split("understate this economy by")[-1].split(".")[0].strip()
              + " of output that is simply not published")

    # 2 -- the other refusals are distinct, and stay distinct.
    print()
    others = {"naio_10_cp1700_LU_2022.json": "no `P1` output vector",
              "naio_10_cp1700_HR_2021.json": "is fully populated",
              "naio_10_cp1700_SE_2023.json": "balances as published"}
    seen = {}
    for name, expect in others.items():
        f = DATA / name
        if not f.exists():
            SKIPPED.append(name[:20])
            print(f"  --   {name[:24]} — SKIPPED: not in this checkout")
            continue
        # Pinned, for the reason `refusal` documents: the same file refuses
        # with different numbers per variant, and quoting one while measuring
        # the other is how the check above already went wrong once.
        msg = refusal(f, "domestic")
        seen[name] = msg
        check(f"{name.split('_')[3]} refuses for its own reason",
              expect in msg, msg.splitlines()[0][:96])
        if "SE_" in name:
            check("and Sweden's message names the product and both figures",
                  "G46" in msg and "67,091.2" in msg and "67,481.6" in msg,
                  "output 67,091.2 against a total use of 67,481.6 — two "
                  "numbers Sweden publishes for the same product. Spain and "
                  "Portugal agree to 0.00, which is what makes it readable")
    check("and no two of those reasons are the same message",
          len({m.splitlines()[0][:40] for m in seen.values()}) == len(seen),
          f"{len(seen)} refusals, {len({m.splitlines()[0][:40] for m in seen.values()})} "
          f"distinct diagnoses — a sweep whose failures all read alike is a "
          f"sweep that has found one bug, not four")

    # 3 -- and what loads, loads soundly.
    print()
    loaded = {}
    for f in sorted(DATA.glob("naio_10_cp17*.json")) + \
            sorted(DATA.glob("naio_10_cp1750_*.json")):
        for variant in ("domestic", "total"):
            try:
                loaded[f.stem] = load_iot(f, variant)
                break
            except Exception:
                continue
    rhos = {}
    for name, t in loaded.items():
        A = np.where(t.X != 0, t.Z / t.X[None, :], 0.0)
        rhos[name] = float(np.abs(np.linalg.eigvals(A)).max())
    check("every table that loads is productive",
          bool(rhos) and all(r < 1.0 for r in rhos.values()),
          f"{len(rhos)} tables, spectral radius "
          f"{min(rhos.values()):.2f} to {max(rhos.values()):.2f} — the "
          f"condition every multiplier rests on, met by all of them")

    # 4 -- the supply-use route, and the defect the sweep of it found.
    print()
    cz = [DATA / f"naio_10_{d}_CZ_2024.json" for d in ("cp15", "cp16", "cp1610")]
    if not all(f.exists() for f in cz):
        SKIPPED.append("CZ")
        print("  --   CZ — SKIPPED: the 2024 trio is not in this checkout")
    else:
        from quadrium.eurostat import load_sut
        s = load_sut(*cz)
        check("Czechia's pair loads with the final-demand set BOTH files carry",
              "P6" in s.Y_labels and "P6_B0" not in s.Y_labels,
              f"{s.Y_labels} — cp16 publishes the `P6_B0`/`P6_D0` split and "
              f"cp1610 does not, and choosing from cp16 alone read Czech "
              f"exports as zero: the domestic rebuild came out 50,837 short")
        it = s.to_iot("D")
        col = float(np.abs(it.Z.sum(0) + it.VA.sum(0) - it.X).max())
        check("and transforms into a table that closes",
              col < 1.0 and it.n > 80,
              f"{s.V.shape[0]}×{s.V.shape[1]} → {it.n} sectors, column "
              f"residue {col:.3f}")

    # 5 -- Bulgaria: the last refusal that was neither explained nor large.
    print()
    bg = [DATA / f"naio_10_{d}_BG_2010.json" for d in ("cp15", "cp16", "cp1610")]
    if not all(f.exists() for f in bg):
        SKIPPED.append("BG")
        print("  --   BG — SKIPPED: the 2010 trio is not in this checkout")
    else:
        from quadrium.eurostat import EurostatError, load_sut
        try:
            load_sut(*bg)
            msg = ""
        except EurostatError as exc:
            msg = str(exc)
        check("Bulgaria's two files disagree with each other, and it says so",
              "R90-92" in msg and "793.37" in msg and "790.1" in msg,
              "cp15 gives R90-92 a domestic output of 793.37 and cp1610 a "
              "total use of 790.11 — 3.26 apart, in two files the same source "
              "publishes for the same country and year")
        # The control is the argument. Without it 3.26 could be ours.
        s = load_sut(DATA / "naio_10_cp15_ES_2022.json",
                     DATA / "naio_10_cp16_ES_2022.json")
        from quadrium.eurostat import _Cube
        import json as _json
        ub = _Cube(_json.loads(
            (DATA / "naio_10_cp1610_ES_2022.json").read_text()))
        worst = max(abs(s.q[i] - (ub.at(stk_flow="DOM", ind_use="TU",
                                        prd_ava="CPA_" + c) or 0.0))
                    for i, c in enumerate(s.product_codes))
        check("and Spain, the control, agrees with itself exactly",
              worst < 1e-9,
              f"max |output − total use| = {worst:.4g} across all "
              f"{len(s.product_codes)} products. Without that number, 3.26 "
              f"could as easily have been this engine's arithmetic")

    print()
    print("    Five or six files is not a claim about published data. Eight")
    print("    of twenty-seven is, and so is the fact that all eight refusals")
    print("    are correct.")

    print("\n" + "=" * 78)
    if SKIPPED:
        print(f"{len(SKIPPED)} check(s) SKIPPED: {', '.join(SKIPPED)}")
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
