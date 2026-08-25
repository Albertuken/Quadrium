"""
The five central objects of MVP 0.1, plus cell provenance.

This is the contract of the system: everything else uses these, not the reverse
(MVP_0.1_IO_Sector_Splitter.md §2).

TWO DEPARTURES FROM THE JUNE SPEC, both deliberate and both reversible
----------------------------------------------------------------------
1. **dataclasses, not Pydantic v2.** The spec chose Pydantic v2 (§0). The
   environment has Pydantic 1.10, and upgrading it inside a shared Anaconda
   install risks other packages for no gain at this scale: the validation the
   spec actually needs is shape checking and weight normalisation, and numpy
   arrays need `arbitrary_types_allowed` in Pydantic anyway. Swapping back is a
   mechanical change confined to this file.

2. **`balancing_method` defaults to GRAS, not RAS.** The spec (§1.7, §7) balances
   with RAS and puts GRAS out of scope. That cannot stand: RAS is defined only
   for non-negative matrices (CORE_012 Box 11.3, p. 345) and a real IO table has
   legitimate negatives in several blocks — margins offsetting to zero
   economy-wide, subsidies as negative taxes, inventory changes, valuables, the
   CIF/FOB adjustment (`library/specs/A_core_accounting_spec.md` §A.8.1). The
   project's own UK fixture has them in five distinct blocks. RAS is the special
   case of GRAS with no negatives, so nothing is lost. See `balancing.py`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import numpy as np

# The shortest string that counts as a quotation rather than as the number
# itself. PROJECT CHOICE: no source states one, and the job it does is to stop
# `quote="361.296"` passing as a citation of the sentence that prints it.
_MIN_QUOTE = 25


def _norm(s: str) -> str:
    """Whitespace- and quote-normalised text, for comparing a quote with a page.

    The same normalisation `check_citations.py` applies before matching a
    verbatim quote, and for the same reason: PDF extraction breaks lines
    wherever the column ended, so a quotation that is correct in the document
    is not character-identical to the extraction.
    """
    s = (s.replace("’", "'").replace("‘", "'")
         .replace("“", '"').replace("”", '"')
         .replace("–", "-").replace("—", "-").replace("­", ""))
    return re.sub(r"\s+", " ", s).strip().lower()


# ---------------------------------------------------------------------------
# Vocabularies
# ---------------------------------------------------------------------------

class ProxyStrength(str, Enum):
    STRONG = "strong"     # direct subsector data, high coverage
    MEDIUM = "medium"     # correlated but indirect proxy
    WEAK = "weak"         # weak proxy, last resort


class CellLabel(str, Enum):
    """Cell provenance, MVP minimal version (spec §2.6).

    Carried as a parallel object-dtype array of the same shape as Z, not as one
    object per cell.

    Each maps onto the project-wide data-status vocabulary of
    `library/specs/A_core_accounting_spec.md` §A.1, which is the authority. The
    mapping is stated so the two never drift:

        OBSERVED            -> OBSERVED
        PROXY_ESTIMATED     -> ESTIMATED
        BALANCED_ADJUSTMENT -> BALANCED
        USER_CONSTRAINT     -> OBSERVED, but pinned by the analyst rather than
                               by a source; recorded separately in the ledger
    """
    OBSERVED = "observed"
    PROXY_ESTIMATED = "proxy_estimated"
    BALANCED_ADJUSTMENT = "balanced_adjustment"
    USER_CONSTRAINT = "user_constraint"


DATA_STATUS = {
    CellLabel.OBSERVED: "OBSERVED",
    CellLabel.PROXY_ESTIMATED: "ESTIMATED",
    CellLabel.BALANCED_ADJUSTMENT: "BALANCED",
    CellLabel.USER_CONSTRAINT: "OBSERVED",
}


def label_mask(prov: np.ndarray, label: CellLabel) -> np.ndarray:
    """Elementwise `prov == label`. Numpy will not do this correctly itself.

    `CellLabel` subclasses `str`, so numpy converts the right-hand side to a
    `numpy.str_` and then compares the object-dtype elements against it by a
    path that never matches:

        a = np.empty((2, 2), dtype=object); a[:, :] = CellLabel.OBSERVED
        a[0, 0] == CellLabel.OBSERVED   ->  True
        a      == CellLabel.OBSERVED    ->  all False

    The scalar comparison is right and the array comparison is wrong, silently,
    and wrong in the direction that hides estimates: every count of untouched
    cells comes out as zero and reads as "nothing to report". Found on
    2026-08-25 by a counterfactual that measured a difference of zero where the
    engine's own tally said twelve.

    Anything comparing a provenance array against a label goes through here.
    `test_label_mask_beats_the_naive_comparison` keeps this from being tidied
    away as a redundant wrapper.
    """
    arr = np.asarray(prov, dtype=object)
    want = label.value
    flat = [(x if isinstance(x, str) else x.value) == want for x in arr.ravel()]
    return np.asarray(flat, dtype=bool).reshape(arr.shape)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 2.1 IOTable
# ---------------------------------------------------------------------------

@dataclass
class IOTable:
    """A symmetric IO table. The MVP does not distinguish supply-use.

    Balance conventions, which the validators enforce rather than assume:
        Z.sum(axis=1) + Y.sum(axis=1) == X      (row / product balance)
        Z.sum(axis=0) + VA.sum(axis=0) == X     (column / industry balance)
    """
    table_id: str
    country: str
    year: int
    unit: str                      # e.g. "million EUR, current prices"
    classification: str            # e.g. "NACE Rev.2"
    sector_codes: list[str]
    sector_labels: list[str]

    Z: np.ndarray                  # intermediate matrix (n x n)
    Y: np.ndarray                  # final demand (n x k)
    Y_labels: list[str]
    VA: np.ndarray                 # value added (m x n)
    VA_labels: list[str]
    X: np.ndarray                  # total output (n,)

    source: str
    retrieved_at: datetime = field(default_factory=_utcnow)
    notes: Optional[str] = None

    # WHAT THIS TABLE'S CELLS ALREADY ARE, when that is known: an n x n array
    # of `CellLabel`, parallel to Z. `None` means the table came from a
    # publisher and every cell is an observation as far as this system can
    # tell.
    #
    # It exists so a table produced by this engine can be read back into it.
    # Without it a second split treats the first split's estimates as
    # observations, and the audit trail resets to zero every time the file is
    # written and reopened -- the one thing an audit trail may not do.
    provenance: Optional[np.ndarray] = None

    # Where this table came from, one line per step, oldest first. A table read
    # from a statistical office has none; one written by this engine carries
    # its parent's and appends its own.
    lineage: list[str] = field(default_factory=list)

    # HOW FAR THE SOURCE WAS ALREADY OUT, carried rather than rediscovered.
    #
    # A table built from a source whose own books do not close inherits that,
    # and every downstream check would otherwise attribute it to this engine.
    # `run_scenario` measures it for a table it can see; a TRANSFORMED table
    # cannot be measured that way, because the transformation has already
    # redistributed the residue across a new axis. So the pair records what it
    # admitted and the table carries the number forward.
    inherited_residue: float = 0.0

    def __post_init__(self) -> None:
        self.Z = np.asarray(self.Z, float)
        self.Y = np.asarray(self.Y, float)
        self.VA = np.asarray(self.VA, float)
        self.X = np.asarray(self.X, float).ravel()
        n = len(self.sector_codes)
        if self.Z.shape != (n, n):
            raise ValueError(f"Z must be {n}x{n}, got {self.Z.shape}")
        if self.Y.shape[0] != n:
            raise ValueError(f"Y has {self.Y.shape[0]} rows, expected {n}")
        if self.VA.shape[1] != n:
            raise ValueError(f"VA has {self.VA.shape[1]} columns, expected {n}")
        if self.X.shape != (n,):
            raise ValueError(f"X must have length {n}, got {self.X.shape}")
        if len(self.sector_labels) != n:
            raise ValueError("sector_labels and sector_codes differ in length")
        if len(self.Y_labels) != self.Y.shape[1]:
            raise ValueError("Y_labels does not match Y columns")
        if len(self.VA_labels) != self.VA.shape[0]:
            raise ValueError("VA_labels does not match VA rows")
        if self.provenance is not None:
            self.provenance = np.asarray(self.provenance, dtype=object)
            if self.provenance.shape != (n, n):
                raise ValueError(
                    f"provenance must be {n}x{n} to sit parallel to Z, got "
                    f"{self.provenance.shape}")

    @property
    def derived(self) -> bool:
        """True when some cell of this table is not an observation.

        A table can be derived and still balance perfectly, which is exactly
        why this is worth asking: nothing in the numbers gives it away.
        """
        if self.provenance is None:
            return False
        return not bool(label_mask(self.provenance, CellLabel.OBSERVED).all())

    def provenance_counts(self) -> dict[str, int]:
        """How many cells of Z hold each data status (§A.1 vocabulary)."""
        out: dict[str, int] = {}
        if self.provenance is None:
            return {"OBSERVED": self.n * self.n}
        for lab in self.provenance.ravel():
            key = DATA_STATUS[CellLabel(lab if isinstance(lab, str) else lab.value)]
            out[key] = out.get(key, 0) + 1
        return out

    @property
    def n(self) -> int:
        return len(self.sector_codes)

    def index_of(self, code: str) -> int:
        try:
            return self.sector_codes.index(code)
        except ValueError:
            raise KeyError(f"sector {code!r} not in table {self.table_id!r}; "
                           f"available: {', '.join(self.sector_codes)}") from None

    def intermediate_row_totals(self) -> np.ndarray:
        """Total intermediate sales by sector = X - final demand."""
        return self.X - self.Y.sum(axis=1)

    def intermediate_col_totals(self) -> np.ndarray:
        """Total intermediate purchases by sector = X - value added."""
        return self.X - self.VA.sum(axis=0)


# ---------------------------------------------------------------------------
# 2.1b SupplyUseTables
# ---------------------------------------------------------------------------

@dataclass
class SupplyUseTables:
    """A supply table and a use table, before any transformation.

    NOT an `IOTable`. An IOT is symmetric — one classification on both axes —
    and a supply-use pair is products by ACTIVITIES, which is rectangular and
    is the form the data is actually collected in. Everything the engine does
    to an IOT it inherits from someone's decision about secondary production;
    this object is the thing that decision has not been applied to yet.

    WHY THE PROJECT WANTED ONE FOR SO LONG
    --------------------------------------
    `OQ-D-03`: an analytical IOT at basic prices has already had its trade and
    transport margins reallocated, so the margin identities — the place where
    the hardest sign problems live — could not be tested at all. `ID-01`,
    `ID-07` to `ID-10` and `ID-13` were reported NOT APPLICABLE rather than
    checked, and the entry says plainly that the project needs a supply-use pair
    as a second fixture.

    A supply table carries its valuation columns explicitly — trade margins,
    transport margins, taxes less subsidies on products — so those identities
    become arithmetic instead of aspiration.

    `V` and `U` are products by activities. The valuation vectors are by
    product. `W` is by activity, like an IOT's value-added block.
    """
    table_id: str
    country: str
    year: int
    unit: str
    classification: str

    product_codes: list[str]
    product_labels: list[str]
    activity_codes: list[str]
    activity_labels: list[str]

    V: np.ndarray                  # supply at basic prices, products x activities
    U: np.ndarray                  # use at purchasers' prices, products x activities
    Y: np.ndarray                  # final demand, products x k
    Y_labels: list[str]
    W: np.ndarray                  # value added, m x activities
    W_labels: list[str]

    imports: np.ndarray            # by product, CIF
    # Margins by product; each sums to zero economy-wide (ID-08). `total_margins`
    # is always present. The two components are OPTIONAL because not every
    # publisher separates them: the INE's own workbook gives trade and transport
    # in separate columns, Eurostat's `naio_10_cp15` gives only their sum as
    # `OTTM`. Filling the pair with the combined figure and a column of zeros
    # would be a lie the accounting could not detect, so a source that does not
    # separate them leaves them None and says so in `notes`.
    total_margins: np.ndarray
    taxes_on_products: np.ndarray  # by product, net of subsidies
    q: np.ndarray                  # product output at basic prices
    g: np.ndarray                  # activity output at basic prices

    source: str
    trade_margins: Optional[np.ndarray] = None
    transport_margins: Optional[np.ndarray] = None

    # ---- the blocks a transformation needs, and only some sources give -----
    #
    # `U` above is use at PURCHASERS' prices and undivided. A transformation
    # needs use at BASIC prices, split into what was produced at home and what
    # was imported, because the two behave differently in a Leontief system:
    # domestic demand pulls domestic output, imported demand leaves the economy.
    #
    # Eurostat publishes exactly that in `naio_10_cp1610`, on a `stk_flow`
    # dimension of TOTAL / DOM / IMP, so the split is READ and not assumed. It
    # matters that it is read: deriving it would mean the import-proportionality
    # assumption -- every user of a product imports the same share of it -- which
    # is a substantive economic hypothesis, not bookkeeping.
    #
    # Measured on Spain and Austria 2022, the blocks close both identities:
    #     q = U_domestic.rows + Y_domestic.rows
    #     g = U_domestic.cols + U_imported.cols + taxes_by_activity + W.cols
    # exactly for Spain, and to 0.10 for Austria against a rounding floor of
    # 0.34 -- Austria prints two decimals where Spain prints one.
    U_domestic: Optional[np.ndarray] = None      # products x activities, basic
    U_imported: Optional[np.ndarray] = None      # products x activities, basic
    Y_domestic: Optional[np.ndarray] = None      # products x k
    Y_imported: Optional[np.ndarray] = None      # products x k
    # Taxes less subsidies on products, BY ACTIVITY -- what carries each
    # industry's intermediate consumption from basic to purchasers' prices. Not
    # value added, and labelled as not, wherever it surfaces.
    taxes_by_activity: Optional[np.ndarray] = None
    # And by FINAL-USE column. The projection methods of UNH_18 ch. 18 take
    # taxes as one vector across industries AND final use -- `tls0` of length
    # n + k -- because that is the row of the use table they are. Measured on
    # Spain 2022: 18,993.1 across industries plus 102,154.9 across final use
    # is 121,148.0, the published total exactly.
    taxes_by_final_demand: Optional[np.ndarray] = None
    # What `unbalanced="cancelling"` let through, if anything: the largest
    # residue admitted, in the table's own units. Zero when nothing was.
    admitted_residue: float = 0.0

    retrieved_at: datetime = field(default_factory=_utcnow)
    notes: Optional[str] = None

    @property
    def transformable(self) -> bool:
        """Whether this pair carries what a SUT->IOT transformation needs."""
        return all(x is not None for x in
                   (self.U_domestic, self.U_imported, self.Y_domestic,
                    self.Y_imported, self.taxes_by_activity))

    def _live(self):
        """Products and industries that produce anything, and what was dropped.

        Every method here divides by output: a transformation to form
        coefficients, a projection to form market shares. A sector producing
        nothing has neither, and Eurostat publishes one in every country --
        `U`, extraterritorial organisations, with zero output.

        The two axes are masked by their OWN output, because a supply-use pair
        is rectangular in general and masking both by one vector is what the
        model validators had to stop doing when France arrived at 89 x 88.
        """
        import numpy as _np
        keep_p, keep_a = self.q > 0, self.g > 0
        dropped = sorted(
            {c for c, k in zip(self.product_codes, keep_p) if not k}
            | {c for c, k in zip(self.activity_codes, keep_a) if not k})
        return _np.flatnonzero(keep_p), _np.flatnonzero(keep_a), dropped

    @property
    def projectable(self) -> bool:
        """Whether this pair carries what UNH_18 ch. 18's methods need."""
        return self.transformable and self.taxes_by_final_demand is not None

    def project(self, *, gva, final_use, taxes, imports,
                method: str = "sut_euro", year: int | None = None
                ) -> "SupplyUseTables":
        """Project this pair onto a later year's totals. UNH_18 ch. 18.

        WHAT THIS IS FOR, AND WHY IT IS A SECOND VERB
        -----------------------------------------------
        Everything else this engine does takes a table and makes it finer. This
        takes a table and moves it in TIME: a detailed pair for a base year,
        plus whatever is known about a later one -- value added by industry,
        final use by category, and two totals -- and it produces a full pair
        consistent with them.

        That is what a statistical office does between benchmark years, and
        what an analyst does to ask "if output looks like this in 2026, what
        does the table look like?". The three methods UNH_18 ch. 18 specifies
        have been implemented and verified against the chapter's own printed
        iterations since v1.5 and v1.66, and until 2026-08-25 there was no
        operation in this engine that projected anything at all.

        THE RESULT IS AN ESTIMATE AND SAYS SO
        ---------------------------------------
        Every cell is BALANCED in the sense of §A.1: the base year's structure
        carried onto the target year's totals. Nothing in it was observed for
        the target year except the totals you supplied.

        Parameters
        ----------
        gva : (n,)         value added by industry, at BASIC prices
        final_use : (k,)   totals by final-use category, at PURCHASERS' prices
        taxes : float      total taxes less subsidies on products
        imports : float    total imports
        method : str       `sut_euro` (default) or `sut_ras`

        THE PRICE BASIS OF `final_use` IS NOT A DETAIL. The method carries
        taxes as a row of the use table, so a final-use target must include
        them — purchasers' prices, which is how national accounts publish
        household consumption and exports anyway.

        This is checkable and was checked: projecting a pair onto its OWN
        totals must return that pair. With the target at purchasers' prices it
        does, in ONE iteration, with every deviation exactly 1.0 and
        `max|Ud − Ud₀| = 0.0000`. With it at basic prices the same call runs to
        the 200-iteration ceiling, never converges, and parks 380 away — and
        every value-added deviation reads 1.00003, which looks like success.
        The identity test is what tells the two apart.
        """
        import numpy as _np

        if not self.projectable:
            raise ValueError(
                "this pair carries no domestic/imported split at basic prices "
                "with taxes by column, so it cannot be projected. For Eurostat "
                "that means `naio_10_cp1610` was not loaded alongside.")

        method = str(method).strip().lower()
        n, k = len(self.activity_codes), len(self.Y_labels)
        gva = _np.asarray(gva, float).ravel()
        final_use = _np.asarray(final_use, float).ravel()
        if gva.size != n or final_use.size != k:
            raise ValueError(
                f"this pair has {n} industries and {k} final-use categories, "
                f"and {gva.size} value-added and {final_use.size} final-use "
                f"targets were given. A projection onto totals that do not "
                f"match the table is not a projection.")

        pi, ai, dropped = self._live()
        Ud0 = _np.hstack([self.U_domestic[_np.ix_(pi, ai)],
                          self.Y_domestic[pi]])
        Um0 = _np.hstack([self.U_imported[_np.ix_(pi, ai)],
                          self.Y_imported[pi]])
        tls0 = _np.concatenate([self.taxes_by_activity[ai],
                                self.taxes_by_final_demand])
        gva, n = gva[ai], len(ai)

        if method == "sut_euro":
            from .sut_euro import sut_euro
            r = sut_euro(Ud0, Um0, tls0, self.V[_np.ix_(pi, ai)].T,
                         va_target=gva, final_use_target=final_use,
                         tls_target=float(taxes),
                         imports_target=float(imports))
            # `r.V` is industries x products and `r.x` is industry output --
            # taken from the result rather than rebuilt, because rebuilding is
            # how a rounding residue becomes a second opinion.
            Ud, Um, V_ip, g_new = r.Ud, r.Um, r.V, r.x
            # `r.tls` is the PROJECTED taxes by column, and `r.gva` the
            # projected value added. Carrying the base year's forward instead
            # left the transformed table's column identity 576 out on a
            # +2 % tax target -- rows exact, columns not, which is the
            # signature of a value-added block that did not move with the
            # rest of the table.
            tls_new, gva_new = r.tls.ravel(), r.gva.ravel()
            note = (f"SUT-EURO, UNH_18 ¶18.89–18.102, pp. 575–577. Converged "
                    f"in {r.iterations} iteration(s) on the chapter's own "
                    f"1 per cent rule.")
        elif method == "sut_ras":
            raise ValueError(
                "SUT-RAS is implemented and verified in `sut_ras.py` against "
                "the chapter's printed iterations, and is not wired here. It "
                "takes a DIFFERENT set of targets -- industry outputs, use "
                "column totals and total imports-plus-taxes (¶18.86, "
                "pp. 571–573) -- not value added and final use, so exposing it "
                "means a second target vocabulary rather than a second name "
                "for this one. Recorded rather than half-done.")
        else:
            raise ValueError(
                f"method {method!r} is not one of: sut_euro, sut_ras")

        # `Ud` and `Um` already carry the final-use columns, so a row sum of
        # each IS product output and imports respectively -- the same two
        # identities `load_sut` checks on the way in.
        q_new = Ud.sum(axis=1)
        imports_new = Um.sum(axis=1)
        label = year if year is not None else self.year

        return SupplyUseTables(
            table_id=f"{self.table_id}::projected-{label}",
            country=self.country, year=int(label), unit=self.unit,
            classification=self.classification,
            product_codes=[self.product_codes[i] for i in pi],
            product_labels=[self.product_labels[i] for i in pi],
            activity_codes=[self.activity_codes[i] for i in ai],
            activity_labels=[self.activity_labels[i] for i in ai],
            V=V_ip.T,
            U=Ud[:, :n] + Um[:, :n],
            Y=Ud[:, n:] + Um[:, n:], Y_labels=list(self.Y_labels),
            W=gva_new.reshape(1, n), W_labels=["Value added"],
            imports=imports_new, total_margins=self.total_margins[pi],
            taxes_on_products=self.taxes_on_products[pi],
            q=q_new, g=g_new,
            U_domestic=Ud[:, :n], U_imported=Um[:, :n],
            Y_domestic=Ud[:, n:], Y_imported=Um[:, n:],
            taxes_by_activity=tls_new[:n], taxes_by_final_demand=tls_new[n:],
            source=f"{self.source}, projected to {label}",
            notes=(f"PROJECTED, NOT OBSERVED. The {self.year} pair's structure "
                   f"carried onto {label} totals by {note} Nothing here was "
                   f"measured for {label} except the value added, final use, "
                   f"taxes and imports totals that were supplied."
                   + (f" Dropped for having no base-year output, which leaves "
                      f"a market share undefined: {', '.join(dropped)}."
                      if dropped else "")))

    def to_iot(self, model: str = "D") -> "IOTable":
        """Transform this pair into a symmetric table, by one named model.

        WHY THE MODEL IS AN ARGUMENT AND NOT A DEFAULT DECISION
        --------------------------------------------------------
        A supply-use pair is what the data is collected as. An input-output
        table is what someone's assumption about secondary production turns it
        into, and the four assumptions are not interchangeable. CORE_013 Figure
        12.2, p. 378 sets them out; `run_model_choice.py` measured what the
        choice costs on four national tables and found model A's negatives
        spanning a factor of fourteen between France and the Netherlands.

        So the caller names the model, the report records it, and nothing here
        picks one quietly. `D` is the argument's default only because CORE_013
        par. 12.76, p. 393 recommends it for rectangular tables and it needs no
        square supply matrix -- but a default is not a recommendation, and the
        note on the returned table says which model produced it.

        WHAT THE RESULT IS, AND IS NOT
        --------------------------------
        A DOMESTIC table. `Z` is domestic intermediate flows, `Y` domestic final
        use, and the imported block becomes a single row of value added marked
        `not value added`, exactly as the ONS and INE loaders do it, so the
        column identity closes the same way everywhere in this engine.

        Every cell is `BALANCED` in the sense of §A.1: none of it was observed
        as a symmetric flow, because no such observation exists. That is what
        `provenance` carries out of here.
        """
        import numpy as _np

        from .transformation import MODELS, transform

        if not self.transformable:
            raise ValueError(
                "this supply-use pair carries no domestic/imported split at "
                "basic prices, so it cannot be transformed. For Eurostat that "
                "means `naio_10_cp1610` was not loaded beside `naio_10_cp15` "
                "and `naio_10_cp16`. Deriving the split instead would impose "
                "the import-proportionality assumption, which is an economic "
                "hypothesis this engine will not make on your behalf.")

        model = str(model).strip().upper()

        # SECTORS WITH NO OUTPUT COME OUT FIRST, and this is not tidying.
        # Every model divides by output to form a coefficient matrix, so a
        # sector producing nothing has no technology to describe and makes the
        # division undefined. Eurostat's tables carry one: `U`, extraterritorial
        # organisations, which is published with zero output in every country
        # here. It is dropped, counted, and named in the note on the result.
        #
        # The two axes are masked by their OWN output, because a supply-use
        # system is rectangular in general -- France publishes 89 products
        # against 88 activities -- and masking both by one vector is what those
        # three model validators had to stop doing.
        keep_p = self.q > 0
        keep_a = self.g > 0
        dropped = ([c for c, k in zip(self.product_codes, keep_p) if not k]
                   + [c for c, k in zip(self.activity_codes, keep_a) if not k])
        pi, ai = _np.flatnonzero(keep_p), _np.flatnonzero(keep_a)
        ix = _np.ix_(pi, ai)

        r = transform(model, self.V[ix], self.U_domestic[ix],
                      self.U_imported[ix],
                      self.Y_domestic[pi], self.Y_imported[pi],
                      _np.vstack([self.taxes_by_activity, self.W])[:, ai],
                      self.g[ai], self.q[pi])

        product_axis = MODELS[model][1].startswith("product")
        idx = pi if product_axis else ai
        src_codes = self.product_codes if product_axis else self.activity_codes
        src_labels = (self.product_labels if product_axis
                      else self.activity_labels)
        codes = [src_codes[i] for i in idx]
        labels = [src_labels[i] for i in idx]
        X = (self.q if product_axis else self.g)[idx]

        # A PRODUCT NOBODY MAKES AT HOME IS STILL BOUGHT, and dropping it
        # from the product axis must not drop what it was bought for.
        #
        # `_live()` removes products with no domestic output, because a
        # symmetric domestic table has no row for something no domestic
        # industry produces and every model divides by that output. But the
        # IMPORTED use of such a product is real, and it belongs in the
        # imported-use row exactly as any other import does.
        #
        # Belgium 2022 is the case that found this: `B06`, crude petroleum and
        # natural gas, has zero domestic output and 20,342 of imports, of which
        # 20,238 goes to `C19`, refining. Masked away, C19's column lost 20,210
        # and the column identity failed by that much. Spain has no wholly
        # imported product, so nothing showed there.
        # THE TWO FAMILIES APPLY `T` FROM OPPOSITE SIDES, so the imported row
        # is built differently for each -- and only one of them needs `T` at
        # all.
        #
        #   A, B, E (product axis):  Sm = Um @ T, so the row is the full
        #       imported use summed over products and then transformed.
        #   C, D (industry axis):    Sm = T @ Um with T a market-share matrix
        #       whose columns sum to 1, so `(T @ Um).sum(0) == Um.sum(0)`
        #       exactly: the transformation PRESERVES column totals and the
        #       plain sum over all products is already the answer.
        #
        # Getting this wrong is not subtle in its effect and is very subtle in
        # its appearance: `@ T` on the industry axis silently produced column
        # residues of 3,175 for Spain, a table that closes to 0.0000 when it is
        # right.
        dead_p = _np.flatnonzero(~keep_p)
        imported_by_activity = self.U_imported[:, ai].sum(axis=0)
        imported_row = (imported_by_activity @ r.T
                        if MODELS[model][1].startswith("product")
                        else imported_by_activity)
        stranded = (float(self.U_domestic[_np.ix_(dead_p, ai)].sum())
                    if dead_p.size else 0.0)
        if abs(stranded) > 1e-6:
            raise ValueError(
                f"{stranded:,.1f} of DOMESTIC use is recorded against "
                f"product(s) with no domestic output at all: "
                f"{', '.join(self.product_codes[i] for i in dead_p)}. That is "
                f"not a rounding residue and not something this engine will "
                f"redistribute on its own.")

        # `E`'s first row is the taxes vector that was stacked on top of `W`,
        # so it rides through the same transformation as everything else on the
        # industry axis rather than being carried across unchanged.
        VA = _np.vstack([imported_row, r.E])
        VA_labels = ["Use of imported products (not value added)",
                     "Taxes less subsidies on products (not value added)"]
        VA_labels += list(self.W_labels)

        prov = _np.empty((len(codes), len(codes)), dtype=object)
        prov[:, :] = CellLabel.BALANCED_ADJUSTMENT

        return IOTable(
            table_id=f"{self.table_id}::model-{model}",
            country=self.country, year=self.year, unit=self.unit,
            classification=f"{self.classification}, transformed to "
                           f"{MODELS[model][1]} by model {model}",
            sector_codes=list(codes), sector_labels=list(labels),
            Z=r.Sd, Y=r.Yd, Y_labels=list(self.Y_labels), VA=VA,
            VA_labels=VA_labels, X=X,
            source=self.source,
            provenance=prov, inherited_residue=self.admitted_residue,
            lineage=[f"{self.table_id}: supply-use pair transformed to "
                     f"{MODELS[model][1]} by model {model} "
                     f"({MODELS[model][0]})"],
            notes=(f"NOT AN OBSERVED TABLE. A supply-use pair transformed by "
                   f"model {model}, {MODELS[model][0]}, on the "
                   f"{MODELS[model][1]} axis. The four models of CORE_013 "
                   f"Figure 12.2, p. 378 embody four different assumptions "
                   f"about secondary production and give four different "
                   f"tables from the same data; which one is right is not a "
                   f"question the data answers. "
                   + (f"{r.n_negatives} negative cell(s) were produced, which "
                      f"model {model} may do. " if r.n_negatives else
                      f"No negative cells were produced. ")
                   + (f"Dropped for having no domestic output, which leaves a "
                      f"coefficient undefined: {', '.join(sorted(set(dropped)))}"
                      + (f"; their imported use, "
                         f"{float(self.U_imported[_np.ix_(dead_p, ai)].sum()):,.1f}, is kept "
                         f"in the imported-use row, because a product nobody "
                         f"makes at home is still bought"
                         if dead_p.size and self.U_imported[_np.ix_(dead_p, ai)].sum() > 1e-6 else "")
                      + ". " if dropped else "")
                   + " ".join(r.notes)))

    def __post_init__(self) -> None:
        for name in ("V", "U", "Y", "W", "imports", "total_margins",
                     "taxes_on_products", "q", "g", "trade_margins",
                     "transport_margins"):
            v = getattr(self, name)
            if v is not None:
                setattr(self, name, np.asarray(v, float))
        n_p, n_a = len(self.product_codes), len(self.activity_codes)
        for name, want in (("V", (n_p, n_a)), ("U", (n_p, n_a))):
            if getattr(self, name).shape != want:
                raise ValueError(f"{name} must be {want}, got "
                                 f"{getattr(self, name).shape}")
        if self.Y.shape[0] != n_p:
            raise ValueError(f"Y has {self.Y.shape[0]} rows, expected {n_p}")
        if self.W.shape[1] != n_a:
            raise ValueError(f"W has {self.W.shape[1]} columns, expected {n_a}")
        for name, want in (("imports", n_p), ("total_margins", n_p),
                           ("taxes_on_products", n_p), ("q", n_p), ("g", n_a),
                           ("trade_margins", n_p), ("transport_margins", n_p)):
            v = getattr(self, name)
            if v is not None and v.shape != (want,):
                raise ValueError(f"{name} must have length {want}")
        if (self.trade_margins is not None
                and self.transport_margins is not None):
            gap = float(np.abs(self.trade_margins + self.transport_margins
                               - self.total_margins).max())
            if gap > 1e-3:
                raise ValueError(
                    f"trade + transport margins differ from total_margins by "
                    f"{gap:,.4f}; the components and their total must agree")
        if len(self.product_labels) != n_p or len(self.activity_labels) != n_a:
            raise ValueError("labels and codes differ in length")
        if len(self.Y_labels) != self.Y.shape[1]:
            raise ValueError("Y_labels does not match Y columns")
        if len(self.W_labels) != self.W.shape[0]:
            raise ValueError("W_labels does not match W rows")

    @property
    def n_products(self) -> int:
        return len(self.product_codes)

    @property
    def n_activities(self) -> int:
        return len(self.activity_codes)

    def supply_at_purchasers(self) -> np.ndarray:
        """q + imports + margins + taxes, by product."""
        return (self.q + self.imports + self.total_margins
                + self.taxes_on_products)

    def use_at_purchasers(self) -> np.ndarray:
        """Intermediate plus final, by product."""
        return self.U.sum(axis=1) + self.Y.sum(axis=1)

    def index_of_product(self, code: str) -> int:
        try:
            return self.product_codes.index(code)
        except ValueError:
            raise KeyError(f"product {code!r} not in {self.table_id!r}") from None


