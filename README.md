# Ledger Hand

## What this is

Ledger Hand is being built as a small program that runs entirely on your own
machine and has one chat box. You type a trade the way you would say it, for
example "bought 0.02 BTC at 94,900 at 9:40, fee 2 USDT", and it works out the
coin, the side, the amount, the price, the fee and the time. It shows the
result in a preview table, saves only when you confirm, and exports a JSON
file in the import format of the Local-First Trading Ledger. A passage that
mentions several trades is split into several entries. The language model
runs locally. Ledger Hand never writes into the ledger application itself; it
only hands over a file.

## Where it stands

**The rules of one trade.** `src/ledger_hand/core/` knows what a trade looks
like and which rules it has to keep. Hand it a draft, the coin table and the
current moment, and `check_draft` returns either a finished record or two
lists: what is still missing, and what breaks a rule. A draft that names two
of quantity, price and total gets the third calculated; an unknown coin has
to be confirmed first; the fee has to be stated even when it is zero; nothing
dated in the future is accepted. The limits of the ledger (digits, lengths,
tolerance) are copied into one file and applied the way the ledger applies
them.

All of this is pure computation. There is no language model, no storage and
no interface yet, and spoken numbers and times ("23k", "last Friday 3pm") are
not converted yet: a draft already holds exact decimals and a definite time.

The repository also has its Python environment, one command that runs every
check, and two guardrails that keep the code base in shape (the layering
check and the hygiene scan).

## What is where

| Path | What it is |
| --- | --- |
| `pyproject.toml` | Package metadata and the configuration of every tool (pytest, ruff, mypy). |
| `requirements.txt` | Exact versions of the development tools, so the environment can be rebuilt identically. |
| `src/ledger_hand/` | The package. Today it holds its version and `core/`. |
| `src/ledger_hand/core/` | Core rules: pure computation, no network, files, database, user interface or clock. Holds the shapes of a trade (`trade.py`), the coin table (`coins.py`), the ledger's limits (`ledger_limits.py`), exact decimal arithmetic (`arithmetic.py`) and the check of a draft (`validation.py`). |
| `tests/` | The tests. `tests/core/` has one test module per core module. |
| `tests/guardrails/` | The layering check and the hygiene scan, the tests that prove they catch what they should, and the two gate tests that apply them to this repository. |
| `scripts/check.sh` | One command that runs all checks. |
| `docs/architecture.md` | How the layers are divided, who may import whom, the house rules, and where new features go. |
| `data/` | Not in Git. Run-time output, caches and, later, the local database. Created when first needed. |
| `.venv/` | Not in Git. The local Python environment. |

Directories for later parts (extraction, export, model client, storage,
flows, user interface) are created by the change that first needs them; see
`docs/architecture.md` for the planned layout.

## Setting up from scratch

You need Python 3.12 or newer and Git. The commands below are for macOS or
Linux and are run from the top of a Git checkout of this repository. (A plain
copy without its `.git` directory is not enough: the hygiene scan asks Git
which files to look at.)

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install --no-deps -e .
```

The second command installs the pinned development tools. The third installs
this package in editable mode, so the tests import the code in `src/`
directly. Both need network access; the third also fetches the build backend
(setuptools) into a temporary build environment.

Then confirm that everything works:

```sh
scripts/check.sh
```

The last line should read `quick: all checks passed`.

## Running the checks

```sh
scripts/check.sh          # the same as: scripts/check.sh quick
```

The script takes one argument, the tier. `quick` is the default and the only
tier so far. It needs no network and no running model, and runs these steps
in order:

| Step | What it runs | What it guards |
| --- | --- | --- |
| `format` | `ruff format --check .` | Formatting is left to the tool. |
| `lint` | `ruff check .` | Basic errors, import order, naming, common pitfalls, needless complexity, boolean flag parameters, overlong functions. |
| `types` | `mypy` | Strict type checking of `core/`. |
| `layering` | `pytest tests/guardrails/test_repo_layering.py` | Each part of the package imports only what the layering table allows; `core/` reads no clock and uses no floating-point number. |
| `hygiene` | `pytest tests/guardrails/test_repo_hygiene.py` | No machine-specific paths, private work-log identifiers or tool-attribution text in any file Git tracks or would add. |
| `tests` | `pytest` | Every test, including the tests of the two guardrails themselves. |

The script stops at the first step that fails and ends with `FAILED: <step>`,
so the last line always says where to look. Exit status: `0` when every step
passed, `1` when a step failed, `2` when the script could not start (unknown
tier, or no Python environment).

Two more tiers are planned and will be added to the same script:

- `ledger` will validate exported files with the ledger's own validator. It
  needs a checkout of the ledger on the same machine.
- `live` will talk to a real model. It needs a local model server running and
  is only ever run by hand.

Until they exist, asking for them is an error, like any other unknown tier.

To let the tool fix formatting instead of only reporting it:

```sh
.venv/bin/python -m ruff format .
```

`scripts/check.sh` uses the Python in `.venv/`. Set `LEDGER_HAND_PYTHON` to
the path of another interpreter to use that one instead.

## Changing the development tools

Dependencies are declared in `pyproject.toml` and pinned in
`requirements.txt`. After changing them, rewrite the pin file from the
environment:

```sh
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pip freeze --exclude-editable > requirements.txt
```

`--exclude-editable` keeps this package itself out of the file; without it
the file would carry the absolute path of your checkout.
