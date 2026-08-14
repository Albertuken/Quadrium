"""
The engine's own operation, specified in a handbook that sat unread.

CORE_014 and CORE_015 were the last two extracted sources and were nearly set
aside on the reasoning that "extended tables are something this project does not
compile". **That was wrong.** CORE_014 p. 69 states the operation:

    "The key idea in the approach described here is to construct ESUTs by
    disaggregating columns and rows of the regular SUTs, using as much as
    possible data to capture the heterogeneity between different types of
    enterprises."

Disaggregating the columns and rows of a regular SUT is this engine. The
dimension differs — enterprise type rather than subsector — the operation does
not. An "extended" table is a disaggregated one, and the word hid it. Recorded
because dismissing a source on its title is the cheapest mistake available.

WHAT THE AUDIT BELOW SHOWS
---------------------------
Five of CORE_014's six steps have a counterpart in `split_sector`. **Step 4 does
not** — deriving extended valuation tables and a use table at basic prices — and
that is the same hole `M-065` found from the H-Approach an hour earlier: the
engine has no valuation dimension and takes whatever basis the published table
is in. Two independent sources, one gap.

THREE PLACES THE DESIGN IS CORROBORATED
-----------------------------------------
* **Four keys, one per block.** CORE_015 p. 93 requires "share in gross output",
  "share in value added", "share in imports" and "share in exports", each by
  industry. That is `keys_by_block`. `M-053` had CORE_031 requiring inputs and
  outputs to take different weights; this is the second source and the first to
  enumerate the blocks.
* **Weights sum to one.** CORE_015 p. 93: the shares "must add up to 100%".
  `AllocationKey.normalize()` has enforced it since v0.1 and now has a citation.
* **Imports get their own key and domestic is the residual.** CORE_014 p. 81
  disaggregates the import use table first, "then derive the extended domestic
  use table by subtracting the extended import use table". `M-064`, written an
  hour before, had recorded exactly this as `NOT SPECIFIED` after CORE_020
  refused proportional allocation without offering a replacement.

AND A SOURCED FALLBACK
-----------------------
CORE_015 p. 94: where import and export shares are unavailable for services —
"The main hurdle is expected to be imports and exports of services" —
practitioners use the goods share as a proxy for the total. `ESTIMATED`, and no
longer an invention.

Run:
    python3 validators/run_topdown_procedure.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

EXTRACTED = ROOT / "library" / "extracted"
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    c14 = EXTRACTED / "CORE_014_OECD_EU2025_CH03_Compiling_Extended_SUTs.txt"
    c15 = EXTRACTED / "CORE_015_OECD_EU2025_CH04_Data_Scarce_ESUT_EIOT.txt"
    if not (c14.exists() and c15.exists()):
        print("extraction(s) absent")
        return 0
    t14 = re.sub(r"\s+", " ", c14.read_text())
    t15 = re.sub(r"\s+", " ", c15.read_text())

    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)

    check("CORE_014 describes this engine's operation, not a different one",
          "disaggregating columns and rows of the regular SUTs" in t14,
          "p. 69 — the dimension differs, the operation does not")

    # ---- the six steps, against the engine --------------------------------
    from quadrium import disaggregation as D
    from quadrium.models import Scenario, SplitSpec
    src = (ROOT / "src" / "quadrium" / "disaggregation.py").read_text()
    steps = [
        ("1 choosing what to disaggregate", "SplitSpec", True),
        ("2 industry output and total intermediate use", "w_out", True),
        ("3 the product distribution of output and use", "_column_shares", True),
        ("4 extended valuation tables, basic prices", None, False),
        ("5 use of imports vs domestic production", "va_row", True),
        ("6 the use of domestic output", "w_row", True),
    ]
    print()
    print("    CORE_014's six steps against `split_sector`:")
    covered = 0
    for label, token, expected in steps:
        present = bool(token and token in src)
        covered += present
        print(f"      {label:<46} {'yes' if present else 'NO'}")
    check("five of the six steps have a counterpart in the engine",
          covered == 5,
          f"{covered} of 6")
    check("and the one that does not is the valuation step",
          "extended valuation" not in src.lower(),
          "step 4 — the same gap M-065 found from the H-Approach. The engine "
          "takes whatever price basis the published table is in; two "
          "independent sources now name the absence")

    # ---- the three corroborations -----------------------------------------
    print()
    for phrase, what, where in (
            ("share in gross output by industry by type of enterprise",
             "four keys, one per block — the engine's keys_by_block",
             "CORE_015 p. 93"),
            ("must add up to 100%",
             "weights sum to one — AllocationKey.normalize()", "CORE_015 p. 93"),
            ("then derive the extended domestic use table by subtracting",
             "imports get their own key, domestic is the residual",
             "CORE_014 p. 81")):
        body = t15 if "CORE_015" in where else t14
        check(f"{where}: {what}", phrase in body, f'"{phrase}"')

    check("CORE_014 p. 81 closes what M-064 recorded as NOT SPECIFIED an hour "
          "earlier",
          "then derive the extended domestic use table by subtracting" in t14,
          "CORE_020 p. 195 refused proportional allocation of imports and "
          "offered no replacement; this is the replacement, and it is an "
          "ordering rather than a formula")

    check("and CORE_015 names a fallback for the key hardest to obtain",
          "The main hurdle is expected to be imports and exports of services"
          in t15,
          "p. 94 — the goods share stands in for the total share. ESTIMATED, "
          "and it belongs in the assumption ledger, but it is sourced")

    # the engine really does take a key per block
    fields = set(Scenario.__dataclass_fields__) | set(SplitSpec.__dataclass_fields__)
    check("the engine accepts a key per block, as CORE_015 requires",
          "keys_by_block" in fields,
          "Scenario.keys_by_block and SplitSpec.keys_by_block")

    print()
    print("    Still NOT SPECIFIED by either chapter: the internal block — how")
    print("    the new subsectors trade with each other. CORE_031 and M-053")
    print("    remain the only treatment, and OQ-S-04 the only measurement.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
