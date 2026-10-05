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
gives it. The same trades always give the same bytes. The caller hands in
today's date, and the ledger is meant to be given the same one. Nothing is
written when there is no trade; an identifier is empty, too long or used
twice (compared the way the ledger compares text); a coin is missing from the
coin table; a trade's time has an offset from UTC with seconds in it (some
zones had one before the 1970s, and the ledger cannot write it); a trade's
date, in its own zone, is after today; or there are more coins, trades or
bytes than one ledger file may hold. The answer lists every such issue
instead. A time zone name is taken only when it is spelled exactly as the
zone database lists it.
`backup_file_name` names the file, with the word `incremental` in it: the
ledger's present import replaces the whole ledger, and a file of a few new
trades must never be taken for a full backup. A golden sample, a committed
export that the export must reproduce byte for byte, records what this format
looks like, and the ledger tier of the checks has the ledger's own validator
judge it (see below).

**Talking to a language model.** The rest of the program will only ever
talk to the model port in `src/ledger_hand/ports.py`: send a list of
messages, optionally a JSON schema the reply has to follow, and the sampling
parameters; get back the reply's text and a short record of the call (which
model answered, how long it took, how many tokens it read and wrote, and
whether it stopped by itself or was cut off at the length limit). The one
plug today, in `src/ledger_hand/llm/`, talks to a local Ollama server
through its own chat endpoint and waits for the whole reply.
`connect_local_model(load_model_settings())` builds it. Every failure is one
`ModelError` with one of six kinds: `unreachable` (nothing answers at the
address: the server is not running, or the name does not resolve),
`timed_out`, `model_not_found`, `rate_limited`, `server_error` (also for
anything no other kind fits, with the raw status and the start of the
answer attached) and `malformed_reply` (not JSON, a field missing, empty
text, too long, not valid text). No odd answer makes the plug raise
anything else or wait without end. Timed out, rate limited and server error
are tried again a few times, with waits that double each time. What the
reply's text says is not checked here: a model reply is untrusted input, and
whoever asked checks it. A small function asks the server for its version
and the model's fingerprint, for the records of an experiment.

Where the model is, which one, its key and the default parameters are
settings read from environment variables (see "Model settings" below);
`src/ledger_hand/settings.py` is the only place in the package that reads
them. A key is never printed and never appears in an error.

**A passage becomes drafts.** `extract` in `src/ledger_hand/extraction/`
takes a passage as typed, a model port, the current moment, the time zone's
name and the coin table. The model does one thing only: it copies phrases
out of the passage into a flat table, one row per trade, each cell a piece of
the passage or empty. The program does the rest. Every phrase must be a
piece of the passage (compared after tidying width and runs of whitespace,
and never cutting a number in two), or the field stays empty; the piece, the
user's own writing, is what goes on. Numbers and times are turned into values
by the core's rules, and whatever the core is unsure of, cannot read, finds
ambiguous or in the future leaves the field empty with the core's reason. A
unit written with a price, total or fee names its currency when that field
was left empty. Every draft keeps the whole passage as its original text.
What comes back is the drafts and a list of issues: every field left empty
and why, every value kept with a caution, every row left out, and the
numbers of the passage no trade used, since a trade may be missing. A reply
that is not the table makes the program ask again, as often as the caller
allows; a failure of the model port is handed back as it was raised. An
empty passage, or one longer than the ledger keeps, is never sent. The
prompt (`extraction/prompts/first.py`) is its first version, with its
invented examples in a file beside it. `scripts/try_extraction.py` tries it
by hand with the real model.

**Measuring how well the model reads.** `evals/` holds the yardstick: 50
invented test sentences with gold answers (30 to tune against, 20 kept back
for the last run of an experiment), the scoring and a runner. The gold
answer says what the drafts of extraction should hold, field by field. The
runner sends every sentence of a set through extraction, with the
sentence's own fixed moment and zone, saves each result the moment it is
done, and scores the run: how often the reply could be read at all, each
field, whole trades right (the main score), trades missed and extra, values
made up, and passages with no trade. Every field that came out wrong is
sorted into its kind: left empty by the program with a reason, left empty
because the model gave nothing, a wrong value with or without an issue about
it, or a value made up.

Apart from asking the model, all of this is pure computation: nothing is
written to disk yet, and nothing that is said is recorded. There is no
storage and no interface yet, and no follow-up questions: a draft with
blanks comes back with its issues, and nothing asks the user anything yet.

The repository also has its Python environment, one command that runs every
check, and two guardrails that keep the code base in shape (the layering
check and the hygiene scan).

## What is where

