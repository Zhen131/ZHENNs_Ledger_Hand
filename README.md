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
dated in the future is accepted, and neither is a moment whose offset from UTC
has seconds in it (some zones had one before the 1970s). The limits of the ledger (digits, lengths,
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
the night the clocks go back, a time shown twice comes back as two
candidates. A date said without its year whose day this year is still to
come ("10月8号" said on 7 October) is ambiguous too: it may mean last year's,
or the day may be a slip, and the program asks instead of picking one. A day
of the month without its month ("8号" said on the 7th) is the same. Only a
day this year (this month) does not have at all, such as 29 February, is
looked for further back. `write_time` writes a time the way the ledger takes
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
coin table; a trade's time has an offset from UTC with seconds in it (the
ledger cannot write it; the check of a draft already refuses one, and this is
a second guard); a trade's
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
comma written full width ("，") ends a number unless the core's number
reader reads both sides together as one number it is sure of: "94，900" is
one number, "63,000，1.5" is two, and so is "1，5" (1 and 5, not 1.5). A
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
it, or a value made up. The results of each run are in `evals/results/`,
and `evals/RESULTS.md` records them; the first is the baseline of the first
prompt with `qwen2.5:7b` on the debug set.

**Judging a passage first.** `screen` in
`src/ledger_hand/extraction/screening.py` asks the model which kinds of thing
a passage reports, from one fixed list: a filled spot trade, futures or
leverage, one coin swapped for another, an order not filled yet, and a plan.
Each report comes with the words of the passage that show it, quoted only
when they really are a piece of the passage. The program decides what
follows: a passage that reports only the kinds the ledger does not record is
stopped, with the reason for each; one that reports nothing has no trade;
one that reports a filled spot trade goes on to extraction, and anything
else it reports is set aside as a caution. The prompt
(`extraction/prompts/screen.py`) gives no example at all.

**Asking about what is missing.** `core/followup.py` says what to ask next
about a draft the check did not pass, from one fixed order of every problem
the check can name: a cell to ask for, a coin word to confirm, which of
several cells is wrong (quantity times price not matching the total; a fee
in the bought coin not below the quantity), or that the trade cannot be
recorded and why (the coin is USDT, or the trade is priced in another coin).
The model words each question as a meticulous bookkeeper
(`src/ledger_hand/asking/`), behind a label of the program's own that says
which trade and which field is asked about; when the model fails, or writes
anything but one plain question, or brings in a number, a coin or a word
that is not among the facts, the program's own sentence is used. An answer
is read by rules first (`extraction/answer_phrase.py`): a number, a time with
the passage's own moment and zone, a coin, and short fixed word lists for
buy or sell, yes or no, "no fee", "skip", "cancel" and which cell is wrong.
Only when the rules cannot read the whole answer is the model asked to copy
the one piece of it that gives what was asked; the piece must be a piece of
the answer, and it is read by the same rules. An answer that cannot be used
gets the same question again, with the reason.

**Recording a passage.** `src/ledger_hand/flows/recording.py` strings all of
this together: judge the passage, extract its trades, check each one, then
ask one trade at a time and one field at a time, put each answer back and
check the trade again, until every trade is a record, skipped or impossible
to record. Each step hands back the whole state as one value that never
changes (`flows/progress.py`): the stage, every trade, the question waiting,
the records, why the passage was stopped, the reminders, which prompt
versions were used, and whether a record can still be removed or the whole
passage dropped. A record can be removed once every trade is settled, even
one that was complete from the start, so a wrong value seen in the records
can be kept out. When the model fails while judging or extracting, nothing
is kept. `scripts/record_trades.py` runs it at the command line (see
"Recording trades by hand" below).

**Keeping the records.** Saved trades are kept in the book: one SQLite file
of this program's own, behind the storage port in `src/ledger_hand/ports.py`
(save the trades of one passage, say whether a passage was saved before,
list the saved trades, mark trades as exported, list the coins the user
confirmed). The one plug, in `src/ledger_hand/storage/`, uses Python's own
`sqlite3`. Each trade is kept field by field: numbers and times as the ledger
writes them, as text, never as floating-point numbers, so a trade read back
is equal to the one saved, down to which amount was worked out; bookkeeping
moments in UTC to the microsecond. The book carries its own version number
(1 today) and a mark that says it is this program's, both in the file's
header, and both are read before anything else: a file that is newer than
this program, not a database or not this program's book is refused, and not
one byte of it is written; a missing or empty file becomes a new book, with
its folder. Numbered upgrade scripts (`storage/upgrades/`) bring an older
book up to date, one transaction each, and are never changed once
committed; neither is the golden sample of each version
(`tests/storage/golden/`). Every failure of the book is one `StorageError`
with one of eight kinds (newer version, not a database, not this program's,
damaged, locked, inaccessible, conflict, unexpected); nothing of `sqlite3`
leaks out. Each operation opens the book and closes it again.

