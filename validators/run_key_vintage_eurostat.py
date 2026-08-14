"""
`OQ-B-14`, refined rather than repeated: eleven EU countries at once, and the
"catastrophic break" finding turns out to depend on how far apart the
subsectors being split are.

Spain (INE, CNAE 55/56, seven years) found value-added moving 21.0 pp and
employment 1.4 pp at the 2019-2020 pandemic break. The UK (ONS ABS,
groups 56.1/56.2/56.3, six years) found the same ranking — aGVA the most
volatile, employment costs the least — with the break-year move being aGVA's
single worst year of the six.

Both were **one country at a time**. Eurostat's structural business statistics
give the same three-group split (`I561`/`I562`/`I563`, division 56's own
groups, the same split the UK series used) for **eleven EU countries
simultaneously**, 2018-2020 -- spanning the same break in one query rather
than one acquisition per country.

WHAT REFINES, AND WHY IT IS NOT A CONTRADICTION
------------------------------------------------
Averaged across the eleven countries, the pandemic break moves turnover shares
by only **1.47x** a normal year's move (1.49 pp against 1.01 pp), and
employment shares by only **1.14x** (1.27 pp against 1.12 pp) -- nothing like
Spain's order-of-magnitude jump for value added.

**The qualitative ranking holds a third time**: turnover more break-sensitive
than employment, in the same direction as Spain (value added over employment)
and the UK (aGVA over employment costs). What does NOT repeat is the
MAGNITUDE, and the reason is visible in the data itself: Spain's split was
**across divisions** -- accommodation (55) against food and beverage service
(56), structurally different industries -- while this split and the UK's are
**within** division 56, three closely related activities (restaurants, event
catering, bars) that tend to move together even under a shared shock.

So `OQ-B-14`'s finding narrows to something more useful than "breaks are
catastrophic": **the risk scales with how far apart the subsectors being split
actually are**, not only with whether a break falls in the gap. A cross-
division split (Spain's) is high-risk in a break year; a within-division split
of closely related activities (this data, the UK's) is lower-risk even in the
same break year, though never risk-free -- Dutch turnover still moved 3.3 pp,
seven times the Czech figure for the same year and the same split.

Run:
    python3 validators/run_key_vintage_eurostat.py
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TURNOVER = ROOT / "data" / "eurostat" / "sbs_i561_i562_i563_turnover_2018_2020.json"
EMPLOYMENT = ROOT / "data" / "eurostat" / "sbs_i561_i562_i563_employment_2018_2020.json"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def _strides(sizes: list[int]) -> list[int]:
    s = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        s[i] = s[i + 1] * sizes[i + 1]
    return s


def _load_shares(path: Path, indic: str) -> dict[str, dict[str, list[float]]]:
    """Returns {country: {year: [share_I561, share_I562, share_I563]}}."""
    d = json.loads(path.read_text())
    dims = d["id"]
    st = _strides(d["size"])
    idx = {dim: d["dimension"][dim]["category"]["index"] for dim in dims}
    nace = sorted(idx["nace_r2"], key=idx["nace_r2"].get)
    geos = sorted(idx["geo"], key=idx["geo"].get)
    years = sorted(idx["time"], key=idx["time"].get)
    vals = d["value"]

    def get(geo, n, y):
        pos = (idx["freq"]["A"] * st[dims.index("freq")]
               + idx["nace_r2"][n] * st[dims.index("nace_r2")]
               + idx["indic_sb"][indic] * st[dims.index("indic_sb")]
               + idx["geo"][geo] * st[dims.index("geo")]
               + idx["time"][y] * st[dims.index("time")])
        return vals.get(str(pos))

    out: dict[str, dict[str, list[float]]] = {}
    for g in geos:
        row = {}
        ok = True
        for y in years:
            v = [get(g, n, y) for n in nace]
            if any(x is None for x in v):
                ok = False
                break
            total = sum(v)
            row[y] = [100 * x / total for x in v]
        if ok:
            out[g] = row
    return out


def _moves(shares: dict[str, dict[str, list[float]]], y0: str, y1: str
          ) -> dict[str, float]:
    return {g: max(abs(row[y1][i] - row[y0][i]) for i in range(3))
            for g, row in shares.items()}


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    if not (TURNOVER.exists() and EMPLOYMENT.exists()):
        print("Eurostat SBS data absent")
        return 0

    turnover = _load_shares(TURNOVER, "V12110")
    employment = _load_shares(EMPLOYMENT, "V16110")

    check("both variables cover the same set of countries",
          set(turnover) == set(employment) and len(turnover) >= 10,
          f"{len(turnover)} countries: {sorted(turnover)}")

    t_normal = _moves(turnover, "2018", "2019")
    t_break = _moves(turnover, "2019", "2020")
    e_normal = _moves(employment, "2018", "2019")
    e_break = _moves(employment, "2019", "2020")

    print()
    print(f"    {'country':<10}{'turnover normal':>17}{'turnover break':>17}"
          f"{'employ. normal':>17}{'employ. break':>16}")
    for g in sorted(turnover):
        print(f"    {g:<10}{t_normal[g]:>16.2f}{t_break[g]:>17.2f}"
              f"{e_normal.get(g, float('nan')):>17.2f}"
              f"{e_break.get(g, float('nan')):>16.2f}")

    t_ratio = statistics.mean(t_break.values()) / statistics.mean(t_normal.values())
    e_ratio = statistics.mean(e_break.values()) / statistics.mean(e_normal.values())
    print()
    print(f"    turnover:   normal mean {statistics.mean(t_normal.values()):.2f} pp, "
          f"break mean {statistics.mean(t_break.values()):.2f} pp, ratio {t_ratio:.2f}x")
    print(f"    employment: normal mean {statistics.mean(e_normal.values()):.2f} pp, "
          f"break mean {statistics.mean(e_break.values()):.2f} pp, ratio {e_ratio:.2f}x")

    check("turnover is more break-sensitive than employment, a third "
          "confirmation of the ranking",
          t_ratio > e_ratio,
          f"turnover ratio {t_ratio:.2f}x against employment's {e_ratio:.2f}x — "
          f"same direction as Spain (value added over employment) and the UK "
          f"(aGVA over employment costs)")

    check("but the magnitude is far short of 'catastrophic' for this split",
          max(t_ratio, e_ratio) < 2.0,
          f"both ratios under 2x — nothing like Spain's order-of-magnitude "
          f"jump. This is a within-division split (56.1/56.2/56.3, closely "
          f"related activities); Spain's was across divisions (55 against 56)")

    spread = max(t_break.values()) - min(t_break.values())
    check("and the SAME split still varies widely country to country in the "
          "SAME break year",
          spread > 2.0,
          f"turnover break-year move ranges {min(t_break.values()):.2f} to "
          f"{max(t_break.values()):.2f} pp across eleven otherwise-comparable "
          f"EU countries — a spread of {spread:.2f} pp for identical groups, "
          f"identical variable, identical year. Another argument against one "
          f"numeric staleness threshold: even holding the split and the "
          f"break fixed, the risk is not one number")

    print()
    print("    Refines OQ-B-14 rather than repeating it: the risk of a stale")
    print("    proxy scales with how far apart the subsectors being split")
    print("    actually are, not only with whether a break falls in the gap.")
    print("    A cross-division split is high-risk in a break year; a")
    print("    within-division split of related activities is lower-risk in")
    print("    the same break year, though never risk-free.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
