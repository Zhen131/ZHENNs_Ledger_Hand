# Architecture

This document says how the code is divided into layers, who may import whom,
which house rules every change follows, and where a new feature goes. The
import rules are not only written here: the layering check enforces them
every time `scripts/check.sh` runs.

## The idea in one paragraph

The rules of the product (what a trade is, how a spoken number becomes an
exact one, what is still missing from a draft) live in `core/` and use
nothing but a short list of standard-library modules. Everything that touches
the outside world sits further out and is replaceable: the language model and
the database each hide behind a port, and the user interface is the outermost
layer. Swapping the model, the database or the interface must never require a
change in `core/`.

## Planned layout

Only what is marked "exists" is in the repository today. Everything else is
created by the change that first needs it; there are no empty folders or
placeholder files.

```text
pyproject.toml            dependencies and tool configuration, all in this one file   (exists)
README.md                                                                             (exists)
docs/                     documentation                                               (exists)
scripts/                  the check script and the ledger tier; scripts outside the package (exists)
data/                     run-time output: the book and the export files; never in Git
src/ledger_hand/
    core/                 core rules: no network, database or user interface          (exists)
        ledger_limits.py      the ledger's limits, and its way of measuring them      (exists)
        arithmetic.py         the decimal contexts every calculation runs in          (exists)
        trade.py              what one trade looks like; drafts may have blanks       (exists)
        coins.py              a small table of common coins                           (exists)
        numbers.py            reads number phrases; writes numbers for the ledger     (exists)
        time_wording.py       which known parts a time phrase is made of              (exists)
        timeparse.py          time phrases to exact moments ("now" is passed in)      (exists)
        validation.py         validation; which fields are still missing              (exists)
        zones.py              which time zone names are taken                         (exists)
        stored.py             a saved trade: record, identifier, two moments          (exists)
        book.py               what the book keeps beside a saved trade; listings      (exists)
        passage_form.py       a passage in the form it is compared in                 (exists)
        followup.py           what to ask next when something is missing or wrong     (exists)
    ports.py              the two ports: model and storage                            (exists)
    extraction/           a passage of text to drafts                                 (exists)
        extractor.py          the entry point: one passage in, drafts and issues out  (exists)
        reply_table.py        the flat table the model fills, as a JSON schema        (exists)
        reply_parser.py       reads a reply against the table; survives a garbled one (exists)
        passage.py            finds a copied phrase in the passage                    (exists)
        passage_numbers.py    the numbers written in a text                           (exists)
        row_draft.py          one row of the table to one draft                       (exists)
        unit_currency.py      which currency a unit word names                        (exists)
        issues.py             what was left empty and what to look at                 (exists)
        prompting.py          what a prompt version is; the messages it makes         (exists)
        prompts/              prompt versions, one file per version, examples beside  (exists)
        passage_check.py      a passage that must not be sent: empty, too long, not text (exists)
        screen_table.py       the list of kinds the model fills when judging a passage (exists)
        screening.py          judging a passage: stopped, no trade, or on to extraction (exists)
        answer_words.py       the fixed word lists an answer is read against          (exists)
        answer_table.py       what the model copies out of an answer; its reply       (exists)
        answer_phrase.py      reading an answer: rules first, the model only to copy  (exists)
    asking/               wording a follow-up question                                (exists)
        question_text.py      the facts, the model's sentence and its checks, the label (exists)
        templates.py          the program's own sentence for every question           (exists)
        prompts/              the persona prompt                                      (exists)
    llm/                  plugs for the model port: a local model server; later a cloud one (exists)
        ollama.py             the local plug: one chat call to Ollama, one try        (exists)
        ollama_request.py     what is sent: the body of one chat request              (exists)
        ollama_reply.py       what comes back: the reply, or the kind of failure      (exists)
        exchange.py           one HTTP exchange; sorts failed connections and statuses (exists)
        error_text.py         a server's words made safe to show, the key hidden      (exists)
        retry.py              tries again after failures that may pass on their own   (exists)
        local.py              the local plug assembled from the settings, with retries (exists)
        ollama_identity.py    the server's version and the model's fingerprint        (exists)
    storage/              plug for the storage port: SQLite, with numbered upgrade scripts (exists)
        sqlite_store.py       the plug: every operation of the port, one connection each (exists)
        book_file.py          opening a book: its mark, its version, upgrading it     (exists)
        rows.py               a saved trade as the values of a row, and back          (exists)
        failures.py           SQLite's failures as the port's kinds                   (exists)
        upgrades/             the numbered upgrade scripts, never changed once committed (exists)
    export/               writes the ledger's backup format as text                   (exists)
        backup.py             the whole file; refuses what the ledger would refuse    (exists)
        trade_entry.py        one saved trade in the ledger's fields                  (exists)
        coin_card.py          one coin in the ledger's fields                         (exists)
        moments.py            creation, change and export moments, in UTC             (exists)
        file_name.py          the name of an export file                              (exists)
    flows/                strings the parts into one task: record, save, export      (exists)
        recording.py          a passage from start to records, one question at a time (exists)
        progress.py           where it stands: one value that never changes           (exists)
        questions.py          putting a question together: facts and notes            (exists)
        filling.py            putting an answer back into a trade                     (exists)
        saving.py             the final records kept in the book                      (exists)
        identifiers.py        a new identifier for a saved trade                      (exists)
        fingerprint.py        a passage's fingerprint, worked out in one place        (exists)
        coin_book.py          the confirmed coins between the book and the coin table (exists)
        exporting.py          the trades not exported yet, written as one file, marked (exists)
        export_file.py        a new file, whole, never replacing another              (exists)
    settings.py           the only place that reads settings                          (exists)
    ui/                   the user interface; the only place that may use Streamlit
evals/                    prompt experiments: test sentences, scoring, runner, results (exists)
    sets/                 the test sentences with gold answers: debug and final   (exists)
    gold.py               the shapes of a sentence and its gold answer             (exists)
    coverage.py           what the sentences cover                                 (exists)
    cells.py              one field judged against the gold answer                 (exists)
    matching.py           drafts paired with gold trades, in any order             (exists)
    scoring.py            the scores of one sentence and of many                   (exists)
    records.py            the results file, line by line                           (exists)
    tables.py             the summary of a run and its tables                      (exists)
    run.py                the runner                                               (exists)
    summarize.py          the summary worked out again from a results file         (exists)
    results/              one results file per run, with its summary               (exists)
    RESULTS.md            the results record                                       (exists)
tests/                    mirrors src; also holds the guardrails, fakes and golden samples  (exists)
    fakes/                stand-ins for the outside world: scripted models, a book in memory (exists)
    storage/              tests of the storage port against every plug; the golden book (exists)
    live/                 the live check against a real model, run by hand only       (exists)
    extraction/           tests of extraction against the scripted model              (exists)
    asking/               tests of wording a question                                 (exists)
    flows/                tests of recording a passage and of its script              (exists)
    evals/                tests of the experiment kit and the test sentences          (exists)
```