| Path | What it is |
| --- | --- |
| `pyproject.toml` | Package metadata and the configuration of every tool (pytest, ruff, mypy). |
| `requirements.txt` | Exact versions of the run-time dependencies (httpx, tzlocal) and the development tools, so the environment can be rebuilt identically. |
| `src/ledger_hand/` | The package. Today it holds its version, `core/`, `export/`, the ports file, the settings, `llm/` and `extraction/`. |
| `src/ledger_hand/core/` | Core rules: pure computation, no network, files, database, user interface or clock. Holds the shapes of a trade (`trade.py`), the coin table (`coins.py`), the ledger's limits (`ledger_limits.py`), exact decimal arithmetic (`arithmetic.py`), the reading and writing of numbers (`numbers.py`), the reading and writing of times (`timeparse.py`, with the wording of a time phrase in `time_wording.py`) and the check of a draft (`validation.py`), a saved trade (`stored.py`) and which time zone names are taken (`zones.py`). |
| `src/ledger_hand/export/` | The ledger's backup format: the whole file (`backup.py`), one trade (`trade_entry.py`), one coin (`coin_card.py`), bookkeeping moments (`moments.py`) and the file's name (`file_name.py`). Writes no file itself. |
| `src/ledger_hand/ports.py` | The model port: messages, parameters, the reply and its record, and the error with its six kinds. Only shapes; it sends nothing. |
| `src/ledger_hand/settings.py` | The only place in the package that reads environment variables: the model settings, their defaults and their checks. |
| `src/ledger_hand/llm/` | The local plug for the model port: the plug itself (`ollama.py`), what is sent (`ollama_request.py`) and how what comes back is read (`ollama_reply.py`), one HTTP exchange and how its failures are sorted (`exchange.py`), making a server's words safe to show (`error_text.py`), trying again (`retry.py`), the assembled local model (`local.py`), and the server's version and the model's fingerprint (`ollama_identity.py`). The only part that may import httpx. |
| `src/ledger_hand/extraction/` | A passage to drafts: the entry point (`extractor.py`), the table the model fills (`reply_table.py`) and how its reply is read (`reply_parser.py`), finding a copied phrase in the passage (`passage.py`) and the numbers written in a text (`passage_numbers.py`), one row to one draft (`row_draft.py`), which currency a unit names (`unit_currency.py`), the issues (`issues.py`), the messages a prompt version makes (`prompting.py`), and the prompt versions with their examples (`prompts/`). Reads no clock, no zone of the machine and no environment variable. |
| `tests/` | The tests. `tests/core/`, `tests/export/`, `tests/llm/` and `tests/extraction/` have one test module per module; `tests/llm/` also has a fake Ollama server and a batch of attacks on the plug, and `tests/extraction/` a batch of attacks on extraction. `tests/evals/` tests the experiment kit and the test sentences. |
| `tests/conftest.py` | Stops every test that is not marked `live_model` from reaching the network. |
| `tests/fakes/` | Stand-ins for the outside world: a scripted model that plays back replies and errors in order and records what it was asked. |
| `tests/live/` | The live check, which talks to a real model, the small schema check it uses, and the smoke test of extraction. |
| `tests/export/samples.py`, `tests/export/attack.py`, `tests/export/golden/` | Invented trades to export, batches of edge cases made to find where this program and the ledger part ways, both shared with the ledger tier, and the golden sample. A golden sample is never edited once committed; a new format version gets one of its own. |
| `tests/guardrails/` | The layering check and the hygiene scan, the tests that prove they catch what they should, and the two gate tests that apply them to this repository. |
| `scripts/check.sh` | One command that runs all checks. |
| `evals/` | The experiment kit, outside the package: the test sentences and their gold answers (`sets/debug.json`, `sets/final.json`, read by `gold.py`), what they cover (`coverage.py`), judging one field (`cells.py`), pairing drafts with gold trades (`matching.py`), the scores (`scoring.py`), the results file (`records.py`), the summary and its tables (`tables.py`), the runner (`run.py`) and the summary worked out again (`summarize.py`). |
| `scripts/try_extraction.py` | Try extraction by hand: a passage in, the drafts, the issues and a record of each call to the model out (see "Trying extraction by hand" below). |
| `scripts/ledger_check.py`, `scripts/ledger_validate.ts`, `scripts/ledger_offsets.ts` | The ledger tier of the checks: sample files judged by the ledger's own validator, and the ledger's offsets compared with ours. |
| `tests/ledger_check/` | What the ledger tier checks (`cases.py`), tests of the tier's own logic, and the one sample for it written by hand. |
| `docs/architecture.md` | How the layers are divided, who may import whom, the house rules, and where new features go. |
| `docs/known-gaps.md` | Known gaps between what this program accepts and what the ledger accepts, each waiting for a decision. |
| `data/` | Not in Git. Run-time output, caches and, later, the local database. Created when first needed. |
| `.venv/` | Not in Git. The local Python environment. |

Directories for later parts (storage, flows, user interface)
are created by the change that first needs them; see `docs/architecture.md`
for the planned layout.

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

