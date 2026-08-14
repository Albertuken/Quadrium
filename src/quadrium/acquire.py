"""
Finding and acquiring a source document, under the project's own rules.

WHY THIS EXISTS
----------------
`models.key_from_report` (v1.58, `M-068`) let the engine take a figure out of a
report the project already held. The owner then asked for the other half on
2026-08-13: **let the engine find the document too.**

That is a larger act than reading one, and the difference is worth naming.
Reading a held document is checkable by the thing doing it — the quote either is
on the page or it is not. Going out to look for a document is not: it touches
the network, it can be pointed at anything, and its failure mode is bringing
back a plausible file from the wrong place and citing it. So the capability is
built as a **narrow, allowlisted, fully recorded** operation rather than a
search engine.

THE FOUR RULES, AND EACH IS A REFUSAL RATHER THAN A PREFERENCE
---------------------------------------------------------------
1. **Official hosts only.** `CLAUDE.md`'s standing authorisation pre-approves
   downloads from official statistical sources and legitimately open-access
   repositories, and nothing else. `OFFICIAL_HOSTS` is that authorisation
   written down: every host in it is one this project has already recorded in
   `library/SOURCE_REGISTER.md`. Anything else is refused — including a
   redirect that leaves the list, which is checked after following it, because
   the first URL is not the one you end up fetching.
2. **One hop.** `find_documents` reads a portal page the caller names and
   returns the document links on it. It does not crawl, follow pagination, or
   fetch what it finds. Discovery and acquisition are separate calls because
   they are separate decisions.
3. **Access control is a stop sign, not an obstacle.** 401, 402, 403 and any
   login or subscription marker raise `AccessRefused` and the function does not
   retry with different headers, a different agent, or a proxy. The standing
   authorisation covers technical friction around content already confirmed
   open; it does not cover getting past a paywall, and an engine cannot tell
   those apart. A human must.
4. **Nothing arrives without provenance.** `acquire` writes the URL, the final
   URL after redirects, the byte count, the content type, the SHA-256 and the
   retrieval time beside the file, and returns them, in the format
   `SOURCE_REGISTER.md` already uses. A document with no provenance record is
   indistinguishable from one someone put there by hand.

WHAT THIS DELIBERATELY DOES NOT DO
------------------------------------
It does not decide that what it found is the right document. `find_documents`
ranks candidates by how well their link text matches what was asked for, and
that is a string match, not a judgement. The chain that ends in a figure the
engine will use runs **find -> acquire -> extract -> `key_from_report`**, and
only the last step verifies anything: the quote must be on the page. Everything
before it is logistics.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

# Every host this project has recorded a source from, and the office it belongs
# to. Built from `library/SOURCE_REGISTER.md` — if a host is not here it is not
# because it is bad, but because nobody has recorded using it, and adding one is
# a decision a human takes and writes down.
OFFICIAL_HOSTS: dict[str, str] = {
    "unstats.un.org": "United Nations Statistics Division",
    "ec.europa.eu": "Eurostat / European Commission",
    "www.oecd.org": "OECD",
    "www.imf.org": "IMF",
    "www.ine.es": "INE (Spain)",
    "servicios.ine.es": "INE (Spain)",
    "www.ons.gov.uk": "ONS (United Kingdom)",
    "www.statistik.at": "Statistik Austria",
    "www.destatis.de": "Destatis (Germany)",
    "www.cbs.nl": "CBS (Netherlands)",
    "www.insee.fr": "INSEE (France)",
    "www.istat.it": "ISTAT (Italy)",
    "www.stat.fi": "Tilastokeskus (Finland)",
    "www.dst.dk": "DST (Denmark)",
    "www.cso.ie": "CSO (Ireland)",
    "stat.gov.pl": "GUS (Poland)",
    "www.scb.se": "SCB (Sweden)",
    "www.stat.si": "SURS (Slovenia)",
    "www.plan.be": "Federal Planning Bureau (Belgium)",
    "www23.statcan.gc.ca": "Statistics Canada",
    "www.abs.gov.au": "Australian Bureau of Statistics",
    "www.gov.wales": "Welsh Government",
    "www.gov.scot": "Scottish Government",
    "www.stats.gov.sa": "GASTAT (Saudi Arabia)",
    "www.ine.pt": "INE (Portugal)",
}

# What a document looks like. A portal page links to a hundred things; these are
# the ones worth returning.
_DOC_SUFFIX = (".pdf", ".xlsx", ".xls", ".csv", ".ods", ".docx")
_DOC_TYPES = ("application/pdf", "text/html", "application/vnd.openxmlformats",
              "application/vnd.ms-excel", "text/csv",
              "application/vnd.oasis.opendocument")

# PROJECT CHOICE. A methodology document runs to a few megabytes; the whole
# pre-edit SNA is 14 MB and is the largest thing this project has fetched. The
# cap exists so a mis-aimed link cannot pull down a database dump.
MAX_BYTES = 64 * 1024 * 1024
TIMEOUT = 60

_UA = ("IO-Model-Foundry/1.0 (research; contact via repository owner) "
       "python-urllib")

_PAYWALL = re.compile(
    r"\b(sign in to (?:read|continue|download)|subscribe to (?:read|download)|"
    r"purchase (?:this )?(?:article|document)|institutional (?:login|access)|"
    r"add to cart)\b", re.I)


class AcquisitionRefused(ValueError):
    """The engine will not fetch this, and the message says which rule."""


class AccessRefused(AcquisitionRefused):
    """The document is behind access control. A human decides what to do."""


@dataclass
class Candidate:
    """A link on a portal page that looks like a document."""
    url: str
    text: str
    office: str
    score: float = 0.0


@dataclass
class Provenance:
    """What `SOURCE_REGISTER.md` needs in order to record an acquisition."""
    url: str
    final_url: str
    office: str
    path: str
    bytes: int
    sha256: str
    content_type: str
    retrieved_at: str
    note: Optional[str] = None

    def register_row(self) -> str:
        """The one-line form this project's register uses."""
        return (f"| `{Path(self.path).name}` | {self.office} | {self.url} — "
                f"✓ {self.bytes:,} bytes, SHA-256 `{self.sha256[:8]}…"
                f"{self.sha256[-6:]}`, retrieved {self.retrieved_at[:10]} |")