A **port** is an interface that the inner code talks to ("ask the model",
"save a trade"). A **plug** is one implementation of a port (a local model
server, a SQLite file). There are exactly two ports: model and storage.

## Who may import whom

| Part | May import | May not import |
| --- | --- | --- |
| `core/` | the standard-library modules on the core allow-list (below); `core/` itself | everything else |
| `ports.py` | `core/`; standard-library modules of the annotation kind (below) | third-party libraries; every other part |
| `extraction/`, `asking/`, `export/` | `core/`, `ports.py` | `llm/`, `storage/`, `settings.py`, `flows/`, `ui/` |
| `llm/`, `storage/` (the plugs) | `core/`, `ports.py`, `settings.py` | `extraction/`, `export/`, `flows/`, `ui/`, each other |
| `settings.py` | the standard library | every other part of the package |
| `flows/` | everything except `ui/` | `ui/` |
| `ui/` | everything | nothing is closed to it |
| outside the package: `scripts/`, `evals/`, `tests/` | anything in the package | the package never imports them back |

How the check reads this table:

- A part may always import itself.
- "May import" is a complete list. What is not on it is refused, even when the
  third column does not name it; so `extraction/`, `asking/` and `export/` may
  not import each other either.
- The package's own `__init__.py` only states the version. It imports nothing
  from the package; `flows/` and `ui/` may import it.