`flows/saving.py` saves the final records of a passage, only when the person
asked for it: each gets a new identifier (`hand-` and a random UUID) and the
moment of saving; the coins the user confirmed that the saved trades use are
kept with them, in the same transaction, and a coin confirmed for a trade
that was then left out is forgotten. When a book is handed to the recording
of a passage, the passage is first looked up by its fingerprint (a digest of
the passage with spacing and character width made uniform): an earlier save
of it is shown as a reminder, with its date and number of trades, and holds
nothing back; and the coins confirmed and saved before are known.

`flows/exporting.py` writes the saved trades not exported yet into a new
file in the exports folder, with `export_backup` (the export moment is the
current moment, and today its date in the person's time zone) and
`backup_file_name`, then marks them as exported, with that moment. A refusal
writes nothing and marks nothing, and says every reason; with nothing new,
nothing is written. The file is written under a temporary name first and
only then given its real one, in a way that never replaces a file of that
name: two exports in the same second would be given the same name, and the
second then writes nothing and marks nothing. A file and the book cannot be
changed together in one step, so the order is chosen for what an
interruption leaves behind: the file is written first and its trades marked
after. Cut off in between, the result is a file whose trades are not
marked, and the next export writes them again, which the person can see;
never trades marked as exported with no file, which would lose them.

**The interface.** `src/ledger_hand/ui/` is one Streamlit page: a chat on
the left and, on the right, a table of what will be recorded (see "Starting
the interface" below). A passage typed in the chat is recorded as above;
each question comes back in the chat with its label, and the answer is typed
in the same box. The table has one row per trade, with where it stands
(complete, asking, left out, or cannot record and why), its time, coin,
side, quantity, price and total side by side, fee and fee coin, platform and
note; the amount the program worked out is marked once the trade has passed
the check. Each row has a "Don't save" button, and under the table are
Save and "Discard all"; each can be pressed only when the flow offers it.
Save keeps the records in the book and empties the table. A new passage
typed while the last one is settled but neither saved nor discarded is not
taken: the page says so and offers the two choices. The interface decides
nothing itself: what to ask, whether a passage is settled, whether it can be
saved and which trade can be left out all come from the flow's progress. It
gets the model, the book, the clock and the machine's zone from one wiring
module, `src/ledger_hand/wiring.py`, the only place in the package that
reads the machine's zone (with tzlocal).

Under the table, Export writes the saved trades not exported yet into a new
file, says where and how many, and marks them; beside it, always, a line in
red says not to import that file into the ledger yet. A second page,
Settings, lists every model setting with its value now, its default and why
the default is what it is, and lets every one but the key be changed for
the browser tab. Every failure, from a model nobody answers to a book
written by a newer version of the program, is said in one plain sentence
that says what happened and what can be done, and nothing breaks. A passage
saved before is reminded of, with the day and the number of trades, and a
fee paid in a third coin, which the ledger leaves out of the cost, is
pointed out in its row and in the chat; neither holds anything back.

Apart from asking the model, keeping the book and drawing the page, all of
this is pure computation.

The repository also has its Python environment, one command that runs every
check, and two guardrails that keep the code base in shape (the layering
check and the hygiene scan).

## What is where

| Path | What it is |
| --- | --- |
| `pyproject.toml` | Package metadata and the configuration of every tool (pytest, ruff, mypy). |
| `requirements.txt` | Exact versions of the run-time dependencies (httpx, Streamlit, tzlocal, and what Streamlit brings with it) and the development tools, so the environment can be rebuilt identically. |
| `.streamlit/config.toml` | Streamlit's settings for the interface: no usage statistics, listen on this machine only, start without questions at the terminal, no developer options (and so no Deploy button) in the menu. Read from the folder Streamlit is started in. |
| `src/ledger_hand/` | The package. Today it holds its version, `core/`, `export/`, the ports file, the settings, `llm/`, `storage/`, `extraction/`, `asking/`, `flows/`, the wiring module and `ui/`. |
| `src/ledger_hand/core/` | Core rules: pure computation, no network, files, database, user interface or clock. Holds the shapes of a trade (`trade.py`), the coin table (`coins.py`), the ledger's limits (`ledger_limits.py`), exact decimal arithmetic (`arithmetic.py`), the reading and writing of numbers (`numbers.py`), the reading and writing of times (`timeparse.py`, with the wording of a time phrase in `time_wording.py`) and the check of a draft (`validation.py`), what to ask next about a draft (`followup.py`), a saved trade (`stored.py`), what the book keeps beside it (`book.py`), the form a passage is compared in (`passage_form.py`), which time zone names are taken (`zones.py`) and whether the ledger counts a trade's fee in the cost (`fee_cost.py`). |
| `src/ledger_hand/export/` | The ledger's backup format: the whole file (`backup.py`), one trade (`trade_entry.py`), one coin (`coin_card.py`), bookkeeping moments (`moments.py`) and the file's name (`file_name.py`). Writes no file itself. |
| `src/ledger_hand/ports.py` | The two ports. The model port: messages, parameters, the reply and its record, and the error with its six kinds. The storage port: its operations and the error with its eight kinds; the shapes it takes and gives are in `core/book.py`. Only shapes; it sends and stores nothing. |
| `src/ledger_hand/settings.py` | The only place in the package that reads environment variables: the model settings, their defaults and their checks, what each sets and why its default is what it is (as data, `ABOUT`), changes from the settings page read the same way (`apply_changes`), and where the data is kept. |
| `src/ledger_hand/storage/` | The SQLite plug for the storage port (`sqlite_store.py`): opening a book, its version and its mark (`book_file.py`), a trade as a row and back (`rows.py`), SQLite's failures as the port's kinds (`failures.py`), and the numbered upgrade scripts (`upgrades/`). The only part that may import sqlite3. |
| `src/ledger_hand/llm/` | The local plug for the model port: the plug itself (`ollama.py`), what is sent (`ollama_request.py`) and how what comes back is read (`ollama_reply.py`), one HTTP exchange and how its failures are sorted (`exchange.py`), making a server's words safe to show (`error_text.py`), trying again (`retry.py`), the assembled local model (`local.py`), and the server's version and the model's fingerprint (`ollama_identity.py`). The only part that may import httpx. |
| `src/ledger_hand/extraction/` | A passage to drafts: the entry point (`extractor.py`), the table the model fills (`reply_table.py`) and how its reply is read (`reply_parser.py`), finding a copied phrase in the passage (`passage.py`) and the numbers written in a text (`passage_numbers.py`), one row to one draft (`row_draft.py`), which currency a unit names (`unit_currency.py`), the issues (`issues.py`), the messages a prompt version makes (`prompting.py`), and the prompt versions with their examples (`prompts/`). Also the check of a passage before it is sent (`passage_check.py`), judging a passage (`screening.py`, with the list the model fills in `screen_table.py`), and reading an answer to a question (`answer_phrase.py`, with its word lists in `answer_words.py` and what the model copies in `answer_table.py`). Reads no clock, no zone of the machine and no environment variable. |
| `src/ledger_hand/asking/` | Wording a follow-up question: the facts, the model's sentence and its checks (`question_text.py`), the program's own sentences (`templates.py`) and the prompt (`prompts/bookkeeper.py`). Imports only `core/` and the ports file; reads no clock. |
| `src/ledger_hand/flows/` | Recording a passage from start to records (`recording.py`): the state it hands back (`progress.py`), putting a question together (`questions.py`) and putting an answer back (`filling.py`). Saving the records (`saving.py`) with new identifiers (`identifiers.py`), a passage's fingerprint (`fingerprint.py`), the confirmed coins between the book and the coin table (`coin_book.py`), and exporting (`exporting.py`) into a new file that never replaces another (`export_file.py`). |
| `src/ledger_hand/wiring.py` | The wiring module: builds the model, the book, the coin table, the clock and the machine's zone from the settings, with the settings page's changes put in, for the interface to hand to the flows. The only part of the package that may import tzlocal. |
| `src/ledger_hand/ui/` | The interface, two Streamlit pages: the entry (`app.py`), the Record page (`record_page.py`) with the chat (`chat.py`), the table and its buttons (`preview.py`) and Export (`export_panel.py`); the Settings page (`settings_page.py`) and its inputs (`settings_form.py`); what happens on a message or a click (`turns.py`), what the program says (`sayings.py`), the plain sentence for every failure (`failure_words.py`), a setting's value as it is shown (`setting_text.py`), the last word after Export or a change of setting (`notes.py`) and what is kept between reruns (`session.py`). The only part that may import Streamlit. |
| `tests/` | The tests. `tests/core/`, `tests/export/`, `tests/llm/`, `tests/extraction/`, `tests/asking/`, `tests/storage/` and `tests/flows/` have one test module per module, or more; `tests/llm/` also has a fake Ollama server and a batch of attacks on the plug, and `tests/extraction/` a batch of attacks on extraction. `tests/storage/` runs the same tests of the storage port against the SQLite plug and the in-memory stand-in, and holds the golden book. `tests/flows/` also tests the script for recording trades. `tests/ui/` runs the pages headless with Streamlit's own test runner, against fake models and a book in a temporary folder (Export, the settings page, every failure, the reminders), checks the plain sentence for every failure, and checks the settings file. `tests/evals/` tests the experiment kit and the test sentences. |
| `tests/conftest.py` | Stops every test that is not marked `live_model` from reaching the network. |
| `tests/fakes/` | Stand-ins for the outside world: a scripted model that plays back replies and errors in order and records what it was asked, a model that answers each kind of call (judging, extraction, wording a question, reading an answer) from its own script, and a book kept in memory that can be made to fail. |
| `tests/live/` | The live check, which talks to a real model, the small schema check it uses, the smoke test of extraction, the check of judging the debug set, the smoke test of the page, and the check of the settings page against an address nobody listens on. |
| `tests/export/samples.py`, `tests/export/attack.py`, `tests/export/golden/` | Invented trades to export, batches of edge cases made to find where this program and the ledger part ways, both shared with the ledger tier, and the golden sample. A golden sample is never edited once committed; a new format version gets one of its own. |
| `tests/guardrails/` | The layering check and the hygiene scan, the tests that prove they catch what they should, and the two gate tests that apply them to this repository. |
| `scripts/check.sh` | One command that runs all checks. |
| `evals/` | The experiment kit, outside the package: the test sentences and their gold answers (`sets/debug.json`, `sets/final.json`, read by `gold.py`), what they cover (`coverage.py`), judging one field (`cells.py`), pairing drafts with gold trades (`matching.py`), the scores (`scoring.py`), the results file (`records.py`), the summary and its tables (`tables.py`), the runner (`run.py`) and the summary worked out again (`summarize.py`). |
| `evals/results/` | One results file per run (`*.jsonl`) and its summary (`*.summary.json`). In Git: all of it is invented data. |
| `evals/RESULTS.md` | The results record: what each run measured, with the tables its results file gives. |
| `scripts/try_extraction.py` | Try extraction by hand: a passage in, the drafts, the issues and a record of each call to the model out (see "Trying extraction by hand" below). |
| `scripts/record_trades.py` | Record trades from a passage at the command line, one question at a time (see "Recording trades by hand" below). |
| `scripts/ledger_check.py`, `scripts/ledger_validate.ts`, `scripts/ledger_offsets.ts` | The ledger tier of the checks: sample files judged by the ledger's own validator, and the ledger's offsets compared with ours. |
| `tests/ledger_check/` | What the ledger tier checks (`cases.py`), tests of the tier's own logic, and the one sample for it written by hand. |
| `docs/architecture.md` | How the layers are divided, who may import whom, the house rules, and where new features go. |
| `docs/known-gaps.md` | Known gaps between what this program accepts and what the ledger accepts, each waiting for a decision. |
| `tests/storage/golden/` | The golden book of version 1, a SQLite file, and its text dump. Never edited once committed; a new version of the book gets one of its own. |
| `data/` | Not in Git. The data folder by default: the book (`ledger-hand-book.sqlite3`) and the export files (`exports/`). Created when first written to. |
| `.venv/` | Not in Git. The local Python environment. |

Directories for later parts are created by the change that first needs
them; see `docs/architecture.md` for the planned layout.

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

The second command installs the pinned run-time dependencies (httpx,
Streamlit and tzlocal, with what Streamlit brings with it) and the development
tools. The third installs
this package in editable mode, so the tests import the code in `src/`
directly. Both need network access; the third also fetches the build backend
(setuptools) into a temporary build environment.

Then confirm that everything works:

```sh
scripts/check.sh
```

The last line should read `quick: all checks passed`.

## Starting the interface

You need the model server running first: by default Ollama on this machine
with `qwen2.5:7b` (see "Model settings" below). Then, from the top of the
repository:

```sh
.venv/bin/streamlit run src/ledger_hand/ui/app.py
```

and open http://127.0.0.1:8501 in your browser. Start it from the top of the
repository: Streamlit reads its settings from `.streamlit/config.toml` in
the folder it is started in. They keep it from sending usage statistics,
make it listen on this machine's own address only, and start it headless, so
it neither stops at the terminal to ask for an e-mail address nor writes a
credentials file into your home folder, and it does not open a browser by
itself. Stop it with Ctrl+C in the terminal.

Type a passage in the box under the chat, for example "Bought 0.02 BTC at
94,900 yesterday". The program's questions come back in the chat, each with
a label saying which trade and which field it is about; type the answer in
the same box, or "skip" to leave that trade out, or "cancel" to drop the
whole passage. The table on the right shows every trade as it stands, with
the price and the total side by side, so a total written where the price
belongs shows at a glance; an amount the program worked out is marked `*`.
Once every trade is settled, "Don't save" leaves one trade out, "Discard
all" drops the passage, and Save keeps the rest in the book and says how
many it saved. Save cannot be pressed while a question is waiting; the
sentence beside it says why.

The current moment is the machine's clock and the time zone is the
machine's own, read with tzlocal; a zone name the program does not take as
it stands, or a model setting it refuses, is said on the page instead of
the chat. The chat lasts as long as the browser tab and is never written to
disk; only the trades saved are kept, in the book (see "Where the data is
kept" below). When the model fails, the chat says so in one sentence and
nothing of that passage is kept; type it again once the model server is
running.

Two more things are said in the chat, as reminders that hold nothing back.
When the same passage, or one that differs from it only in spacing or
full-width characters, was saved before, the chat says so first, with the
day of each earlier save and how many trades it saved; the passage can
still be answered and saved. When a trade's fee is paid in a third coin,
neither USDT nor the coin traded (buying ETH with the fee taken in BNB,
say), its fee coin is marked "(not in cost)" in the table, a sentence under
the table says why, and the chat says it once every trade is settled: the
ledger takes the trade, but leaves that fee out when it works out the cost.

### Exporting from the interface

Export, under the table, writes the saved trades not exported yet into a new
file in the exports folder, the same file `record_trades.py --export`
writes, and marks them as exported. The page then says where the file is
and how many trades it holds; with nothing new it says so and writes
nothing. When the trades cannot be written as a file as they are, it gives
every reason, one to a line; when the file cannot be written, it says why;
in both cases nothing is marked. When the file was written but its trades
could not be marked, it says where the file is and that the next export
writes them again.

Beside the button, always, a line in red says not to import this file into
the ledger yet: the ledger's import replaces the whole ledger with what the
file holds, which would leave it with these trades only.

### The settings page

Settings, at the top of the page beside Record, lists every model setting
(see "Model settings" below) with its value now, its default, what it sets
and why its default is what it is; the key only says whether there is one.
Every setting but the key can be changed there: type the new value, as it
would be written in the environment, and press Apply. A blank value takes
the default. The values are read and checked exactly as the environment's
are; a value that is refused is named with its rule, and nothing changes.
Once applied, the next call to the model uses it, even in the middle of a
passage. "Back to the environment and the defaults" drops every change.

A change lasts for the browser tab only: opening the page again, or
starting the program again, goes back to the environment variables and the
defaults. Nothing is written to a file or to the environment, and what the
page does not change, the key among it, stays as the environment set it.
The data folder is shown there too, and is changed only with
`LEDGER_HAND_DATA_DIR` before the program starts. When a setting in the
environment is refused, the Record page says why and shows nothing else,
and the Settings page still opens, with the same sentence and every
setting's default and why.

### What the page says when something fails

Each failure is said in one plain sentence: what happened, and what can be
done. The page never breaks, and nothing is recorded, saved or marked by
the step that failed.

| What failed | What the page says |
| --- | --- |
| No model answered | The address asked; whether Ollama is running; the address on the Settings page |
| The model took too long | The time allowed; the first call has to load the model and can be slow; try again, or allow more time on the Settings page |
| The model is not there | The model's name and the address; check the name, or install it with `ollama pull` |
| Called too often | The server turned the call away; wait a little, then try again |
| The server failed | Its status code, when it gave one; try again, or look at the server's own log |
| A reply not in the agreed form | The reply could not be used; try again, or put the passage another way |
| Replies that cannot be read as a table | The same, said apart |
| An empty passage | Nothing was sent to the model: the passage is empty |
| A passage too long | The limit, 16,384 characters; split it into shorter passages |
| A passage that is not valid text | Type it again, or paste it from somewhere else |
| A setting in the environment refused | Which one and its rule; correct or remove it, then start the program again |
| A change on the settings page refused | Which one and its rule; the settings were not changed |
| The book written by a newer version, not a database, or not this program's book | Which file, and that it was left as it is; use the newer version, move the file away, or point `LEDGER_HAND_DATA_DIR` elsewhere |
| The book damaged | Which file, and that the program does not write to it; keep a copy and move it away, or point `LEDGER_HAND_DATA_DIR` elsewhere |
| The book in use, unreadable or unwritable, clashing with what was asked, or failing otherwise | Why, in the book's own words; what to check, then try again |
| An export refused | Every reason, one to a line; nothing was marked |
| An export file not written | Why; nothing was marked; press Export again once that is put right |
| An export file written but not marked | Where it is; the next export writes the trades again |

The sentences are in `src/ledger_hand/ui/failure_words.py`, one for each
kind of each failure; a test walks every kind, so a new one cannot go
without a sentence. None of them ever shows the key.

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
| `layering` | `pytest tests/guardrails/test_repo_layering.py` | Each part of the package imports only what the layering table allows; `core/` reads no clock and uses no floating-point number; `extraction/` and `asking/` read no clock and no zone of the machine; only `settings.py` reads environment variables; only `ui/` imports Streamlit and only the wiring module imports tzlocal. |
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
One sample is the file the export flow writes from a book of invented trades
in a temporary folder, so that what the flow writes is judged as well. The
two samples that allow for the gap between the time zone databases are also
judged strictly: once both sides have been asked which of their trades they
give different offsets, those trades are left out, the rest are exported
again, and these two samples must be accepted with no error at all. The
output lists every trade left out, with its zone, its moment and both
offsets.
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
whether the model read them right is not judged there. Then it judges the
debug set (never the final set): the four sentences that report only what
the ledger does not record (leverage, one coin for another, an order not
filled, a plan) must each be stopped, with nothing extracted and no
question asked; the kind the model named is printed beside the kind the
sentence was written as. For the other 26 it prints where each would go,
and checks nothing about it. It also runs the page headless with the parts
the wiring module builds (the data folder pointed at a temporary one), sends
one invented passage, and checks that the page comes to its first question
or settles every trade without breaking; it prints what the program said,
the table and how long it took. On the settings page it then points the
model's address at a port on this machine nobody listens on, checks that a
passage is answered by the sentence that names that address, goes back to
the environment and the defaults, and checks that the same passage comes to
its first question. When the server cannot be reached, it fails with a
message that starts with `unreachable`.
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

### Recording trades by hand

```sh
.venv/bin/python scripts/record_trades.py "昨天晚上在 OKX 买了 0.3 个 ETH，又卖了 50 个 SOL"
.venv/bin/python scripts/record_trades.py --answers answers.txt "sold 2 SOL at 150 yesterday"
printf '3,180\nnone\ndone\n' | .venv/bin/python scripts/record_trades.py --answers - "..."
```

The passage is the arguments, or else the first line of standard input. The
script records it as described under "Recording a passage" above: each
question is printed with its label and the program's notes beside it, and
the answer is read from standard input. Answer "skip" to leave the trade
being asked about out, or "cancel" to drop the whole passage. Once every
trade is settled, the records are listed with the trades skipped, those
that cannot be recorded and why, the reminders and anything set aside; then
"remove N" leaves record N out, "cancel" drops the whole passage, and "done"
ends. Nothing is saved unless `--save` is given (see "Saving, listing and
exporting" below).

With `--answers FILE` the script is not interactive: the answers are the
lines of the file (`-` for standard input, after the passage when the
passage is not given as arguments), each printed after its question. When
they run out before every trade is settled, the script stops; when they run
out once every trade is settled, that counts as "done". The current moment
is the machine's clock and the zone the machine's own, read with tzlocal.
Without `--save`, `--list` or `--export`, nothing is written to disk and no
book is opened. Exit status: `0` done, with the records listed (there may be
none); `1` nothing is kept (the passage was refused, stopped, held no trade,
the model failed, or the passage was dropped); `2` the script could not
start (a setting or the zone); `3` the answers or the input ran out before
the end.

### Saving, listing and exporting

```sh
.venv/bin/python scripts/record_trades.py --save "昨天晚上在 OKX 买了 0.3 个 ETH，价格 3,180，手续费 0"
.venv/bin/python scripts/record_trades.py --list
.venv/bin/python scripts/record_trades.py --export
```

`--save` records the passage as above, with the book open. Before the first
question it says whether the same passage, or one that differs from it only
in spacing or full-width characters, was saved before: on which day, and how
many trades. That is a reminder only; nothing is held back. The coins
confirmed and saved before need no confirming again. Once the records are
final (after "done", and any "remove N" before it), it asks whether to save
them, and saves them only when the answer is `save` (or `yes`, `y`, `存`,
`保存`). Any other answer saves nothing, and so does running out of answers
with `--answers`: saving is never assumed.

`--list` lists every saved trade with its identifier, its fields, when it was
saved and whether and when it was exported. `--export` writes the saved
trades not exported yet into a new file in the exports folder and marks them
as exported, as described under "Keeping the records" above; with nothing
new, it says so and writes nothing.

The book and the exports folder are in the data folder; see "Where the data
is kept" below. Exit status, besides those above: `0` saved (or there was
nothing to save), listed, exported, or nothing new to export; `1` the
records were not saved, or the export was refused or its file could not be
written (nothing was marked); `4` the book failed (the message gives its
kind), or the export file was written but its trades could not be marked,
so that the next export writes them again.

### The prompts and their techniques

Each prompt version is a file of its own, never changed once measured; a new
wording is a new version.

| Prompt | Step | Technique |
| --- | --- | --- |
| `first` (`extraction/prompts/first.py`) | Extraction: copy the phrases of each trade into a table | A few examples (few-shot), in a file beside it |
| `screen-1` (`extraction/prompts/screen.py`) | Judging a passage: which kinds of thing it reports | No example at all (zero-shot) |
| `answer-1` (`extraction/prompts/answer.py`) | Reading an answer the rules could not: copy the one piece that gives what was asked | No example at all (zero-shot) |
| `bookkeeper-1` (`asking/prompts/bookkeeper.py`) | Wording a follow-up question | A role (persona): a meticulous bookkeeper who asks for one thing at a time |

Every prompt except the one for wording a question runs at the temperature
of `LEDGER_HAND_MODEL_TEMPERATURE` (0 by default); wording a question runs
at `LEDGER_HAND_MODEL_QUESTION_TEMPERATURE`. The state of a recorded passage
names the version used for each step.

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
compares it with the saved one. The debug set took about two minutes with
`qwen2.5:7b` on the machine it was built on, with the model already loaded;
the first sentence of a run includes loading the model when it is not.

The quick tier tests the scoring against cases worked out by hand and the
test sentences (coverage, no repeat of a prompt example, every gold answer
kept by the core's rules), and reads the final set only: no test sends a
test sentence to a model. It also checks that every committed run is
finished, that its saved summary is the one its results file gives, and
that `evals/RESULTS.md` shows exactly the tables each results file gives.

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
Every one of them but the key can also be changed on the interface's
settings page, for the browser tab only (see "The settings page" above).

| Variable | Default | What it sets | Why this default |
| --- | --- | --- | --- |
| `LEDGER_HAND_MODEL_URL` | `http://127.0.0.1:11434` | Where the model server is: an http or https address, with no user name, password, query or fragment. | Ollama's own address on this machine, so by default the model runs locally and nothing that is typed leaves the machine. |
| `LEDGER_HAND_MODEL_NAME` | `qwen2.5:7b` | Which model to ask. | The model the program was built and measured with. |
| `LEDGER_HAND_MODEL_KEY` | (none) | A key, sent as a bearer token, for a server that needs one. Never shown, and set in the environment only. | None: the local Ollama needs no key. |
| `LEDGER_HAND_MODEL_TEMPERATURE` | `0` | How adventurous the model is when it judges a passage, extracts the trades and reads an answer. 0 or more. | Extraction has to give the same answer to the same text, so the model always takes its likeliest word. |
| `LEDGER_HAND_MODEL_TOP_P` | `1` | Keeps only the likeliest words whose chances add up to this. Above 0, at most 1. | Keeps every word in play, so the temperature alone says how adventurous the model is; at temperature 0 it changes nothing. |
| `LEDGER_HAND_MODEL_MAX_REPLY_TOKENS` | `1024` | The longest reply, in tokens, the pieces of words a model counts in. A whole number, 1 or more. | Room for a JSON list of about ten trades. A reply that reaches it is marked as cut off rather than passed on as if it were whole. |
| `LEDGER_HAND_MODEL_CONTEXT_TOKENS` | `16384` | How much the model reads at once, in tokens. A whole number, 1 or more. | Ollama's own default (2048 or 4096, depending on the version) is too short for a prompt with examples and a schema, and Ollama drops the start of a prompt that does not fit, without an error. Measured with qwen2.5:7b, which reads up to 32768: the first prompt with its examples is about 1,750 tokens, and the longest passage the ledger keeps, 16,384 characters of Chinese, about 11,600 (English text takes fewer). With a full reply that is about 14,400, which leaves some 2,000 to spare; a longer window costs memory. |
| `LEDGER_HAND_MODEL_TIMEOUT_SECONDS` | `120` | How long to wait for the whole reply, in seconds. Above 0. Not sent to the model. | Leaves room for loading the model into memory on the first call (a cold start takes seconds to tens of seconds) and then writing a full-length reply. |
| `LEDGER_HAND_MODEL_RETRIES` | `2` | How many times a call that timed out, was rate limited or met a server error is tried again. 0 to 10. | Three tries in all, for the failures that may pass on their own, without keeping the person waiting for long. |
| `LEDGER_HAND_MODEL_RETRY_WAIT_SECONDS` | `1` | The wait before the first retry, in seconds; each later wait is twice the one before. 0 or more. | A second gives a busy server a moment to recover, and with each wait twice the one before, two retries add three seconds at most. |
| `LEDGER_HAND_MODEL_QUESTION_TEMPERATURE` | `0.7` | The temperature for wording a follow-up question. 0 or more. | Wording a follow-up question is the one call where some variety reads more naturally than the same sentence every time. What is asked, and every fact the question may use, are fixed by the program before the model writes, and a sentence that strays is replaced by the program's own, so a higher temperature changes only the wording. Judging a passage, extraction and reading an answer keep LEDGER_HAND_MODEL_TEMPERATURE, 0 by default. |

Numbers are written with plain digits and at most one point (`0.7`, `45`),
with no sign or exponent. The defaults are named constants in
`src/ledger_hand/settings.py`. What each variable sets and why its default
is what it is are kept there once, as data (`ABOUT`); this table and the
interface's settings page show them as written there, and a test checks
this table against them.

The time allowed is counted from sending. Connecting, sending and each wait
for the next piece of the reply are each cut off at the time allowed, and a
reply still arriving once that time has passed is abandoned at its next
piece. So a server that keeps trickling bytes cannot keep a call open for
long past the time allowed.

The plug ignores the proxy settings of the environment (`HTTP_PROXY` and the
like), so a request for the model on this machine never leaves it through a
proxy.

## Where the data is kept

| Variable | Default | What it sets |
| --- | --- | --- |
| `LEDGER_HAND_DATA_DIR` | `data` in the working directory | The data folder. The book is `ledger-hand-book.sqlite3` in it and export files go into `exports/` in it. A relative folder is taken from the working directory; a leading `~` is the home folder. |

The data folder and the exports folder are made when something is first
written there; reading the setting makes nothing, and recording a passage
without `--save` never opens the book. The interface opens the book when it
takes a passage (to find an earlier save of it and the coins confirmed
before), so the book is made then if it is not there yet; it writes trades
into it only on Save. This variable is not one of the model
settings above and does not start with their prefix, so setting it never
makes the model settings refuse anything; neither do `LEDGER_HAND_LEDGER_DIR`
and `LEDGER_HAND_PYTHON`, which the scripts read. The default `data/` is
kept out of Git by the repository's ignore file. The book holds the original
passages, as typed: keep it out of anything shared.

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