# ---------------------------------------------------------------------------
# 2.2 AllocationKey
# ---------------------------------------------------------------------------

VALID_BLOCKS = ("output", "value_added", "final_demand",
                "intermediate_rows", "intermediate_cols")


@dataclass
class AllocationKey:
    """The auxiliary variable used to split the aggregate sector."""
    key_id: str
    applies_to: str
    new_sector_codes: list[str]
    raw_values: list[float]
    source: str
    source_year: int
    strength: ProxyStrength
    weights: Optional[list[float]] = None
    retrieved_at: datetime = field(default_factory=_utcnow)
    notes: Optional[str] = None
    # How this key came to speak for its `source_year`, when it was not simply
    # measured in it. Set by `key_from_series`; None means "measured".
    vintage: Optional[dict] = None

    def __post_init__(self) -> None:
        if self.applies_to not in VALID_BLOCKS:
            raise ValueError(f"applies_to={self.applies_to!r} not one of "
                             f"{VALID_BLOCKS}")
        if len(self.raw_values) != len(self.new_sector_codes):
            raise ValueError(f"AllocationKey {self.key_id}: "
                             f"{len(self.raw_values)} values for "
                             f"{len(self.new_sector_codes)} subsectors")
        if self.weights is None:
            self.normalize()

    def normalize(self) -> "AllocationKey":
        """Shares, and therefore every value must be non-negative.

        The `total <= 0` guard alone is not enough, and real data proves it.
        Spanish hospitality in 2020 had gross operating surplus of -1,838,308
        thousand EUR in accommodation against +231,683 in food service. That
        particular pair sums negative and was already refused — but flip the
        signs, or split a different pair, and the sum is positive while a
        component is not. `[1000, -100]` normalises to `[1.111, -0.111]` and
        used to be ACCEPTED, which would have handed a subsector -11 % of a
        block.

        A share of a variable that changes sign is not a share. Operating
        surplus, changes in inventories and net taxes all change sign in
        ordinary years, so this is a routine input, not an exotic one.
        """
        vals = [float(v) for v in self.raw_values]
        neg = [(c, v) for c, v in zip(self.new_sector_codes, vals) if v < 0]
        if neg:
            raise ValueError(
                f"AllocationKey {self.key_id}: negative raw value(s) "
                + ", ".join(f"{c}={v:,.1f}" for c, v in neg)
                + ". A key is a SHARE, and a share of a quantity that changes "
                  "sign is not a share — normalising this would give one "
                  "subsector a negative fraction of its block. Pick a variable "
                  "that cannot go negative (output, employment, compensation), "
                  "or state the split some other way.")
        total = float(sum(vals))
        if total <= 0:
            raise ValueError(f"AllocationKey {self.key_id}: raw_values sum "
                             f"to {total} <= 0")
        self.weights = [v / total for v in vals]
        return self

    def vintage_gap(self, table_year: int) -> int:
        """Years between what this key measures and what the table measures.

        Positive means the key is NEWER than the table.
        """
        return int(self.source_year) - int(table_year)

    @property
    def w(self) -> np.ndarray:
        return np.asarray(self.weights, float)