- Parts other than `core/` and `ports.py` may use the standard library freely,
  apart from the reserved modules below.
- A part that does not exist yet is simply not checked. A directory or
  top-level module that has no row in the table is refused until a row is
  added for it.
- Importing by name at run time (`importlib.import_module`, `__import__`) is
  refused everywhere, because it hides the import from the check.
- Only `settings.py` may touch environment variables (see below).

### Reserved modules

| Module | The only place that may import it |
| --- | --- |
| `streamlit` | `ui/` |
| `httpx` | `llm/` |
| `sqlite3` | `storage/` |
| `tzlocal` | no part of the package today: only scripts outside it. A wiring module that assembles the application is planned; when it is added, it becomes the one place inside the package that may import it. |

Any other third-party import is refused in every part. A new run-time
dependency is a design decision, not a routine edit.

### Environment variables

Settings are read in one place. Only `settings.py` may touch environment
variables; everywhere else in the package the check reports:

- `environ`, `environb`, `getenv`, `getenvb`, `putenv` and `unsetenv` used
  as an attribute of anything (`os.environ`, `os.getenv(...)`, an alias of
  `os`, `posix.environ`);
- importing any of them from `os`, `posix` or `nt`, and `from os import *`;
- fetching one of them with `getattr` by its name.

Scripts and tests outside the package are free to read the environment. A
second gate, `tests/guardrails/test_repo_model_boundaries.py`, checks the real
package straight from its source, without the table: only `llm/` imports
httpx, the ports file imports only the standard library and the core, and
only `settings.py` reads the environment.

### The core allow-list

`core/` may import these standard-library modules and nothing else:

`__future__`, `abc`, `collections`, `dataclasses`, `datetime`, `decimal`,
`enum`, `fractions`, `functools`, `itertools`, `math`, `numbers`, `operator`,
`re`, `string`, `typing`, `unicodedata`, `zoneinfo`

The test for joining the list: the module **only computes and never touches
the outside world** (mathematics, exact decimals, date and time types, time
zones, enumerations, data classes, regular expressions, type annotations).
Modules for files, the network, databases, processes, random numbers or
reading the clock never join it.

`ports.py` may import `core/` and these: `__future__`, `abc`, `collections`,
`dataclasses`, `enum`, `typing`. They declare shapes (annotations and plain
data types) and nothing else.

### What else `core/` may not do

`core/` does not look at the clock or at the machine's time zone. The caller
passes the current moment and the zone in as arguments. The check reports:

- any call to `.now()`, `.utcnow()` or `.today()`, and any mention of those
  methods on `datetime` or `date` even without a call;
- the `time` module (it is not on the allow-list);
- `astimezone()` and `fromtimestamp()` without an explicit zone, and
  `ZoneInfo("localtime")`, all of which silently use the machine's zone;
- the same name given by keyword (`ZoneInfo(key="localtime")`) or to the
  uncached constructor (`ZoneInfo.no_cache("localtime")`), `from_file()`,
  which is how the machine's own zone file is loaded, and any call to
  `.timestamp()`, which takes a time without a zone to be in the machine's
  zone;
- the builtins that reach outside the program: `open`, `input`, `print`,
  `breakpoint`, `eval`, `exec`, `compile`.

It cannot see `astimezone(zone)` called on a time without a zone, which also
takes that time to be in the machine's zone. The core therefore only ever
handles moments that carry an offset; a current moment without one is refused
where it comes in.

There is one look outside the program the core does take: the zone database.
`ZoneInfo` reads a zone's rules from it, and `core/zones.py` reads from it,
once, the list of zone names, because a time zone name is taken only when it
is spelled exactly as that list has it. The rules of time zones are kept
nowhere else. Reading the database tells the core nothing about the machine's
own clock or zone.

