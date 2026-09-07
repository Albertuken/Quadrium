"""
The proxy's numbers, not just the name of the file that has them — OQ-E-01.

WHAT THIS IS FOR
-----------------
`--find` already named the sources that measure the parts of a sector and then
left the analyst to go and get the figures. The owner opened `OQ-E-01` on that,
in his own words: he might not know where to look, and a tool built for people
who do not know where to look has to look for them.

`proxy_values()` reduces a JSON-stat cube to one number per sector, and `--find`
prints the `keys` rows to paste.

WHAT WAS FOUND ON THE WAY, AND IT IS WORTH MORE THAN THE FEATURE
------------------------------------------------------------------
**`--find` answered "none" for every NACE GROUP.** Asked about `C101`, meat
processing, in Belgium, it said no code in any Belgian table covers it — while
the Belgian table carries `C10`, which contains it and is precisely the sector
to divide. The holder search used `_covers`, which reads DIVISIONS because that
is the level an input-output table publishes; a user does not ask at that level.

`_inside` exists for exactly this and its own docstring explains the failure. It
had been applied to the proxy search and not to the call site three lines above
it. Both have been there as long as each other. **Fixing it is what made this
feature reachable at all**: before it, no code in the corpus produced a proxy
that tiles its container, so the printing path could never have run.

THREE REFUSALS AND A FILTER, EACH FROM A REAL CUBE
----------------------------------------------------
**48 indicators.** `sbs_ovw_act` measures value added, turnover, wages,
employment and 44 other things for the same sectors. A key is one number per
sector, so the cube is refused until `--measure` names one. Summing across them
would give a figure that reads as a measurement and is none.

**Every level at once.** Asked for the parts of `C10` the same file returns
`C101` and `C1011`, `C1012`, `C1013` — the group and the classes inside it — and
`C109` beside `C1091`. Pasted as a key those count the same euro twice, and the
shares look perfectly ordinary. `tiling_only` keeps one level.

**A label that was a guess.** The first version printed "a count of ENTERPRISES"
whatever had been asked for, over a column of value added in millions of euro.
It prints the measure's own label now.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FAIL = []


def check(label, ok, detail=""):
    print(f"  [{'ok' if ok else 'FAIL'}] {label}")
    if detail:
        print(f"         {detail}")
    if not ok:
        FAIL.append(label)


def main():
    from quadrium.catalogue import (ProxyValueError, advise, proxy_values,
                                    scan, tiling_only)

    # 1 -- the filter, which needs no data.
    check("a code contained by another is dropped",
          tiling_only(["C101", "C1011", "C1012", "C109", "C1091", "C102"])
          == ["C101", "C102", "C109"],
          "C1011 is inside C101; keeping both counts the same euro twice")
    check("and a set already at one level is left alone",
          tiling_only(["I561", "I562", "I563"]) == ["I561", "I562", "I563"])
    check("and it keeps the COARSER level, which is the one that tiles",
          tiling_only(["C10", "C101"]) == ["C10"],
          "taking C101 and dropping C102 would tile nothing")

    root = ROOT if (ROOT / "data" / "eurostat").exists() else None
    if root is None:
        print("  no Eurostat cache here; the rest needs one.")
        return 1 if FAIL else 0

    sources = scan(root)

    # 2 -- the defect that made this reachable: a GROUP finds its division.
    a = advise("C101", sources, "BE")
    check("a NACE group is placed inside the division that carries it",
          a["action"] == "split"
          and (a.get("best") or {}).get("container") == "C10",
          f"action={a['action']}, container="
          f"{(a.get('best') or {}).get('container')} — this answered 'none' "
          f"until 2026-09-07, while BE's table carried C10 all along")
    tiling = [p for p in a.get("proxies", []) if p["tiles"]]
    check("and a proxy that measures its parts is offered",
          bool(tiling),
          f"{len(a.get('proxies', []))} proxies, {len(tiling)} tiling")

    if not tiling:
        print("\n" + "=" * 78)
        print(f"{len(FAIL)} check(s) FAILED" if FAIL else "All checks passed.")
        return 1 if FAIL else 0

    src = tiling[0]["source"]

    # 3 -- the refusal, before the values.
    try:
        proxy_values(src, "BE")
        check("a cube with several indicators is refused until one is named",
              False, "it returned a number, which means it chose or summed")
    except ProxyValueError as exc:
        check("a cube with several indicators is refused until one is named",
              "--measure" in str(exc), str(exc)[:110])
        check("and the refusal lists what it holds, so it can be answered",
              "—" in str(exc) or "-" in str(exc),
              "a refusal that names no alternative is a dead end")

    # 4 -- with one named, real numbers with their provenance pinned.
    got = proxy_values(src, "BE", measure="AV_MEUR")
    check("naming a measure yields one number per sector",
          len(got["values"]) > 2 and all(isinstance(v, float)
                                         for v in got["values"].values()),
          f"{len(got['values'])} sectors")
    check("and every dimension but the sectors' is pinned and recorded",
          {"geo", "time"} <= set(got["pinned"]) and got["pinned"]["geo"] == "BE",
          str(got["pinned"]))
    check("and the measure's own label travels with the numbers",
          "Value added" in got["measure_label"],
          f"{got['measure_label']!r} — the first version asserted "
          f"'a count of ENTERPRISES' over this")

    # 5 -- a country the cube does not carry is named, not silently empty.
    try:
        proxy_values(src, "ZZ", measure="AV_MEUR")
        check("a country the cube does not carry is refused", False)
    except ProxyValueError as exc:
        check("a country the cube does not carry is refused",
              "ZZ" in str(exc), str(exc)[:90])

    print()
    print("    The afternoon this module exists to remove was only half")
    print("    removed: it named the file and left the numbers in it.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
