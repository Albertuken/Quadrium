"""
Loading real tables from disk (MVP_0.1 §4).

Four entry points, because there are four situations:

`load_io_table()`   the project's own interchange format — labelled blocks and a
                    `metadata` sheet. Use this for tables you control.

`load_uk_analytical_iot()`  an adapter for the specific published workbook the
                    project ships as its fixture. Real national tables do not
                    come in anyone's interchange format, and pretending
                    otherwise is how loaders acquire silent assumptions. The
                    layout is hard-coded, documented, and asserted on load.

`load_ine_tio()`    the same, for the Spanish table. Product by product, not
                    industry by industry, and split across three sheets rather
                    than one.

`load_ine_tod()`    the Spanish SUPPLY AND USE tables — 110 products by 81
                    activities, the finest the INE publishes, and the only
                    fixture in the project where the valuation identities can
                    be checked at all. It returns a `SupplyUseTables`, not an
                    `IOTable`: a supply-use pair is rectangular and has had no
                    assumption about secondary production applied to it yet.

Each national adapter is written separately on purpose. The two published
tables share every accounting identity and almost no layout convention, and the
one heuristic that could be shared — "a final-demand column whose code is a
strict prefix of another's is a subtotal of it" — is defeated by the INE, which
names its columns in Spanish prose and gives them no codes at all. The concept
generalises; the detection rule does not. So `load_ine_tio` declares its
subtotal groupings and then checks them, which is stronger than the UK
heuristic rather than weaker.

WHAT THE LOADER REFUSES TO DO
-----------------------------
It never repairs. If the table does not balance, it says by how much and stops,
because a table that does not balance is not a table — every number downstream
would inherit the discrepancy silently. MVP_0.1 §5 step 2 makes the original
validation a gate, not a report.

The one crack in that door is `load_ine_tio(unbalanced="residual_column")`, and
it is a crack the caller has to open by name. The INE's interior table genuinely
does not balance for one product (OQ-D-04); the option puts the difference in a
labelled RESIDUAL column that travels into every downstream report, rather than
into a cell that would read as observed.

It never reads the reference period from the filename. The project's own fixture
shipped for twenty-four versions as `UK IO 2022.csv`, was not a CSV, and was for
2023 (`library/specs/D_open_questions.md` OQ-D-01, closed at v1.25 and the file
renamed once the owner confirmed the vintage). The INE's is named
`cne_tio_22.xlsx` and carries only two digits. **A truthful filename today is not
a reason to start trusting filenames** — the rename removed one instance, not the
class.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .models import (AllocationKey, IOTable, ProxyStrength,
                     SupplyUseTables)


class LoaderError(ValueError):
    pass


def _open_workbook(path: Path):
    """openpyxl refuses a .csv extension. Copy to a temporary .xlsx rather than
    renaming the user's file."""
    import openpyxl
    path = Path(path)
    if not path.exists():
        raise LoaderError(f"no such file: {path}")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "wb.xlsx"
        shutil.copy(path, tmp)
        wb = openpyxl.load_workbook(tmp, read_only=True, data_only=True)
        sheets = {name: [list(r) for r in wb[name].iter_rows(values_only=True)]
                  for name in wb.sheetnames}
    return sheets


def _num(v) -> float:
    return float(v) if isinstance(v, (int, float)) else 0.0


# ---------------------------------------------------------------------------
# The UK analytical IOT
# ---------------------------------------------------------------------------

# Layout of the "IOT" sheet, 0-based, established by inspection and re-asserted
# on every load. Mirrors library/validators/run_uk_iot.py, which is where it was
# first worked out.
_UK = dict(
    row_codes=3, row_names=4, first_row=6, last_row=110,
    first_col=2, last_col=106,
    row_imports=111, row_taxes_products=112,
    row_compensation=114, row_gos=115, row_other_taxes=116,
    row_gva=117, row_output=118,
    first_fd_col=107, last_fd_col=117,
)


def load_uk_analytical_iot(path: Path | str) -> IOTable:
    """Load the UK Input-Output Analytical Tables workbook into an `IOTable`.

    The table is industry-by-industry, DOMESTIC use, at basic prices, GBP
    million, 104 x 104.

    A note on what goes into `VA`. The model's column identity is
    `Z.sum(0) + VA.sum(0) == X`. For a *domestic* IOT that identity reads

        domestic intermediate + imported intermediate
            + taxes less subsidies on products + GVA  =  output

    so `VA` here holds five rows, of which the first two — imports and taxes
    less subsidies on products — are **not value added** in the SNA sense. They
    are primary inputs to the column of a domestic table. The labels say so;
    do not sum the block and call it GVA.
    """
    path = Path(path)
    sheets = _open_workbook(path)
    if "IOT" not in sheets:
        raise LoaderError(f"{path.name} has no 'IOT' sheet; found: "
                          f"{', '.join(sheets)}")
    R = sheets["IOT"]
    L = _UK

    rows = range(L["first_row"], L["last_row"])
    cols = range(L["first_col"], L["last_col"])
    codes = [str(R[i][0]) for i in rows]
    names = [str(R[i][1]) for i in rows]
    n = len(codes)
    if n != len(cols):
        raise LoaderError(f"{n} row labels against {len(cols)} columns — the "
                          f"hard-coded layout in _UK no longer fits this file")

    Z = np.array([[_num(R[i][j]) for j in cols] for i in rows])
    X = np.array([_num(R[L["row_output"]][j]) for j in cols])

    # Final demand. The published sheet mixes components with SUBTOTALS of those
    # components: `P3 S1` (final consumption expenditure) is the sum of
    # `P3 S13`, `P3 S14` and `P3 S15`. Summing the block as printed
    # double-counts household consumption -- for Owner-Occupiers' Housing that
    # is GBP 259,330 million on one row, and the row identity fails by exactly
    # that amount. Aggregates are dropped, not special-cased: a column whose
    # code is a strict prefix of another column's code is a subtotal of it.
    all_fd = list(range(L["first_fd_col"], L["last_fd_col"]))
    all_codes = [str(R[L["row_codes"]][j]) for j in all_fd]
    aggregate = {j for j, c in zip(all_fd, all_codes)
                 if any(o != c and o.startswith(c) for o in all_codes)}
    fd_cols = [j for j in all_fd if j not in aggregate]
    dropped = [c for j, c in zip(all_fd, all_codes) if j in aggregate]
    Y_labels = [str(R[L["row_codes"]][j]) for j in fd_cols]
    Y = np.array([[_num(R[i][j]) for j in fd_cols] for i in rows])

    VA_labels = ["Imports of goods and services (cif)",
                 "Taxes less subsidies on products",
                 "Compensation of employees",
                 "Gross operating surplus and mixed income",
                 "Other taxes less subsidies on production"]
    VA = np.array([[_num(R[L[k]][j]) for j in cols] for k in
                   ("row_imports", "row_taxes_products", "row_compensation",
                    "row_gos", "row_other_taxes")])

    menu = []
    if "Menu" in sheets:
        menu = [str(c) for r in sheets["Menu"][:6] for c in r if c]

    year = _infer_year(menu)
    table = IOTable(
        table_id=f"UK-IOT-IXI-{year}", country="United Kingdom", year=year,
        unit="GBP million, current prices, basic prices",
        classification="SIC 2007 (104 industries)",
        sector_codes=codes, sector_labels=names,
        Z=Z, Y=Y, Y_labels=Y_labels, VA=VA, VA_labels=VA_labels, X=X,
        source=f"ONS, {menu[1] if len(menu) > 1 else path.name}",
        retrieved_at=datetime.now(timezone.utc),
        notes=("Industry-by-industry, domestic use, basic prices. The first two "
               "VA rows are imports and taxes on products, not value added — "
               "see the loader docstring. Reference year read from the Menu "
               "sheet, never from the filename (OQ-D-01)."
               + (f" Dropped {len(dropped)} final-demand subtotal column(s) "
                  f"({', '.join(dropped)}) to avoid double counting."
                  if dropped else "")))
    _assert_balances(table, path.name)
    return table


