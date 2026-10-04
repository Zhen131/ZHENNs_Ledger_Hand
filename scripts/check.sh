#!/usr/bin/env bash
# Runs the repository checks, one tier at a time.
#
#   scripts/check.sh [tier]
#
# Tiers:
#   quick   format, lint, types, layering, hygiene, tests. The default.
#           Needs no network and no running model.
#
# Steps run in order. The script stops at the first step that fails and names
# it, so the last line always says where to look.
#
# Exit status: 0 every step passed; 1 a step failed; 2 the script could not
# start (unknown tier, or no Python environment).
#
# LEDGER_HAND_PYTHON overrides which Python runs the tools; the default is the
# one in .venv/.

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${LEDGER_HAND_PYTHON:-$ROOT/.venv/bin/python}"
TIERS="quick"

run_step() {
    local name="$1"
    shift
    printf '\n== %s ==\n' "$name"
    if ! "$@"; then
        printf '\nFAILED: %s\n' "$name" >&2
        exit 1
    fi
}

quick() {
    run_step format "$PYTHON" -m ruff format --check .
    run_step lint "$PYTHON" -m ruff check .
    run_step types "$PYTHON" -m mypy
    run_step layering "$PYTHON" -m pytest -q tests/guardrails/test_repo_layering.py
    run_step hygiene "$PYTHON" -m pytest -q tests/guardrails/test_repo_hygiene.py
    run_step tests "$PYTHON" -m pytest -q
}

if [ "$#" -gt 1 ]; then
    echo "usage: scripts/check.sh [tier]   (tiers: $TIERS)" >&2
    exit 2
fi

tier="${1:-quick}"
case "$tier" in
    quick) ;;
    *)
        echo "unknown tier: $tier   (tiers: $TIERS)" >&2
        exit 2
        ;;
esac

if [ ! -x "$PYTHON" ]; then
    echo "no Python at $PYTHON; set the environment up first (see README.md)" >&2
    exit 2
fi

cd "$ROOT" || exit 2
"$tier"
printf '\n%s: all checks passed\n' "$tier"