def host_of(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def check_allowed(url: str) -> str:
    """Return the office, or refuse. The allowlist IS the authorisation."""
    host = host_of(url)
    if host not in OFFICIAL_HOSTS:
        raise AcquisitionRefused(
            f"{host or url!r} is not in OFFICIAL_HOSTS. CLAUDE.md's standing "
            f"authorisation covers official statistical sources and "
            f"legitimately open-access repositories; this engine treats that "
            f"as an allowlist rather than a judgement it makes at run time. "
            f"Add the host deliberately, and record why.")
    return OFFICIAL_HOSTS[host]


def _robots_allows(url: str) -> bool:
    """Ask the site whether an automated client may fetch this.

    A statistics portal is public and this is one request, but an engine that
    fetches on its own account should still read the sign on the door. A
    robots.txt that cannot be fetched is treated as permission — that is the
    convention, and refusing on a missing file would block most sites.
    """
    parts = urllib.parse.urlsplit(url)
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"{parts.scheme}://{parts.netloc}/robots.txt")
    try:
        rp.read()
    except Exception:
        return True
    try:
        return rp.can_fetch(_UA, url)
    except Exception:
        return True


def _open(url: str, method: str = "GET"):
    req = urllib.request.Request(url, method=method,
                                 headers={"User-Agent": _UA,
                                          "Accept": "*/*"})
    try:
        return urllib.request.urlopen(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 402, 403, 407):
            raise AccessRefused(
                f"{url} answered HTTP {exc.code}. That is access control, and "
                f"this engine stops at it: the standing authorisation covers "
                f"technical friction around content already confirmed open, "
                f"not getting past a paywall or a login, and nothing here can "
                f"tell those apart. A human decides — see CLAUDE.md.") from exc
        raise AcquisitionRefused(f"{url} answered HTTP {exc.code}.") from exc


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: Optional[str] = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href, self._text = None, []