def _infer_year(menu: list[str]) -> int:
    """Read the reference year from the workbook's own banner, not the filename."""
    import re
    for line in menu:
        m = re.search(r"Tables,\s*(\d{4})", line) or re.search(r"\b(20\d\d)\b", line)
        if m:
            return int(m.group(1))
    raise LoaderError("could not read the reference year from the Menu sheet. "
                      "Refusing to guess it from the filename — the project's "
                      "own fixture is named 2022 and is for 2023 (OQ-D-01).")


def _assert_balances(table: IOTable, name: str,
                     rel_tol: float = 1e-6) -> None:
    """Gate, not report (MVP_0.1 §5 step 2). PROJECT CHOICE tolerance."""
    scale = max(float(np.abs(table.X).max()), 1.0)
    row = np.abs(table.Z.sum(axis=1) + table.Y.sum(axis=1) - table.X)
    col = np.abs(table.Z.sum(axis=0) + table.VA.sum(axis=0) - table.X)
    tol = rel_tol * scale
    if row.max() > tol or col.max() > tol:
        i, j = int(row.argmax()), int(col.argmax())
        raise LoaderError(
            f"{name} does not balance and will not be loaded.\n"
            f"  worst row: {table.sector_codes[i]} off by {row[i]:,.3f} "
            f"({table.sector_labels[i]})\n"
            f"  worst col: {table.sector_codes[j]} off by {col[j]:,.3f}\n"
            f"  tolerance {tol:,.3f} (PROJECT CHOICE, {rel_tol:g} of the "
            f"largest output; no loaded source states one — OQ-B-02)\n"
            f"A table that does not balance is not a table: every number "
            f"downstream would inherit the discrepancy without saying so.")


# ---------------------------------------------------------------------------
# The Spanish TIO (INE)
# ---------------------------------------------------------------------------

# Layout of the INE workbook, 0-based. Nothing here is trusted because it was
# read off the screen: `_assert_ine_layout` re-derives every one of these
# indices from an accounting identity on each load, so a moved row fails loudly
# instead of quietly becoming the wrong number.
_INE = dict(
    col_label=1, first_row=9, n=64, first_col=2,
    row_uses_basic=74,        # Total de empleos a precios básicos
    row_taxes_products=76,    # Impuestos netos sobre los productos
    row_uses_purch=77,        # Total de empleos a precios de adquisición
    row_ic_purch=79,          # Consumos intermedios a precios de adquisición
    row_compensation=80,
    row_wages=81, row_social=82,        # components of compensation
    row_other_taxes=83,
    row_gos=84,               # Excedente de explotación bruto / Renta mixta
    row_gva=85,               # subtotal of compensation + other taxes + gos
    row_output=86,            # Producción a precios básicos
    row_imports=87, row_imports_eu=88, row_imports_nonue=89,
    row_supply=90,            # Oferta a precios básicos
)

# Final demand. The same trap as the UK sheet — subtotals sit next to their own
# components — but the UK detection rule does not transfer: the INE labels its
# columns in Spanish prose, and there are no codes to compare as prefixes. The
# concept generalises; the detection rule does not. So the grouping is declared
# here and then *checked* on load: each subtotal must equal the sum of its
# declared components, or nothing is loaded.
_INE_FD_GROUPS = (
    (68, (69, 70, 71), "Total gasto en consumo final"),
    (72, (73, 74), "Formación bruta de capital"),
    (75, (76, 77), "Total exportaciones"),
)
_INE_FD_COLS = (69, 70, 71, 73, 74, 76, 77)
_INE_COL_INTERMEDIATE, _INE_COL_FD, _INE_COL_USES = 67, 78, 79

_INE_TOL = 1e-3   # million EUR. Observed residuals are ~1e-11; see M-058.


def _ine_block(R, rows, cols) -> np.ndarray:
    return np.array([[_num(R[i][j]) if j < len(R[i]) else 0.0 for j in cols]
                     for i in rows])


def _ine_row(R, i, cols) -> np.ndarray:
    return np.array([_num(R[i][j]) if j < len(R[i]) else 0.0 for j in cols])


