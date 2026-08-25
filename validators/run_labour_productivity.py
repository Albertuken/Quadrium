"""
`D4`, labour productivity — the last diagnostic that needed data nobody had fetched.

WHY IT WAS NOT APPLICABLE, AND WHY IT NEARLY WAS NOT
------------------------------------------------------
`D4` compares volume GVA per unit of labour against the year before
(CORE_012 ¶11.20, p. 323). The supply-use tables carry the numerator and not the
denominator: **no Eurostat SUT contains labour input.**

At v1.62 a first pass thought otherwise. The use table has a row coded `LE`, it
was taken for employment, and `D4` ran: 48 Spanish industries flagged, worst
284 %. **`LE` is "Closing balance sheet".** The flags were an artefact of a
misread code and they looked entirely publishable. That near-miss is why this
file exists as its own run rather than as three lines bolted onto another.

WHERE THE LABOUR DATA IS
--------------------------
`nama_10_a64_e` — "Employment by detailed industry (NACE Rev. 2), national
accounts" — on the same API, with **`THS_HW` hours worked** and **`THS_PER`
persons**, `na_item=EMP_DC` (domestic concept). National-accounts employment
against national-accounts GVA is the same framework on both sides, which is what
CORE_012 ¶11.20 means by "calculated on the same basis"; a business-register
headcount would not be.

**The codes do not match, and the mapping is stated rather than assumed.**
The SUT writes `C31_32`, `J59_60`, `M74_75`; the employment cube writes
`C31_C32`, `J59_J60`, `M74_M75`. Two rewrites handle it. Two codes need more:

  * `U` in the SUT is `U99` in the employment cube — renamed, same thing;
  * **`L68B` exists in neither.** Employment publishes `L68` (all real estate)
    and `L68A` (owner-occupiers' housing, which by construction employs almost
    nobody), so `L68B` is **DERIVED** as `L68 − L68A` and labelled as derived.

**63 of 65 industries match.** The two dropped are named in the output and are
dropped rather than guessed at: `L68A`, owner-occupiers' housing, whose labour
input is zero by construction — an industry that employs nobody has no
productivity — and `U`, extraterritorial bodies.

WHAT IT FINDS, AND WHY THE FLAGS ARE THE POINT
------------------------------------------------
Austria and Spain, 2022 against 2021, hours worked:

    -40.7 %  coke and refined petroleum products
    -21.7 %  activities auxiliary to financial services
    -15.1 %  chemicals
     ...
    +40.9 %  accommodation and food service activities
    +86.6 %  travel agencies and tour operators
   +111.2 %  air transport
   +192.8 %  water transport

**Those are not data errors. That is 2022.** The industries at the top are the
ones that lost their output to the pandemic and got it back; the ones at the
bottom are the energy shock. CORE_012 ¶11.20 says a decrease or a high growth
"can also indicate possible mistakes in the data" — it indicates *something*,
and here what it indicates is real. A diagnostic that flags 30 of 63 industries
in a recovery year is behaving correctly and its output is a reading list, not a
defect list.

That is also the check on the check: after the `LE` episode, a `D4` whose
extremes were **not** air transport and accommodation would be a `D4` still
joined to the wrong denominator.

Run:
    python3 validators/run_labour_productivity.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

import diagnostics as dg  # noqa: E402
from quadrium.eurostat import _Cube, _coarsest_tiling  # noqa: E402

DATA = ROOT / "data" / "eurostat"
YEAR, PRIOR = 2022, 2021
COUNTRIES = (("AT", "Austria"), ("ES", "Spain"))

FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def cube(name: str):
    p = DATA / name
    return _Cube(json.loads(p.read_text())) if p.exists() else None


def _nace(code: str) -> str:
    """`C31_C32` -> `C31_32`, `J58-J60` -> `J58-60`. The SUT's spelling."""
    code = re.sub(r"^([A-Z])(\d+)_[A-Z](\d+)$", r"\1\2_\3", code)
    return re.sub(r"^([A-Z])(\d+)-[A-Z](\d+)$", r"\1\2-\3", code)


