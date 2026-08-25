"""
What tables you can reach, and whether any of them has the sector you want.

THE QUESTION THIS ANSWERS
--------------------------
An analyst does not begin with a table. They begin with "I want to look at
restaurants", and then spend an afternoon opening workbooks to find out that
their country's published table does not separate restaurants from hotels.
That afternoon is what this module removes.

`scan()` reads every table on disk and records which sector codes CARRY DATA.
`find()` takes a target code and reports, per source, one of three verdicts:

    SEPARATE   the code is a sector of its own — load and use it
    INSIDE     it exists only within a coarser code — that coarser code is
               what you would split, and it is named
    ABSENT     no code in this source covers it at all

`advise()` ranks those and says which source to use, or — when nothing
separates the target — which aggregate to divide, which is the case this whole
engine exists for.

LISTED IS NOT AVAILABLE, AND THIS IS THE WHOLE REASON THE MODULE READS VALUES
-----------------------------------------------------------------------------
Eurostat's dimension metadata lists the entire CPA hierarchy whether or not a
country publishes at that level. Spain's symmetric table for 2022 lists
`CPA_I55` (accommodation) and `CPA_I56` (food and beverage services) among 121
product categories — and **neither carries a single value**. Only the aggregate
`CPA_I` does. A catalogue built from the labels would tell a Spanish analyst
that accommodation is available separately; it is not, in that table, and the
answer they need is the opposite one: `I` is the sector to split.

So every entry here is built from the codes that appear in the data, and the
hierarchy is read from the notation by `eurostat._covers`, which already knows
that `C10-12` contains `C11` and that a section letter contains its divisions
and not its accounting rows.

WHAT THIS DOES NOT AND CANNOT TELL YOU
----------------------------------------
Whether two of these sources are comparable. Eurostat harmonises the format —
the same dataset codes, the same classification, the same envelope for every
member state — and neither harmonises nor records the method. The ONS uses a
hybrid of two transformation models chosen per cell by whether it goes
negative; the INE a hybrid chosen per secondary production; Statistik Austria
product technology with manual correction above 15 million euros. That was
measured, not assumed: the harmonised metadata files for all thirteen countries
that publish one contain zero occurrences of "technology assumption"
(`SOURCE_REGISTER.md` §6b). Two entries below with the same classification and
the same number of products were not made the same way, and this module ranks
by resolution, which is the only thing it can see.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .eurostat import (DATASETS, _bare, _covers, _finest_tiling,
                       _rounding_tol)

# Which `table_kind` a configuration would need, per publisher.
# The dimension names Eurostat uses for a classification axis, in the order
# they are preferred when a response carries more than one.
_SECTOR_DIMS = ("prd_use", "prd_ava", "prd_amo", "ind_use", "ind_ava",
                "ind_impv", "prod_na", "cpa2_1", "nace_r2")


@dataclass
class Source:
    """One loadable table, and the sectors it actually distinguishes."""
    source_id: str
    publisher: str
    geo: str
    year: int
    dataset: str
    path: Path
    table_kind: str
    classification: str
    # "table" -- an IO or supply-use table you can load and split.
    # "proxy" -- a measurement of sectors, usable as an allocation key. Not
    #            loadable as a table, and catalogued because the answer to
    #            "no source separates your sector" is incomplete without one.
    kind: str = "table"
    codes: list[str] = field(default_factory=list)
    labels: dict = field(default_factory=dict)
    # Codes the PUBLISHER publishes that this entry's tiling does not carry.
    #
    # It was the point of this field until 2026-08-25: the loaders kept the
    # COARSER tiling, so France's supply table arrived at 65 products when 89
    # were published, and an analyst wanting food manufacturing would have been
    # told to estimate what their own office had measured. The loaders now keep
    # the finest tiling whose components verifiably sum to their parent, so for
    # a table this is normally empty.
    #
    # It stays populated here because the catalogue reads the file directly and
    # can still see a level the loader declined — where the components do NOT
    # sum to their parent, the parent is kept and the partial set is dropped,
    # and an analyst asking for one of those codes deserves to be told that it
    # exists and why it is not loadable rather than told to split.
    finer: list[str] = field(default_factory=list)
    # Every country in the response. A table is one country; a proxy cube is
    # often eleven, and taking the first of them -- as this did until the SBS
    # file was catalogued as Belgian -- files a source under a country that
    # merely sorts first.
    geos: list[str] = field(default_factory=list)
    note: str = ""

    @property
    def resolution(self) -> int:
        return len(self.codes)

    def config_lines(self) -> list[str]:
        """The `project` rows a workbook would need to load this."""
        if self.table_kind == "eurostat":
            friendly = next((k for k, v in DATASETS.items()
                             if v == self.dataset), self.dataset)
            return ["table_kind       eurostat",
                    f"eurostat_geo     {self.geo}",
                    f"eurostat_year    {self.year}",
                    f"eurostat_dataset {friendly}"]
        return [f"table_kind      {self.table_kind}",
                f"table_path      {self.path}"]


def _eurostat_source(path: Path) -> Source | None:
    """Read one cached JSON-stat response without building its matrices.

    Only the product/industry dimension is touched, and only to find which of
    its categories carry a value. Decoding the whole cube would be the same
    answer at ten times the cost, and `load_iot` refuses variants this does not
    need to care about.
    """
    try:
        doc = json.loads(path.read_text())
    except (ValueError, OSError):
        return None
    if not isinstance(doc, dict) or "id" not in doc or "size" not in doc:
        return None                       # a provenance sidecar, or not JSON-stat

    ids, size, value = doc["id"], doc["size"], doc.get("value") or {}
    # WHICH DIMENSION HOLDS THE SECTORS, by name and not by length.
    #
    # "the long one" is a heuristic that holds for an IO table, where `geo`,
    # `time`, `unit`, `freq` and `stk_flow` are all length 1 or 3. It fails on
    # the sources most worth cataloguing: the Structural Business Statistics
    # cube carries eleven countries and three NACE groups, so the longest
    # dimension is `geo`, and the file was filed as measuring Belgium, Czechia
    # and Germany rather than restaurants, bars and catering.
    pos = next((ids.index(k) for k in _SECTOR_DIMS if k in ids), None)
    if pos is None:
        cand = [i for i, k in enumerate(ids) if size[i] > 10]
        if not cand:
            return None
        pos = cand[0]
    dim = doc["dimension"][ids[pos]]
    idx = dim["category"]["index"]
    lab = dim["category"].get("label", {})
    stride = 1
    for s in size[pos + 1:]:
        stride *= s
    live_positions = {(int(k) // stride) % size[pos] for k in value}
    inverse = {v: k for k, v in idx.items()}
    live = [inverse[i] for i in sorted(live_positions) if i in inverse]

    bare_live = [_bare(c) for c in live]

    # THE SAME RULE THE LOADERS USE, so the catalogue reports what the engine
    # will actually deliver. The components replace their parent when their
    # totals sum to its total; where they do not, the parent stays.
    #
    # The total per code here is the sum of ITS OWN published cells across the
    # rest of the cube, because a bare scan does not know which column is the
    # published total and must not guess. That is close to what `load_iot` and
    # `load_sut` compute from `TU` and `TS_BP` and not identical to it — those
    # also intersect the supply and use files — so a count here can differ from
    # the loaded table's by a few codes. It is a catalogue, and the question it
    # answers is whether a code is reachable at all.
    values = [v for v in value.values() if isinstance(v, (int, float))]
    totals: dict = {}
    for k, v in value.items():
        if not isinstance(v, (int, float)):
            continue
        c = inverse.get((int(k) // stride) % size[pos])
        if c:
            totals[_bare(c)] = totals.get(_bare(c), 0.0) + v
    kept, dropped, _notes = _finest_tiling(
        bare_live, totals.get, lambda n: _rounding_tol(n, values))
    # What is published and still not carried: a partial set of components,
    # kept out because taking them would lose whatever the publisher did not
    # serve. An analyst asking for one of those deserves to hear that it exists
    # and why it is not loadable, rather than be told to split.
    finer_only = sorted(c for c in dropped if any(_covers(o, c) for o in kept))
    geo = doc["dimension"].get("geo", {}).get("category", {}).get("index", {})
    time = doc["dimension"].get("time", {}).get("category", {}).get("index", {})
    geo_all = sorted(geo)
    geo_code = geo_all[0] if len(geo_all) == 1 else "*"
    year = int(next(iter(time), 0) or 0)
    # Eurostat returns the id upper-cased; the configuration and
    # `DATASETS` both use lower case, and a catalogue that prints one
    # while the workbook needs the other is a catalogue nobody can act on.
    dataset = str(doc.get("extension", {}).get("id")
                  or path.stem.rsplit("_", 2)[0]).lower()

    # Two files from one dataset are two sources. `sbs_na_1a_se_r2` serves both
    # employment and turnover, and keying on the dataset alone filed them as a
    # single entry that listed one of them twice.
    # Whatever the filename says that the dataset, country and year do not.
    # `nama_10_a64_e_ES_2022_THS_HW` and `..._THS_PER` are hours worked and
    # persons employed: two different measurements of the same industries, and
    # two different keys. Keyed on the dataset alone they collapsed into one
    # entry printed twice.
    # TOKEN BY TOKEN, not by substring. Stripping country codes as substrings
    # turned `sbs_i561_i562_i563_employment_2018_2020` into
    # `..._emoyment_...` -- because Poland is in that cube and `pl` sits inside
    # "employment". The filename's parts are separated by underscores; that is
    # the boundary to respect.
    drop = {dataset, geo_code.lower(), str(year)} | {g.lower() for g in geo_all}
    drop |= set(dataset.split("_"))
    extra = "_".join(x for x in path.stem.lower().split("_")
                     if x and x not in drop)
    ident = f"{dataset}:{extra}" if extra else dataset
    return Source(
        source_id=f"eurostat:{ident}:{geo_code}:{year}",
        publisher="Eurostat", geo=geo_code, year=year, dataset=dataset,
        path=path, table_kind="eurostat",
        classification=f"CPA/NACE, {len(kept)} loaded categories",
        kind="table" if dataset.startswith("naio_10_") else "proxy",
        codes=list(kept), geos=geo_all,
        labels={_bare(c): lab.get(c, c) for c in live},
        finer=finer_only,
        note=(f"{len(live)} of {len(idx)} categories listed in the metadata "
              f"carry a value" if len(live) < len(idx) else ""))


def _workbook_source(path: Path, kind: str, publisher: str,
                     geo: str) -> Source | None:
    from .io_loader import LoaderError, load_ine_tio, load_uk_analytical_iot
    try:
        if kind == "uk_analytical":
            t = load_uk_analytical_iot(path)
        else:
            t = load_ine_tio(path, "interior", "residual_column")
    except (LoaderError, ValueError, OSError):
        return None
    return Source(
        source_id=f"{publisher.lower()}:{path.stem}:{geo}:{t.year}",
        publisher=publisher, geo=geo, year=t.year, dataset=path.stem,
        geos=[geo],
        path=path, table_kind=kind, classification=t.classification,
        codes=list(t.sector_codes),
        labels=dict(zip(t.sector_codes, t.sector_labels)))


def scan(root: Path | str) -> list[Source]:
    """Every table under `root` that this engine can load, newest first."""
    root = Path(root)
    out: list[Source] = []

    for f in sorted((root / "data" / "eurostat").glob("*.json")):
        s = _eurostat_source(f)
        if s and s.codes:
            out.append(s)

    for f in sorted(root.glob("UK_IOAT_*.xlsx")):
        s = _workbook_source(f, "uk_analytical", "ONS", "UK")
        if s:
            out.append(s)
    for f in sorted((root / "data" / "ine").glob("cne_tio_*.xlsx")):
        s = _workbook_source(f, "ine_interior", "INE", "ES")
        if s:
            out.append(s)

    return sorted(out, key=lambda s: (-s.year, s.publisher, s.source_id))


def find(target: str, sources: list[Source]) -> list[dict]:
    """Per source: is `target` a sector of its own, inside one, or absent?

    `target` is a classification code — `I55`, `C10`, `56` — matched without a
    dataset prefix and case-insensitively.
    """
    t = _bare(str(target).strip().upper())
    out = []
    for s in sources:
        if t in s.codes:
            out.append({"source": s, "verdict": "SEPARATE", "code": t,
                        "label": s.labels.get(t, t), "container": None})
            continue
        if t in s.finer:
            holders = [c for c in s.codes if _covers(c, t)]
            out.append({"source": s, "verdict": "PUBLISHED_NOT_LOADED",
                        "code": t, "label": s.labels.get(t, t),
                        "container": holders[0] if holders else None})
            continue
        holders = [c for c in s.codes if _covers(c, t)]
        if holders:
            # The finest container is the one no other container covers.
            finest = min(holders, key=lambda c: len(
                [o for o in s.codes if _covers(c, o)]) or 10 ** 6)
            out.append({"source": s, "verdict": "INSIDE", "code": t,
                        "label": s.labels.get(finest, finest),
                        "container": finest})
        else:
            out.append({"source": s, "verdict": "ABSENT", "code": t,
                        "label": None, "container": None})
    return out


def advise(target: str, sources: list[Source], geo: str | None = None) -> dict:
    """What to do about `target`, for one country.

    `geo` IS NOT OPTIONAL IN PRACTICE, and the first draft of this function
    treated it as though it were. Ranking every source by resolution and
    returning the winner told a Spanish analyst asking about accommodation to
    use the ONS table for the United Kingdom, because that one separates `I55`
    and Spain's does not. A finer table for a different economy is not a better
    source for the same question; it is an answer to a different question. When
    no country is named the result reports each country separately and picks
    nothing.

    Within one country, three outcomes:

      * some table separates it        -> use the finest such table
      * none does, but some contain it -> divide the finest container, which is
                                          what this engine is for
      * nothing contains it            -> the code is wrong, or the tables are
    """
    code = _bare(str(target).strip().upper())
    hits = find(code, sources)

    if geo is None:
        by_geo = {}
        for h in hits:
            g = h["source"].geo
            keep = by_geo.get(g)
            rank = {"SEPARATE": 3, "PUBLISHED_NOT_LOADED": 2,
                    "INSIDE": 1, "ABSENT": 0}
            if keep is None or (rank[h["verdict"]], h["source"].resolution) > \
                    (rank[keep["verdict"]], keep["source"].resolution):
                by_geo[g] = h
        separates = sorted(g for g, h in by_geo.items()
                           if h["verdict"] == "SEPARATE")
        return {"target": code, "action": "choose_country", "best": None,
                "hits": hits, "by_geo": by_geo,
                "why": (f"{code} is a sector of its own in "
                        + (f"{len(separates)} of the {len(by_geo)} countries "
                           f"here ({', '.join(separates)})"
                           if separates else
                           f"none of the {len(by_geo)} countries here")
                        + ", and sits inside a coarser code in the rest. Name "
                          "the country you are working on — a finer table for "
                          "another economy answers a different question.")}

    geo = geo.strip().upper()
    mine = [h for h in hits if h["source"].geo == geo]
    if not mine:
        return {"target": code, "action": "none", "best": None, "hits": hits,
                "geo": geo,
                "why": (f"No table for {geo} is on disk. "
                        f"`table_kind: eurostat` with `eurostat_geo {geo}` "
                        f"fetches one for any EU member state and year it "
                        f"publishes.")}

    tables = [h for h in mine if h["source"].kind == "table"]
    separate = [h for h in tables if h["verdict"] == "SEPARATE"]
    published = [h for h in tables if h["verdict"] == "PUBLISHED_NOT_LOADED"]
    inside = [h for h in tables if h["verdict"] == "INSIDE"]
    elsewhere = sorted({h["source"].geo for h in hits
                        if h["verdict"] == "SEPARATE"
                        and h["source"].geo != geo})

    if separate:
        best = max(separate, key=lambda h: h["source"].resolution)
        return {"target": code, "action": "load", "best": best, "hits": hits,
                "geo": geo, "proxies": [],
                "why": (f"{code} is a sector of its own in "
                        f"{best['source'].source_id}, which distinguishes "
                        f"{best['source'].resolution} sectors — the finest of "
                        f"the {len(separate)} {geo} table(s) that separate "
                        f"it.")}
    if published:
        best = max(published, key=lambda h: h["source"].resolution)
        return {"target": code, "action": "publisher_has_it", "best": best,
                "hits": hits, "geo": geo, "proxies": [],
                "why": (f"{geo} PUBLISHES {code} separately in "
                        f"{best['source'].source_id} — and this engine "
                        f"discards it. Where a country serves both a code and "
                        f"its components, the loader keeps the coarser tiling, "
                        f"so {code} arrives folded into "
                        f"`{best['container']}`. Splitting that with a proxy "
                        f"would estimate what your own office has measured. "
                        f"Read the file directly, or raise it.")}
    if inside:
        best = max(inside, key=lambda h: h["source"].resolution)
        note = ""
        if elsewhere:
            note = (f" {', '.join(elsewhere)} publish{'es' if len(elsewhere) == 1 else ''} "
                    f"it separately, which tells you the split is a real "
                    f"distinction and NOT that you may borrow their figures.")
        return {"target": code, "action": "split", "best": best, "hits": hits,
                "geo": geo,
                "proxies": _proxies_for(best["container"], sources, geo),
                "why": (f"No {geo} table here separates {code}. The finest "
                        f"that contains it is {best['source'].source_id}, "
                        f"where it sits inside `{best['container']}` "
                        f"({best['label']}). That is the sector to divide, and "
                        f"dividing it is what this engine does — bring a proxy "
                        f"that measures the parts.{note}")}
    return {"target": code, "action": "none", "best": None, "hits": hits,
            "geo": geo, "proxies": [],
            "why": (f"No code in any {geo} table here covers {code}. Check it "
                    f"against the classification the table uses — the ONS "
                    f"writes SIC 2007, Eurostat writes CPA.")}


def _proxies_for(container: str, sources: list[Source],
                 geo: str) -> list[dict]:
    """Sources that measure the PARTS of `container`, for this country.

    The answer "divide `I`" is only half an answer. Dividing it needs a proxy
    that measures the pieces, and finding one is the afternoon this module
    exists to remove. So: any non-table source for the same country that
    carries codes strictly inside the container, with those codes named.

    A proxy is a candidate, not a recommendation. Whether employment is the
    right key for a split is a judgement about the sectors — a labour-intensive
    subsector and a capital-intensive one share an output far less evenly than
    they share a headcount — and nothing here can make it.
    """
    out = []
    for s in sources:
        if s.kind != "proxy" or not container or geo not in s.geos:
            continue
        parts = sorted(c for c in s.codes if _inside(container, c))
        if len(parts) < 2:
            continue
        # DOES IT TILE THE SECTOR, or only a corner of it? SBS measures I561,
        # I562 and I563 — the groups of division 56. Asked for a proxy to
        # divide section `I`, which is accommodation AND food service, those
        # three cover the food half and say nothing about hotels. Offering them
        # without that distinction would put a key behind a split it cannot
        # support, which is the one thing this engine is supposed to refuse.
        parents = {_division_of(c) or c for c in parts}
        tiles = parents == {_bare(container).upper()}
        out.append({"source": s, "parts": parts, "tiles": tiles,
                    "covers": sorted(parents),
                    "labels": {c: s.labels.get(c, c) for c in parts}})
    return sorted(out, key=lambda d: (not d["tiles"], -len(d["parts"])))


def _division_of(code: str) -> str | None:
    """`I561` -> `I56`; `I56` -> `I56`; `I` -> None."""
    m = re.fullmatch(r"([A-Z])(\d{2})\d*", _bare(code).upper())
    return f"{m.group(1)}{m.group(2)}" if m else None


def _inside(container: str, code: str) -> bool:
    """Is `code` a part of `container`, allowing NACE GROUP codes?

    `eurostat._covers` reads divisions — two digits after the letter — because
    that is the level the input-output tables publish. Proxy sources go finer:
    Structural Business Statistics measures `I561`, `I562` and `I563`, the
    groups inside division 56, and those are precisely the sources worth
    finding, because a table that stops at `I` needs a proxy that does not.

    `_divisions('I561')` returns an empty set — the pattern wants two digits —
    so `_covers('I', 'I561')` is False and the SBS file matched nothing. Here a
    group falls back to its own division: `I561` is inside `I56`, which is
    inside `I`.
    """
    container, code = _bare(container).upper(), _bare(code).upper()
    if _covers(container, code):
        return True
    m = re.fullmatch(r"([A-Z])(\d{2})\d+", code)
    if not m:
        return False
    division = f"{m.group(1)}{m.group(2)}"
    return division == container or _covers(container, division)


# ---------------------------------------------------------------------------
# What exists that is NOT on disk
# ---------------------------------------------------------------------------
#
# `scan()` answers "what can I load", and for a fresh install the answer is
# "whatever shipped". A first-time user asking about their own country gets
# "no table for DE is on disk", which is true and useless: what they need next
# is which years exist, and that is one small query per dataset.
#
# The filter differs by dataset because the product dimension does -- cp1700
# indexes `prd_use`, cp15 `prd_amo`, the use tables `prd_ava`, and cp1750 is on
# industries. Asking for one total keeps each response near 24 KB instead of
# several megabytes.
# `prd_use` is the USE axis and its total is `TU`, not `CPA_TOTAL` -- that is
# the total on the AVAILABLE axis. Asking for `prd_use=CPA_TOTAL` names a
# category that does not exist there, and Eurostat answers 200 with an empty
# result rather than an error, so the probe reported that NO country publishes
# a symmetric product-by-product table. Spain publishes twenty-two years of
# one, and `load_iot` reads it with `prd_use="TU"`, three files away.
_YEAR_PROBE = {
    "product_by_product": ("prd_use", "TU"),
    "industry_by_industry": ("ind_use", "TOTAL"),
    "supply": ("prd_amo", "CPA_TOTAL"),
    "use_purchasers": ("prd_ava", "CPA_TOTAL"),
    "use_basic": ("prd_ava", "CPA_TOTAL"),
}


def available_years(geo: str, cache_dir: Path | str,
                    refresh: bool = False) -> dict:
    """Which years Eurostat carries for `geo`, per dataset.

    Cached, because it changes once or twice a year and a catalogue that costs
    five network round trips is a catalogue nobody runs twice. The cache
    records when it was taken so a reader can judge it; nothing here decides
    that a stale answer is fresh.

    Returns `{}` on any network failure rather than raising: this is an
    enrichment of an answer that already exists, and losing it should degrade
    the answer, not the command.
    """
    import json as _json
    import urllib.error
    import urllib.request

    from .eurostat import API, DATASETS

    geo = str(geo).strip().upper()
    cache = Path(cache_dir) / f"_availability_{geo}.json"
    if cache.exists() and not refresh:
        try:
            return _json.loads(cache.read_text())
        except (ValueError, OSError):
            pass

    out: dict = {}
    for name, (dim, value) in _YEAR_PROBE.items():
        url = (API.format(dataset=DATASETS[name])
               + f"&geo={geo}&unit=MIO_EUR&{dim}={value}")
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                doc = _json.loads(r.read())
            # LISTED IS NOT AVAILABLE, for the third time in this module.
            #
            # The `time` dimension lists every year the DATASET spans, not the
            # years this country populates. Reading it directly said Germany
            # had 35 years of supply-use to 2024, so `--find` printed a
            # configuration naming 2024 — and that configuration fails, because
            # Eurostat answers 200 with an empty `value` for a year a country
            # does not publish. Advice you have not run is not advice.
            #
            # So the years are read off the VALUE map, exactly as the product
            # codes are: a year is available when some cell carries a figure.
            idx = doc["dimension"]["time"]["category"]["index"]
            ids, size = doc["id"], doc["size"]
            pos = ids.index("time")
            stride = 1
            for s in size[pos + 1:]:
                stride *= s
            live = {(int(k) // stride) % size[pos] for k in doc.get("value", {})}
            inverse = {v: k for k, v in idx.items()}
            years = sorted(int(inverse[i]) for i in live if i in inverse)
            if years:
                out[name] = years
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            continue
    if not out:
        return {}

    from datetime import datetime, timezone
    out["_taken"] = datetime.now(timezone.utc).isoformat()
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(_json.dumps(out, indent=2))
    except OSError:
        pass
    return out