def _assert_ine_layout(S, cols, rows) -> None:
    """Re-derive the hard-coded layout from the workbook's own identities.

    Each check pins one hard-coded index. If the INE moves a row, the identity
    it participates in stops holding and the load stops here, rather than
    silently reading (say) gross value added where output was meant.
    """
    L = _INE
    t1, t2, t3 = S["Tabla1"], S["Tabla2"], S["Tabla3"]
    Zt, Zd, Zm = (_ine_block(t, rows, cols) for t in (t1, t2, t3))
    r1 = lambda k: _ine_row(t1, L[k], cols)

    checks = [
        ("Tabla1 == Tabla2 + Tabla3 (intermediate block)", Zt, Zd + Zm),
        ("row 'Total de empleos a precios básicos'", r1("row_uses_basic"),
         Zt.sum(0)),
        ("row 'Total de empleos a precios de adquisición'",
         r1("row_uses_purch"), r1("row_uses_basic") + r1("row_taxes_products")),
        ("row 'Consumos intermedios a precios de adquisición'",
         r1("row_ic_purch"), r1("row_uses_purch")),
        ("row 'Remuneración de los asalariados'", r1("row_compensation"),
         r1("row_wages") + r1("row_social")),
        ("row 'Valor añadido bruto a precios básicos'", r1("row_gva"),
         r1("row_compensation") + r1("row_other_taxes") + r1("row_gos")),
        ("row 'Importaciones'", r1("row_imports"),
         r1("row_imports_eu") + r1("row_imports_nonue")),
        ("row 'Oferta a precios básicos'", r1("row_supply"),
         r1("row_output") + r1("row_imports")),
        ("column identity pins 'Producción a precios básicos'", r1("row_output"),
         Zt.sum(0) + r1("row_taxes_products") + r1("row_gva")),
    ]
    for name, tbl in (("Tabla1", t1), ("Tabla2", t2), ("Tabla3", t3)):
        Y = _ine_block(tbl, rows, _INE_FD_COLS)
        Z = _ine_block(tbl, rows, cols)
        checks.append((f"{name}: final-demand components sum to 'Total demanda "
                       f"final'", Y.sum(1), _ine_row_col(tbl, rows, _INE_COL_FD)))
        checks.append((f"{name}: 'Total demanda intermedia' column",
                       Z.sum(1), _ine_row_col(tbl, rows, _INE_COL_INTERMEDIATE)))
        for sub, comp, lab in _INE_FD_GROUPS:
            checks.append((f"{name}: subtotal {lab!r}",
                           _ine_row_col(tbl, rows, sub),
                           sum(_ine_row_col(tbl, rows, c) for c in comp)))

    for what, a, b in checks:
        d = float(np.abs(np.asarray(a) - np.asarray(b)).max())
        if d > _INE_TOL:
            raise LoaderError(
                f"the INE workbook's layout no longer matches the one this "
                f"loader hard-codes.\n  failed check: {what}\n"
                f"  off by {d:,.4f} (tolerance {_INE_TOL:g}, million EUR)\n"
                f"Fix _INE / _INE_FD_GROUPS in io_loader.py against the actual "
                f"sheet. Do not widen the tolerance: these identities hold "
                f"exactly in the published file.")


def _ine_row_col(R, rows, j) -> np.ndarray:
    return np.array([_num(R[i][j]) if j < len(R[i]) else 0.0 for i in rows])


def _ine_codes(R, rows) -> tuple[list[str], list[str]]:
    """Split '44 bis. Alquileres imputados…' into code and label.

    The numeric index row runs 1..64, but the INE's own product numbering does
    not: it carries a '44 bis'. Tabla8 maps the *label* numbering to CPA, so
    that is the one kept as the code.
    """
    # The separator is not reliably ". ". The supply-use workbook writes
    # `5 .Pescado y otros productos de la pesca` -- space BEFORE the dot, none
    # after -- so a `partition(". ")` drops that product and every one after it.
    # Matched on the code instead, which is what actually has a shape.
    import re as _re
    pat = _re.compile(r"^\s*(\d{1,3}(?:\s+bis)?)\s*\.\s*(.+)$")
    codes, labels = [], []
    for i in rows:
        # Whitespace is collapsed FIRST. Some labels carry an embedded newline
        # -- product 26 of the input-output table runs onto a second line --
        # and `.` does not cross one, so a regex written without this silently
        # rejects a label the old `partition(". ")` had accepted.
        raw = _re.sub(r"\s+", " ", str(R[i][_INE["col_label"]] or "")).strip()
        m = pat.match(raw)
        if not m:
            raise LoaderError(f"row {i + 1} is not a numbered product label: "
                              f"{raw!r}")
        codes.append(_re.sub(r"\s+", " ", m.group(1)).strip())
        labels.append(m.group(2).strip())
    if len(set(codes)) != len(codes):
        dup = sorted({c for c in codes if codes.count(c) > 1})
        raise LoaderError(f"duplicate INE product codes: {', '.join(dup)}")
    return codes, labels


def _infer_ine_year(S) -> int:
    """Read the reference year from the workbook's own index sheet.

    Never from the filename: the INE names this file `cne_tio_22.xlsx`, and a
    two-digit year in a filename is exactly the sort of thing OQ-D-01 exists to
    stop the loader from believing.
    """
    import re
    for row in S.get("Lista_Tablas", [])[:12]:
        for cell in row:
            # Two workbooks, two banners: "Tablas Input-Output 2022" and
            # "Tablas de origen y de destino 2022". Deliberately NOT a bare
            # four-digit search — the same sheet says "Revisión Estadística
            # 2024", which is the vintage of the methodology, not of the data.
            m = re.search(r"(?:Input-Output|origen y (?:de )?destino)\s+(\d{4})",
                          str(cell or ""), re.IGNORECASE)
            if m:
                return int(m.group(1))
    raise LoaderError("could not read the reference year from the "
                      "'Lista_Tablas' sheet. Refusing to take it from the "
                      "filename, which carries only two digits (OQ-D-01).")


