"""
Turn supply and use tables into an input-output table.

WHAT THIS IS, IN NATIONAL ACCOUNTS TERMS
----------------------------------------
A supply table says which industry made which product. A use table says which
industry bought which product. An input-output table needs ONE classification on
both axes -- product by product, or industry by industry -- so somebody has to
decide what to assume about secondary production: the cars a food company makes,
the meals a hotel serves.

CORE_013 (UN Handbook 2018 ch. 12) gives four such assumptions and, in Box 12.3,
p. 383, the matrix formula for each. This module is those four formulas and
nothing else. It invents no assumption, it chooses no model, and it does not
balance -- CORE_013 par. 12.50, p. 385 notes that a correctly transformed IOT
already has "its row sums being equal to column sums".

    model A   product technology       product x product     negatives possible
    model B   industry technology      product x product     no negatives
    model C   fixed industry sales     industry x industry   negatives possible
    model D   fixed product sales      industry x industry   no negatives
    model E   hybrid of A and B        product x product     negatives possible

MODEL E, AND WHY IT IS HERE RATHER THAN FLAGGED
-----------------------------------------------
Model E mixes A and B cell by cell, driven by a product-by-industry matrix `H`
of ones (use product technology) and zeros (use industry technology). It was
left unimplemented until v1.8 on the ground that the Handbook calls it "no new
theoretical viewpoint" (par. 12.63, p. 389).

What changed is not the theory. `NSO_UK_01` — the ONS quality report for the
table this project actually loads — says the published UK product-by-product
IOATs are built exactly this way, and states the rule for filling `H`:
model A per combination unless it produces negatives, then model B. So model E
stopped being a curiosity and became the procedure of the office whose data the
engine consumes. `hybrid_matrix_avoiding_negatives()` implements that rule.

WHICH ONE TO USE IS NOT THIS MODULE'S DECISION, AND THE HANDBOOK IS UNUSUALLY
DIRECT ABOUT IT
---------------------------------------------------------------------------
CORE_013 par. 12.76, p. 393 states the recommendation plainly -- apply model D
directly to rectangular SUTs -- and par. 12.108, p. 406 reports that model A and
model D are the two that "best fulfil the standard quality criteria". Models B
and C are here because the Handbook specifies them, and because a project that
implements only the models it likes cannot check the ones it does not.

`choose_model()` reports that guidance and refuses to pick for you.

THE ONE THING WORTH KNOWING BEFORE USING MODEL A OR C
-----------------------------------------------------
They invert a matrix of shares, and the negatives that come out are not bad luck.
CORE_013 par. 12.95, p. 403 reports de Mesnard's result that the negatives are
"systematically present in the inverse matrices" and therefore "structurally
inevitable", and goes further: since those matrices are Markovian, negatives in
them are forbidden, so "computing these inverse matrices becomes meaningless,
even if no negatives are present in the IOTs". The Handbook still specifies the
models, and so do we; `TransformationResult` counts the negatives and says where
they are, rather than hiding them.

Removing them is a separate problem with its own card -- see
`library/specs/B_method_cards/M-054`. It is deliberately NOT done here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# CORE_013 Figure 12.2, p. 378 and Box 12.3, p. 383.
MODELS = {
    "A": ("product technology", "product x product", True),
    "B": ("industry technology", "product x product", False),
    "C": ("fixed industry sales structure", "industry x industry", True),
    "D": ("fixed product sales structure", "industry x industry", False),
    "E": ("hybrid of product and industry technology", "product x product",
          True),
}


class TransformationError(ValueError):
    """Said in the compiler's terms, not the solver's."""


@dataclass
class TransformationResult:
    """An IOT and everything needed to say how much to trust it."""
    model: str
    axis: str                       # "product x product" / "industry x industry"
    T: np.ndarray                   # the transformation matrix itself
    Sd: np.ndarray                  # domestic intermediates
    Sm: np.ndarray                  # imported intermediates
    Yd: np.ndarray                  # final use, domestic
    Ym: np.ndarray                  # final use, imported
    E: np.ndarray                   # value added, on the new axis
    negatives: list[tuple[str, int, int, float]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def n_negatives(self) -> int:
        return len(self.negatives)

    def summary(self) -> str:
        name, axis, may = MODELS[self.model]
        head = f"model {self.model} ({name}), {axis}"
        if self.n_negatives == 0:
            return head + " -- no negative entries"
        worst = min(self.negatives, key=lambda t: t[3])
        tail = (f" -- {self.n_negatives} negative entries, most negative "
                f"{worst[3]:.4f} in {worst[0]}[{worst[1]},{worst[2]}]")
        if not may:
            # A negative here means the inputs were wrong, not the model.
            return head + tail + "  *** UNEXPECTED: this model cannot " \
                                 "produce negatives from valid SUTs ***"
        return head + tail + " (structural, CORE_013 par. 12.95, p. 403)"


def _diag_inv(v: np.ndarray, what: str) -> np.ndarray:
    v = np.asarray(v, float).ravel()
    bad = np.flatnonzero(v == 0)
    if bad.size:
        raise TransformationError(
            f"{what} is zero for position(s) {bad.tolist()}. The coefficient "
            f"matrices of CORE_013 Box 12.2, p. 381 divide by it, so a zero "
            f"total has no transformation. Drop the empty product or industry, "
            f"or aggregate it into a neighbour, before transforming.")
    return np.diag(1.0 / v)


def product_mix(V_T: np.ndarray, g: np.ndarray) -> np.ndarray:
    """C = V^T (g_hat)^-1 -- share of each product in an industry's output.

    CORE_013 Box 12.2, p. 382: "Product-mix matrix (share of each product in
    output of an industry)". Product by industry; its COLUMNS sum to one.
    """
    return np.asarray(V_T, float) @ _diag_inv(g, "industry output g")


def market_shares(V_T: np.ndarray, x: np.ndarray) -> np.ndarray:
    """D = V (x_hat)^-1 -- share of each industry in a product's output.

    CORE_013 Box 12.2, p. 382: "Market shares matrix (contribution of each
    industry to the output of a product)". Industry by product; its COLUMNS sum
    to one. Note V is the MAKE matrix, the transpose of the supply matrix.
    """
    return np.asarray(V_T, float).T @ _diag_inv(x, "product output x")


def hybrid_transformation_matrix(V_T, g, x, H) -> np.ndarray:
    """`R` for model E. CORE_013 Box 12.3, p. 383.

        V1 = V # H              supply produced with product technology
        V2 = V - V1             the rest, on industry technology
        C1 = V1 (g1_hat)^-1     g1 = industry output under product technology
        D2 = V2^T (x_hat)^-1
        R  = C1^-1 (I - diag(D2^T i)) + D2

    `H` is product by industry — CORE_013 par. 12.62, p. 389 — with 1 meaning
    product technology.

    ONE READING IN THIS BOX IS SETTLED BY ARITHMETIC, NOT BY THE PAGE.
    The typeset page prints the C1 denominator as a bare `g` with a circumflex
    and no subscript, while the box's own legend defines `g1` = "Vector of
    industry output with product technology" and uses it nowhere else. That
    contradiction is `OQ-T-07`, and it is decided here the only way it can be:
    only `g1` — the COLUMN SUMS of V1 — reproduces the Handbook's own printed
    Table 12.9, and it does so to 4.4e-05 on a table printed to four decimals.
    Plain `g` reproduces nothing. `B_method_cards/M-027` read it as `g1` from
    the legend before anyone checked, and was right.

    Returns `R` as INDUSTRY by PRODUCT, which is the orientation the application
    step needs; it matches Table 12.9 as printed.
    """
    V_T = np.asarray(V_T, float)
    H = np.asarray(H, float)
    if H.shape != V_T.shape:
        raise TransformationError(
            f"H is {H.shape} and the supply table is {V_T.shape}. CORE_013 "
            f"par. 12.62, p. 389 defines H as a product-by-industry matrix, so "
            f"it has the same shape as the supply table.")
    if not np.all(np.isin(H, (0.0, 1.0))):
        raise TransformationError(
            "H must hold only 0 and 1: par. 12.62, p. 389 calls it a matrix of "
            "ones for products using the product technology assumption and "
            "zeros for those using industry technology. A fraction would be a "
            "different model, not this one.")
    V1 = V_T * H
    V2 = V_T - V1
    n_prod, n_ind = V_T.shape
    C1 = V1 @ _diag_inv(V1.sum(axis=0), "industry output under product "
                                        "technology g1 (column sums of V1)")
    D2 = V2.T @ _diag_inv(x, "product output x")
    return (np.linalg.inv(C1)
            @ (np.eye(n_prod) - np.diag(D2.T @ np.ones(n_ind))) + D2)


def hybrid_matrix_avoiding_negatives(V_T, Ud, Um, W, g, x,
                                     max_flips: int | None = None) -> dict:
    """Fill `H` by the rule the ONS states for its own published tables.

    NSO_UK_01 p. 5: the hybrid assumption "uses model A if it can, providing it
    does not produce negative values, otherwise it uses model B". CORE_013
    par. 12.63, p. 389 gives the objective the search is under: start from all
    ones, and "the challenge is to fill in as few zeros as possible until all
    negative values have disappeared".

    **The objective is sourced; the search is not.** Neither document states an
    algorithm, and "as few zeros as possible" is a combinatorial problem with
    2^(m*n) candidates. What runs here is a greedy descent — flip the single
    cell that removes the most negative mass, repeat — which is a PROJECT
    CHOICE and is reported as one. It finds *a* small set of zeros, not
    provably the smallest.

    Returns `H`, and the record of how it got there: the flips in order, and
    whether it actually reached zero negatives.
    """
    V_T = np.asarray(V_T, float)
    m, n = V_T.shape
    if m != n:
        raise TransformationError(
            f"the hybrid search needs a square supply table and this one is "
            f"{m} products by {n} industries: model E inverts C1, as model A "
            f"inverts D^T.")
    cap = m * n if max_flips is None else int(max_flips)

    def neg_mass(H):
        try:
            R = hybrid_transformation_matrix(V_T, g, x, H)
        except (TransformationError, np.linalg.LinAlgError):
            return None
        T = _diag_inv(g, "industry output g") @ R @ np.diag(np.asarray(x, float))
        blocks = [np.asarray(Ud, float) @ T, np.asarray(Um, float) @ T,
                  np.atleast_2d(np.asarray(W, float)) @ T]
        return float(sum(-M[M < 0].sum() for M in blocks))

    H = np.ones((m, n))
    best = neg_mass(H)
    if best is None:
        raise TransformationError(
            "model A (H all ones) cannot even be computed on this table, so "
            "the hybrid search has no starting point.")
    flips: list[dict] = []
    while best > 0 and len(flips) < cap:
        cand = None
        for i in range(m):
            for j in range(n):
                if H[i, j] == 0.0 or V_T[i, j] == 0.0:
                    continue
                H[i, j] = 0.0
                val = neg_mass(H)
                H[i, j] = 1.0
                if val is not None and (cand is None or val < cand[0]):
                    cand = (val, i, j)
        if cand is None or cand[0] >= best - 1e-12:
            break                       # no single flip helps: stop, say so
        best, i, j = cand
        H[i, j] = 0.0
        flips.append({"product": i, "industry": j,
                      "negative_mass_after": round(best, 6)})
    return {"H": H, "flips": flips, "negative_mass": best,
            "cleared": best <= 1e-9,
            "search": "greedy descent, PROJECT CHOICE — the objective is "
                      "CORE_013 par. 12.63, p. 389; the algorithm is not "
                      "stated by any loaded source"}


def almon(U, V_T, q=None, lower=None, max_iter: int = 500,
          tol: float = 1e-12) -> dict:
    """Almon's procedure: product technology, without negative flows.

    CORE_022 p. 328, Box 11.4 and p. 350, Box 11.7 (Eurostat manual, ch. 11);
    Almon (2000). It is **not an alternative to product technology** — CORE_022
    p. 326 says so directly. It is a way of computing the same model that stops
    a flow before it goes negative instead of inverting a matrix and living with
    what comes out.

    WHAT IT SOLVES
    --------------
    Product technology says the input of `i` per unit of product `h` is the same
    whichever industry makes it. That gives

        U = Z M      with      M = V (q_hat)^-1

    where `M[h, j]` is the share of product `h` made by industry `j`, so `M`'s
    rows sum to one. Model A takes `Z = U M^-1` and accepts the negatives.
    Almon solves the same system **row by row**, holding every entry at or above
    a floor, and lets the *use table* move instead. That is the trade, and it is
    explicit in the source: the procedure also reports a "New use table", and
    what it says is how the use table would have to be revised for the product
    technology assumption to hold without negatives.

    Preserves each row's total exactly, because `M`'s rows sum to one and the
    row total is therefore the same on both sides. **Column totals are NOT
    preserved** — CORE_022 p. 326 and `NSO_AT_01` p. 61 both say a RAS pass is
    needed afterwards. This function does not do it; `balancing.balance()` does.

    `lower` is Austria's refinement, `NSO_AT_01` p. 65: the plain procedure
    drives a threatened cell to zero, and zero is often wrong, because some
    products are consumed in every process — electricity is the example the
    document gives. Pass a scalar or an array of the same shape as `U` to hold
    cells above a floor instead. Statistik Austria sets these as input
    COEFFICIENTS rather than absolute values, so they need not be reset each
    year; that choice belongs to the caller, not here.

    ONE THING IS RECONSTRUCTED, AND IT IS SAID PLAINLY.
    Box 11.7's subscripts do not survive text extraction — the summation indices
    collapse into a run of `i`s and `j`s. What is implemented is the
    mathematical object the surrounding prose describes, not a transcription of
    the printed formula. It is warranted by reproducing **all four** of the
    box's printed claims to machine precision; see
    `library/validators/run_almon_eurostat.py`.
    """
    U = np.asarray(U, float)
    V_T = np.asarray(V_T, float)
    m, n = V_T.shape
    if m != n:
        raise TransformationError(
            f"Almon's procedure needs a square supply table and this one is "
            f"{m} products by {n} industries. CORE_022 p. 350, Box 11.7 opens "
            f"with 'We assume that U and V are square.'")
    if U.shape[1] != n:
        raise TransformationError(
            f"U has {U.shape[1]} columns and V_T has {n}; both are indexed by "
            f"industry.")
    q = V_T.sum(axis=1) if q is None else np.asarray(q, float).ravel()
    M = V_T / _nz(q)[:, None]

    floor = np.zeros_like(U) if lower is None else np.broadcast_to(
        np.asarray(lower, float), U.shape).astype(float).copy()

    Z = U.copy()
    diag = np.diag(M).copy()
    converged, used = False, 0
    for used in range(1, max_iter + 1):
        prev = Z.copy()
        for i in range(U.shape[0]):
            for j in range(n):
                if diag[j] <= 1e-12:
                    continue          # industry makes none of its own product
                c = float(M[:, j] @ Z[i, :] - M[j, j] * Z[i, j])
                Z[i, j] = max(floor[i, j], (U[i, j] - c) / diag[j])
            # Row totals are invariant under this system -- M's rows sum to
            # one -- so they are held rather than hoped for. Cells sitting ON
            # their floor are held there and the rescaling is spread over the
            # rest; scaling the whole row would push floored cells back under,
            # which is what the first version did.
            total = float(U[i].sum())
            at_floor = Z[i] <= floor[i] + 1e-12
            room = total - float(floor[i][at_floor].sum())
            free = float(Z[i][~at_floor].sum())
            if free > 1e-12 and room > 0:
                Z[i, ~at_floor] *= room / free
                Z[i, at_floor] = floor[i][at_floor]
            elif float(Z[i].sum()) > 1e-12:
                Z[i] *= total / float(Z[i].sum())
        if np.abs(Z - prev).max() < tol:
            converged = True
            break

    new_use = Z @ M
    short = float(np.maximum(floor.sum(axis=1) - U.sum(axis=1), 0.0).max())
    return {"Z": Z, "new_use": new_use, "M": M,
            "floor_exceeds_row_total_by": short,
            "iterations": used, "converged": converged,
            "n_negatives": int((Z < -1e-9).sum()),
            "row_total_error": float(np.abs(Z.sum(1) - U.sum(1)).max()),
            "col_total_error": float(np.abs(new_use.sum(0) - U.sum(0)).max()),
            "use_table_moved": float(np.abs(new_use - U).max())}


def _nz(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, float).ravel()
    return np.where(np.abs(v) < 1e-12, np.inf, v)


def transform(model: str, V_T, Ud, Um, Yd, Ym, W, g, x,
              H=None) -> TransformationResult:
    """Apply one of CORE_013's five models. Box 12.3, p. 383.

    `V_T` is the supply matrix as published (product by industry); `Ud` and `Um`
    the domestic and imported use matrices (product by industry); `Yd`, `Ym`
    final use (product by category); `W` value added (component by industry);
    `g`, `x` industry and product output.
    """
    model = str(model).strip().upper()
    if model not in MODELS:
        raise TransformationError(
            f"model {model!r} is not one of the four in CORE_013 Figure 12.2, "
            f"p. 378: {', '.join(sorted(MODELS))}")
    V_T, Ud, Um = (np.asarray(a, float) for a in (V_T, Ud, Um))
    Yd, Ym, W = (np.asarray(a, float) for a in (Yd, Ym, W))
    m, n = V_T.shape                      # products, industries
    name, axis, may_be_negative = MODELS[model]
    notes: list[str] = []

    # Models A and C invert a share matrix, so they need as many products as
    # industries. CORE_013 par. 12.53, p. 385 states the requirement for A and
    # par. 12.23, p. 376 explains the aggregation it forces -- with the cost:
    # "leads to some information loss".
    if model in ("A", "C", "E") and m != n:
        raise TransformationError(
            f"model {model} ({name}) needs a SQUARE supply table and this one "
            f"is {m} products by {n} industries. Aggregate products to their "
            f"primary producing industry first (CORE_013 par. 12.23, p. 376), "
            f"or use model D, which CORE_013 par. 12.76, p. 393 recommends "
            f"applying directly to rectangular tables.")

    if model == "A":
        D = market_shares(V_T, x)
        T = np.linalg.inv(D.T)
        Sd, Sm, E = Ud @ T, Um @ T, W @ T
        Yd_out, Ym_out = Yd, Ym       # final use is already by product
        notes.append("final use is unchanged: CORE_013 par. 12.56, p. 386 -- "
                     "it is already defined in terms of products")
    elif model == "B":
        C = product_mix(V_T, g)
        T = C.T
        Sd, Sm, E = Ud @ T, Um @ T, W @ T
        Yd_out, Ym_out = Yd, Ym
        notes.append("final use is unchanged: already defined by product")
    elif model == "C":
        C = product_mix(V_T, g)
        T = np.linalg.inv(C)
        Sd, Sm, E = T @ Ud, T @ Um, W
        Yd_out, Ym_out = T @ Yd, T @ Ym
    elif model == "E":
        if H is None:
            raise TransformationError(
                "model E needs the hybrid technology matrix H (CORE_013 "
                "par. 12.62, p. 389). Build one with "
                "`hybrid_matrix_avoiding_negatives()`, which follows the rule "
                "the ONS states for its own tables, or pass your own.")
        R = hybrid_transformation_matrix(V_T, g, x, H)
        # Box 12.3 writes model E in coefficient form -- A = Z R, S = Z R x_hat
        # -- where Z = U g_hat^-1. Grouped here so the same `T` applies to every
        # block exactly as models A and B do.
        T = _diag_inv(g, "industry output g") @ R @ np.diag(np.asarray(x, float))
        Sd, Sm, E = Ud @ T, Um @ T, W @ T
        Yd_out, Ym_out = Yd, Ym
        zeros = int((np.asarray(H, float) == 0).sum())
        notes.append(f"hybrid H puts {zeros} of {m * n} cells on industry "
                     f"technology; the rest use product technology")
        notes.append("final use is unchanged: already defined by product")
    else:                              # model D
        T = market_shares(V_T, x)
        Sd, Sm, E = T @ Ud, T @ Um, W
        Yd_out, Ym_out = T @ Yd, T @ Ym
        if m != n:
            notes.append("applied directly to a rectangular table, which "
                         "CORE_013 par. 12.75, p. 393 gives as this model's "
                         "advantage: no aggregation, so no aggregation loss")

    res = TransformationResult(model=model, axis=axis, T=T, Sd=Sd, Sm=Sm,
                               Yd=Yd_out, Ym=Ym_out, E=E, notes=notes)
    for label, M in (("Sd", Sd), ("Sm", Sm), ("Yd", Yd_out), ("Ym", Ym_out),
                     ("E", np.atleast_2d(E))):
        for i, j in zip(*np.where(M < 0)):
            res.negatives.append((label, int(i), int(j), float(M[i, j])))
    return res


def choose_model(square: bool, secondary_type: str | None = None) -> dict:
    """What CORE_013 says about picking a model. It does NOT pick one.

    `secondary_type` is one of the three the 2008 SNA distinguishes and
    CORE_013 par. 12.26, p. 376 repeats: subsidiary, by-product, joint.
    """
    out = {
        "recommended": "D",
        "why": ("CORE_013 par. 12.76, p. 393: apply model D directly to "
                "rectangular SUTs. Par. 12.108, p. 406 reports models A and D "
                "as those that best fulfil the standard quality criteria."),
        "square_required_for": ["A", "C"],
        "caution": ("Models A and C may produce negatives, and CORE_013 "
                    "par. 12.95, p. 403 reports them as structurally "
                    "inevitable rather than accidental."),
        "by_secondary_production_type": None,
        "caveat": ("CORE_013 par. 12.27, p. 377 states that the four standard "
                   "models do NOT distinguish the three types of secondary "
                   "product, and that a compiler is often not in a position to "
                   "tell them apart. The mapping below is guidance about "
                   "suitability, not a rule the models encode."),
    }
    if not square:
        out["available"] = ["B", "D"]
        out["why_limited"] = ("A and C invert a share matrix and need as many "
                              "products as industries.")
    else:
        out["available"] = ["A", "B", "C", "D"]
    if secondary_type:
        s = secondary_type.strip().lower()
        # CORE_013 par. 12.61, p. 388 and par. 12.58, p. 387.
        table = {
            "subsidiary": ("A", "CORE_013 par. 12.61, p. 388: the product "
                           "technology assumption is most suitable in cases "
                           "of subsidiary products."),
            "by-product": ("B", "CORE_013 par. 12.61, p. 388: the industry "
                           "technology assumption applies best to cases of "
                           "by-products or joint products."),
            "joint": ("B", "CORE_013 par. 12.58, p. 387: applies best to "
                      "cases of by-products or joint products, since several "
                      "products are produced in a single process."),
        }
        table["byproduct"] = table["by-product"]
        if s not in table:
            raise TransformationError(
                f"secondary production type {secondary_type!r} is not one of "
                f"the three in CORE_013 par. 12.26, p. 376: subsidiary, "
                f"by-product, joint")
        out["by_secondary_production_type"] = table[s]
    return out