def key_from_series(key_id: str, applies_to: str, new_sector_codes: list[str],
                    values_by_year: dict[int, list[float]], target_year: int,
                    source: str, strength: "ProxyStrength",
                    notes: Optional[str] = None) -> AllocationKey:
    """Build a key for `target_year` from a proxy measured in several years.

    This is the answer to "the figure exists for x+1 but not for x". It has one
    idea behind it: **a key is a share, not a level.** The engine normalises
    `raw_values` away, so nothing about prices, inflation or growth survives
    into the result. The only question that matters is whether the SHARE moved,
    and shares are far steadier than the levels they come from.

    So the interpolation is done on the shares, not on the levels. Interpolating
    levels and normalising afterwards weights the answer by each year's total,
    which imports exactly the growth the share was supposed to have cancelled.

    Three cases, and the third is the one with teeth:

    `target_year` is present
        Used as measured. `vintage["method"] == "observed"`.

    `target_year` lies between two measured years
        Linear interpolation of the shares. Recorded as DERIVED, with both
        years named.

    `target_year` lies outside the measured range
        The **nearest** year is used as it stands, and `source_year` keeps that
        year so the vintage check still fires. **No trend is extrapolated**,
        and the refusal is not fastidiousness. Spanish hospitality, share of
        accommodation in output: 34.6 % in 2019, 22.7 % in 2020, 27.3 % in
        2021. Any trend fitted before 2020 points the wrong way through it, and
        one fitted through 2020-2021 points the wrong way out of it. A series
        long enough to fit a trend to is a series long enough to contain a
        break.

    `vintage["max_yoy_share_move_pp"]` carries the largest year-on-year move in
    the first subsector's share across the whole supplied series, in percentage
    points. It is the empirical answer to "does the vintage matter for THIS
    key", measured on the analyst's own data instead of against a rule of
    thumb. For the same Spanish source it is 1.9 pp for employment and 21.0 pp
    for value added — same two subsectors, same years.
    """
    if not values_by_year:
        raise ValueError(f"AllocationKey {key_id}: values_by_year is empty")
    years = sorted(int(y) for y in values_by_year)
    shares: dict[int, np.ndarray] = {}
    for y in years:
        v = np.asarray(values_by_year[y], float)
        if v.size != len(new_sector_codes):
            raise ValueError(f"AllocationKey {key_id}: year {y} has {v.size} "
                             f"values for {len(new_sector_codes)} subsectors")
        if np.any(v < 0) or v.sum() <= 0:
            raise ValueError(
                f"AllocationKey {key_id}: year {y} cannot be made into shares "
                f"({list(v)}). See AllocationKey.normalize.")
        shares[y] = v / v.sum()

    moves = [abs(shares[b][0] - shares[a][0]) * 100.0
             for a, b in zip(years, years[1:])]
    vintage = {"years_available": years,
               "max_yoy_share_move_pp": round(max(moves), 3) if moves else None}

    if target_year in shares:
        w, vintage["method"], vintage["years_used"] = (
            shares[target_year], "observed", [target_year])
        eff_year = target_year
    elif years[0] < target_year < years[-1]:
        lo = max(y for y in years if y < target_year)
        hi = min(y for y in years if y > target_year)
        t = (target_year - lo) / (hi - lo)
        w = (1.0 - t) * shares[lo] + t * shares[hi]
        vintage.update(method="interpolated", years_used=[lo, hi],
                       weight_on_later=round(t, 6))
        eff_year = target_year
    else:
        near = min(years, key=lambda y: abs(y - target_year))
        w = shares[near]
        vintage.update(method="nearest_year", years_used=[near],
                       refused="extrapolation — see key_from_series docstring")
        eff_year = near

    return AllocationKey(
        key_id=key_id, applies_to=applies_to,
        new_sector_codes=list(new_sector_codes),
        raw_values=[float(x) for x in w], weights=[float(x) for x in w],
        source=source, source_year=eff_year, strength=strength,
        notes=notes, vintage=vintage)


