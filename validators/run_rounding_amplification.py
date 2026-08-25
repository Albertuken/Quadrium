"""
`OQ-T-06`'s second-order claim, tested on four economies instead of one example.

The entry closes with an observation offered without evidence: "Model A's inverse
amplifies rounding most where the industry is smallest. That is a property of the
model, not of this example, and it is a practical argument for `M-026` (model D)
beyond the ones the Handbook gives: model D inverts nothing."

That was inferred from CORE_013's worked example, where every fourth-decimal
discrepancy sat in agriculture — output 40.45 of 1,238.41. One example, one
industry. Here it is put to four published supply-use systems.

METHOD
------
Perturb each supply table uniformly inside its **own published precision band**
— `±0.5·10^-d`, with `d` read off the values by `quadrium.precision` — then
re-run models A and D and measure how far each industry's column of the resulting
IOT moves. Twenty replications. Relative to industry output, because absolute
movement scales with size for arithmetic reasons and says nothing.

WHAT HOLDS, AND WHAT DOES NOT
------------------------------
**The claim holds in substance.** Averaged over the ten smallest industries
against the ten largest:

    country   model A small/large    model D small/large
    ES              23x                    4.3x
    AT              33x                    3.1x
    FR              13x                    3.7x
    NL              35x                    3.8x

Small industries are more sensitive under both models, and **model A amplifies
that by four to ten times more than model D does**, in every one of the four.
The practical argument for model D is confirmed on real data.

**The mechanism is not what the wording implies.** The correlation between
relative movement and log industry size is weak and its sign is not stable —
−0.16 to +0.28 across the eight cases. There is no smooth gradient in size; the
effect lives in the tails. "Amplifies most where the industry is smallest" is
right about the smallest industries and wrong as a description of a monotone
relationship, and this file records the distinction rather than letting the
convenient reading stand.

A MEASUREMENT ERROR OF MINE, RECORDED
--------------------------------------
The first run measured **absolute** deviation against size and found positive
correlations of 0.10–0.57, which looked like a refutation. It was not: absolute
movement grows with industry size for trivial reasons, so that test could only
ever have found what it found. The quantity the claim is about is relative, and
switching to it changed the answer entirely.

Run:
    python3 validators/run_rounding_amplification.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "eurostat"
REPLICATIONS = 20
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    from quadrium.eurostat import load_sut
    from quadrium.transformation import transform
    from quadrium.precision import printed_decimals

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    rng = np.random.default_rng(11)
    results = {}
    for geo in ("ES", "AT", "FR", "NL"):
        sup, use = (DATA / f"naio_10_cp15_{geo}_2022.json",
                    DATA / f"naio_10_cp16_{geo}_2022.json")
        if not (sup.exists() and use.exists()):
            continue
        s = load_sut(sup, use)
        # Squared on the codes present on both axes -- see run_model_axioms.
        # France publishes 89 products against 88 industries; `T98` is a
        # product and not an industry.
        codes = [c.replace("CPA_", "") for c in s.product_codes]
        both = set(codes) & set(s.activity_codes)
        pi = [i for i, c in enumerate(codes) if c in both]
        ai = [s.activity_codes.index(c) for c in codes if c in both]
        k = (s.q[pi] > 0) & (s.g[ai] > 0)
        pi = [pi[i] for i, keep in enumerate(k) if keep]
        ai = [ai[i] for i, keep in enumerate(k) if keep]
        V0, U = s.V[np.ix_(pi, ai)], s.U[np.ix_(pi, ai)]
        Y, W, g, q = s.Y[pi], s.W[:, ai], s.g[ai], s.q[pi]
        zero = np.zeros_like(U)
        d = printed_decimals(V0)
        band = 0.5 * 10.0 ** -d if d is not None else 0.0

        base = {m: transform(m, V0, U, zero, Y, np.zeros_like(Y), W, g, q).Sd
                for m in ("A", "D")}
        dev = {m: np.zeros(len(g)) for m in ("A", "D")}
        for _ in range(REPLICATIONS):
            Vp = V0 + rng.uniform(-band, band, V0.shape) * (V0 != 0)
            for m in ("A", "D"):
                Z = transform(m, Vp, U, zero, Y, np.zeros_like(Y), W, g,
                              q).Sd
                dev[m] += np.abs(Z - base[m]).sum(axis=0) / REPLICATIONS

        order = np.argsort(g)
        entry = {"d": d}
        for m in ("A", "D"):
            rel = dev[m] / g
            entry[m] = {
                "small": float(rel[order[:10]].mean()),
                "large": float(rel[order[-10:]].mean()),
                "corr": float(np.corrcoef(np.log(g),
                                          np.log(np.maximum(rel, 1e-18)))[0, 1]),
            }
            entry[m]["ratio"] = entry[m]["small"] / entry[m]["large"]
        results[geo] = entry

    if not results:
        print("no supply-use pair available")
        return 0

    print(f"    relative movement, 10 smallest industries vs 10 largest,")
    print(f"    perturbed inside each table's own precision band, "
          f"{REPLICATIONS} replications")
    print(f"    {'country':<9}{'dp':>4}{'A small/large':>16}"
          f"{'D small/large':>16}{'corr A':>9}{'corr D':>9}")
    for geo, e in results.items():
        print(f"    {geo:<9}{e['d']:>4}{e['A']['ratio']:>15.0f}x"
              f"{e['D']['ratio']:>15.1f}x{e['A']['corr']:>9.2f}"
              f"{e['D']['corr']:>9.2f}")
    print()

    check("small industries move more, relative to size, under both models",
          all(e[m]["ratio"] > 2 for e in results.values() for m in ("A", "D")),
          "the smallest decile against the largest, in every country and both "
          "models")
    check("and model A amplifies it several times more than model D",
          all(e["A"]["ratio"] > 3 * e["D"]["ratio"] for e in results.values()),
          "ratios of " + ", ".join(
              f"{g} {e['A']['ratio'] / e['D']['ratio']:.0f}x"
              for g, e in results.items())
          + " — the practical argument for model D, confirmed on four "
            "economies rather than one worked example")

    corrs = [e[m]["corr"] for e in results.values() for m in ("A", "D")]
    check("but there is NO smooth gradient in size, and the entry implies one",
          min(corrs) < 0 < max(corrs) and max(abs(c) for c in corrs) < 0.5,
          f"correlation of relative movement with log size runs "
          f"{min(corrs):.2f} to {max(corrs):.2f} across the eight cases — the "
          f"effect lives in the tails, not along a gradient. 'Amplifies most "
          f"where the industry is smallest' is right about the smallest and "
          f"wrong as a description of the relationship")

    print()
    print("    A measurement error of mine, kept here rather than tidied away:")
    print("    the first run measured ABSOLUTE deviation against size, found")
    print("    correlations of 0.10-0.57, and looked like a refutation. It was")
    print("    not — absolute movement grows with industry size for trivial")
    print("    reasons, so that test could only ever find what it found. The")
    print("    claim is about relative movement, and switching changed the")
    print("    answer entirely.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
