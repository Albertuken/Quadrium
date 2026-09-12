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
        if self.table_kind == "eu_mrio":
            return ["table_kind      eu_mrio",
                    f"table_path      {self.path}",
                    f"mrio_region     {self.geo}",
                    f"mrio_year       {self.year}"]
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


def _mrio_sources(folder: Path) -> list[Source]:
    """One regional table per region of the European MRIO in `folder`.

    Read from the block's HEADER ROW and the 240 kB final-demand file, in a
    fraction of a second. Loading a region reads the whole 35 MB block and
    inverts a 2,720 x 2,720 system, and a listing that did that 272 times would
    take longer than the work it was listing. So a region is listed when it has
    output; the nine that trade with no other region -- which only the block
    can show -- are listed, and refused on loading with the reason.

    Each is filed under its own NUTS-2 code and never under its country. A
    region's table answers a different question from the country's, which is
    the rule `advise` already applies to another economy's table.
    """
    import openpyxl

    from .io_loader import (LoaderError, _MRIO_S, _MRIO_SECTORS, _MRIO_YEARS,
                            _mrio_files, _mrio_relabel, _mrio_side)
    out: list[Source] = []
    # Every year of the deposit that is in the folder, each under its own id.
    for year in _MRIO_YEARS:
        try:
            blk, fdf, _ = _mrio_files(folder, year)
            wb = openpyxl.load_workbook(blk, read_only=True, data_only=True)
            try:
                head = next(wb.worksheets[0].iter_rows(values_only=True,
                                                       max_row=1))
            finally:
                wb.close()
            fd_head, FD = _mrio_side(fdf, "rows")
        except (LoaderError, OSError, ValueError, StopIteration, KeyError):
            continue
        # Corrected for Greece and Finland, as the loader corrects them: the
        # catalogue must list the region a user can then load.
        labels = _mrio_relabel([str(x) for x in head[1:] if x is not None])
        S = _MRIO_S
        regions = list(dict.fromkeys(l.split("-", 1)[0] for l in labels))
        if (len(regions) * S != len(labels) or FD.shape[0] != len(labels)
                or "TOTAL" not in fd_head):
            continue
        sectors = [l.split("-", 1)[1] for l in labels[:S]]
        output = FD[:, fd_head.index("TOTAL")].reshape(len(regions), S).sum(1)
        out += [Source(
            source_id=f"mrio:eu{year}:{r}", publisher="Huang & Koutroumpis",
            geo=r, geos=[r], year=year, dataset=blk.stem, path=blk.parent,
            table_kind="eu_mrio",
            classification=("10 sectors, NACE sections grouped as the "
                            "archive groups them"),
            codes=list(sectors),
            labels={c: _MRIO_SECTORS.get(c, c) for c in sectors},
            note=("a region's own table, cut from an ESTIMATED archive that "
                  "does not balance: the residue is carried and sized in the "
                  "report, and a region that trades with no other region is "
                  "refused on loading"))
            for r, x in zip(regions, output) if x > 0]
    return out


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
    out.extend(_mrio_sources(root / "data" / "mrio"))

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
            holders = [c for c in s.codes if _inside(c, t)]
            out.append({"source": s, "verdict": "PUBLISHED_NOT_LOADED",
                        "code": t, "label": s.labels.get(t, t),
                        "container": holders[0] if holders else None})
            continue
        # `_inside` and not `_covers`, and the difference is a whole answer.
        #
        # `_covers` reads DIVISIONS, which is the level an input-output table
        # publishes. A user does not ask at that level: they ask about C101,
        # meat processing, or I561, restaurants. Asked for a NACE GROUP this
        # matched nothing and the verdict came back ABSENT -- "no code in any
        # BE table covers C101" -- while the Belgian table carries C10, which
        # contains it and is exactly the sector to divide.
        #
        # `_inside` was written for precisely this, for the proxy search, and
        # its own docstring explains the failure. It was not applied here. The
        # fix existed one function away and the neighbouring call site kept the
        # bug for as long as both have existed (2026-09-07).
        holders = [c for c in s.codes if _inside(c, t)]
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
        # Eurostat publishes COUNTRIES. Sending someone who typed a region to
        # fetch it there names a download that does not exist.
        why = (f"No table for {geo} is on disk. "
               + (f"`table_kind: eurostat` with `eurostat_geo {geo}` fetches "
                  f"one for any EU member state and year it publishes."
                  if len(geo) == 2 else
                  f"It is not a country code, so Eurostat has nothing to "
                  f"fetch for it: it publishes national tables."))
        regional = sorted(s.geo for s in sources
                          if s.table_kind == "eu_mrio"
                          and s.geo[:2] == geo[:2] and s.geo != geo)
        if regional:
            why += (f" The European MRIO here has {len(regional)} regional "
                    f"tables for {geo[:2]} ({', '.join(regional[:6])}"
                    f"{'…' if len(regional) > 6 else ''}); `--geo "
                    f"{regional[0]}` asks about one of them — a region's own "
                    f"table, not the country's.")
        return {"target": code, "action": "none", "best": None, "hits": hits,
                "geo": geo, "why": why}

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
    # A range of SECTIONS -- `G-I`, `B-E`, `M_N` -- is how the European MRIO
    # writes its ten sectors. `_covers` reads divisions and knows nothing of
    # these, so each contained nothing and `--find I55` against a regional
    # table said no code covers accommodation when `G-I` does. Read on the raw
    # code, before `_bare`, whose job is stripping dataset prefixes. A range of
    # DIVISIONS such as `C10-12` has digits and does not match.
    m = re.fullmatch(r"([A-Z])[-_]([A-Z])", str(container).strip().upper())
    if m:
        part = re.fullmatch(r"([A-Z])(\d{2}\d*)?", _bare(code).upper())
        return (part is not None
                and str(container).strip().upper() != _bare(code).upper()
                and m.group(1) <= part.group(1) <= m.group(2))
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