# The value as the report prints it: 361.296, 361,296, 361296 or 34.6. Grouping
# separators differ by country and the same document uses one of them, so the
# comparison is made on digits alone after the separators are removed.
#
# WHITESPACE IS NOT A SEPARATOR HERE, and the first version had it as one. A
# quoted table row is a line of numbers separated by spaces, so allowing a space
# to group digits made the whole row ONE token -- and then no single figure in
# it could ever be matched. It refused the first real quote it was given.
_DIGITS = re.compile(r"[0-9]+(?:[.,][0-9]+)*")


def _as_printed(value: float, text: str) -> bool:
    """Does `value` occur in `text` as a number a human would read that way?"""
    want = f"{value:.10g}"
    want_digits = want.replace(".", "").replace("-", "").lstrip("0") or "0"
    for m in _DIGITS.finditer(text):
        got = m.group(0)
        # 361.296 is three hundred sixty-one thousand in this document and
        # 361.296 exactly in another. Accept either reading of the separators
        # rather than guessing the locale: both readings are checked against
        # the digits the caller supplied.
        for cleaned in (re.sub(r"[.,\s]", "", got),
                        got.replace(".", "").replace(" ", "").replace(",", ".")):
            digits = cleaned.replace(".", "").lstrip("0") or "0"
            if digits == want_digits:
                return True
    return False