def load_ine_tio(path: Path | str, variant: str = "interior",
                 unbalanced: str = "refuse") -> IOTable:
    """Load the INE's Spanish input-output table into an `IOTable`.

    The table is **product by product** — unlike the UK fixture, which is
    industry by industry. Both are symmetric, so the engine handles them the
    same way, but a disaggregation of "restaurants" means a different object in
    each, and results are not comparable across the two without saying so.

    `variant` picks which of the INE's three tables is loaded:

    `"interior"`  (default) Tabla 2, domestic output only. This is the
        analytically right one and the one that matches the UK pilot: imports
        enter as a primary input row, so Leontief multipliers count only
        domestic production. As with the UK loader, the first two `VA` rows —
        imported intermediate inputs and taxes less subsidies on products — are
        **not value added**. Do not sum the block and call it GVA.

    `"total"`  Tabla 1, domestic and imported flows together, with imports
        carried as a negative final-demand column so the row identity closes.
        Multipliers from it treat an imported input as if it had been produced
        in Spain, and overstate domestic effects. Offered because it balances
        exactly with nothing derived, but it is not the table you want for
        impact work.

    A DISCREPANCY IN THE PUBLISHED SOURCE
    -------------------------------------
    The interior table does not satisfy the row identity for one product.
    Domestic uses of agricultural products fall 4,921.6 million EUR short of
    domestic agricultural output, and uses of *imported* agricultural products
    exceed recorded imports by exactly the same amount. The two errors cancel,
    which is why Tabla 1 balances to the last decimal while Tabla 2 does not.

    This is a property of the data, not of the parse: every block here is
    verified against the INE's own published totals, and the INE's own
    coefficient matrices (Tabla 4 and Tabla 5) confirm that
    `Producción a precios básicos` is the intended denominator, to zero
    difference in all 64 branches. What the INE does not publish is why —
    OQ-D-04.

    `unbalanced` says what to do about it:

    `"refuse"`  (default) stop, and report the product and the amount. A table
        that does not balance is not a table.

    `"residual_column"`  add one final-demand column holding
        `X - (Z.sum(1) + Y.sum(1))` per product. The residual is *computed
        here, not published by the INE*; the column is labelled as such and the
        amount is recorded in `notes`, so it can be seen in every downstream
        report rather than being absorbed into a cell that looks observed. This
        is the project's RESIDUAL status made explicit, not a repair.
    """
    if variant not in ("interior", "total"):
        raise LoaderError(f"variant must be 'interior' or 'total', "
                          f"not {variant!r}")
    if unbalanced not in ("refuse", "residual_column"):
        raise LoaderError(f"unbalanced must be 'refuse' or 'residual_column', "
                          f"not {unbalanced!r}")

    path = Path(path)
    S = _open_workbook(path)
    missing = [s for s in ("Tabla1", "Tabla2", "Tabla3") if s not in S]
    if missing:
        raise LoaderError(f"{path.name} is missing {', '.join(missing)}; "
                          f"found: {', '.join(S)}. This loader expects the "
                          f"INE's `cne_tio_YY.xlsx` layout.")

    L = _INE
    rows = range(L["first_row"], L["first_row"] + L["n"])
    cols = range(L["first_col"], L["first_col"] + L["n"])
    _assert_ine_layout(S, cols, rows)

    t1, t2, t3 = S["Tabla1"], S["Tabla2"], S["Tabla3"]
    codes, labels = _ine_codes(t2, rows)
    r1 = lambda k: _ine_row(t1, L[k], cols)
    X = r1("row_output")

    fd_labels = [str(t2[7][j] or "").strip() for j in _INE_FD_COLS]
    dropped = [str(t2[7][sub] or "").strip() for sub, _, _ in _INE_FD_GROUPS]

    if variant == "interior":
        Z = _ine_block(t2, rows, cols)
        Y = _ine_block(t2, rows, _INE_FD_COLS)
        Y_labels = list(fd_labels)
        VA_labels = ["Importaciones de bienes y servicios (consumos "
                     "intermedios importados)",
                     "Impuestos netos sobre los productos",
                     "Remuneración de los asalariados",
                     "Otros impuestos netos sobre la producción",
                     "Excedente de explotación bruto / Renta mixta"]
        VA = np.vstack([_ine_block(t3, rows, cols).sum(0),
                        r1("row_taxes_products"), r1("row_compensation"),
                        r1("row_other_taxes"), r1("row_gos")])
        scope = ("Producción interior (Tabla 2). Las importaciones son un input "
                 "primario, no valor añadido: las dos primeras filas del bloque "
                 "VA no son VAB.")
    else:
        Z = _ine_block(t1, rows, cols)
        Y = np.hstack([_ine_block(t1, rows, _INE_FD_COLS),
                       -r1("row_imports").reshape(-1, 1)])
        Y_labels = fd_labels + ["Importaciones de bienes y servicios "
                                "(columna negativa, DERIVADA)"]
        VA_labels = ["Impuestos netos sobre los productos",
                     "Remuneración de los asalariados",
                     "Otros impuestos netos sobre la producción",
                     "Excedente de explotación bruto / Renta mixta"]
        VA = np.vstack([r1("row_taxes_products"), r1("row_compensation"),
                        r1("row_other_taxes"), r1("row_gos")])
        scope = ("Flujos totales (Tabla 1): interiores e importados juntos. Las "
                 "importaciones van como columna negativa de demanda final para "
                 "cerrar la identidad de fila. Los multiplicadores tratan un "
                 "input importado como si se produjese en España.")

    residual_note = ""
    gap = X - (Z.sum(1) + Y.sum(1))
    if unbalanced == "residual_column" and np.abs(gap).max() > _INE_TOL:
        worst = int(np.abs(gap).argmax())
        affected = int((np.abs(gap) > _INE_TOL).sum())
        Y = np.hstack([Y, gap.reshape(-1, 1)])
        Y_labels = Y_labels + ["Discrepancia estadística (RESIDUAL, calculada "
                               "por el cargador; el INE no la publica)"]
        residual_note = (
            f" Se añadió una columna de demanda final RESIDUAL, calculada aquí "
            f"y no publicada por el INE: {np.abs(gap).sum():,.1f} millones de "
            f"euros en total repartidos en {affected} producto(s), el mayor "
            f"{gap[worst]:,.1f} en «{labels[worst]}». Véase OQ-D-04.")

    year = _infer_ine_year(S)
    table = IOTable(
        table_id=f"ES-TIO-PXP-{year}-{variant}", country="España", year=year,
        unit="millones de euros, precios corrientes, precios básicos",
        classification="CPA 2008 (64 productos, numeración TIO del INE)",
        sector_codes=codes, sector_labels=labels,
        Z=Z, Y=Y, Y_labels=Y_labels, VA=VA, VA_labels=VA_labels, X=X,
        source=(f"INE, Contabilidad Nacional Anual de España, Revisión "
                f"Estadística 2024. Tablas Input-Output {year} ({path.name})"),
        retrieved_at=datetime.now(timezone.utc),
        notes=("Producto x producto, precios básicos. " + scope
               + f" Año de referencia leído de la hoja 'Lista_Tablas', nunca "
                 f"del nombre del fichero, que sólo lleva dos dígitos "
                 f"(OQ-D-01). Se descartaron {len(dropped)} columnas subtotal "
                 f"de demanda final ({', '.join(dropped)}) para no contar dos "
                 f"veces; cada subtotal se comprobó contra sus componentes "
                 f"antes de descartarlo." + residual_note))
    _assert_balances(table, f"{path.name} ({variant})")
    return table


