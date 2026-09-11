"""
Every `IOTable(...)` in the engine, and whether the cross-cutting fields travel.

WHY A CHECK ON THE CLASS AND NOT ON THE INSTANCES
---------------------------------------------------
Between 2026-09-08 and 09 this engine gained satellite accounts, a type II
closure and `--plan`, and **four times** the same defect appeared: a code path
builds a fresh `IOTable`, the fields that ride on a table do not come with it,
and nothing says so.

    split -> export -> read back        the account came back gone
    regionalise                          the account went in and vanished
    the multi-split loop                 latent: rebuilt without them
    read a file, re-run from a workbook  ERASED, on the documented route

Three were found by walking a chain and one by reading for this file. Fixing
them one at a time has a bad record: each fix was written the day after the
feature and the next feature broke the next chain. So this checks the CLASS.

`ast` finds every construction of `IOTable` under `src/quadrium/`, and each one
must be DECLARED here: it carries the fields, or it sets them immediately after,
or there is a reason it does not. **An undeclared construction fails the suite**,
the same rule `run_refusal_coverage.py` applies to a refusal with no reason. The
next `IOTable(` anybody writes has to say what it does about them, and the fifth
case of this family does not get to exist.

WHAT COUNTS AS CARRYING
-------------------------
Three honest answers, and the file says which each site gives:

`constructor`  the fields are passed in the call.
`after`        the call is followed, in the same function, by an assignment to
               `.satellites` or `.type_ii`. `run_scenario` does this because it
               needs the split's weights, which do not exist yet at the call.
`none`         nothing carries them, and the reason is one of:
                 `primary`   a table read from a statistical office. There is no
                             parent to carry from; an office's file has no
                             satellite account until someone attaches one.
                 `no-parent` the object it is built from cannot hold them. A
                             supply-use pair has neither field, so `to_iot` has
                             nothing to lose.
                 `by-design` a parent exists and the field is deliberately not
                             carried, with the reason written at the site.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "quadrium"

FAIL = []

# The declaration. Keyed by `file.py::function`, because a line number moves
# every time somebody edits above it -- which is how `run_refusal_coverage`
# silently re-labelled 38 sites once.
DECLARED = {
    "scenarios.py::run_scenario": (
        "after",
        "the expanded table. `satellites` needs the split's weights and "
        "`type_ii` the expanded labels, neither of which exists at the call, "
        "so both are set on the next lines. `interregional` is set EMPTY on "
        "purpose: it is the archive's leakage for the table as loaded, a "
        "split changes the block it was measured on, and the report reads it "
        "from the original table instead."),
    "regionalise.py::to_table": (
        "constructor",
        "`satellites=` scaled by the region's share of national output. "
        "`type_ii` is deliberately NOT carried: it names a wages row and a "
        "household column, and a regionalised table has one value-added row "
        "and one final-demand column, both residuals. Said in the lineage."),
    "io_loader.py::load_io_table": (
        "constructor",
        "the interchange format carries both, so reading them back is the "
        "whole point of the Satellites sheet."),
    "disaggregation.py::split_sectors": (
        "constructor",
        "the loop variable between one split and the next, with the accounts "
        "DIVIDED as it goes: carrying the parent's values into a table that "
        "has grown leaves 64 figures on 65 sectors, which __post_init__ now "
        "refuses. Dividing per iteration keeps the object well formed after "
        "each."),
    "models.py::to_iot": (
        "no-parent",
        "built from a supply-use pair, which has neither field. A workbook "
        "that declares them attaches them after loading, in build_config."),
    "io_loader.py::load_uk_analytical_iot": ("primary", "the ONS workbook."),
    "io_loader.py::load_ine_tio": ("primary", "the INE workbook."),
    "io_loader.py::load_idescat_mioc": ("primary", "the IDESCAT workbook."),
    "io_loader.py::load_rokicki_austria": ("primary", "the MRIO archive."),
    "io_loader.py::load_eu_mrio_2018": (
        "constructor",
        "passes `interregional`, the leakage computed on the archive's full "
        "inverse. `satellites` and `type_ii` have no parent here: a table "
        "from an archive has no account until a workbook attaches one."),
    "eurostat.py::load_iot": ("primary", "a Eurostat download."),
}

# `interregional` joined on 2026-09-11, and it is the first field whose right
# answer is almost everywhere NOT to travel: it is the archive's leakage for a
# region as loaded, and a split changes the block it was measured on. Being
# listed here is what makes each site say so rather than drop it quietly.
FIELDS = ("satellites", "type_ii", "interregional")


def check(label, ok, detail=""):
    print(f"  [{'ok' if ok else 'FAIL'}] {label}")
    if detail:
        print(f"         {detail}")
    if not ok:
        FAIL.append(label)


def sites() -> dict:
    """Every `IOTable(...)` call, keyed by file::function, with what it does."""
    found = {}
    for path in sorted(SRC.glob("*.py")):
        tree = ast.parse(path.read_text())
        parent = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parent[child] = node

        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "IOTable"):
                continue
            fn, up = "<module>", parent.get(node)
            while up is not None:
                if isinstance(up, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fn = up.name
                    break
                up = parent.get(up)
            key = f"{path.name}::{fn}"

            passed = {k.arg for k in node.keywords if k.arg in FIELDS}

            # An assignment to `.satellites` / `.type_ii` anywhere in the same
            # function counts as `after`. Deliberately not "the next line":
            # tying this to adjacency would fail the moment somebody inserts a
            # comment, and the question is whether the function handles them.
            after = set()
            enclosing = None
            up = parent.get(node)
            while up is not None:
                if isinstance(up, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    enclosing = up
                    break
                up = parent.get(up)
            if enclosing is not None:
                for n in ast.walk(enclosing):
                    if isinstance(n, ast.Attribute) and n.attr in FIELDS \
                            and isinstance(parent.get(n), ast.Assign):
                        after.add(n.attr)

            found[key] = {"line": node.lineno, "passed": passed,
                          "after": after, "file": path.name}
    return found


def main():
    found = sites()

    print(f"    {len(found)} construction(s) of IOTable under src/quadrium/")
    print()
    print(f"    {'site':44}{'declared':<12}{'does'}")
    for key in sorted(found):
        d = DECLARED.get(key)
        does = ("constructor" if found[key]["passed"]
                else "after" if found[key]["after"] else "none")
        print(f"    {key:44}{(d[0] if d else '—'):<12}{does}")
    print()

    # 1 -- nothing undeclared. This is the check that stops the class.
    undeclared = sorted(set(found) - set(DECLARED))
    check("every IOTable construction is declared here",
          not undeclared,
          "UNDECLARED: " + ", ".join(undeclared) if undeclared else
          "a new one has to say what it does about the fields that ride on a "
          "table, or the suite fails")

    # 2 -- and nothing declared has disappeared, so a stale reason cannot
    #      outlive the site it explained.
    orphaned = sorted(set(DECLARED) - set(found))
    check("and no declaration outlives the site it explained",
          not orphaned,
          "ORPHANED: " + ", ".join(orphaned) if orphaned else
          "a reason for a call nobody makes is a reason nobody can check")

    # 3 -- what each site claims is what it does.
    for key in sorted(set(found) & set(DECLARED)):
        how, why = DECLARED[key]
        got = found[key]
        if how == "constructor":
            check(f"{key} carries them in the call",
                  bool(got["passed"]),
                  why + f" — passes {sorted(got['passed']) or 'nothing'}")
        elif how == "after":
            check(f"{key} sets them on the table it built",
                  got["after"] >= set(FIELDS),
                  why + f" — assigns {sorted(got['after'])}")
        else:
            check(f"{key} carries nothing, and {how} is why",
                  not got["passed"] and not got["after"], why)

    # 4 -- the fourth instance was not a construction at all. It was an
    #      unconditional ASSIGNMENT in build_config that erased what the file
    #      carried, so an ast walk over `IOTable(` would never have seen it.
    #      Checked by reading the source, because a defect this file cannot
    #      see is one it should say it cannot see.
    cfg = (SRC / "config.py").read_text()
    check("build_config adds or replaces satellites, it does not erase them",
          "table.satellites = {**from_file, **from_book}" in cfg,
          "an unconditional assignment wiped the account a file carried the "
          "moment a workbook that did not repeat the sheet ran on it")
    check("and keeps a type II closure the workbook is silent about",
          "elif getattr(table, \"type_ii\", None):" in cfg,
          "silence is not a request for deletion")

    print()
    print("    Four instances of one defect in three days. Fixing them one at")
    print("    a time has a bad record; this is the class, and an undeclared")
    print("    construction fails the suite.")

    print("\n" + "=" * 78)
    if FAIL:
        print(f"{len(FAIL)} check(s) FAILED: {', '.join(FAIL)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