def key_from_report(key_id: str, applies_to: str, new_sector_codes: list[str],
                    figures: list[tuple[float, int, str]], source_id: str,
                    source_year: int, strength: "ProxyStrength",
                    verifier=None, notes: Optional[str] = None
                    ) -> AllocationKey:
    """Build a key from figures read out of a REPORT rather than a dataset.

    Authorised by the project owner on 2026-08-13, closing the last live item of
    `OQ-B-14`: when the dataset for the year does not exist, the engine may take
    the figure from a published report. `key_from_series` already answers "the
    figure exists for x+1 but not for x"; this answers "the figure exists only
    in prose".

    THE POINT IS NOT THE READING. IT IS WHAT THE READING MUST CARRY.
    -----------------------------------------------------------------
    A number lifted out of a document is the easiest thing in this project to
    get wrong and the hardest to notice afterwards, because it arrives looking
    exactly like a number from a dataset. So a report-sourced key is admitted
    only with the same apparatus the specs' own citations carry:

    `figures` is one `(value, page, quote)` per subsector, and

      * **the value must appear in its own quote.** Not near it, not on the
        page — in the sentence being quoted. This is the guard against the
        failure that matters: attributing a figure to a source that does not
        state it. Separators are normalised, so `361.296`, `361,296` and
        `361296` all match 361296.
      * **the quote must be a quote**, not the bare number: at least
        `_MIN_QUOTE` characters, so the anchor identifies a location a human
        can check.
      * **`verifier(source_id, page) -> str`, when supplied, must return the
        text of that page**, and every quote is checked to occur on the page it
        claims. `src/` does not know the library's layout, so the caller
        supplies it; `validation.check_report_keys` treats a key that was never
        verified as an ERROR, because an unverified quotation is exactly the
        thing this project refuses.

    The result is an ordinary `AllocationKey` — it normalises, it refuses
    negatives, and `check_key_vintage` still fires on `source_year`, because a
    figure read out of a report is no fresher than the report.
    """
    if len(figures) != len(new_sector_codes):
        raise ValueError(f"AllocationKey {key_id}: {len(figures)} figures for "
                         f"{len(new_sector_codes)} subsectors")
    values, pages, quotes = [], [], []
    for code, item in zip(new_sector_codes, figures):
        value, page, quote = float(item[0]), int(item[1]), str(item[2])
        if len(quote.strip()) < _MIN_QUOTE:
            raise ValueError(
                f"AllocationKey {key_id}: the quote for {code} is "
                f"{len(quote.strip())} characters. A number is not a citation "
                f"— quote enough of {source_id} p. {page} that a reader can "
                f"find it.")
        if not _as_printed(value, quote):
            raise ValueError(
                f"AllocationKey {key_id}: {code} = {value:,.10g} does not "
                f"appear in the quote it claims to come from "
                f"({source_id} p. {page}: {quote.strip()[:60]!r}...). Either "
                f"the figure was derived rather than read, in which case say "
                f"so and record the derivation, or it is wrong.")
        if verifier is not None:
            page_text = verifier(source_id, page)
            if _norm(quote) not in _norm(page_text or ""):
                raise ValueError(
                    f"AllocationKey {key_id}: the quote for {code} is not on "
                    f"{source_id} p. {page}. The citation is wrong, and a "
                    f"wrong citation on a right number is still a wrong "
                    f"citation.")
        values.append(value)
        pages.append(page)
        quotes.append(quote.strip())

    vintage = {"method": "report", "source_id": source_id, "pages": pages,
               "quotes": quotes, "verified": verifier is not None,
               "years_available": [source_year],
               "max_yoy_share_move_pp": None}
    return AllocationKey(
        key_id=key_id, applies_to=applies_to,
        new_sector_codes=list(new_sector_codes),
        raw_values=values, source=f"{source_id} (report)",
        source_year=source_year, strength=strength, notes=notes,
        vintage=vintage)