# ---------------------------------------------------------------------------
# The Spanish supply-use tables (INE)
# ---------------------------------------------------------------------------

# Layout of `cne_tod_22.xlsx`, 0-based. Same discipline as `_INE`: every index
# is re-derived from an identity on load.
_TOD = dict(
    col_label=1, first_row=9, n_products=110,
    first_col=2, n_activities=81,
    row_activity_labels=7, row_activity_index=8,
    # supply sheet
    s_output=83, s_imports=84, s_imports_eu=85, s_imports_nonue=86,
    s_supply_basic=87, s_trade=88, s_transport=89, s_taxes=90,
    s_supply_purch=91,
    # use sheet
    u_intermediate=83, u_final=94, u_uses=95,
    u_ic_total=124, u_compensation=126, u_wages=127, u_social=128,
    u_other_taxes=129, u_gos=130, u_mixed=131, u_gva=132, u_output=133,
)
_TOD_FD_GROUPS = ((84, (85, 86, 87)), (88, (89, 90)), (91, (92, 93)))
_TOD_FD_COLS = (85, 86, 87, 89, 90, 92, 93)


def load_ine_tod(path: Path | str) -> SupplyUseTables:
    """Load the INE's supply and use tables at their published detail.

    **110 products by 81 activities** — the finest table the INE publishes, and
    far finer than either its own input-output table or Eurostat's, both of
    which come at 64. `OQ-S-05` opened on the assumption that more detail would
    have to be requested; it did not, and this is the file that settled it.

    Two things it gives the project that no IOT can.

    **The margin identities become testable.** A supply table carries trade
    margins, transport margins and taxes less subsidies on products as explicit
    columns, so `ID-19` — that a margin column sums to zero economy-wide and
    that its negatives are mandatory — is arithmetic here rather than
    `NOT APPLICABLE`. That is what `OQ-D-03` said the project needed and could
    not get from an analytical IOT.

    **It balances.** Domestic uses equal domestic output and imported uses equal
    imports, for all 64 products of the aggregated sheets, to 0.0 — where the
    published input-output table fails by 4,921.6 on one of them (`OQ-D-04`).
    Where a clean Spanish domestic table is wanted, this is the source.

    Loaded at purchasers' prices, because that is the valuation at which the
    110-product detail exists. The basic-price, domestic and import versions are
    published only at 64 (sheets `Tabla3`, `Tabla4`, `Tabla5`) and are not
    loaded here.
    """
    path = Path(path)
    S = _open_workbook(path)
    for sheet in ("Tabla1", "Tabla2"):
        if sheet not in S:
            raise LoaderError(f"{path.name} has no {sheet!r}; found: "
                              f"{', '.join(S)}. This loader expects the INE's "
                              f"`cne_tod_YY.xlsx` layout.")
    L = _TOD
    sup, use = S["Tabla1"], S["Tabla2"]
    rows = range(L["first_row"], L["first_row"] + L["n_products"])
    cols = range(L["first_col"], L["first_col"] + L["n_activities"])

    V = _ine_block(sup, rows, cols)
    U = _ine_block(use, rows, cols)
    Y = _ine_block(use, rows, _TOD_FD_COLS)
    P = lambda g, c: _ine_row_col(g, rows, c)
    q, imports = P(sup, L["s_output"]), P(sup, L["s_imports"])
    trade, transport = P(sup, L["s_trade"]), P(sup, L["s_transport"])
    taxes = P(sup, L["s_taxes"])
    W = np.vstack([_ine_row(use, L[k], cols) for k in
                   ("u_compensation", "u_other_taxes", "u_gos", "u_mixed")])
    g = _ine_row(use, L["u_output"], cols)

    checks = [
        ("supply rows sum to product output", V.sum(1), q),
        ("supply at basic prices = output + imports",
         P(sup, L["s_supply_basic"]), q + imports),
        ("supply at purchasers' = basic + margins + taxes",
         P(sup, L["s_supply_purch"]),
         P(sup, L["s_supply_basic"]) + trade + transport + taxes),
        ("imports EU + non-EU = total imports",
         P(sup, L["s_imports_eu"]) + P(sup, L["s_imports_nonue"]), imports),
        ("use rows sum to intermediate demand", U.sum(1),
         P(use, L["u_intermediate"])),
        ("final-demand components sum to total final demand", Y.sum(1),
         P(use, L["u_final"])),
        ("total uses = intermediate + final", P(use, L["u_uses"]),
         P(use, L["u_intermediate"]) + Y.sum(1)),
        ("compensation = wages + social contributions",
         _ine_row(use, L["u_compensation"], cols),
         _ine_row(use, L["u_wages"], cols)
         + _ine_row(use, L["u_social"], cols)),
        ("gross value added = its four components",
         _ine_row(use, L["u_gva"], cols), W.sum(0)),
        ("use columns sum to intermediate consumption",
         _ine_row(use, L["u_ic_total"], cols), U.sum(0)),
        ("output = intermediate consumption + value added", g,
         _ine_row(use, L["u_ic_total"], cols) + W.sum(0)),
        # THE central identity of the framework, and the reason a supply-use
        # pair is worth more than an IOT: supply and use meet product by
        # product, at purchasers' prices, before anyone assumes anything.
        ("supply at purchasers' prices == total uses",
         P(sup, L["s_supply_purch"]), P(use, L["u_uses"])),
    ]
    for sub, comp in _TOD_FD_GROUPS:
        checks.append((f"final-demand subtotal in column {sub}",
                       P(use, sub), sum(P(use, c) for c in comp)))
    for what, a, b in checks:
        d = float(np.abs(np.asarray(a) - np.asarray(b)).max())
        if d > _INE_TOL:
            raise LoaderError(
                f"the INE supply-use workbook's layout no longer matches the "
                f"one this loader hard-codes.\n  failed check: {what}\n"
                f"  off by {d:,.4f} (tolerance {_INE_TOL:g}, million EUR)\n"
                f"Fix _TOD in io_loader.py against the actual sheet.")

    p_codes, p_labels = _ine_codes(use, rows)
    a_labels = [str(sup[L["row_activity_labels"]][j] or "").strip() for j in cols]
    a_codes = [str(sup[L["row_activity_index"]][j] or "").strip() for j in cols]
    year = _infer_ine_year(S)
    return SupplyUseTables(
        table_id=f"ES-SUT-{year}", country="España", year=year,
        unit="millones de euros, precios corrientes",
        classification="CPA 2008 (110 productos) x CNAE 2009 (81 ramas)",
        product_codes=p_codes, product_labels=p_labels,
        activity_codes=a_codes, activity_labels=a_labels,
        V=V, U=U, Y=Y,
        Y_labels=[str(use[7][c] or "").strip() for c in _TOD_FD_COLS],
        W=W, W_labels=["Remuneración de los asalariados",
                       "Otros impuestos netos sobre la producción",
                       "Excedente bruto de explotación", "Renta mixta bruta"],
        imports=imports, total_margins=trade + transport,
        trade_margins=trade, transport_margins=transport,
        taxes_on_products=taxes, q=q, g=g,
        source=(f"INE, Contabilidad Nacional Anual de España, Revisión "
                f"Estadística 2024. Tablas de Origen y Destino {year} "
                f"({path.name})"),
        retrieved_at=datetime.now(timezone.utc),
        notes=("Origen a precios básicos y destino a precios de adquisición, "
               "110 productos x 81 ramas — el mayor detalle que publica el INE. "
               "Las columnas de márgenes e impuestos vienen explícitas, así que "
               "las identidades de valoración son comprobables aquí y no en una "
               "TIO analítica (OQ-D-03). Las versiones a precios básicos, "
               "interior e importaciones sólo se publican a 64 productos y no "
               "se cargan."))


