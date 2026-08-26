"""
Moving a table in TIME — the second verb, and the last of the four orphans.

WHAT WAS UNREACHABLE
---------------------
UNH_18 chapter 18 specifies three methods for projecting a supply-use pair onto
a later year's totals. All three have been implemented here and verified
against the chapter's own printed iterations — GRAS at v1.2, SUT-RAS at v1.3,
SUT-EURO at v1.66. **No operation in this engine projected anything.** A whole
chapter, built and checked, with no way in.

That was the fourth instance of one shape, found by a sweep that listed every
public name reachable from the validators and not from the user path. The other
three: the Eurostat download, the interchange format, the supply-use input.

Everything else this engine does makes a table finer. This moves it in time: a
detailed base-year pair, plus what is known about a later year — value added by
industry, final use by category, and two totals — and out comes a full pair
consistent with them. That is what an office does between benchmark years, and
what an analyst does to ask "if output looks like this, what does the table
look like?".

THE IDENTITY TEST, AND WHAT IT CAUGHT
---------------------------------------
A projection onto a pair's OWN totals must return that pair. It is the cheapest
possible check and it caught the thing that mattered.

`final_use` has to be at PURCHASERS' prices, because the method carries taxes as
a row of the use table. Supplied at basic prices instead, the projection does
not fail: it runs to the 200-iteration ceiling, never converges, parks 380 away
from the base pair, and reports every value-added deviation as 1.00003 — which
reads like success. At purchasers' prices the same call converges in ONE
iteration with every deviation exactly 1.0 and `max|Ud − Ud₀| = 0.000000`.

A second thing it caught: the projected pair was carrying the BASE year's taxes
and value added. Rows stayed exact and the transformed table's column identity
went 576 out — the signature of a value-added block that did not move with the
rest of the table.

Run:
    python3 validators/run_projection.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "eurostat"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def pair(geo: str = "ES", year: int = 2022):
    from quadrium.eurostat import load_sut
    return load_sut(DATA / f"naio_10_cp15_{geo}_{year}.json",
                    DATA / f"naio_10_cp16_{geo}_{year}.json",
                    DATA / f"naio_10_cp1610_{geo}_{year}.json")


def own_totals(s):
    """The pair's own totals, in the bases `project` documents."""
    return dict(
        gva=s.W.sum(axis=0),
        final_use=(s.Y_domestic.sum(axis=0) + s.Y_imported.sum(axis=0)
                   + s.taxes_by_final_demand),
        taxes=float(s.taxes_by_activity.sum() + s.taxes_by_final_demand.sum()),
        imports=float(s.imports[s.q > 0].sum()))


