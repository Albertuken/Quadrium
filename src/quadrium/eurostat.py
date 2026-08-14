"""
Eurostat as a source: one API, one format, twenty-seven countries.

WHY THIS IS A SEPARATE MODULE FROM `io_loader`
----------------------------------------------
Fetching is a different concern from loading. `fetch()` touches the network and
writes a file with its checksum; `load_iot()` reads that file and never touches
the network. Keeping them apart is what makes a run reproducible: the loader can
be re-run offline against exactly the bytes that produced a result.

WHAT TRAVELS WITH THE DATA, AND WHAT DOES NOT
---------------------------------------------
**The method does not travel with the data**, and this module is the wrong place
to look for it. Eurostat harmonises the *format*: the same dataset codes, the
same ESA classifications, the same JSON-stat envelope for every member state.
It does not harmonise, and does not record, how each office got there.

That is measured rather than assumed. The harmonised metadata files
(`na10_esms_<cc>.htm`) were harvested for all thirteen countries that have one —
about 200,000 words — and contain **zero** occurrences of "product technology",
"industry technology", "technology assumption", "symmetric", "hybrid" or
"Almon". Thirteen of thirteen carry the same boilerplate sentence. See
`library/SOURCE_REGISTER.md` §6b.

So three tables downloaded from here look alike and were not made alike: the
ONS uses a hybrid of models A and B chosen per cell by whether it goes negative,
the INE a hybrid chosen per secondary production, Statistik Austria product
technology throughout with manual correction above 15 million EUR and the Almon
algorithm below. Any comparison across countries that does not say so is
comparing the format.

THE DATASETS
------------
    naio_10_cp1700   symmetric IOT at basic prices, product by product
    naio_10_cp1750   symmetric IOT at basic prices, industry by industry
    naio_10_cp15     supply table, basic prices + transformation to purchasers'
    naio_10_cp16     use table at purchasers' prices
    naio_10_cp1610   use table at basic prices
    naio_10_cp1620   trade and transport margins
    naio_10_cp1630   taxes less subsidies on products

Each IOT dataset carries all three valuation variants in one response, on the
`stk_flow` dimension: `TOTAL`, `DOM` (domestic) and `IMP` (imports).
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .precision import assertable_tolerance, printed_decimals as _pd

from .models import IOTable, SupplyUseTables

API = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
       "{dataset}?format=JSON&lang=EN")

DATASETS = {
    "product_by_product": "naio_10_cp1700",
    "industry_by_industry": "naio_10_cp1750",
    "supply": "naio_10_cp15",
    "use_purchasers": "naio_10_cp16",
    "use_basic": "naio_10_cp1610",
    "margins": "naio_10_cp1620",
    "taxes_on_products": "naio_10_cp1630",
}

VARIANTS = {"total": "TOTAL", "domestic": "DOM", "imports": "IMP"}

# Final-demand components, finest first. A country publishes whichever it
# publishes -- Spain gives `P52`/`P53` separately for the total table and only
# the combined `P5M` for the domestic and import ones -- so the set is CHOSEN
# from what is actually populated and then checked against the published total.
_FD_ALTERNATIVES = [
    (["P3_S13", "P3_S14", "P3_S15"], ["P3"]),
    (["P51G", "P52", "P53"], ["P51G", "P5M"], ["P5"]),
    (["P6_B0", "P6_D0"], ["P6"]),
]

_VA_ROWS = {
    # For a DOMESTIC table the first two rows are not value added: they are
    # imported intermediate inputs and taxes on products. Same convention as the
    # UK and Spanish loaders; the labels say so.
    "domestic": ["IMP", "D21X31", "D1", "D29X39", "B2A3G"],
    "total": ["D21X31", "D1", "D29X39", "B2A3G"],
}

_LABELS = {
    "IMP": "Use of imported products (not value added)",
    "D21X31": "Taxes less subsidies on products (not value added)",
    "D1": "Compensation of employees",
    "D29X39": "Other taxes less other subsidies on production",
    "B2A3G": "Operating surplus and mixed income, gross",
}

TOL = 1e-3          # million EUR; observed residuals are ~1e-11


class EurostatError(ValueError):
    pass


def fetch(dataset: str, geo: str, year: int, dest: Path | str,
          unit: str = "MIO_EUR", stk_flow: str | None = None,
          **filters: str) -> dict:
    """Download one dataset for one country and year, and record what arrived.

    `dataset` is a key of `DATASETS` or a raw Eurostat code. Returns the
    provenance record — URL, bytes, SHA-256, timestamp — which the caller should
    keep beside the file. Nothing else in this module touches the network.

    `stk_flow` narrows the request to one valuation variant (`TOTAL`, `DOM` or
    `IMP`), which cuts `naio_10_cp1750` for one country from 267 KB to 103 KB.

    HTTP 413 IS TRANSIENT AND CARRIES NO DIAGNOSIS. It has now been seen
    twice, and NEITHER time survived a retry.

    The second sighting (2026-08-11) looked like a clean mechanism: `geo=ES`
    answered 200 with 6,038 values while `geo=GB` and `geo=XX` both answered
    413, which reads as "an unrecognised filter value is dropped, so the request
    becomes every country and trips the cell limit". That explanation was written
    into this docstring as measured fact. **Three minutes later all three codes
    answered 200 with an empty result, three times running.** The 413 was server
    load, not the filter.

    So: a 413 here means retry, and it means nothing else. Do not infer a
    mechanism from one observation of it — this docstring has now done that
    twice and been wrong twice. What IS stable is the empty answer: a geo code
    the dataset has no data for returns 200 with an empty `value`, and `UK` is
    one of those — Eurostat carries no `naio_10_cp1700` for the United Kingdom
    in 2018 or 2019.
    """
    code = DATASETS.get(dataset, dataset)
    url = (API.format(dataset=code)
           + f"&geo={geo}&time={int(year)}&unit={unit}")
    if stk_flow:
        url += f"&stk_flow={stk_flow}"
    # Any other dimension the dataset happens to have. The SUT tables need
    # none; `nama_10_a64_e` needs `na_item` to pick employment rather than one
    # of the other series sharing the cube (D4, labour productivity).
    for key, value in sorted(filters.items()):
        url += f"&{key}={value}"
    dest = Path(dest)
    try:
        with urllib.request.urlopen(url, timeout=180) as r:
            raw = r.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 413:
            raise EurostatError(
                f"HTTP 413 for {code}, geo={geo!r}, {year}. This has been "
                f"transient both times the project has seen it — retry first. "
                f"If it persists, narrow the request: `stk_flow='DOM'` fetches "
                f"one valuation variant at a time.") from None
        raise EurostatError(f"{url} returned HTTP {exc.code}") from None
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EurostatError(f"{url} did not return JSON: "
                            f"{raw[:200]!r}") from exc
    if not doc.get("value"):
        raise EurostatError(
            f"{code} returned no values for geo={geo}, time={year}. The "
            f"country may not publish that year, or the dataset may not cover "
            f"it — Eurostat answers 200 with an empty `value` either way.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    return {"dataset": code, "url": url, "geo": geo, "year": int(year),
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "n_values": len(doc["value"])}


def _rounding_tol(n_terms: int, values=None) -> float:
    """The tightest an `n_terms` identity can be held to, for THIS source.

    Delegates to `quadrium.precision`, which reads the published precision off
    the values instead of assuming it. Assuming it would be wrong here in
    particular: Eurostat serves Spain at one decimal and Italy at two, from the
    same `naio_10_*` family under the same regulation. See `OQ-B-02`.
    """
    if values is None:                      # no values to read: assume the
        return max(TOL, 0.005 * n_terms)    # coarsest precision seen, 2 dp
    return max(TOL, assertable_tolerance(values, n_terms))


_PREFIXED = re.compile(r"^(?:CPA_|CPA2_1_)")


def _bare(code: str) -> str:
    """The classification code without a dataset prefix.

    `_covers` and `_divisions` read the NOTATION -- a letter, two digits, a
    range separator -- so a `CPA_` in front of it defeats every pattern they
    match. THEY WERE BEING GIVEN PREFIXED CODES, and had been since they were
    written: `load_iot` strips `pref` only when it builds `sector_codes`, long
    after `_drop_aggregates` has run. The filter was a silent no-op on every
    `CPA_` dataset, and the conclusion drawn from that -- "no fixture mixes
    hierarchy levels" -- was an artefact of the blindness, not a fact about the
    data. France publishes `B` beside `B05`-`B09` and `C10-12` beside `C10`,
    `C11`, `C12`; its supply table sums to 7,939,582.2 against a published
    6,121,102.4 until the aggregates come out.
    """
    return _PREFIXED.sub("", code)


def _divisions(code: str) -> set | None:
    """The NACE/CPA divisions a code covers, from the code string alone.

        `C10`      -> {C10}
        `C10-12`   -> {C10, C11, C12}
        `C31_32`   -> {C31, C32}
        `B`        -> None, meaning "the whole section B"
        `L68A`     -> {L68A}, a lettered sub-division that nests in nothing else

    Derived from the notation because there is no correspondence table in the
    response, and hard-coding the 64-item list would be exactly the assumption
    this module refuses to make elsewhere.
    """
    code = _bare(code)
    m = re.match(r"^([A-Z])(\d{2})(?:([-_])(\d{2}))?([A-Z])?$", code)
    if not m:
        return set() if code else set()
    letter, first, sep, second, suffix = m.groups()
    if suffix:
        return {code}
    if sep == "-":
        return {f"{letter}{n:02d}" for n in range(int(first), int(second) + 1)}
    if sep == "_":
        return {f"{letter}{first}", f"{letter}{second}"}
    return {f"{letter}{first}"}


def _covers(a: str, b: str) -> bool:
    """True if `a` is a strict aggregate of `b`."""
    if a == b:
        return False
    a, b = _bare(a), _bare(b)
    if re.fullmatch(r"[A-Z]", a):
        # A section covers its own DIVISIONS and nothing else. `b.startswith(a)`
        # alone is not that test: section O then "covers" `OP_RES` and section D
        # "covers" `D21X31`, which are accounting rows, not divisions. Those two
        # false positives appear in every `cp15`/`cp16` fixture here. In
        # `load_iot` the both-axes rule removes such rows before this runs, so
        # they were harmless there; `load_sut` has no such rule and they were
        # not.
        return b.startswith(a) and bool(_divisions(b))
    da, db = _divisions(a), _divisions(b)
    if not da or not db:
        return False
    return db < da or (db <= da and len(db) < len(da))


def _drop_aggregates(codes: list[str]) -> tuple[list[str], list[str]]:
    """Keep the codes no other populated code contains; report what went.

    NO FIXTURE IN THIS PROJECT EXERCISES THIS, AND THE HONEST HISTORY IS THAT
    IT WAS WRITTEN FOR A MISDIAGNOSIS. Italy's industry table summed to
    10,096,344 against a published 4,124,091 -- 2.4x -- and the cause looked
    like an aggregate sitting beside its own components. It was not: the excess
    was the value-added rows (`P1` output, `P2_ADJ`, `IMP`) entering the sector
    set because no prefix was there to keep them out. Rule 1 in `load_iot`,
    "it must appear on both axes", is what actually fixed it. All seven
    Eurostat fixtures held here publish exactly one level, so this function has
    never had anything to drop.

    It stays because publishing both levels is a national choice and a country
    that made it would otherwise be double counted. But the guard that would
    CATCH that is the published-total check below; this only tries to repair
    it, and an unrepaired mix still refuses to load.
    """
    kept = [c for c in codes if not any(_covers(o, c) for o in codes)]
    return kept, [c for c in codes if c not in kept]


class _Cube:
    """Random access into a JSON-stat 2.0 response.

    `at()` returns **None** for a cell Eurostat did not publish, and that
    distinction is the whole point: a missing cell is not a zero. Substituting
    one for the other is how `P52`/`P53`, published for the total table and not
    for the domestic one, silently became a 5,321 million EUR imbalance in the
    first draft of this module.
    """

    def __init__(self, doc: dict):
        self.doc = doc
        self.ids = doc["id"]
        self.size = doc["size"]
        self.index = {k: doc["dimension"][k]["category"]["index"]
                      for k in self.ids}
        self.labels = {k: doc["dimension"][k]["category"].get("label", {})
                       for k in self.ids}
        self.value = doc["value"]
        self.stride = [1] * len(self.size)
        for i in range(len(self.size) - 2, -1, -1):
            self.stride[i] = self.stride[i + 1] * self.size[i + 1]
        self.fixed = {k: next(iter(self.index[k])) for k in self.ids
                      if len(self.index[k]) == 1}

    def at(self, **kw):
        pos = 0
        for i, k in enumerate(self.ids):
            v = kw.get(k, self.fixed.get(k))
            if v is None:
                raise EurostatError(f"dimension {k!r} needs a value")
            j = self.index[k].get(v)
            if j is None:
                return None
            pos += j * self.stride[i]
        return self.value.get(str(pos))


def load_iot(path: Path | str, variant: str = "domestic") -> IOTable:
    """Read a saved `naio_10_cp1700` / `cp1750` response into an `IOTable`.

    `variant` is `"domestic"` (the default, and the one Leontief analysis wants)
    or `"total"`. `"imports"` is refused: Eurostat publishes no output vector
    for it, so it is an input table and not a symmetric IOT — the same reasoning
    the Spanish loader applies.

    NOTHING HERE IS HARD-CODED TO A CLASSIFICATION.
    The product set is **derived from the data**: the codes that carry a value,
    checked against the published total. Eurostat serves the whole CPA hierarchy
    — `C10-12` sits beside `C10`, `C11` and `C12` — so a fixed list of 64 would
    be wrong for any country publishing at a different level, and a rule like
    "drop a code that is a prefix of another" is defeated by `P5M`, which is a
    subtotal of `P52` and `P53` and a prefix of neither. Spain resolves to 65
    codes summing to 2,664,587.0, exactly the published `CPA_TOTAL`.
    """
    if variant not in ("domestic", "total"):
        if variant == "imports":
            raise EurostatError(
                "variant 'imports' is an input table, not a symmetric IOT: "
                "Eurostat publishes no `P1` output vector for it, so the "
                "column identity has nothing to close against. Load 'total' "
                "or 'domestic'.")
        raise EurostatError(f"variant must be 'domestic' or 'total', "
                            f"not {variant!r}")
    path = Path(path)
    cube = _Cube(json.loads(path.read_text()))
    flow = VARIANTS[variant]
    if "stk_flow" not in cube.ids:
        raise EurostatError(f"{path.name} has no `stk_flow` dimension; this "
                            f"loader expects naio_10_cp1700 or cp1750.")
    # The two datasets do not agree on anything but the shape.
    #   naio_10_cp1700   `prd_use` / `prd_ava`, products carry a `CPA_` prefix
    #   naio_10_cp1750   `ind_use` / `ind_ava`, industries carry NO prefix
    # So neither the dimension names nor a prefix can be assumed, and the
    # earlier guess of `induse`/`indava` was simply wrong. What does generalise
    # is the DATA-DRIVEN rule: a sector is a code that carries a total-use
    # value, and the set is accepted only if it sums to the published total.
    if "prd_use" in cube.ids:
        use_dim, ava_dim, pref = "prd_use", "prd_ava", "CPA_"
    elif "ind_use" in cube.ids:
        use_dim, ava_dim, pref = "ind_use", "ind_ava", ""
    else:
        raise EurostatError(
            f"{path.name} has neither `prd_use` nor `ind_use`; this loader "
            f"expects naio_10_cp1700 or naio_10_cp1750. Dimensions: "
            f"{', '.join(cube.ids)}")

    total_code = pref + "TOTAL"
    # Three rules, and they are kept apart because each is sound for its own
    # reason and none of them is sound for the others' work.
    #
    #   1. it appears on BOTH axes. A branch of activity both buys and sells,
    #      so a genuine sector is indexed on `*_ava` and on `*_use` alike.
    #      Value-added rows (`D1`, `B2A3G`, `P1`, `IMP`, `TS_BP`) appear only as
    #      suppliers and final-demand columns only as users, so this removes
    #      every accounting row without a hard-coded list of them.
    #   2. it carries a value. The country actually publishes it.
    #   3. it is not contained in another surviving code (`_drop_aggregates`).
    #
    # RULE 1 IS NOT DECORATION. With `pref = "CPA_"` the prefix did this work by
    # accident; with the bare NACE codes of `cp1750` there is no prefix, and
    # leaving it to rule 3 dropped `D21X31`, `P2_ADJ` and `IMP` for the wrong
    # reason -- their first letters collide with NACE sections D, P and I, so
    # the section "contained" the tax row. Right answer, false reasoning, and
    # the same collision already cost this project NACE section P (Education)
    # once. Rule 3 now only ever sees real classification codes.
    # The published precision, read off this response rather than assumed --
    # it differs by country within one dataset family. See `OQ-B-02`.
    published_values = [v for v in cube.doc["value"].values()
                        if isinstance(v, (int, float))]

    on_both = set(cube.index[use_dim])
    codes = [c for c in cube.index[ava_dim]
             if c != total_code and c.startswith(pref) and c in on_both
             and cube.at(stk_flow=flow, **{use_dim: "TU", ava_dim: c})
             is not None]
    if not codes:
        raise EurostatError(
            f"no {pref} code carries a value for stk_flow={flow!r} in "
            f"{path.name}. The country may not publish this variant.")
    codes, aggregated_away = _drop_aggregates(codes)
    published_total = cube.at(stk_flow=flow, **{use_dim: "TU",
                                                ava_dim: total_code})
    got = sum(cube.at(stk_flow=flow, **{use_dim: "TU", ava_dim: c})
              for c in codes)
    # Relative, for the reason given in `load_sut`: cells are rounded to two
    # decimals and the aggregate is published independently, so a 65-term sum
    # lands a few hundredths away. A set that genuinely mixed levels would be
    # out by a factor, not by a rounding -- Italy's was 2.4x before the
    # hierarchy filter.
    if (published_total is not None
            and abs(got - published_total) > 1e-6 * abs(published_total)):
        raise EurostatError(
            f"the {len(codes)} codes that carry values sum to {got:,.1f} "
            f"against a published total of {published_total:,.1f}. Eurostat "
            f"serves the whole hierarchy. Dropping the {len(aggregated_away)} "
            f"code(s) another populated code contains did not make the rest a "
            f"partition, so the set still mixes levels or still carries a row "
            f"that is not a sector. Kept: {', '.join(codes[:8])}...")

    def col(name, allow_missing=False):
        out = []
        for c in codes:
            v = cube.at(stk_flow=flow, **{use_dim: name, ava_dim: c})
            if v is None and not allow_missing:
                return None
            out.append(0.0 if v is None else float(v))
        return np.asarray(out, float)

    def row(name):
        """A row across the industries, with absent cells PROVED to be zeros.

        Eurostat omits a cell from the JSON both when the value is a
        structural zero and when it is unpublished, and the two are not
        distinguishable at the cell. Reading absence as zero is how an earlier
        probe in this project turned unpublished `P52`/`P53` into zeros and
        fabricated a 5,321 million EUR imbalance; reading it as "row
        unavailable" is how this loader silently zeroed Italy's whole 503,956.8
        imports row over ONE missing cell, which the balance check then caught
        as a 70,444 gap.

        Neither guess is needed, because the row's own total is published.
        Fill with zeros, then check the filled row against `TOTAL` — the total
        intermediate use of that row. If it reconciles, the absences were
        zeros and we have the source's word for it. If it does not, or if no
        total is published, refuse and return None.

        Italy's `D1` has one absent cell and reconciles exactly: an industry
        with no compensation of employees, which for `L68A` imputed rents is
        what one would expect.
        """
        out, missing = [], 0
        for c in codes:
            v = cube.at(stk_flow=flow, **{use_dim: c, ava_dim: name})
            missing += v is None
            out.append(0.0 if v is None else float(v))
        arr = np.asarray(out, float)
        if not missing:
            return arr
        published = cube.at(stk_flow=flow, **{use_dim: "TOTAL", ava_dim: name})
        if published is None or abs(arr.sum() - published) > _rounding_tol(
                len(codes), published_values):
            return None
        return arr

    # Final demand: take the finest alternative that is fully populated.
    fd, dropped = [], []
    for alternatives in _FD_ALTERNATIVES:
        for cand in alternatives:
            if all(col(c) is not None for c in cand):
                fd += cand
                dropped += [c for alt in alternatives for c in alt
                            if c not in cand]
                break
        else:
            raise EurostatError(
                f"none of {alternatives} is fully populated for "
                f"stk_flow={flow!r}; the final-demand block cannot be built "
                f"without either double counting or dropping a component.")

    Z = np.array([[cube.at(stk_flow=flow, **{use_dim: c2, ava_dim: c1}) or 0.0
                   for c2 in codes] for c1 in codes], float)
    Y = np.column_stack([col(c) for c in fd])
    X = row("P1")
    if X is None:
        raise EurostatError(f"no `P1` output vector for stk_flow={flow!r}")
    VA_names = _VA_ROWS[variant]
    VA = np.vstack([row(r) if row(r) is not None else np.zeros(len(codes))
                    for r in VA_names])

    # The SOURCE's own identities, on the source's own final demand. Checked
    # before anything is derived, because a derived column would mask them.
    # Tolerance scales with the number of terms summed, because every cell is
    # published rounded to two decimals and can be half a hundredth out. A
    # 66-term sum is therefore entitled to 0.33 while a single cell is entitled
    # to 0.005, and one flat threshold cannot serve both: 1e-3 rejected Italy's
    # final-demand identity at 0.0200 across 8 columns. A real imbalance is
    # orders of magnitude larger -- the one this guard was written for was
    # 78,638.
    for what, a, b, n_terms in (
            ("final-demand components sum to total final use", Y.sum(1),
             col("TFU"), len(fd)),
            ("intermediate + final use equals total use", Z.sum(1) + Y.sum(1),
             col("TU"), len(codes) + len(fd)),
            ("intermediate + primary inputs equals output", Z.sum(0)
             + VA.sum(0), X, len(codes) + len(VA_names))):
        if b is None:
            continue
        d = float(np.abs(np.asarray(a) - np.asarray(b)).max())
        tol = _rounding_tol(n_terms, published_values)
        if d > tol:
            raise EurostatError(
                f"{path.name} does not balance as published and will not be "
                f"loaded.\n  failed: {what}\n  off by {d:,.4f} "
                f"(tolerance {tol:g}, for a sum of {n_terms} rounded cells)"
                f"\nA table that does not balance is not a table.")

    if variant == "total":
        # A total-flows table's uses are output PLUS imports, so the row
        # identity an `IOTable` promises -- Z.sum(1) + Y.sum(1) == X -- cannot
        # hold without them. Imports by product are the `IMP` variant's own
        # total-use column, carried here as a negative final-demand column: the
        # standard convention, and the one `load_ine_tio` already uses.
        imp = []
        for c in codes:
            v = cube.at(stk_flow="IMP", **{use_dim: "TU", ava_dim: c})
            if v is None:
                raise EurostatError(
                    f"the total table needs imports by product to close its "
                    f"row identity, and `IMP`/`TU` is not published for {c}.")
            imp.append(float(v))
        Y = np.column_stack([Y, -np.asarray(imp, float)])
        fd = fd + ["P7_NEG"]

    # And now the OBJECT's contract, which is a different claim from the
    # source's. The first draft of this module checked only the source's
    # identities and handed back a total-flows table whose `IOTable` row
    # balance was off by 78,638 -- the imports it had never been given.
    d = float(np.abs(Z.sum(1) + Y.sum(1) - X).max())
    if d > _rounding_tol(len(codes) + len(fd), published_values):
        raise EurostatError(
            f"{path.name} balances as published but the IOTable it would "
            f"produce does not: Z.sum(1) + Y.sum(1) - X is off by {d:,.4f}. "
            f"Every consumer of an `IOTable` is entitled to that identity.")

    geo = cube.fixed.get("geo", "?")
    year = int(cube.fixed.get("time", 0))
    labels = cube.labels[ava_dim]
    axis = ("product by product" if use_dim == "prd_use"
            else "industry by industry")
    return IOTable(
        table_id=f"EUROSTAT-{geo}-{year}-{variant}",
        country=str(cube.labels["geo"].get(geo, geo)), year=year,
        unit=f"{cube.labels.get('unit', {}).get(cube.fixed.get('unit'), 'million EUR')}"
             f", current prices, basic prices",
        classification=f"{pref.rstrip('_') or 'NACE Rev.2'} ({len(codes)} "
                       f"{'products' if pref else 'industries'}, derived from the data, "
                       f"not assumed)",
        sector_codes=[c[len(pref):] if pref else c for c in codes],
        sector_labels=[str(labels.get(c, c)) for c in codes],
        Z=Z, Y=Y,
        Y_labels=["Imports of goods and services (negative column, DERIVED)"
                  if f == "P7_NEG" else f for f in fd], VA=VA,
        VA_labels=[_LABELS.get(r, r) for r in VA_names], X=X,
        source=f"Eurostat, {cube.doc.get('label', 'naio_10')} ({path.name})",
        retrieved_at=datetime.now(timezone.utc),
        notes=(f"{axis}, {variant} use, basic prices. The "
               f"{'product' if pref else 'industry'} set is derived from the "
               f"data: {len(codes)} codes carry values and sum to the published "
               f"total"
               + (f", after dropping {len(aggregated_away)} code(s) that "
                  f"another populated code contains ({', '.join(aggregated_away)})"
                  if aggregated_away else "")
               + f". Published to "
               + (f"{_pd(published_values)} decimal(s)"
                  if _pd(published_values) is not None else "full precision")
               + f", so an identity over {len(codes) + len(fd)} of its cells "
               f"cannot be checked tighter than "
               f"{_rounding_tol(len(codes) + len(fd), published_values):.4g}, "
               f"and this table's row identity is out by {d:.3g} — see "
               f"`OQ-B-02`, and do not read a residual under that floor as an "
               f"exact balance"
               + f". Final demand uses {', '.join(fd)}; "
               f"{', '.join(dropped)} dropped as subtotals or left unpublished. "
               f"THE METHOD DOES NOT TRAVEL WITH THE DATA — Eurostat harmonises "
               f"the format, not the transformation. See the module docstring "
               f"and library/SOURCE_REGISTER.md before comparing countries."))


# ---------------------------------------------------------------------------
# Supply and use, from `naio_10_cp15` + `naio_10_cp16`
# ---------------------------------------------------------------------------

_SUT_VA_ROWS = ["D1", "D29X39", "B2A3G"]
_SUT_VA_LABELS = ["Compensation of employees",
                  "Other taxes less other subsidies on production",
                  "Operating surplus and mixed income, gross"]


def load_sut(supply_path: Path | str, use_path: Path | str) -> SupplyUseTables:
    """Build a `SupplyUseTables` from Eurostat's supply and use tables.

    `supply_path` is a saved `naio_10_cp15` (supply at basic prices, with the
    columns that carry it to purchasers' prices); `use_path` a saved
    `naio_10_cp16` (use at purchasers' prices). Both for the same country and
    year — the loader refuses a mismatched pair rather than silently crossing
    two economies.

    This generalises what `load_ine_tod` does for one national workbook. The
    Spanish supply-use pair had to be read out of a spreadsheet whose layout is
    unique to the INE; this reaches the same object for any member state that
    transmits the tables.

    ONE THING EUROSTAT DOES NOT GIVE, AND IT IS RECORDED RATHER THAN INVENTED.
    The supply table carries **`OTTM`, trade and transport margins combined**,
    where the INE's own workbook publishes the two separately. So
    `total_margins` is populated and `trade_margins` / `transport_margins` are
    left `None`. Splitting the total between them would be an invention the
    accounting could not detect, and `ID-09` — which is about who earns which
    margin — cannot be asked of this source at all.

    Note the code conventions differ between the two datasets and neither is
    prefixed the way `naio_10_cp1700` is: products carry `CPA_`, industries are
    bare (`A01`, `C10-12`).
    """
    sup = _Cube(json.loads(Path(supply_path).read_text()))
    use = _Cube(json.loads(Path(use_path).read_text()))
    for dim, cube, name in (("prd_amo", sup, "supply"), ("prd_ava", use, "use")):
        if dim not in cube.ids:
            raise EurostatError(f"the {name} file has no `{dim}` dimension; "
                                f"expected naio_10_cp15 and naio_10_cp16.")
    geo = sup.fixed.get("geo")
    year = sup.fixed.get("time")
    if (geo, year) != (use.fixed.get("geo"), use.fixed.get("time")):
        raise EurostatError(
            f"the supply file is {geo} {year} and the use file is "
            f"{use.fixed.get('geo')} {use.fixed.get('time')}. Two economies, "
            f"or two years, do not make a supply-use pair.")

    # Products: those carrying a value in BOTH tables, checked against the
    # published total supply. Same rule as `load_iot` -- derived, not assumed.
    products = [c for c in sup.index["prd_amo"]
                if c.startswith("CPA_") and c != "CPA_TOTAL"
                and sup.at(ind_impv="TS_BP", prd_amo=c) is not None
                and use.at(ind_use="TU", prd_ava=c) is not None]
    if not products:
        raise EurostatError(f"no product carries values in both files for "
                            f"{geo} {year}")
    # France and Denmark populate BOTH levels -- `CPA_B` beside `CPA_B05`...`B09`,
    # `CPA_C10-12` beside `C10`, `C11`, `C12` -- 39 containments in each. Every
    # other fixture here populates one level and this drops nothing. The filter
    # was in `load_iot` and not here, and in `load_iot` it had never actually
    # run: it was being handed `CPA_`-prefixed codes and reads bare notation.
    products, aggregated_away = _drop_aggregates(products)
    published = sup.at(ind_impv="TS_BP", prd_amo="CPA_TOTAL")
    got = sum(sup.at(ind_impv="TS_BP", prd_amo=c) for c in products)
    # Relative, unlike every other tolerance in this module, and for a reason
    # that is measured: Eurostat rounds each cell to two decimals and publishes
    # the aggregate independently, so a 65-term sum lands 0.03 from the printed
    # `CPA_TOTAL` on Austria 2022 -- 2.5e-8 of it. An absolute 1e-3 rejects a
    # table that is fine. A mixed-level product set, which is what this check
    # exists to catch, would be out by a whole aggregate.
    if published is not None and abs(got - published) > 1e-6 * abs(published):
        raise EurostatError(
            f"the {len(products)} populated products sum to {got:,.1f} against "
            f"a published total supply of {published:,.1f}: the set mixes "
            f"levels of the CPA hierarchy and would double count. "
            f"{len(aggregated_away)} aggregate(s) were already dropped.")

    # Industries: the bare codes that carry output in the use table.
    # `P` followed by a DIGIT is a final-demand category (`P3`, `P5`, `P6`).
    # Bare `P` is NACE section P, Education. Excluding everything starting with
    # "P" drops the education industry and leaves activity output 25,913 short
    # on Austria 2022 -- which the total check below then catches, but only
    # because it is there.
    industries = [j for j in use.index["ind_use"]
                  if j not in ("TOTAL", "TU", "TFU")
                  and not re.match(r"^P\d", j)
                  and use.at(ind_use=j, prd_ava="P1") is not None]
    industries, _ = _drop_aggregates(industries)   # France, Denmark: both levels
    g = np.array([use.at(ind_use=j, prd_ava="P1") for j in industries], float)
    published_g = use.at(ind_use="TOTAL", prd_ava="P1")
    if published_g is not None and abs(g.sum() - published_g) > 1e-6 * abs(published_g):
        raise EurostatError(
            f"the {len(industries)} populated industries' output sums to "
            f"{g.sum():,.1f} against a published {published_g:,.1f}; the set "
            f"mixes levels of the NACE hierarchy.")

    V = np.array([[sup.at(ind_impv=j, prd_amo=p) or 0.0 for j in industries]
                  for p in products], float)
    U = np.array([[use.at(ind_use=j, prd_ava=p) or 0.0 for j in industries]
                  for p in products], float)
    P = lambda c: np.array([sup.at(ind_impv=c, prd_amo=p) or 0.0
                            for p in products], float)
    imports, margins, taxes = P("P7"), P("OTTM"), P("D21X31")
    # Product output from Eurostat's OWN arithmetic -- published total supply
    # less published imports -- rather than from `V.sum(1)`. Every cell here is
    # rounded to two decimals, so each reconstruction step adds error: measured
    # on Austria 2022, `V.sum(1)` sits 0.06 from `TS_BP - P7`, and building the
    # purchasers'-price identity out of two reconstructions instead of one puts
    # it 0.10 out where the published aggregates are exact.
    q = P("TS_BP") - imports

    fd, dropped = [], []
    for alternatives in _FD_ALTERNATIVES:
        for cand in alternatives:
            if all(all(use.at(ind_use=c, prd_ava=p) is not None
                       for p in products) for c in cand):
                fd += cand
                dropped += [c for alt in alternatives for c in alt
                            if c not in cand]
                break
        else:
            raise EurostatError(f"none of {alternatives} is fully populated")
    Y = np.column_stack([[use.at(ind_use=c, prd_ava=p) for p in products]
                         for c in fd]).astype(float)
    W = np.array([[use.at(ind_use=j, prd_ava=r) or 0.0 for j in industries]
                  for r in _SUT_VA_ROWS], float)

    sut = SupplyUseTables(
        table_id=f"EUROSTAT-SUT-{geo}-{year}",
        country=str(sup.labels["geo"].get(geo, geo)), year=int(year),
        unit="million EUR, current prices",
        classification=f"CPA 2008 ({len(products)} products) x NACE Rev.2 "
                       f"({len(industries)} activities), derived from the data",
        product_codes=[p[4:] for p in products],
        product_labels=[str(sup.labels["prd_amo"].get(p, p)) for p in products],
        activity_codes=list(industries),
        activity_labels=[str(use.labels["ind_use"].get(j, j))
                         for j in industries],
        V=V, U=U, Y=Y, Y_labels=fd, W=W, W_labels=list(_SUT_VA_LABELS),
        imports=imports, total_margins=margins, taxes_on_products=taxes,
        q=q, g=g,
        source=f"Eurostat naio_10_cp15 + naio_10_cp16, {geo} {year}",
        retrieved_at=datetime.now(timezone.utc),
        notes=(f"Supply at basic prices and use at purchasers' prices, "
               f"{len(products)} products by {len(industries)} activities. "
               f"Trade and transport margins are published COMBINED as `OTTM`, "
               f"so `trade_margins` and `transport_margins` are None and ID-09 "
               f"cannot be asked of this source. Final demand uses "
               f"{', '.join(fd)}; {', '.join(dropped)} dropped as subtotals or "
               f"unpublished. THE METHOD DOES NOT TRAVEL WITH THE DATA."))

    # TWO KINDS OF CHECK, AND THE DIFFERENCE IS NOT PEDANTRY.
    #
    # The source's own aggregates satisfy the identity EXACTLY: published total
    # supply at purchasers' prices equals published total use, to 0.0000. Any
    # figure this loader rebuilds from components inherits Eurostat's two-decimal
    # rounding instead, and that is bounded, measured, and separate.
    exact = [("ID-01 published supply at purchasers' prices equals published "
              "total use", P("TS_PP"), np.array([use.at(ind_use="TU",
                                                        prd_ava=p)
                                                 for p in products], float))]
    # The allowance is DERIVED FROM THE NUMBER OF TERMS SUMMED, not picked. Each
    # cell is rounded to two decimals, so a sum of `k` of them can be out by
    # 0.005k in the worst case. A flat 0.05 was tried first and rejected the
    # table over `V.sum(1)`, which sums 65 industry cells and lands 0.06 out --
    # well inside its own 0.325 bound. The distinction that matters is that a
    # genuinely mixed-level product set would be out by thousands, not tenths.
    n_p, n_a = len(products), len(industries)
    rounded = [
        ("the rebuilt supply at purchasers' prices matches the published one",
         sut.supply_at_purchasers(), P("TS_PP"), 4),
        ("supply rows give product output", V.sum(1), q, n_a),
        ("supply columns give activity output", V.sum(0), g, n_p),
        ("intermediate consumption plus value added equals output",
         U.sum(0) + W.sum(0), g, n_p + len(_SUT_VA_ROWS)),
    ]
    for label, items, flat in (("as published", exact, TOL),
                               ("as rebuilt", rounded, None)):
        for item in items:
            what, a, b = item[0], item[1], item[2]
            tol = flat if flat is not None else 0.005 * item[3]
            d = float(np.abs(np.asarray(a, float) - np.asarray(b, float)).max())
            if d > tol:
                raise EurostatError(
                    f"{Path(supply_path).name} + {Path(use_path).name} do not "
                    f"balance and will not be loaded.\n  failed ({label}): "
                    f"{what}\n  off by {d:,.4f} (tolerance {tol:g}"
                    + (f", 0.005 x {item[3]} summed cells at two decimals)"
                       if flat is None else ")"))
    return sut