# ---------------------------------------------------------------------------
# The project's own interchange format (MVP_0.1 §4.1)
# ---------------------------------------------------------------------------

_REQUIRED_META = ("country", "year", "unit", "classification", "source")


def load_io_table(path: Path | str, sheet: str = "table") -> IOTable:
    """Load a table in the project's interchange format.

    Blocks are found by their labels, not by fixed positions (§4.1). The sheet
    holds, in order: a header row of sector codes, then one row per sector, then
    a row labelled with each value-added component, then a row `Output`. Final
    demand columns follow the sector columns and are named in the header.

    A separate `metadata` sheet must carry country, year, unit, classification
    and source as key/value rows. Missing metadata is an error: an IO table
    without its price basis and classification cannot be used safely.
    """
    sheets = _open_workbook(path)
    if sheet not in sheets:
        raise LoaderError(f"no sheet named {sheet!r}; found: {', '.join(sheets)}")
    if "metadata" not in sheets:
        raise LoaderError("no 'metadata' sheet. It must carry: "
                          + ", ".join(_REQUIRED_META))

    meta = {str(r[0]).strip().lower(): r[1] for r in sheets["metadata"]
            if r and r[0] is not None}
    missing = [k for k in _REQUIRED_META if k not in meta]
    if missing:
        raise LoaderError(f"metadata sheet is missing: {', '.join(missing)}")

    R = [r for r in sheets[sheet] if r and any(c is not None for c in r)]
    header = [str(c).strip() if c is not None else "" for c in R[0]]
    try:
        out_row = next(i for i, r in enumerate(R)
                       if str(r[0]).strip().lower() in ("output", "total output"))
    except StopIteration:
        raise LoaderError("no row labelled 'Output' or 'Total output'; §4.1 "
                          "requires one so the blocks can be located") from None

    while len(header) > 1 and not header[-1]:
        header.pop()
    labels_col = [str(r[0]).strip() if r[0] is not None else "" for r in R]

    # WHERE THE SECTOR BLOCK ENDS. Between the header and `Output` sit the
    # sector rows and then the value-added rows, and nothing marks the join --
    # so it is found the way §4.1 finds every block, by the labels: the sector
    # rows are the longest run whose labels match the header's leading codes,
    # one for one and in order. What follows that run down the page is value
    # added; what follows it across the header is final demand.
    #
    # Counting non-empty row labels instead, as this did until 2026-08-25, made
    # every value-added row a sector. `n` came out too large, no rows were left
    # for value added, and the loader rejected a well-formed file with a
    # complaint about the rows it had just miscounted. This is the only route
    # into the engine for a table from anywhere other than the UK or Spain, and
    # nothing exercised it -- no test, no validator, no fixture. Writing the
    # user guide is what ran it. `run_interchange_roundtrip.py` now does.
    n = 0
    while (1 + n < out_row and 1 + n < len(header)
           and labels_col[1 + n] and labels_col[1 + n] == header[1 + n]):
        n += 1
    if n == 0:
        raise LoaderError(
            f"no sector rows found. §4.1 locates the sector block by matching "
            f"the leading row labels against the header: row 2 is labelled "
            f"{labels_col[1]!r} and the first sector column is headed "
            f"{header[1]!r}. The sector rows must carry the same codes as the "
            f"sector columns, in the same order.")

    sector_codes = header[1:1 + n]   # == labels_col[1:1 + n], by the match
    va_start = 1 + n
    va_labels = [labels_col[i] for i in range(va_start, out_row)]
    if not va_labels:
        raise LoaderError(
            f"{n} sector row(s) run straight into the Output row, so there are "
            f"no value-added rows; §4.1 requires at least one. Value added is "
            f"not optional: without it a column does not add up to output.")
    stray = [lab for lab in va_labels if lab in header[1:1 + n]]
    if stray:
        raise LoaderError(
            f"the sector code(s) {', '.join(stray)} appear below the sector "
            f"block. Sector rows must be contiguous and in header order — a "
            f"value-added row cannot sit between two of them, because the "
            f"sector block is located by that run.")

    n_cols_total = len(header) - 1
    if n_cols_total <= n:
        raise LoaderError(f"{n_cols_total} data columns for {n} sectors: §4.1 "
                          f"requires at least one final-demand column")
    Y_labels = header[1 + n:1 + n_cols_total]

    Z = np.array([[_num(R[1 + i][1 + j]) for j in range(n)] for i in range(n)])
    Y = np.array([[_num(R[1 + i][1 + n + c]) for c in range(len(Y_labels))]
                  for i in range(n)])
    VA = np.array([[_num(R[va_start + m][1 + j]) for j in range(n)]
                   for m in range(len(va_labels))])
    X = np.array([_num(R[out_row][1 + j]) for j in range(n)])

    table = IOTable(
        table_id=str(meta.get("table_id", Path(path).stem)),
        country=str(meta["country"]), year=int(meta["year"]),
        unit=str(meta["unit"]), classification=str(meta["classification"]),
        sector_codes=sector_codes,
        # `meta` keys were lowercased on the way in, so the lookup must be
        # too. It was not, so every `label_B` row in a metadata sheet was
        # silently ignored and the report named sectors by their codes.
        sector_labels=[str(meta.get(f"label_{c}".lower(), c))
                       for c in sector_codes],
        Z=Z, Y=Y, Y_labels=Y_labels, VA=VA, VA_labels=va_labels, X=X,
        source=str(meta["source"]), retrieved_at=datetime.now(timezone.utc),
        notes=str(meta.get("notes") or "") or None,
        provenance=_read_provenance(sheets, sector_codes),
        lineage=_read_lineage(meta))
    _assert_balances(table, Path(path).name)
    return table