def main() -> int:
    from quadrium.sut_euro import sut_euro

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    s = pair()
    pi, ai = np.flatnonzero(s.q > 0), np.flatnonzero(s.g > 0)
    check("a supply-use pair knows whether it can be projected",
          s.projectable,
          "it needs the domestic/imported split at basic prices AND taxes by "
          "column, which is what `naio_10_cp1610` carries")

    # 1 -- the identity test.
    t = own_totals(s)
    same = s.project(**t, year=s.year)
    dev = max(float(np.abs(same.U_domestic - s.U_domestic[np.ix_(pi, ai)]).max()),
              float(np.abs(same.V - s.V[np.ix_(pi, ai)]).max()),
              float(np.abs(same.g - s.g[ai]).max()))
    # Float noise, not zero -- the distinction this project has now had to
    # learn in four different places. `1e-12 of output` is the noise floor.
    check("projecting a pair onto its own totals returns that pair",
          dev / abs(s.q[pi].sum()) < 1e-12,
          f"use, supply and industry output all reproduce to {dev:.3g} on an "
          f"output of {s.q[pi].sum():,.0f}. The cheapest check there is, and "
          f"the one that found the price basis")

    # 2 -- and the counterfactual that makes it a check rather than a ritual.
    Ud0 = np.hstack([s.U_domestic[np.ix_(pi, ai)], s.Y_domestic[pi]])
    Um0 = np.hstack([s.U_imported[np.ix_(pi, ai)], s.Y_imported[pi]])
    tls0 = np.concatenate([s.taxes_by_activity[ai], s.taxes_by_final_demand])
    wrong = sut_euro(Ud0, Um0, tls0, s.V[np.ix_(pi, ai)].T,
                     va_target=s.W.sum(axis=0)[ai],
                     final_use_target=(s.Y_domestic.sum(axis=0)
                                       + s.Y_imported.sum(axis=0)),
                     tls_target=float(tls0.sum()),
                     imports_target=float(Um0.sum()))
    va_dev = max(abs(v - 1.0) for k, v in wrong.deviations.items()
                 if k.startswith("va["))
    parked = float(np.abs(wrong.Ud - Ud0).max())
    check("the same call at BASIC prices fails, and fails quietly",
          not wrong.converged and parked > dev * 1e6 and va_dev < 1e-3,
          f"{wrong.iterations} iterations without converging, parked "
          f"{parked:,.0f} from the base pair against the {dev:.3g} the right "
          f"basis returns — a factor of {parked / dev:,.0f} — while the worst "
          f"value-added deviation reads {1 + va_dev:.5f}, which looks like "
          f"success. Only the identity test tells them apart")

    # 3 -- a real projection moves everything, and moves it consistently.
    print()
    grown = s.project(gva=t["gva"] * 1.03, final_use=t["final_use"] * 1.02,
                      taxes=t["taxes"] * 1.02, imports=t["imports"] * 1.04,
                      year=s.year + 1)
    dq = grown.q.sum() / same.q.sum() - 1
    check("a projection onto grown totals grows the table between them",
          0.02 < dq < 0.03,
          f"+3 % value added, +2 % final use, +4 % imports gives {dq:+.2%} "
          f"output — between the two demands that drive it, which is where it "
          f"should land and is not something the method was told")
    # SUT-EURO STOPS AT 1 PER CENT, and that is the chapter's own rule
    # (Box 18.8), not a project choice: it iterates until every aggregate is
    # within one per cent of its target and then stops. So a target is
    # approached, not attained, and asserting attainment would be asserting
    # something the method does not offer. What IS assertable is that the
    # projected taxes moved with the target rather than staying at the base
    # year's -- the failure that left the transformed table's COLUMN identity
    # 576 out while its rows stayed exact.
    got = float(grown.taxes_by_activity.sum()
                + grown.taxes_by_final_demand.sum())
    want, base = t["taxes"] * 1.02, t["taxes"]
    check("the projected pair carries the projected taxes, not the base's",
          abs(got - want) / want < 0.01 and abs(got - base) > abs(got - want),
          f"{got:,.0f} against a target of {want:,.0f} — {abs(got - want) / want:.2%} "
          f"away, inside the chapter's own 1 per cent stopping rule, and "
          f"closer to the target than to the base year's {base:,.0f}")

    # 4 -- and the whole chain: project, transform, and it still balances.
    iot = grown.to_iot("D")
    row = float(np.abs(iot.Z.sum(1) + iot.Y.sum(1) - iot.X).max())
    col = float(np.abs(iot.Z.sum(0) + iot.VA.sum(0) - iot.X).max())
    check("a projected pair transforms into a table that balances",
          max(row, col) / abs(iot.X.sum()) < 1e-9,
          f"row {row:.3g}, column {col:.3g} on an output of "
          f"{iot.X.sum():,.0f} — projected, then transformed, and both "
          f"identities still close")
    check("and it says it was projected, in its own lineage",
          "projected" in iot.table_id and "PROJECTED" in (grown.notes or ""),
          iot.table_id)

    # 5 -- SUT-RAS is wired, and it keeps its own target vocabulary.
    #
    # It was refused here until 2026-08-26 with a reasoned message about a
    # second target vocabulary being a real cost. The cost is real and the
    # method is wired anyway, because the back-test settled it: SUT-RAS beats
    # SUT-EURO on 61 of 61 Eurostat pairs. `run_projection_backtest.py`.
    print()
    try:
        s.project(**t, method="sut_ras")
        msg = ""
    except ValueError as exc:
        msg = str(exc)
    check("SUT-RAS will not take SUT-EURO's targets by mistake",
          "INDUSTRY OUTPUTS" in msg and "18.84" in msg,
          "value added and final use are not industry outputs and use column "
          "totals; a second method with the same argument names would be a "
          "silent alias")

    ras_u = (np.hstack([s.U_domestic[np.ix_(pi, ai)], s.Y_domestic[pi]]).sum(0)
             + np.hstack([s.U_imported[np.ix_(pi, ai)], s.Y_imported[pi]]).sum(0)
             + np.concatenate([s.taxes_by_activity[ai],
                               s.taxes_by_final_demand]))
    same_ras = s.project(taxes=t["taxes"], imports=t["imports"],
                         method="sut_ras", industry_output=s.g[ai],
                         use_column_totals=ras_u, year=s.year)
    dev_ras = float(np.abs(same_ras.U_domestic
                           - s.U_domestic[np.ix_(pi, ai)]).max())
    check("and projecting a pair onto its own totals returns that pair",
          dev_ras / abs(s.q[pi].sum()) < 1e-12,
          f"{dev_ras:.3g} on an output of {s.q[pi].sum():,.0f} — the same "
          f"cheapest-check-there-is that found SUT-EURO's price basis")
    check("its industry output hits the target exactly, which is its target",
          float(np.abs(same_ras.g - s.g[ai]).max()) < 1e-9,
          "SUT-EURO approaches value added iteratively; SUT-RAS is given "
          "industry output and imposes it")

    # 6 -- targets that do not match the table are refused.
    for bad, why in (({"gva": t["gva"][:-1]}, "value-added"),
                     ({"final_use": t["final_use"][:-1]}, "final-use")):
        args = dict(t)
        args.update(bad)
        try:
            s.project(**args)
            m = ""
        except ValueError as exc:
            m = str(exc)
        check(f"a projection onto the wrong number of {why} targets is refused",
              "is not a projection" in m, m.split(".")[0][:88])

    print()
    print("    Four orphans found, four accounted for: three wired up and one")
    print("    — the ONS supply-use loader, which has no make matrix to")
    print("    transform — correctly out of reach and now recorded as such.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