`core/` does not use floating-point numbers either: an amount is an exact
decimal built from text. The check reports:

- any floating-point or complex constant (`0.1`, `1e5`, `1j`);
- any call that turns something into such a number: `float()`, `complex()`,
  `.__float__()`, `.__complex__()`, `.from_float()` and `float.fromhex()`.

It cannot see everything. Dividing two whole numbers with `/`, for one, gives
a floating-point number without any of these signs; that is left to whoever
reads the change.

### What `extraction/` may not do

`extraction/` is handed the current moment and the time zone's name, like
the core. The check reports in it the same reads of the clock and of the
machine's zone as in `core/` (see above), and also those through the `time`
module: its clock functions (`time.time()`, `time.monotonic()`,
`time.perf_counter()` and the like) and what it says about the machine's
zone (`time.localtime()`, `time.tzname`, `time.timezone` and the like),
called as an attribute of the module under any name or imported by name.
`extraction/` may still import the module for anything else. A second gate,
`tests/guardrails/test_repo_extraction_boundaries.py`, checks the real
`extraction/` straight from its source, without the table: it imports only
the standard library, the core and the ports file, never the `time` module,
calls no method that reads the clock or the machine's zone, and names no
environment variable.

### What `storage/` may not do

`storage/` is the only part that may import `sqlite3`, and it imports
nothing of the package but the core, the ports file and the settings. It
reads no clock: every moment it keeps is handed in. A second gate,
`tests/guardrails/test_repo_storage_boundaries.py`, checks the real package
straight from its source: only `storage/` imports sqlite3, `storage/`
imports only what it may, and the ports file names the storage shapes from
the core only.

### What `asking/` and `flows/` may not do

`asking/` is handed the facts of a question and reads neither the clock nor
the machine's zone; the layering check reports in it the same reads as in
`extraction/`. `flows/` is handed the current moment and the zone by whoever
starts it (a script or, later, the interface) and passes them on; it never
reads them itself. The identifiers it gives saved trades are random UUIDs
(version 4), never ones made from the clock. A gate,
`tests/guardrails/test_repo_clock_free_parts.py`,
checks the real source of both straight, without the table: neither imports
the `time` module, calls a method that reads the clock or the machine's zone,
or names an environment variable, and `asking/` imports only the standard
library, the core and the ports file.

## The eleven rules

| # | Rule | Why |
| --- | --- | --- |
| 1 | `core/` holds only pure computation and the shapes of data. It does not touch the network, a database or the user interface, and it never reads the clock itself. | It can be tested with no setup, and it can be carried anywhere, forever. |
| 2 | Outer layers use inner layers, never the reverse: interface, then flows, then core. An automated check enforces it. | Changing the model or the database does not touch the core. |
| 3 | There are only two ports: model and storage. Everywhere else the code just says "ask the model" or "save a trade". | This is what keeps the program from bloating: a different storage or a cloud model changes one piece. |
| 4 | Streamlit appears only in `ui/`, and the interface makes no business decisions. | The interface reruns from the top on every click; business logic mixed into it is convoluted and cannot be tested. |
| 5 | Numbers are exact decimals and are stored as text. Times are written the way the ledger writes them. | Ordinary floating-point numbers carry error, and a ledger cannot. |
| 6 | A model reply is untrusted input. It first becomes a draft, and the core then validates the draft. A draft that fails leads to a follow-up question, not an error. | A different model replies in a different shape; the validation line stays where it is. |
| 7 | The model only copies times and numbers as they were written; the program does the converting. Whatever it copied must be found in the original text. | It stops the model from miscalculating or inventing figures. |
| 8 | Settings are read in exactly one place. | A new address or key is changed in one spot. |
| 9 | One file does one job. No junk-drawer files. A function fits on one screen. | A junk drawer only ever grows. |
| 10 | States are named options, not bare strings, and never a true/false switch passed as a parameter. | The reader sees at a glance what a value means. |
| 11 | Export files and the local database carry version numbers. A change that raises a version adds a golden sample of that version in the same change. | A file written ten years ago can still be read ten years from now. |