The second command installs the pinned run-time dependencies (httpx and
tzlocal) and development tools. The third installs
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

The script takes one argument, the tier: `quick` (the default), `ledger` or
`live`.

`quick` needs no network and no running model, and runs these steps in order:

| Step | What it runs | What it guards |
| --- | --- | --- |
| `format` | `ruff format --check .` | Formatting is left to the tool. |
| `lint` | `ruff check .` | Basic errors, import order, naming, common pitfalls, needless complexity, boolean flag parameters, overlong functions. |
| `types` | `mypy` | Strict type checking of `core/` and `ports.py`. |
| `layering` | `pytest tests/guardrails/test_repo_layering.py` | Each part of the package imports only what the layering table allows; `core/` reads no clock and uses no floating-point number; only `settings.py` reads environment variables. |
| `hygiene` | `pytest tests/guardrails/test_repo_hygiene.py` | No machine-specific paths, private work-log identifiers or tool-attribution text in any file Git tracks or would add. |
| `tests` | `pytest` | Every test except the live ones, including the tests of the two guardrails themselves. No test reaches the network: the model plug is tested against a fake transport, and a test that tries to connect fails on the spot. |

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
refused with exactly the errors planted in it. Two samples, which hold a
trade in every time zone, are expected to be accepted except for one known
gap: where the ledger's time zone database gives a zone another offset than
ours, the ledger refuses the trade's offset. Which zones and moments those
are is worked out each run by asking both sides
(`scripts/ledger_offsets.ts`); such refusals are announced in a notice marked
`!!!` and not counted as a failure, and any other refusal is. The gap is
described in `docs/known-gaps.md`. The output lists every error the ledger
reported for every sample.