# ---------------------------------------------------------------------------
# 2.2b SplitSpec — one sector to divide, and how
# ---------------------------------------------------------------------------

@dataclass
class ProfileProvenance:
    """Where an input profile came from. OQ-B-13.

    An `AllocationKey` has carried a source, a year and a strength since the
    first version, and the report prints all three, refuses to corroborate with
    a weak one, and says whether a block chose its key or inherited it. An input
    profile — the statement that restaurants buy more food and hotels more
    premises — carried none of that. It was a bare `dict[str, float]`, so a
    profile derived from an official survey and a profile someone guessed
    reached the reader identically labelled.

    That is the same failure the project already fixed one level up, where an
    inherited key looked exactly like a chosen one.

    Attaching this does NOT make a profile verifiable. Nothing in the engine can
    check a purchasing pattern against anything — that limitation is real and
    the report still says so. What it makes possible is telling a sourced
    profile from an unsourced one, which is a different and lower bar, and the
    one the project was failing.
    """
    source: str
    source_year: int
    strength: "ProxyStrength"
    notes: Optional[str] = None
    # Set by `neutralise_profile()`: how far the raw intensities moved each
    # subsector's total purchases before the level was corrected out.
    level_shift_before: Optional[float] = None


@dataclass
class SplitSpec:
    """One sector to divide, with the keys and profiles that govern it.

    Added when the engine learned to split several sectors in one run. A single
    `Scenario` can now carry several of these, each with its own allocation keys
    and its own input profiles, because "split hotels by employment and split
    transport by vehicle-kilometres" is a perfectly ordinary request and forcing
    one key set on both would be wrong.

    `keys_by_block` and `input_profiles` override the scenario's own; anything
    left unset falls back to the scenario, which keeps the single-split case as
    short as it was.
    """
    sector_code: str
    new_codes: list[str]
    new_labels: list[str]
    keys_by_block: dict[str, str] = field(default_factory=dict)
    input_profiles: dict[str, dict[str, float]] = field(default_factory=dict)
    # Per-ROW keys for the value-added block, and the row that absorbs what they
    # leave over. See OQ-B-12: the block used to split by one scalar per
    # subsector, so a survey that measures compensation and operating surplus
    # separately could not be used at all.
    va_row_keys: dict[str, str] = field(default_factory=dict)
    va_residual_row: Optional[str] = None
    # Where `input_profiles` came from. None means unsourced, and the report
    # says so rather than leaving the reader to assume either way. OQ-B-13.
    profile_provenance: Optional[ProfileProvenance] = None

    def __post_init__(self) -> None:
        if len(self.new_codes) != len(self.new_labels):
            raise ValueError(f"{self.sector_code}: {len(self.new_codes)} codes "
                             f"against {len(self.new_labels)} labels")
        if len(self.new_codes) < 2:
            raise ValueError(f"{self.sector_code}: splitting into "
                             f"{len(self.new_codes)} is not a disaggregation")
        if len(set(self.new_codes)) != len(self.new_codes):
            raise ValueError(f"{self.sector_code}: duplicate new codes")
        if self.va_row_keys and not self.va_residual_row:
            raise ValueError(
                f"{self.sector_code}: va_row_keys names "
                f"{', '.join(sorted(self.va_row_keys))} but no "
                f"va_residual_row. Pinning some value-added rows leaves the "
                f"rest to make up the block total, and which row absorbs it is "
                f"an economic judgement — usually gross operating surplus, "
                f"because it is the residual in the accounts too. The engine "
                f"will not choose it for you.")
        if self.va_residual_row and self.va_residual_row in self.va_row_keys:
            raise ValueError(
                f"{self.sector_code}: {self.va_residual_row!r} is named both as "
                f"a pinned row and as the residual. It can be one or the other.")