Two more sit beside the eleven: comments say only **why**; formatting is
left to the tool.

How the rules are applied in practice:

- **"A function fits on one screen" is measured in statements, not lines:**
  a function has **no more than 30 statements** (ruff rule `PLR0915`), and its
  branching complexity is no more than 10 (ruff rule `C901`).
- **No junk-drawer files** means no `utils.py`, `helpers.py` or `common.py`.
- **Every module opens with a short description** of what it is responsible
  for and what it is not.
- **States and reasons are enumerations.** Boolean flag parameters are
  reported by the linter.
- **Version numbers are named constants.** A golden sample that has been
  committed is never edited afterwards.
- **Create on first use.** A file or folder appears in the change that first
  needs it.
- **Type checking is strict where it matters most:** `core/` and `ports.py`.
  The rest is not type-checked.
- **Everything in the repository is written in English:** documentation, code
  comments, error messages and interface text. Inputs inside tests may be in
  Chinese, because they are the data under test.
- **All test data is invented.** No real trade and no real ledger export ever
  enters the repository.

## The model port

The model port in `ports.py` is a `ModelPort` with one method, `chat`:
messages in (each with a role and its text), optionally a JSON schema the
reply has to follow and a set of `ModelParameters`; a `ModelReply` out (the
text and a `ReplyRecord`). Without parameters the plug uses the defaults it
was built with from the settings. Every failure is a `ModelError` whose
`kind` is one of six (`ModelErrorKind`):

| Kind | Raised when |
| --- | --- |
| `UNREACHABLE` | The connection cannot be made (refused, or the name does not resolve), or the address is one httpx cannot use. |
| `TIMED_OUT` | Connecting, sending or a wait for the answer passed the time allowed, or the answer was not complete once that time had passed. |
| `MODEL_NOT_FOUND` | Ollama answers 404 with a JSON `error` that says "not found"; or the model is not in the server's list when its fingerprint is asked for. |
| `RATE_LIMITED` | The server answers 429. |
| `SERVER_ERROR` | The server answers 500 to 599. Also every failure that fits no other kind, with the raw status, error and start of the answer attached: any other status, a connection that breaks off mid-answer, broken HTTP. |
| `MALFORMED_REPLY` | Status 200, but the answer is not UTF-8, not JSON, not an object, has no message or no text, has blank text or text that is not valid Unicode, is not marked done, or is longer than the cap. |

Each kind is recognised by what it positively looks like; what is not
recognised falls to `SERVER_ERROR` (or, for an answer with status 200, to
`MALFORMED_REPLY`), never to an exception of another type. Errors in the
program itself (a call in the wrong shape, a bug) are not model failures and
are not turned into one.

`llm/retry.py` tries a call again after `TIMED_OUT`, `RATE_LIMITED` and
`SERVER_ERROR`, a limited number of times, each wait twice the one before.
The other three are raised at once: waiting does not mend them, and on this
machine `UNREACHABLE` means the server is not running, which the person at
the keyboard should hear straight away.

Whether a reply's text is valid JSON that follows the schema is not checked
by the plug. A model reply is untrusted input (rule 6), and the code that
asked checks it.

`tests/fakes/scripted_model.py` is the port's stand-in for tests: it plays
back a script of replies and errors in order, records every call, and fails
the test when the script runs out.

## The storage port

The storage port in `ports.py` is a `StoragePort` with five methods. Their
shapes carry moments, so they are declared in `core/book.py` and only named
in the ports file, which may not use `datetime` itself.

