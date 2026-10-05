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

**Numbers as people write and say them.** `read_number` turns a short piece
of text into an exact decimal: "94,900", "1.2k", "3w", "8万刀", "两万三",
"9万4", "零点五". A unit that came with the number is handed back as written,
but only a unit made of words the program knows: the words for USDT, the
coins in the coin table, a few counters such as "个", and any word the caller
allows for that one call. When the text has more than one reading ("1,5",
"一亿五千"), names no single exact amount ("8万到8万5", "大概两万", "半个"),
has more digits than the ledger holds or carries any other unit ("3个w",
"2 thousands", "100 sats", "5毛"), the answer is "unsure" with a reason, never
a guess. `write_number` goes the other way and writes an exact decimal the
way the ledger accepts it.

**Times as people say them.** `read_time` turns a short piece of text into a
definite time, given the current moment and the time zone, both handed in by
the caller: "刚才", "3 小时前", "昨天晚上 9 点 40", "上周五下午三点", "last
Friday 3pm", "Oct 2", "15:05:30". A date said gives a day, and so does a day
with only a half of it ("昨天晚上", "Friday night"), with a caution; a clock
time gives the minute, or the second when seconds were said. Spans back from
now count real elapsed time, so they stay right when the clocks change; day
words, weekdays and dates count calendar days. Every part of the text must be
one the program knows. When the text can mean more than one time ("10/2",
"晚上 12 点", "last Monday" on most days of the week), the clocks skipped
that time, or it lies in the future, the answer says so, never a guess; on
the night the clocks go back, a time shown twice comes back as two candidates. `write_time` writes a time the way the ledger takes
it: a date, or a moment with its seconds and offset.

**A file the ledger accepts.** `export_backup` in `src/ledger_hand/export/`
writes saved trades as the text of a backup file in the ledger's own format
(backup format 3, ledger schema 5): the trades, in the order they happened,
and a card for every coin they use, with its full name and Binance market
taken from the coin table. A saved trade (`core/stored.py`) is a finished
record with the identifier and the creation and change moments that saving
gives it. The same trades always give the same bytes. Nothing is written when
there is no trade, an identifier is empty, too long or used twice, a coin is
missing from the coin table, or a trade's time has an offset from UTC with
seconds in it (some zones had one before the 1970s, and the ledger cannot
write it); the answer lists every such issue instead.
`backup_file_name` names the file, with the word `incremental` in it: the
ledger's present import replaces the whole ledger, and a file of a few new
trades must never be taken for a full backup. A golden sample, a committed
export that the export must reproduce byte for byte, records what this format
looks like, and the ledger tier of the checks has the ledger's own validator
judge it (see below).

All of this is pure computation: nothing is written to disk yet. There is no
language model, no storage and no interface yet.

The repository also has its Python environment, one command that runs every
check, and two guardrails that keep the code base in shape (the layering
check and the hygiene scan).

## What is where

| Path | What it is |
| --- | --- |
| `pyproject.toml` | Package metadata and the configuration of every tool (pytest, ruff, mypy). |
| `requirements.txt` | Exact versions of the development tools, so the environment can be rebuilt identically. |
| `src/ledger_hand/` | The package. Today it holds its version, `core/` and `export/`. |
| `src/ledger_hand/core/` | Core rules: pure computation, no network, files, database, user interface or clock. Holds the shapes of a trade (`trade.py`), the coin table (`coins.py`), the ledger's limits (`ledger_limits.py`), exact decimal arithmetic (`arithmetic.py`), the reading and writing of numbers (`numbers.py`), the reading and writing of times (`timeparse.py`, with the wording of a time phrase in `time_wording.py`) and the check of a draft (`validation.py`), a saved trade (`stored.py`) and which time zone names are taken (`zones.py`). |
| `src/ledger_hand/export/` | The ledger's backup format: the whole file (`backup.py`), one trade (`trade_entry.py`), one coin (`coin_card.py`), bookkeeping moments (`moments.py`) and the file's name (`file_name.py`). Writes no file itself. |
| `tests/` | The tests. `tests/core/` and `tests/export/` have one test module per module. |
| `tests/export/samples.py`, `tests/export/golden/` | Invented trades to export, shared with the ledger tier, and the golden sample. A golden sample is never edited once committed; a new format version gets one of its own. |
| `tests/guardrails/` | The layering check and the hygiene scan, the tests that prove they catch what they should, and the two gate tests that apply them to this repository. |
| `scripts/check.sh` | One command that runs all checks. |
| `scripts/ledger_check.py`, `scripts/ledger_validate.ts` | The ledger tier of the checks: sample files judged by the ledger's own validator. |
| `tests/ledger_check/` | Tests of the ledger tier's own logic, and the one sample for it written by hand. |
| `docs/architecture.md` | How the layers are divided, who may import whom, the house rules, and where new features go. |
| `data/` | Not in Git. Run-time output, caches and, later, the local database. Created when first needed. |
| `.venv/` | Not in Git. The local Python environment. |

Directories for later parts (extraction, model client, storage, flows, user
interface) are created by the change that first needs them; see
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

The script takes one argument, the tier: `quick` (the default) or `ledger`.

`quick` needs no network and no running model, and runs these steps in order:

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
tier, or no Python environment), `3` when the tier was skipped.

### The ledger tier

```sh
LEDGER_HAND_LEDGER_DIR=path/to/LocalFirstTradingLedger scripts/check.sh ledger
```

`ledger` asks the ledger itself whether it accepts the files this program
writes. It needs a checkout of the Local-First Trading Ledger on the same
machine with its packages installed (`npm install` there), and Node.js on the
`PATH`. The checkout is named by the environment variable
`LEDGER_HAND_LEDGER_DIR`; `scripts/ledger_check.py --ledger PATH` takes it as
an argument instead.

It is two scripts. `scripts/ledger_check.py` (Python) writes the sample files
into a fresh temporary directory, runs the ledger's validator on them and
judges each answer. `scripts/ledger_validate.ts` (TypeScript) is the part that
runs inside the ledger checkout: started with the checkout's own `tsx`, it
imports the ledger's `parseBackupJson` and prints what it says about each
file. Each sample is expected to be accepted with no error, refused only for
selling more than is held (this program cannot know what the ledger holds), or
refused with exactly the errors planted in it. The output lists every error
the ledger reported for every sample.

The ledger checkout is only read. Before and after, the tier asks Git whether
the checkout is clean, with `git --no-optional-locks status --porcelain`,
which writes nothing into it, and fails when it is not. `tsx` runs with
`--no-cache`, and the configuration file it needs (one that extends the
ledger's own, because it has to name the checkout) is generated in the
temporary directory.

When no checkout is named, the named one is missing, or `tsx`, Node.js or Git
is missing, the tier is skipped: it prints why and ends with exit status `3`,
which is neither a pass nor a failure. `quick` never depends on it.

One more tier is planned and will be added to the same script: `live` will
talk to a real model. It needs a local model server running and is only ever
run by hand. Until it exists, asking for it is an error, like any other
unknown tier.

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
