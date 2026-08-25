#!/usr/bin/env bash
#
# Every check this repository can run without a network, in one command.
#
# The same script runs on a laptop and in CI, which is the point: a check that
# only exists inside a workflow file is a check nobody runs before pushing, and
# a check that only runs locally is one that passes because of something
# installed on one machine three months ago.
#
# It works in both repositories. The private one keeps its validators under
# `library/validators/` and carries checks that read the methodological library;
# the public one has them at `validators/` and carries the subset that runs
# without it. The only difference is the directory, so the script finds it
# rather than being told.
#
#     ./check.sh            everything
#     ./check.sh --tests    unit tests only
#     ./check.sh --quick    skip the slowest validators
#
# Exit code 0 means every check passed. Anything else prints the output of the
# ones that did not, in full, because a failure you have to go and look up is a
# failure you will not look up.

set -uo pipefail

if [ -d library/validators ]; then
    VDIR=library/validators
    WHICH="private tree"
else
    VDIR=validators
    WHICH="public tree"
fi

PY=${PYTHON:-python3}

# numpy deprecated converting an array with ndim > 0 to a scalar in 1.25 and
# made it an ERROR in 2.3. Between those two releases it is a warning nobody
# reads, so a `float(one_element_array)` sits in the tree passing every check
# until someone with a current numpy runs it. Two were found that way, by CI,
# on a machine that was not this one. Raising it here means the next one fails
# on whoever writes it.
export PYTHONWARNINGS="${PYTHONWARNINGS:-error:Conversion of an array with ndim > 0 to a scalar:DeprecationWarning}"
ONLY_TESTS=0
QUICK=0
for arg in "$@"; do
    case "$arg" in
        --tests) ONLY_TESTS=1 ;;
        --quick) QUICK=1 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

echo "== $WHICH, $($PY -V 2>&1)"
echo

# ---- unit tests ----------------------------------------------------------
echo "-- unit tests"
if ! $PY -m pytest tests -q; then
    echo
    echo "FAILED: unit tests"
    exit 1
fi
[ "$ONLY_TESTS" = 1 ] && exit 0

# ---- validators ----------------------------------------------------------
# Each one is a check against something a statistical office or a manual
# published, and each prints what it measured. Their output is kept and shown
# only for the ones that fail: 70 passing validators are 4,000 lines nobody
# reads, and one failing validator is the only thing that matters.
echo
echo "-- validators"
LOGS=$(mktemp -d)
trap 'rm -rf "$LOGS"' EXIT
FAILED=()
COUNT=0
START=$(date +%s)

for v in "$VDIR"/*.py; do
    name=$(basename "$v")
    case "$name" in
        __init__.py) continue ;;
    esac
    # `--quick` drops the two that read 27 years of UK supply-use tables.
    if [ "$QUICK" = 1 ]; then
        case "$name" in
            run_uk_sut_identities.py|run_uk_sut_fisim_series.py) continue ;;
        esac
    fi
    COUNT=$((COUNT + 1))
    if $PY "$v" > "$LOGS/$name.log" 2>&1; then
        printf '.'
    else
        printf 'F'
        FAILED+=("$name")
    fi
done
echo
ELAPSED=$(( $(date +%s) - START ))

echo
if [ ${#FAILED[@]} -eq 0 ]; then
    echo "$COUNT validators passed in ${ELAPSED}s."
    exit 0
fi

echo "$COUNT validators ran in ${ELAPSED}s; ${#FAILED[@]} FAILED."
for name in "${FAILED[@]}"; do
    echo
    echo "================================================================"
    echo "FAILED: $name"
    echo "================================================================"
    cat "$LOGS/$name.log"
done
exit 1
