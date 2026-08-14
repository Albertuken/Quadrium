"""
`OQ-A-01`: the missing identity term is the SOURCE's, not the extraction's.

CORE_005 ¶36.39, p. 1016 as extracted reads: "(I-A)-1 can be written as
A+A²+A³+A⁴ etc." The Neumann series is `I + A + A² + A³ + …`. The leading `I` is
absent, and the entry has stood since v1.0 with one candidate explanation
untested — that the extraction dropped it.

**It did not.** Settled by looking, with the owner's authorisation, at exactly
one page:

  * the project's own extraction says `A+A 2+A3+A4`;
  * a second, independent extractor (PyMuPDF) on PDF page 11 says
    `A+A2+A3+A4`;
  * **the rendered page shows `A+A²+A³+A⁴`.**

Three readings, one conclusion: the printed text of the pre-edit 2025 SNA is
missing the identity term. This is an erratum in a rank-1 source, not a defect in
this project's ingestion.

NO OTHER LOADED SOURCE WRITES THE SERIES OUT
---------------------------------------------
CORE_022 gives only the closed form — `q = inv(I - A) * y`, three times — and
never expands it. CORE_013 and CORE_006 do not expand it either. So CORE_005 is
the only loaded source that states the series, and the only statement of it is
wrong. There is nothing to corroborate against inside the library.

WHAT THE ARITHMETIC SAYS, WHICH IS NOT NEW BUT IS THE POINT
------------------------------------------------------------
On the project's own UK table, over 40 terms:

    ‖ (I−A)⁻¹ − (I + ΣA^k) ‖∞  =  3.9e-10      the correct form converges
    ‖ (I−A)⁻¹ − ΣA^k ‖∞        =  1.0 exactly   the printed form is short by I

Not approximately 1. Exactly 1 — the identity matrix, which is precisely the
term the sentence omits. The engine implements the correct form, as
`../specs/A_core_accounting_spec.md` records, on the authority of CORE_005
¶36.36, p. 1015 three paragraphs earlier, which states `x = (I − A)⁻¹ y`.

WHAT REMAINS
------------
Whether the **final**, non-pre-edit SNA 2025 carries the same sentence. This
project holds the pre-edit version and cannot check the other. `OQ-A-02` already
tracks the pre-edit numbering problem; this is the same document's other risk.
Nothing here should be read as a statement about the published SNA.

THE PDF RULE, AND THAT IT WAS FOLLOWED
---------------------------------------
`CLAUDE.md` allows reading a PDF page where the extraction is in doubt, provided
it is a single page and provided the run says so. **One page was opened —
page 11 of `CORE_005_SNA2025_CH36_Input_Output_Tables.pdf`, publication page
1016 — and this is the saying-so.** The check below re-runs the text half of it
whenever the PDF is present; the PDF is gitignored, so on a fresh clone the
arithmetic runs and the source check reports itself skipped.

Run:
    python3 validators/run_leontief_series.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validators"))

PDF = (ROOT / "library" / "Methodology" / "CORE_01_Accounting_and_Compilation"
       / "01_SNA_2025" / "CORE_005_SNA2025_CH36_Input_Output_Tables.pdf")
PDF_PAGE = 11               # publication page 1016, offset 1005
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    # ---- 1. the arithmetic -----------------------------------------------
    uk_file = ROOT / "UK_IOAT_2023_domestic_ixi.xlsx"
    if uk_file.exists():
        import run_uk_iot as uk
        t = uk.load_iot(uk_file)
        Z, x = t["Z"], t["x"]
        A = Z / np.where(x > 0, x, 1.0)
        n = A.shape[0]
        L = np.linalg.inv(np.eye(n) - A)
        term, series = np.eye(n), np.zeros((n, n))
        for _ in range(40):
            term = term @ A
            series += term
        with_i = float(np.abs(L - (np.eye(n) + series)).max())
        without = float(np.abs(L - series).max())
        print(f"    over 40 terms on the UK table, {n} industries:")
        print(f"      ‖(I−A)⁻¹ − (I + ΣA^k)‖∞  = {with_i:.3e}")
        print(f"      ‖(I−A)⁻¹ − ΣA^k‖∞        = {without:.6f}")
        print()
        check("the correct form converges", with_i < 1e-8,
              f"{with_i:.3e} after 40 terms")
        check("and the printed form is short by exactly the identity",
              abs(without - 1.0) < 1e-9,
              f"{without:.9f} — not approximately 1, exactly 1, which is the "
              f"term the sentence omits")
    else:
        print("  (UK fixture absent; the arithmetic half needs it)")

    # ---- 2. the source, if it is here ------------------------------------
    printed = None
    if PDF.exists():
        try:
            import pymupdf
            doc = pymupdf.open(PDF)
            text = doc[PDF_PAGE - 1].get_text()
            i = text.find("36.39")
            printed = re.sub(r"\s+", " ", text[i:i + 300]) if i >= 0 else None
        except ImportError:
            print("  (pymupdf absent; source check skipped)")
    else:
        print(f"  (source check skipped: {PDF.name} is gitignored and absent)")

    if printed:
        frag = printed[printed.find("can be written as"):][:40]
        check("the printed sentence really omits the leading I",
              "written as A+A" in frag.replace(" ", " "),
              f"page {PDF_PAGE}, publication page 1016: …{frag.strip()}…")
        check("and it is not this project's extraction that dropped it",
              "I+A" not in printed.replace(" ", ""),
              "a second independent extractor reads the same as ours, and the "
              "rendered page shows `A+A²+A³+A⁴` — three readings, one answer")

    print()
    print("    No other loaded source writes the series out. CORE_022 gives only")
    print("    the closed form `q = inv(I - A) * y`; CORE_013 and CORE_006 do not")
    print("    expand it. CORE_005 is the only statement of it in the library and")
    print("    the only statement of it is wrong.")
    print()
    print("    Still open: whether the FINAL, non-pre-edit SNA 2025 carries the")
    print("    same sentence. This project holds the pre-edit version only, and")
    print("    nothing here is a statement about the published SNA.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