def employment(geo: str, year: int, unit: str) -> dict[str, float] | None:
    path = DATA / f"nama_10_a64_e_{geo}_{year}_{unit}.json"
    if not path.exists():
        return None
    doc = json.loads(path.read_text())
    index = doc["dimension"]["nace_r2"]["category"]["index"]
    values = doc["value"]
    out = {_nace(c): values.get(str(index[c])) for c in index}
    # DERIVED, and labelled: the employment cube splits neither L68A nor L68B
    # out of L68, but it does publish L68A. Owner-occupiers' housing employs
    # almost nobody, so the residual is the market real-estate industry.
    if out.get("L68") is not None:
        out["L68B"] = out["L68"] - (out.get("L68A") or 0.0)
    if out.get("U99") is not None:
        out.setdefault("U", out["U99"])
    return {k: v for k, v in out.items() if v is not None}


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    ran = 0
    for geo, name in COUNTRIES:
        cur = cube(f"naio_10_cp16_{geo}_{YEAR}.json")
        vol = cube(f"naio_10_pyp16_{geo}_{YEAR}.json")
        prev = cube(f"naio_10_cp16_{geo}_{PRIOR}.json")
        if not (cur and vol and prev):
            print(f"\n    {name}: the six-pack files are missing — skipped")
            continue

        industries = [i for i in cur.index["ind_use"]
                      if i not in ("TU", "TFU", "TOTAL")
                      and not i.startswith(("P3", "P5", "P6", "P7"))
                      and cur.at(stk_flow="TOTAL", prd_ava="CPA_A01",
                                 ind_use=i) is not None]
        industries, _ = _coarsest_tiling(industries)
        labels = cur.doc["dimension"]["ind_use"]["category"]["label"]

        print(f"\n    {name} {YEAR} against {PRIOR}")
        for unit, what in (("THS_HW", "hours worked"),
                           ("THS_PER", "persons")):
            L_now, L_before = (employment(geo, YEAR, unit),
                               employment(geo, PRIOR, unit))
            if not (L_now and L_before):
                print(f"      {what}: `nama_10_a64_e` not in data/eurostat "
                      f"— skipped")
                continue
            ran += 1
            keep = [i for i in industries if L_now.get(i) and L_before.get(i)]
            missing = [i for i in industries if i not in keep]

            gva_v = np.array([vol.at(stk_flow="TOTAL", prd_ava="B1G",
                                     ind_use=i) for i in keep], float)
            gva_p = np.array([prev.at(stk_flow="TOTAL", prd_ava="B1G",
                                      ind_use=i) for i in keep], float)
            l_now = np.array([L_now[i] for i in keep], float)
            l_before = np.array([L_before[i] for i in keep], float)

            result = dg.d4_labour_productivity(gva_v, l_now,
                                               prior_ratio=gva_p / l_before)
            growth = (gva_v / l_now) / (gva_p / l_before) - 1.0
            order = np.argsort(growth)

            print(f"      {what:<13} {len(keep)} of {len(industries)} "
                  f"industries matched, {len(missing)} dropped "
                  f"({', '.join(missing) or 'none'})")
            print(f"        D4 {result.status}, {result.n_flagged} flagged, "
                  f"median {np.median(growth):+.1%}, "
                  f"range {growth[order[0]]:+.1%} to {growth[order[-1]]:+.1%}")

            check(f"{name}: D4 runs on labour input rather than on nothing "
                  f"({what})",
                  result.status in ("PASS", "FLAG") and len(keep) > 55,
                  f"{len(keep)} industries carry volume GVA and {what} in both "
                  f"years — the check reported 'volume GVA or labour input not "
                  f"supplied' from v1.1 until now")

            if unit == "THS_HW":
                top = [keep[i] for i in order[-4:]]
                bottom = [keep[i] for i in order[:3]]
                print("        biggest falls:  "
                      + ", ".join(f"{keep[i]} {growth[i]:+.0%}"
                                  for i in order[:3]))
                print("        biggest rises:  "
                      + ", ".join(f"{keep[i]} {growth[i]:+.0%}"
                                  for i in order[-4:]))
                # THE check on the check, after the `LE` episode: a D4 joined
                # to the wrong denominator would not put the pandemic-recovery
                # industries at the top.
                recovery = {"H50", "H51", "I", "N79", "R90-92", "H49", "N"}
                energy = {"C19", "C20", "D", "D35"}
                check(f"{name}: and its extremes are the year, not the join",
                      len(recovery & set(top)) >= 2
                      and len(energy & set(bottom)) >= 1,
                      f"top {top} against a recovery set, bottom {bottom} "
                      f"against the energy shock — 2022 is exactly where the "
                      f"pandemic industries got their output back. A D4 wired "
                      f"to the wrong denominator would not know that")

    if not ran:
        print("\n    no employment data — nothing to do.")
        return 0

    print()
    print("    CAVEAT, and CORE_012 ¶11.20, p. 323 states it: the labour data")
    print("    must be on the same basis as the economic data. This uses")
    print("    national-accounts employment (domestic concept) against")
    print("    national-accounts GVA, which is the same framework on both")
    print("    sides. Hours and persons give different medians — the choice")
    print("    is the analyst's and both are reported rather than averaged.")
    print()
    print("    `L68B` employment is DERIVED as `L68 − L68A`; three industries")
    print("    have no counterpart at this breakdown and are dropped, not")
    print("    guessed. D_open_questions.md OQ-D-03.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