What is checked is listed in `tests/ledger_check/cases.py`: the golden sample,
edge cases, batches of awkward trades (every time zone, the first and last
days there are, awkward characters, extreme numbers, buys followed by sales,
the ledger's limits of one file) and copies with mistakes planted in them.
Each sample is handed to the ledger together with the date it is to take as
today, the same date it was exported on, and is judged three times: in the
machine's own time zone, in Los Angeles and in Kiritimati. Before that, the
export itself must refuse one coin, one trade and one byte more than a file
may hold. One sample is about 128 MiB, so the tier takes several seconds and
over a gigabyte of memory.

The ledger checkout is only read. Before and after, the tier asks Git whether
the checkout is clean, with `git --no-optional-locks status --porcelain`,
which writes nothing into it, and fails when it is not. `tsx` runs with
`--no-cache`, and the configuration file it needs (one that extends the
ledger's own, because it has to name the checkout) is generated in the
temporary directory. Git does not see files it ignores, such as caches under
`node_modules`; to make sure nothing at all was written, look for files newer
than a marker made just before the run (`find <checkout> -newer <marker>`).

When no checkout is named, the named one is missing, or `tsx`, Node.js or Git
is missing, the tier is skipped: it prints why and ends with exit status `3`,
which is neither a pass nor a failure. `quick` never depends on it.

### The live tier

```sh
scripts/check.sh live
```

`live` talks to a real model, so it is only ever run by hand. It needs the
model server named in the settings running, with the model there: by
default Ollama on this machine with `qwen2.5:7b`. It runs the tests marked
`live_model` in `tests/live/`, with the settings read from the environment
as the program reads them. It asks the server for its version and the
model's fingerprint, then hands the model an invented question with a small
table (a JSON schema) and checks that the reply is valid JSON that follows
the table. It prints the table, the reply, how long the call took and the
token counts. Then it takes four invented passages (one trade in Chinese,
one in English, several trades, and talk with no trade) the whole way
through extraction, prints the drafts, the issues and how long each passage
took, and checks only that each comes back as drafts and a list of issues;
whether the model read them right is not judged there. When the server
cannot be reached, it fails with a message that starts with `unreachable`.
The first call after the model has been idle includes loading it into
memory, which takes several seconds more than the calls after it.

To see what happens when no model server is running, do not stop the one you
have: point the address at a port nothing listens on instead, for example
`LEDGER_HAND_MODEL_URL=http://127.0.0.1:59999 scripts/check.sh live`.
`quick` gives the same result either way, because it never talks to a model.

### Trying extraction by hand

```sh
.venv/bin/python scripts/try_extraction.py "9:40 bought 0.02 BTC at 94,900, fee 2 USDT"
echo "昨天卖了 2 ETH，价格 3,420" | .venv/bin/python scripts/try_extraction.py
```

The passage is the arguments, or else standard input. The script sends it
to the model the settings name and prints every draft field by field, the
issues, and one line per call to the model with how long it took and how
many tokens it read and wrote. The current moment is the machine's clock and
the time zone is the machine's own, read with tzlocal; a zone name the
program does not take as it stands stops the script instead of being
replaced. Nothing is written to disk. Exit status: `0` the passage was read
(even with no trade in it), `1` it was not (refused, no readable reply, or
the model failed), `2` the script could not start (a setting or the zone).

### Running an experiment

```sh
.venv/bin/python -m evals.run                    # the debug set, prompt "first", the model the settings name
.venv/bin/python -m evals.run --model qwen2.5:7b --prompt first
.venv/bin/python -m evals.run --resume evals/results/<file>.jsonl
.venv/bin/python -m evals.summarize evals/results/<file>.jsonl [--check]
```

Run these from the top of the repository, with the model server running.
The runner takes the debug set. The final set is run only with
`--final-exam`, and its results file says so; it is meant for the last run
of an experiment, once the prompt is settled, so that the scores are not
tuned to it. `--only` runs some sentences of the set by their ids.

The first line of the results file records the conditions: the set and
its fingerprint, the prompt version with its files and their fingerprints,
the commit and whether the work tree was clean, the model, its fingerprint
and the server's version, every parameter (temperature included, as the
settings give it) and when the run began. Each sentence's line is added the
moment it is done: the model's raw replies, the drafts, the issues, the
phrases the model copied, the scores and how long it took. A run cut short
can be carried on with `--resume`, under the same conditions only. The
summary is saved beside the results file and printed as tables;
`evals.summarize` works it out again from the file alone, and `--check`
compares it with the saved one. The first sentence of a run includes loading
the model, which takes several seconds more than the sentences after it.

The quick tier tests the scoring against cases worked out by hand and the
test sentences (coverage, no repeat of a prompt example, every gold answer
kept by the core's rules), and reads the final set only: no test sends a
test sentence to a model.

To let the tool fix formatting instead of only reporting it:

```sh
.venv/bin/python -m ruff format .
```

`scripts/check.sh` uses the Python in `.venv/`. Set `LEDGER_HAND_PYTHON` to
the path of another interpreter to use that one instead.

## Model settings

The model settings are read from these environment variables. A variable
that is not set, or is blank, takes its default. A value in the wrong form
or out of range stops the program with a message that names the variable,
and so does a variable that starts with `LEDGER_HAND_MODEL_` but is not one
of these, because a misspelt name would otherwise be ignored without a word.

| Variable | Default | What it sets |
| --- | --- | --- |
| `LEDGER_HAND_MODEL_URL` | `http://127.0.0.1:11434` | Where the model server is: Ollama on this machine. An `http` or `https` address, with no user name, password, query or fragment. |
| `LEDGER_HAND_MODEL_NAME` | `qwen2.5:7b` | Which model to ask. |
| `LEDGER_HAND_MODEL_KEY` | (none) | A key, sent as a bearer token, for a server that needs one. The local Ollama does not. Never printed. |
| `LEDGER_HAND_MODEL_TEMPERATURE` | `0` | How adventurous the model is; 0 gives the same answer to the same text, which extraction needs. 0 or more. |
| `LEDGER_HAND_MODEL_TOP_P` | `1` | Keeps only the likeliest words whose chances add up to this; 1 keeps all of them, so the temperature alone decides. Above 0, at most 1. |
| `LEDGER_HAND_MODEL_MAX_REPLY_TOKENS` | `1024` | The longest reply, in tokens; room for a JSON list of about ten trades. A reply that reaches it is marked as cut off. |
| `LEDGER_HAND_MODEL_CONTEXT_TOKENS` | `16384` | How much the model reads at once, in tokens: room for the extraction prompt (about 1,750 tokens with qwen2.5:7b), the longest passage the ledger keeps and a full reply. Ollama's own default is shorter, and it drops the start of a prompt that does not fit without saying so. |
| `LEDGER_HAND_MODEL_TIMEOUT_SECONDS` | `120` | How long to wait for the whole reply. Leaves room for loading the model on the first call. Not sent to the model. |
| `LEDGER_HAND_MODEL_RETRIES` | `2` | How many times a call that timed out, was rate limited or met a server error is tried again. 0 to 10. |
| `LEDGER_HAND_MODEL_RETRY_WAIT_SECONDS` | `1` | The wait before the first retry; each later wait is twice the one before. |

Numbers are written with plain digits and at most one point (`0.7`, `45`),
with no sign or exponent. The defaults are named constants in
`src/ledger_hand/settings.py`, each with the reason for its value.

The time allowed is counted from sending. Connecting, sending and each wait
for the next piece of the reply are each cut off at the time allowed, and a
reply still arriving once that time has passed is abandoned at its next
piece. So a server that keeps trickling bytes cannot keep a call open for
long past the time allowed.

The plug ignores the proxy settings of the environment (`HTTP_PROXY` and the
like), so a request for the model on this machine never leaves it through a
proxy.

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
