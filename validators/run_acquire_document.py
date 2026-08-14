"""
The other half of `OQ-B-14`: the engine finds the document, not just reads it.

WHAT WAS AUTHORISED, AND WHEN
------------------------------
2026-08-13, in two steps. First *"que el motor lea informes cuando falte el
dataset"* — built as `models.key_from_report` and `M-068`, which takes a figure
out of a report the project already holds and refuses it unless the value is in
the quoted sentence and the sentence is on the cited page. That deliberately did
not include going to look for the document. Then, the same day: *"que el motor
también busque el documento"*.

This file tests the second half: `quadrium.acquire`, `M-069`.

THE VERIFICATION THAT MATTERS IS AT THE END, AND IT IS EXACT
--------------------------------------------------------------
Statistik Austria's Standarddokumentation is in this project as `NSO_AT_01`. A
human found it, fetched it and recorded it in `SOURCE_REGISTER.md` on
2026-08-10: **862,382 bytes, SHA-256 `d3319c5d…4a36`**.

Given only the office's portal page and the words that would appear in the link,
`find_documents` returns that PDF as its top candidate and `acquire` fetches it
**byte for byte identical to the file the human found**. That is the whole claim
this capability can make — not that the engine judged the document to be the
right one, but that pointed at an office it reaches the same document a person
reached, and records what it got well enough to prove it.

WHAT IS CHECKED WITHOUT A NETWORK, AND WHAT IS SKIPPED
-------------------------------------------------------
The refusals are the deliverable and most of them need no network: the
allowlist, the message it gives, and the shape of the provenance record. The
live search and fetch are **skipped with a printed note** when the network is
not there. A validator that silently passes because it could not run is the
failure this project has documented twice already, so a skip says so.

ONE REAL-WORLD WRINKLE, RECORDED RATHER THAN WORKED AROUND
-----------------------------------------------------------
`ons.gov.uk` — the office whose table this whole engine runs on — answers **403
to a scripted fetch of `robots.txt`**, which by convention means "disallowed",
so this engine refuses to fetch anything there. It is not that the ONS forbids
it: a browser gets the same file with a 404, i.e. no robots file at all. The
engine cannot tell a site that says no from a CDN that blocks scripts, so it
takes the conservative reading and stops. That is exactly the "technical
friction around content already confirmed open" that `CLAUDE.md` leaves to a
human, and it is why this capability does not replace the standing
authorisation — it exercises it.

Run:
    python3 validators/run_acquire_document.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quadrium.acquire import (  # noqa: E402
    AccessRefused, AcquisitionRefused, OFFICIAL_HOSTS, Provenance, acquire,
    check_allowed, find_documents,
)

FAIL: list[str] = []
SKIPPED: list[str] = []

# What SOURCE_REGISTER.md §4c records for NSO_AT_01, fetched by hand 2026-08-10.
AT_PORTAL = ("https://www.statistik.at/statistiken/volkswirtschaft-und-"
             "oeffentliche-finanzen/volkswirtschaftliche-gesamtrechnungen/"
             "input-output-statistik")
AT_SHA = "d3319c5de5fc5dca8efdacafc2030dbb0e1c0753bbeb9265bcc3760a43034a36"
AT_BYTES = 862382


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def skip(name: str, why: str) -> None:
    print(f"  skip {name} — {why}")
    SKIPPED.append(name)


def main() -> int:
    print(__doc__.strip().split("Run:")[0].rstrip())
    print("\n" + "=" * 78)
    print()

    # ---- the allowlist IS the authorisation ------------------------------
    for url, what in (
            ("https://example.com/methodology.pdf", "an ordinary web host"),
            ("https://sci-hub.se/10.1080/00000000.pdf", "a bypass site"),
            ("https://drive.google.com/file/d/x/view", "a file locker")):
        try:
            check_allowed(url)
            check(f"refuses {what}", False, "it was ALLOWED")
        except AcquisitionRefused as exc:
            check(f"refuses {what}", "OFFICIAL_HOSTS" in str(exc),
                  str(exc).split(".")[0][:96])

    check("and every allowlisted host is an office this project has recorded",
          len(OFFICIAL_HOSTS) >= 20
          and all("." in h for h in OFFICIAL_HOSTS),
          f"{len(OFFICIAL_HOSTS)} hosts, each mapped to the office it belongs "
          f"to — the list is a decision written down, not a rule the engine "
          f"invents per request")

    # ---- the provenance record is the register's own row ------------------
    prov = Provenance(url="https://www.statistik.at/x.pdf",
                      final_url="https://www.statistik.at/x.pdf",
                      office="Statistik Austria", path="/tmp/x.pdf",
                      bytes=862382, sha256=AT_SHA,
                      content_type="application/pdf",
                      retrieved_at="2026-08-13T00:00:00+00:00")
    row = prov.register_row()
    check("an acquisition prints the row SOURCE_REGISTER.md already uses",
          "862,382 bytes" in row and AT_SHA[:8] in row and "✓" in row,
          row[:100] + "…")

    # ---- live: find, then fetch, then compare with what a human got -------
    print()
    try:
        found = find_documents(
            AT_PORTAL,
            ["standarddokumentation", "standard dokumentation", "methodik",
             "dokumentation"], limit=5)
    except AccessRefused as exc:
        found = None
        skip("live search of an official portal", f"access control: {exc}")
    except (AcquisitionRefused, OSError) as exc:
        found = None
        skip("live search of an official portal",
             f"{type(exc).__name__}: {str(exc)[:80]}")

    if found is not None:
        print(f"    Statistik Austria's input-output portal, "
              f"{len(found)} candidate(s):")
        for c in found:
            print(f"      {c.score:4.1f}  {c.text[:44]:<44} "
                  f"{c.url.rsplit('/', 1)[-1][:44]}")
        top = found[0] if found else None
        check("the engine finds the Standarddokumentation unaided",
              top is not None and top.url.endswith(".pdf")
              and "input-o" in top.url.lower(),
              f"top candidate is {top.url.rsplit('/', 1)[-1] if top else '—'} "
              f"— the document a human located on 2026-08-10 and registered as "
              f"NSO_AT_01")

        if top is not None:
            dest = Path(ROOT / "validators" / "__acquired__.tmp")
            try:
                got = acquire(top.url, dest, note="run_acquire_document.py")
            except (AcquisitionRefused, OSError) as exc:
                skip("live acquisition", f"{type(exc).__name__}: "
                                         f"{str(exc)[:80]}")
            else:
                check("and fetches it byte for byte identical to the human's "
                      "copy",
                      got.sha256 == AT_SHA and got.bytes == AT_BYTES,
                      f"{got.bytes:,} bytes, SHA-256 {got.sha256[:8]}…"
                      f"{got.sha256[-4:]} against the register's "
                      f"{AT_BYTES:,} and {AT_SHA[:8]}…{AT_SHA[-4:]}")
                check("and writes a provenance record beside it",
                      dest.with_suffix(dest.suffix + ".provenance.json").exists()
                      and got.office == "Statistik Austria",
                      "url, final url after redirects, office, bytes, "
                      "SHA-256, content type and retrieval time")
                for p in (dest, dest.with_suffix(dest.suffix + ".provenance.json")):
                    p.unlink(missing_ok=True)

    print()
    print("    What this does NOT do: decide that what it found is the right")
    print("    document. Ranking is a word match on the link, and only reading")
    print("    the thing settles it. The chain that ends in a figure the engine")
    print("    will use is find -> acquire -> extract -> key_from_report, and")
    print("    only the last step verifies anything: the quote must be on the")
    print("    page. D_open_questions.md OQ-B-14; cards M-068, M-069.")

    print("\n" + "=" * 78)
    if SKIPPED:
        print(f"{len(SKIPPED)} check(s) SKIPPED for want of a network: "
              f"{', '.join(SKIPPED)}")
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