# ---------------------------------------------------------------------------
# 2.3 Scenario
# ---------------------------------------------------------------------------

@dataclass
class Scenario:
    scenario_id: str
    label: str
    # block -> key_id, as a DEFAULT for splits that name none of their own.
    # Optional since each SplitSpec can carry its own keys, which is the normal
    # case once more than one sector is being divided.
    keys_by_block: dict[str, str] = field(default_factory=dict)
    description: Optional[str] = None

    # PROJECT CHOICE. No loaded source states a numerical tolerance for an
    # accounting identity -- see D_open_questions.md OQ-B-02, still open after
    # both CORE_012 and UNH_18. UNH_18 par. 18.81, p. 569 does give a solver
    # convergence threshold, but that is a different quantity: a dimensionless
    # step on a scaling factor, not a residual in currency units.
    balancing_method: str = "GRAS"         # see models.py header
    balancing_tolerance: float = 1e-9      # solver step, dimensionless
    reaggregation_tolerance_pct: float = 1e-6   # accounting, PROJECT CHOICE
    balancing_max_iter: int = 10_000

    # Self-consumption damping on the internal block diagonal (spec §6.3).
    #
    # alpha=1.0 is pure double proportionality, and it is NO LONGER unsourced:
    # CORE_031 (Wolsky 1984, via Zhao 2014) eq. (14) gives the internal block as
    # z*_kk' = rho_k * z_pp * rho_k', and eq. (15) that it conserves the parent
    # cell exactly. library/validators/check_wolsky_internal_block.py confirms
    # this engine reproduces both, to 5.6e-17 and to 0.0 respectively.
    #
    # THE DEFAULT WAS 0.5 AND IT WAS BACKWARDS. That number rested on the
    # intuition that "a subsector plausibly buys from itself LESS than
    # proportionality implies". Measured on 1,403 sibling pairs across three
    # published tables -- Italy ixi 65, Spain pxp 65, the UK pxp 104 -- the
    # diagonal of a two-sector block is about **1.5x** the outer product, in
    # 96 % of pairs, and the off-diagonal about **0.1x**. The intuition had the
    # sign wrong. On the pilot's own pair, UK I55 accommodation x I56 food
    # service, accommodation buys 887.3 from itself where the outer product
    # says 208.4, and 101.3 from food service where it says 518.4.
    #
    # It is NOT set to the measured 1.5 either. 1.5 is this project's
    # measurement, not a source, and substituting it for eq. (14) would be the
    # same mistake in the other direction. The default is the SOURCED rule, and
    # the measurement is here so an analyst can raise alpha deliberately and
    # knows roughly how far.
    #
    # `alpha` is also no longer a leak. The off-diagonal now takes
    # `beta = (1 - alpha*d)/(1 - d)` with `d = sum_a w_row[a]*w_col[a]`, so the
    # block conserves the parent cell for EVERY alpha, satisfying eq. (15)
    # instead of leaving a shortfall for a balancer that knows nothing about
    # the block. At alpha = 1 it reduces exactly to eq. (14); at alpha = 1/d
    # beta reaches zero, which bounds it. See D_open_questions.md OQ-S-04 and
    # library/validators/run_internal_block.py.
    internal_block_alpha: float = 1.0

    locked_cells: list[tuple[int, int]] = field(default_factory=list)
    user_constraints: dict[str, float] = field(default_factory=dict)

    # Relative input intensities: {subsector_code: {supplier_code: multiplier}}.
    # 1.0 means "the parent sector's average". 1.6 means this subsector buys
    # 1.6 times as intensively from that supplier as the parent does.
    #
    # This is what makes subsectors differ as BUYERS. Without it, a single
    # allocation key gives every subsector a scaled copy of the parent's input
    # structure, the weight cancels in a_ij = Z_ij / X_j, and every subsector
    # ends up with the same technical coefficients and the same multiplier —
    # a property of the arithmetic, not a finding about the economy.
    #
    # Multipliers are normalised per supplier so that each supplier's total
    # sales to the group are preserved exactly. That is what keeps the
    # Reaggregation Guarantee (MVP_0.1 §8) intact: the profile redistributes
    # within the group and never changes what leaves it.
    input_profiles: dict[str, dict[str, float]] = field(default_factory=dict)
    profile_provenance: Optional[ProfileProvenance] = None

    def key_for(self, block: str, default: Optional[str] = None) -> str:
        return self.keys_by_block.get(block, default)