def _read_provenance(sheets: dict, sector_codes: list[str]):
    """Read a `Provenance` sheet back, if the file carries one.

    This engine writes one beside every table it exports. Reading it is what
    keeps a second split from promoting the first split's estimates to
    observations -- a table that has been through a disaggregation balances
    exactly as well as a published one, so nothing in the numbers would give
    it away.

    The sheet stores the §A.1 data status, which is coarser than the internal
    label: `USER_CONSTRAINT` is written as OBSERVED, so a pinned cell comes
    back as an ordinary observation. That loss is deliberate and stated here
    rather than hidden -- on reload the analyst who pinned it is not in the
    room, and the cell is as good as any other observation to whoever is.
    """
    import numpy as np

    from .models import CellLabel

    name = next((s for s in sheets if s.strip().lower() == "provenance"), None)
    if name is None:
        return None
    back = {"OBSERVED": CellLabel.OBSERVED,
            "ESTIMATED": CellLabel.PROXY_ESTIMATED,
            "BALANCED": CellLabel.BALANCED_ADJUSTMENT}
    R = [r for r in sheets[name] if r and any(c is not None for c in r)]
    n = len(sector_codes)
    if len(R) < 1 + n:
        raise LoaderError(
            f"the Provenance sheet has {len(R) - 1} data row(s) for {n} "
            f"sectors. A provenance grid that does not match the table is "
            f"worse than none: it would mislabel cells rather than leave them "
            f"unlabelled. Delete the sheet or correct it.")
    prov = np.empty((n, n), dtype=object)
    for i in range(n):
        for j in range(n):
            cell = R[1 + i][1 + j]
            key = str(cell).strip().upper() if cell is not None else "OBSERVED"
            if key not in back:
                raise LoaderError(
                    f"Provenance cell ({sector_codes[i]}, {sector_codes[j]}) "
                    f"reads {cell!r}; expected one of "
                    f"{', '.join(sorted(back))}.")
            prov[i, j] = back[key]
    return prov


def _read_lineage(meta: dict) -> list[str]:
    """The table's ancestry: `lineage_1`, `lineage_2`, … then `derived_from`.

    Oldest first, so appending this run's own line keeps the order. A table
    from a statistical office has neither key and comes back with an empty
    list, which is the correct answer -- it is the start of a lineage, not a
    step in one.
    """
    older = sorted((k for k in meta if k.startswith("lineage_")),
                   key=lambda k: int(k.rsplit("_", 1)[1]))
    out = [str(meta[k]) for k in older]
    # `derived_from` is a one-line summary for whoever opens the workbook, and
    # on a file this engine wrote it restates the last lineage row with the
    # estimated share appended -- a share the Provenance sheet already carries
    # cell by cell. Taking it as well would double the newest step every time
    # the file went round the loop. It is read only when there is no `lineage_`
    # row at all, which is the hand-written case.
    if not out and meta.get("derived_from"):
        out.append(str(meta["derived_from"]))
    return out


# ---------------------------------------------------------------------------
# Allocation keys (MVP_0.1 §4.2)
# ---------------------------------------------------------------------------

def load_allocation_keys(path: Path | str, applies_to: str = "output",
                         sheet: str | None = None) -> AllocationKey:
    """Load one proxy table: new_sector_code, new_sector_label, value, source,
    source_year, strength.

    One file per block, which is what makes the multi-proxy splitting of §8.C
    possible from the MVP onward.
    """
    sheets = _open_workbook(path)
    name = sheet or next(iter(sheets))
    R = [r for r in sheets[name] if r and any(c is not None for c in r)]
    head = [str(c).strip().lower() if c is not None else "" for c in R[0]]

    def col(*names) -> int:
        for nm in names:
            if nm in head:
                return head.index(nm)
        raise LoaderError(f"{Path(path).name}: no column named "
                          f"{' or '.join(names)}; found {head}")

    c_code, c_val = col("new_sector_code", "code"), col("value", "raw_value")
    c_src, c_yr = col("source"), col("source_year", "year")
    c_str = col("strength")

    codes, vals, srcs, yrs, strs = [], [], [], [], []
    for r in R[1:]:
        if r[c_code] is None:
            continue
        codes.append(str(r[c_code]).strip())
        vals.append(_num(r[c_val]))
        srcs.append(str(r[c_src]))
        yrs.append(int(r[c_yr]))
        strs.append(str(r[c_str]).strip().lower())

    if len(set(srcs)) > 1 or len(set(yrs)) > 1:
        # Not fatal, but the AllocationKey carries one source and one year, so
        # say which one is being recorded rather than picking silently.
        raise LoaderError(
            f"{Path(path).name}: rows disagree on source or source_year "
            f"({sorted(set(srcs))}, {sorted(set(yrs))}). One AllocationKey "
            f"records one source. Split the file, or reconcile it.")

    weakest = min(strs, key=lambda s: ["strong", "medium", "weak"].index(s)
                  if s in ("strong", "medium", "weak") else 0)
    # The key is only as strong as its weakest row: a split resting on one weak
    # proxy is a weak split, whatever the other rows say.
    for s in strs:
        if s not in ("strong", "medium", "weak"):
            raise LoaderError(f"strength {s!r} is not strong/medium/weak")
        if ["strong", "medium", "weak"].index(s) > \
           ["strong", "medium", "weak"].index(weakest):
            weakest = s

    return AllocationKey(
        key_id=Path(path).stem, applies_to=applies_to,
        new_sector_codes=codes, raw_values=vals,
        source=srcs[0], source_year=yrs[0],
        strength=ProxyStrength(weakest),
        notes=f"loaded from {Path(path).name}")