def find_documents(portal_url: str, want: list[str], limit: int = 10
                   ) -> list[Candidate]:
    """Document links on ONE page of an allowlisted official site.

    `want` is the words that would appear in the link — "methodology",
    "metodolog", "quality report", "Standarddokumentation". Scoring is a word
    match on the link text and the URL, and it is not a judgement about whether
    the document is the right one. It cannot be: only reading it settles that.

    One page, no crawling. If the portal paginates its publications, name the
    page you mean.
    """
    office = check_allowed(portal_url)
    if not _robots_allows(portal_url):
        raise AcquisitionRefused(
            f"{portal_url} is disallowed for automated clients by the site's "
            f"own robots.txt. Fetch it yourself if you need it.")
    with _open(portal_url) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        html = resp.read(MAX_BYTES).decode(charset, errors="replace")

    parser = _Links()
    parser.feed(html)
    terms = [w.lower() for w in want]
    out: dict[str, Candidate] = {}
    for href, text in parser.links:
        url = urllib.parse.urljoin(portal_url, href)
        if host_of(url) not in OFFICIAL_HOSTS:
            continue                      # a link off the allowlist is not a
        low_url = url.lower()             # candidate, however good it looks
        low_text = text.lower()
        looks_like_doc = low_url.endswith(_DOC_SUFFIX)
        score = sum(2.0 for t in terms if t in low_text)
        score += sum(1.0 for t in terms if t in low_url)
        if score <= 0:
            continue
        if looks_like_doc:
            score += 1.0
        prev = out.get(url)
        if prev is None or score > prev.score:
            out[url] = Candidate(url=url, text=text or "(no link text)",
                                 office=office, score=score)
    return sorted(out.values(), key=lambda c: -c.score)[:limit]


def acquire(url: str, dest: Path | str, note: Optional[str] = None
            ) -> Provenance:
    """Fetch one document from an allowlisted host, and record what arrived.

    Writes the file and a `<name>.provenance.json` beside it. Returns the record
    so the caller can put it in `SOURCE_REGISTER.md`, which is where this
    project keeps acquisitions and which no code updates automatically —
    deliberately, because the register carries judgements as well as facts.
    """
    office = check_allowed(url)
    if not _robots_allows(url):
        raise AcquisitionRefused(
            f"{url} is disallowed for automated clients by robots.txt.")
    dest = Path(dest)
    with _open(url) as resp:
        final_url = resp.geturl()
        # The URL you asked for is not the URL you got. A redirect off the
        # allowlist is the one way a single hop can leave it.
        final_office = check_allowed(final_url)
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
        if ctype and not ctype.startswith(_DOC_TYPES):
            raise AcquisitionRefused(
                f"{final_url} served `{ctype}`, which is not a document type "
                f"this engine acquires ({', '.join(_DOC_TYPES)}).")
        body = resp.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise AcquisitionRefused(
            f"{final_url} is larger than the {MAX_BYTES:,}-byte cap. Fetch it "
            f"deliberately if it is really wanted.")
    if ctype.startswith("text/html"):
        text = body.decode("utf-8", errors="replace")
        hit = _PAYWALL.search(text)
        if hit:
            raise AccessRefused(
                f"{final_url} looks like a paywall or login page — it says "
                f"{hit.group(0)!r}. Refusing rather than saving it: a login "
                f"page saved under a document's name is worse than no "
                f"document, because it will be cited.")

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    prov = Provenance(
        url=url, final_url=final_url, office=final_office, path=str(dest),
        bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
        content_type=ctype or "(unstated)",
        retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        note=note)
    dest.with_suffix(dest.suffix + ".provenance.json").write_text(
        json.dumps(asdict(prov), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    return prov
