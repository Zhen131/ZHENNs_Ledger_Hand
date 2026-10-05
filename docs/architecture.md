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
scripts/                  the check script; later, other scripts outside the package  (exists)
data/                     run-time output and the local database; never in Git
src/ledger_hand/
    core/                 core rules: no network, database or user interface          (exists)
        ledger_limits.py      the ledger's limits, and its way of measuring them      (exists)
        arithmetic.py         the decimal contexts every calculation runs in          (exists)
        trade.py              what one trade looks like; drafts may have blanks       (exists)
        coins.py              a small table of common coins                           (exists)
        numbers.py            reads number phrases; writes numbers for the ledger     (exists)
        timeparse.py          time phrases to exact moments ("now" is passed in)
        validation.py         validation; which fields are still missing              (exists)
        followup.py           what to ask when something is missing
    ports.py              the two ports: model and storage
    extraction/           a passage of text to drafts
        prompts/              prompt versions, one file per version
        reply_parser.py       turns a model reply into drafts; survives a garbled reply
        extractor.py
    llm/                  plugs for the model port: a local model server; later a cloud one
    storage/              plug for the storage port: SQLite, with numbered upgrade scripts
    export/               writes the ledger's JSON import format
    flows/                strings the parts into one task: record a trade, export
    settings.py           the only place that reads settings
    ui/                   the user interface; the only place that may use Streamlit
evals/                    prompt experiments: test sentences, scoring script, results
tests/                    mirrors src; also holds the guardrails, fakes and golden samples  (exists)
```

A **port** is an interface that the inner code talks to ("ask the model",
"save a trade"). A **plug** is one implementation of a port (a local model
server, a SQLite file). There are exactly two ports: model and storage.

## Who may import whom

| Part | May import | May not import |
| --- | --- | --- |
| `core/` | the standard-library modules on the core allow-list (below); `core/` itself | everything else |
| `ports.py` | `core/`; standard-library modules of the annotation kind (below) | third-party libraries; every other part |
| `extraction/`, `export/` | `core/`, `ports.py` | `llm/`, `storage/`, `settings.py`, `flows/`, `ui/` |
| `llm/`, `storage/` (the plugs) | `core/`, `ports.py`, `settings.py` | `extraction/`, `export/`, `flows/`, `ui/`, each other |
| `settings.py` | the standard library | every other part of the package |
| `flows/` | everything except `ui/` | `ui/` |
| `ui/` | everything | nothing is closed to it |
| outside the package: `scripts/`, `evals/`, `tests/` | anything in the package | the package never imports them back |

How the check reads this table:

- A part may always import itself.
- "May import" is a complete list. What is not on it is refused, even when the
  third column does not name it; so `extraction/` and `export/` may not import
  each other either.
- The package's own `__init__.py` only states the version. It imports nothing
  from the package; `flows/` and `ui/` may import it.
- Parts other than `core/` and `ports.py` may use the standard library freely,
  apart from the reserved modules below.
- A part that does not exist yet is simply not checked. A directory or
  top-level module that has no row in the table is refused until a row is
  added for it.
- Importing by name at run time (`importlib.import_module`, `__import__`) is
  refused everywhere, because it hides the import from the check.

### Reserved modules

| Module | The only place that may import it |
| --- | --- |
| `streamlit` | `ui/` |
| `httpx` | `llm/` |
| `sqlite3` | `storage/` |
| `tzlocal` | no part of the package today: only scripts outside it. A wiring module that assembles the application is planned; when it is added, it becomes the one place inside the package that may import it. |

Any other third-party import is refused in every part. A new run-time
dependency is a design decision, not a routine edit.

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

`core/` does not use floating-point numbers either: an amount is an exact
decimal built from text. The check reports:

- any floating-point or complex constant (`0.1`, `1e5`, `1j`);
- any call that turns something into such a number: `float()`, `complex()`,
  `.__float__()`, `.__complex__()`, `.from_float()` and `float.fromhex()`.

It cannot see everything. Dividing two whole numbers with `/`, for one, gives
a floating-point number without any of these signs; that is left to whoever
reads the change.

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
- **Type checking is strict where it matters most:** `core/`, and `ports.py`
  once it exists. The rest is not type-checked.
- **Everything in the repository is written in English:** documentation, code
  comments, error messages and interface text. Inputs inside tests may be in
  Chinese, because they are the data under test.
- **All test data is invented.** No real trade and no real ledger export ever
  enters the repository.

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