# ---------------------------------------------------------------------------
# The ONS supply-use tables — the second fixture, and NOT a SupplyUseTables
# ---------------------------------------------------------------------------

@dataclass
class OnsSupplyUse:
    """One year of the ONS's published supply and use tables.

    **This is deliberately not a `SupplyUseTables`**, and the reason is the
    whole point of the object. That class promises `V`, the supply matrix of
    products by industries — and the ONS's published workbook does not contain
    one. Its supply table gives each product's *total* domestic output beside
    its imports, margins and taxes; who made what is not published. Filling `V`
    with anything would be an invention the accounting could not detect, which
    is exactly what `load_sut` refuses to do for Eurostat's combined margins.

    So this carries what the source actually has, and the identities that need
    `V` — `ID-07`, and `ID-09`'s margins by industry — stay NOT APPLICABLE on
    this fixture and say why.
    """
    year: int
    product_codes: list[str]
    industry_codes: list[str]
    U: np.ndarray                  # intermediate use, products x industries
    Y: np.ndarray                  # final demand, products x categories
    Y_labels: list[str]
    output_basic: np.ndarray       # by product, total domestic output
    imports: np.ndarray            # by product, goods and services
    margins: np.ndarray            # by product, distributors' trading margins
    taxes_on_products: np.ndarray  # by product, net of subsidies
    total_supply: np.ndarray       # by product, at purchasers' prices
    total_demand: np.ndarray       # by product, as published
    ic_by_industry: np.ndarray     # published total intermediate consumption
    taxes_on_production: np.ndarray
    compensation: np.ndarray
    gos_mixed: np.ndarray
    gva: np.ndarray
    output_by_industry: np.ndarray
    source: str


_ONS_VA_ROWS = {
    "ic": "Total intermediate consumption at purchasers' prices",
    "taxes": "Taxes less subsidies on production",
    "coe": "Compensation of employees",
    "gos": "Gross operating surplus and mixed income",
    "gva": "Gross valued added at basic prices",     # the source's own spelling
    "output": "Total output at basic prices",
}


def load_ons_sut(path: Path | str, year: int) -> OnsSupplyUse:
    """One year out of `NSO_UK_04`, the ONS supply-use workbook (1997-2023).

    The workbook holds five sheets per year. Three are used here: the supply
    table (product totals and valuation columns), the intermediate-consumption
    matrix with the value-added block underneath it, and final demand.

    Products and industries are taken from the sheets themselves rather than
    assumed, and the value-added rows are found **by their printed labels** —
    including the source's own "Gross valued added at basic prices", which is a
    typo in the workbook and is matched as printed rather than corrected.
    """
    import openpyxl

    path = Path(path)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)

    def sheet(prefix: str):
        name = f"Table {prefix} {year}"
        if name not in wb.sheetnames:
            raise LoaderError(
                f"{path.name} has no sheet {name!r}. Years present: "
                f"{sorted({int(s.rsplit(' ', 1)[1]) for s in wb.sheetnames if s[-4:].isdigit()})}")
        return list(wb[name].iter_rows(values_only=True))

    use, supply, final = sheet("2 - Int Con"), sheet("1 - Supply"), sheet("2 - Final Demand")

    industries = [str(c).strip() for c in use[3][2:106] if c]
    prod_rows = [r for r in use if r and str(r[0] or "").startswith("CPA_")]
    products = [str(r[0]).strip() for r in prod_rows]
    n_ind = len(industries)
    U = np.array([[_num(r[j]) for j in range(2, 2 + n_ind)] for r in prod_rows],
                 float)

    va = {}
    for row in use:
        label = str(row[1] or "").strip()
        for key, want in _ONS_VA_ROWS.items():
            if label == want:
                va[key] = np.array([_num(row[j]) for j in range(2, 2 + n_ind)],
                                   float)
    missing = set(_ONS_VA_ROWS) - set(va)
    if missing:
        raise LoaderError(
            f"{path.name} {year}: the value-added block is missing "
            f"{sorted(_ONS_VA_ROWS[k] for k in missing)}. The labels are matched "
            f"as printed, including the source's own spelling.")

    sup = {str(r[0]).strip(): r for r in supply
           if r and str(r[0] or "").startswith("CPA_")}
    fin = {str(r[0]).strip(): r for r in final
           if r and str(r[0] or "").startswith("CPA_")}
    if set(sup) != set(products) or set(fin) != set(products):
        raise LoaderError(
            f"{path.name} {year}: the three sheets do not carry the same "
            f"products — supply {len(sup)}, use {len(products)}, final demand "
            f"{len(fin)}. They are matched by code, never by position.")

    def col(table, index):
        return np.array([_num(table[p][index]) for p in products], float)

    # Final demand: the four consumption columns, three capital columns and the
    # two export columns, taking the components and never the printed subtotals.
    y_cols = [(2, "households"), (3, "npish"), (4, "central government"),
              (5, "local government"), (8, "gross fixed capital formation"),
              (9, "valuables"), (10, "changes in inventories"),
              (15, "exports of goods"), (16, "exports of services")]
    Y = np.column_stack([col(fin, i) for i, _ in y_cols])

    return OnsSupplyUse(
        year=year, product_codes=products, industry_codes=industries,
        U=U, Y=Y, Y_labels=[lab for _, lab in y_cols],
        output_basic=col(sup, 2), imports=col(sup, 7), margins=col(sup, 8),
        taxes_on_products=col(sup, 9), total_supply=col(sup, 10),
        total_demand=col(fin, 21),
        ic_by_industry=va["ic"], taxes_on_production=va["taxes"],
        compensation=va["coe"], gos_mixed=va["gos"], gva=va["gva"],
        output_by_industry=va["output"],
        source=f"ONS, Input-output supply and use tables, Blue Book 2025 "
               f"({path.name}), {year}")