# ---------------------------------------------------------------------------
# 2.4 AssumptionLedger
# ---------------------------------------------------------------------------

@dataclass
class Assumption:
    assumption_id: str
    description: str
    applies_to: str
    source: str
    validated_by: str
    confidence: ProxyStrength
    impact_on_results: str
    discarded_alternative: Optional[str] = None
    discard_reason: Optional[str] = None
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class AssumptionLedger:
    project_id: str
    assumptions: list[Assumption] = field(default_factory=list)

    def add(self, a: Assumption) -> None:
        self.assumptions.append(a)

    def to_markdown_table(self) -> str:
        if not self.assumptions:
            return "_No assumptions recorded._"
        rows = ["| ID | Assumption | Source | Confidence | Impact |",
                "|---|---|---|---|---|"]
        for a in self.assumptions:
            rows.append(f"| `{a.assumption_id}` | {a.description} | {a.source} "
                        f"| {a.confidence.value} | {a.impact_on_results} |")
        return "\n".join(rows)


# ---------------------------------------------------------------------------
# 2.5 ValidationReport
# ---------------------------------------------------------------------------

def count_label(provenance: np.ndarray, label: "CellLabel") -> int:
    """Count cells carrying `label`.

    Not `(provenance == label).sum()`. numpy coerces an Enum member to its
    `str()`, which for a str-Enum on Python 3.10 is "CellLabel.OBSERVED" rather
    than "observed", so the array comparison silently counts zero everywhere.
    Comparing against `.value` is correct and is why this helper exists.
    """
    return int((provenance == label.value).sum())


def label_counts(provenance: np.ndarray) -> dict:
    return {lbl: count_label(provenance, lbl) for lbl in CellLabel}


@dataclass
class ValidationCheck:
    name: str
    passed: bool
    detail: str
    severity: str          # "info" | "warning" | "error"
    citation: Optional[str] = None


@dataclass
class ValidationReport:
    table_id: str
    scenario_id: str
    checks: list[ValidationCheck] = field(default_factory=list)
    reaggregation_error_pct: Optional[float] = None
    solver_converged: Optional[bool] = None
    solver_iterations: Optional[int] = None
    method_used: Optional[str] = None
    method_reason: Optional[str] = None

    def add(self, name, passed, detail, severity, citation=None) -> None:
        self.checks.append(ValidationCheck(name, passed, detail, severity,
                                           citation))

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.severity == "error")

    @property
    def n_warnings(self) -> int:
        return sum(1 for c in self.checks
                   if not c.passed and c.severity == "warning")

    def to_markdown(self) -> str:
        lines = [f"**Scenario `{self.scenario_id}`** — "
                 f"{'PASSED' if self.passed else 'FAILED'}"]
        if self.method_used:
            lines.append(f"\nMethod: **{self.method_used}** — {self.method_reason}")
        lines.append("")
        for c in self.checks:
            mark = "OK  " if c.passed else ("WARN" if c.severity == "warning"
                                            else "FAIL")
            cite = f"  \n  <sub>{c.citation}</sub>" if c.citation else ""
            lines.append(f"- `{mark}` **{c.name}** — {c.detail}{cite}")
        lines.append("")
        lines.append("> Solver convergence is necessary but **not sufficient** "
                     "for statistical validity (CORE_006 ¶9.51, p. 288; "
                     "CORE_012 ¶11.105, pp. 342–343).")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Result container for one scenario run
# ---------------------------------------------------------------------------

@dataclass
class DisaggregationResult:
    scenario_id: str
    table: IOTable                     # the expanded, balanced table
    provenance: np.ndarray             # object array of CellLabel, shape of Z
    mapping: list[int]                 # new sector index -> original index
    splits: list[dict]                 # one entry per sector divided
    report: ValidationReport
    seed_Z: np.ndarray                 # before balancing, for audit
    diagnostics: dict = field(default_factory=dict)