# ---------------------------------------------------------------------------
# Reading a proxy's actual numbers -- OQ-E-01
# ---------------------------------------------------------------------------

class ProxyValueError(Exception):
    """A proxy cube that cannot be reduced to one number per sector."""


def proxy_values(source: "Source", geo: str, year: int | None = None,
                 measure: str | None = None) -> dict:
    """One number per sector code, for a country and a year.

    WHY THIS EXISTS
    ----------------
    `--find` already names the proxies that measure the parts of a sector, and
    then leaves the analyst to go and get the numbers. That is the afternoon
    this module was written to remove, and it was only half removed. `OQ-E-01`,
    opened by the owner on 2026-09-06 in his own words -- he might not know
    where to look, and a tool for people who do not know where to look has to
    look for them.

    WHAT IT REFUSES, AND THIS IS THE WHOLE DESIGN
    -----------------------------------------------
    A JSON-stat cube has more dimensions than sectors. `sbs_na_1a_se_r2` is
    `freq x nace_r2 x indic_sb x geo x time`: eleven countries, three years and
    an indicator. A key is one number per sector, so every other dimension has
    to be pinned to one category.

    `geo` and `time` are pinned by argument. **Anything else with more than one
    category is refused by name**, because the alternative is summing across
    it -- and summing employment over three years, or across two indicators
    that measure different things, produces a number that looks like a
    measurement and is not one. `_eurostat_source` does sum a code's cells that
    way, deliberately, because it only asks whether a code carries data at all;
    a value that will drive a split cannot be built the same way.

    WHAT IT RETURNS
    ----------------
    `{"values": {code: float}, "pinned": {dim: category}, "year": int,
      "label": str}`. Codes are bare, matching what the catalogue reports.
    Raises `ProxyValueError` with the reason otherwise.
    """
    try:
        doc = json.loads(Path(source.path).read_text())
    except (ValueError, OSError) as exc:
        raise ProxyValueError(f"{source.path.name} could not be read: {exc}")

    ids, size, value = doc["id"], doc["size"], doc.get("value") or {}
    pos = next((ids.index(k) for k in _SECTOR_DIMS if k in ids), None)
    if pos is None:
        raise ProxyValueError(
            f"{source.source_id} has no sector dimension among "
            f"{', '.join(ids)}, so it cannot be read as a key")

    def cats(dim):
        return doc["dimension"][dim]["category"]["index"]

    # Pin every dimension but the sectors'.
    pinned, offset_parts = {}, []
    for i, dim in enumerate(ids):
        if i == pos:
            continue
        index = cats(dim)
        if dim == "geo":
            want = geo.upper()
            if want not in index:
                raise ProxyValueError(
                    f"{source.source_id} does not carry {want}. It has "
                    f"{', '.join(sorted(index))}")
            pinned[dim] = want
        elif dim == "time":
            years = sorted(index, key=lambda y: -int(y))
            want = str(year) if year is not None else years[0]
            if want not in index:
                raise ProxyValueError(
                    f"{source.source_id} has no {want}. It has "
                    f"{', '.join(years)}")
            pinned[dim] = want
        elif len(index) == 1:
            pinned[dim] = next(iter(index))
        elif measure and measure.upper() in {k.upper() for k in index}:
            pinned[dim] = next(k for k in index
                               if k.upper() == measure.upper())
        else:
            # The refusal that matters. Named rather than summed, and it says
            # what to do next: the alternative is adding employment to
            # turnover, which produces a number that reads as one measurement
            # and is none.
            lab = doc["dimension"][dim]["category"].get("label", {})
            shown = sorted(index)[:6]
            listed = "; ".join(f"{k} — {lab.get(k, k)}"[:60] for k in shown)
            raise ProxyValueError(
                f"{source.source_id} carries {len(index)} categories of "
                f"{dim!r} and this cannot choose between them. They are "
                f"different measurements of the same sectors. Name one with "
                f"--measure. The first few are: {listed}"
                f"{'; …' if len(index) > 6 else ''}"
                + (f" — {measure!r} is not among them." if measure else ""))
        offset_parts.append((i, index[pinned[dim]]))

    strides = [1] * len(size)
    for i in range(len(size) - 2, -1, -1):
        strides[i] = strides[i + 1] * size[i + 1]

    base = sum(strides[i] * j for i, j in offset_parts)
    sector_index = cats(ids[pos])
    labels = doc["dimension"][ids[pos]]["category"].get("label", {})

    out = {}
    for code, j in sector_index.items():
        v = value.get(str(base + strides[pos] * j))
        if isinstance(v, (int, float)):
            out[_bare(code)] = float(v)
    if not out:
        raise ProxyValueError(
            f"{source.source_id} carries no value for {geo.upper()} in "
            f"{pinned.get('time', '?')}. The cube lists the sectors and the "
            f"cells are empty, which is a gap in the publisher's data and not "
            f"in this file.")

    # The label of whatever was pinned as the measurement, so a caller can
    # print what the number IS instead of guessing. A cube's own `label` names
    # the dataset, not the indicator, and the two are not the same sentence.
    measure_label = ""
    for dim, cat in pinned.items():
        if dim in ("geo", "time", "freq"):
            continue
        lab = doc["dimension"][dim]["category"].get("label", {})
        if lab.get(cat):
            measure_label = str(lab[cat])
            break

    return {"values": out, "pinned": pinned,
            "year": int(pinned.get("time", source.year) or 0),
            "labels": {_bare(c): labels.get(c, c) for c in sector_index},
            "measure_label": measure_label,
            "label": str(doc.get("label") or source.dataset)}


def tiling_only(codes) -> list[str]:
    """The codes of one level: drop any code another code in the set contains.

    A proxy cube lists every level it publishes. Asked for the parts of `C10`
    the Belgian SBS file returns C101 AND C1011, C1012, C1013 -- the group and
    the classes inside it -- and `C109` alongside `C1091` and `C1092`. Pasted
    into a `keys` sheet as they come, those count the same euro twice, and the
    shares that result are meaningless while looking perfectly ordinary.

    `_inside` does not settle it: it was written to carry a NACE GROUP up to
    its DIVISION, which is the step an input-output table needs, and it does
    not know that `C1091` sits inside `C109`. The rule here is the
    classification's own — a NACE code contains every code it prefixes — and it
    is kept separate rather than folded into `_inside`, whose callers depend on
    the narrower behaviour.

    Keeps the COARSER level, because that is the one whose parts sum to the
    parent: taking C1011 and dropping C102 would tile nothing.
    """
    bare = {_bare(c).upper(): c for c in codes}
    keep = []
    for b, original in bare.items():
        if any(o != b and b.startswith(o) for o in bare):
            continue
        keep.append(original)
    return sorted(keep)