| Method | What it does |
| --- | --- |
| `save(PassageSave)` | Saves the trades recorded from one passage, with the passage's fingerprint, the moment of saving and the coins the user confirmed that they use, all in one transaction. Gives back the trades as saved. An identifier already in the book is a `CONFLICT` and nothing is saved. |
| `earlier_saves(fingerprint)` | Every earlier save of a passage with that fingerprint: when, and how many trades. |
| `trades(Listing)` | The saved trades, all of them or those not exported yet, in the order saved, each with the moment it was exported. |
| `mark_exported(ExportMark)` | Marks the trades named as exported at the moment given, all of them or none; a trade not in the book, or already exported, is a `CONFLICT`. |
| `confirmed_coins()` | The coins the user confirmed and saved a trade with. |

Every failure is a `StorageError` whose `kind` is one of eight
(`StorageErrorKind`):

| Kind | Raised when |
| --- | --- |
| `NEWER_VERSION` | The book was written by a newer version of this program. It is left as it is. |
| `NOT_A_DATABASE` | The file is not a SQLite database at all. It is left as it is. |
| `NOT_THIS_PROGRAMS` | The file is a database without this program's mark, or its tables are not exactly those of its version. It is left as it is. |
| `DAMAGED` | SQLite finds the book damaged (cut short, malformed), or a row cannot be read back as what the book wrote. |
| `LOCKED` | Someone else is using the book and it stayed busy for longer than the wait allowed. |
| `INACCESSIBLE` | The book or its folder cannot be made, read or written: no permission, a read-only folder, a folder that is a file, a full disk, an input or output error. |
| `CONFLICT` | What was asked does not fit what the book holds (see the table above). |
| `UNEXPECTED` | A failure that fits no other kind, with SQLite's own words. |

**The book's version.** The book carries two numbers in its file header: a
mark that says it is this program's book (SQLite's `application_id`) and its
version (`user_version`), a named constant, `BOOK_VERSION`, in
`storage/book_file.py`. They are read first, through a connection that
cannot write. A file that is newer, not a database or not this program's is
refused without one byte written; a missing or empty file becomes a new book
of the current version. These numbers are the book's own and none of the
ledger's four version numbers.

**Upgrade scripts.** `storage/upgrades/upgrade_NNNN.py`, numbered from 1 with
no gap: script `n` turns a book of version `n - 1` into one of version `n`.
They run in order, each in a transaction of its own, and are never changed
once committed: a change to the tables is the next script, with a golden
sample of the version it makes, in the same change. A test lists the
scripts from the folder and checks that running them one by one from an
empty file gives exactly the tables of a new book.

**The golden sample.** `tests/storage/golden/book-v1.sqlite3`, made by the
store itself and compacted, and its text dump `book-v1.sql`, so that the
hygiene scan sees what is inside. Tests copy it to a temporary folder before
opening it and check that the current code reads exactly what it holds,
that the dump makes the same tables and rows, and that both files are the
bytes committed.

`tests/fakes/memory_store.py` is the port's stand-in for tests: it keeps
everything in memory, does what the port promises the way the SQLite plug
does, passes the same tests of the port, and can be made to fail.

## Deliberately left out

Too heavy for a program of this size: wrapper frameworks around language
models, evaluation frameworks as the main harness, database abstraction
layers, data-validation libraries, plug-in systems, dependency-injection
frameworks, containers, multiple packages, coverage thresholds, and a second
formatting tool.

## Where a new feature goes

- **Screenshot input:** one more file in `extraction/`; the model port gains a
  way to send an image.
- **Voice input:** a new folder of its own that turns speech into text; the
  text then takes the existing path.
- **Asking questions about the ledger:** one more file in `flows/`.
- **A cloud model:** one more plug in `llm/`, chosen through settings.
- **A new folder or top-level module:** add its row to the layering table in
  `tests/guardrails/layering.py`, to the expected table in the tests next to
  it, and to the table above.

## Changing the rules

Adding a rule, a check or a test is always welcome. Loosening one is a design
decision for the project owner and never a routine edit. That covers widening
a cell of the import table, switching off a lint rule, raising a threshold,
granting a new run-time dependency, adding a third port, and changing or
removing an existing test.

The tests of the layering check write the table out a second time by hand, so
a check that has been loosened without touching them fails.
