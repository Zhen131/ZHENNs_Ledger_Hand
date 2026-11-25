# Architecture

This document says how the code is divided into layers, who may import whom,
which house rules every change follows, and where a new feature goes. The
import rules are not only written here: the layering check enforces them
every time `scripts/check.sh` runs.

## The idea in one paragraph

The rules of the product (what a trade is, how a spoken number becomes an
exact one, what is still missing from a draft) live in `core/` and use
nothing but a short list of standard-library modules. Everything that touches
the outside world sits further out and is replaceable: the language model,
the database and the person's ledger each hide behind a port, and the user
interface is the outermost layer. Swapping the model, the database or the interface must never require a
change in `core/`.

## Layout

Everything below is in the repository and marked "exists", except `data/`,
which the program makes when it first writes there and which is never
committed. A folder or file is created by the change that first needs it;
there are no empty folders or placeholder files.

```text
pyproject.toml            dependencies and tool configuration, all in this one file   (exists)
requirements.txt          the exact versions of every dependency, to rebuild the environment (exists)
README.md                 what the program is, how to install, run and check it      (exists)
.streamlit/config.toml    Streamlit's settings: nothing sent, this machine only, headless, no developer menu (exists)
docs/                     documentation                                               (exists)
    architecture.md       this file                                                   (exists)
    known-gaps.md         known limits, each waiting for a decision                   (exists)
    project-report.md     the project described for a reader new to it                (exists)
scripts/                  scripts outside the package                                 (exists)
    check.sh              every check, one tier at a time: quick, ledger, live        (exists)
    ledger_check.py       the ledger tier, with ledger_validate.ts and ledger_offsets.ts (exists)
    record_trades.py      record, save, list and export at the command line           (exists)
    try_extraction.py     try extraction by hand with the real model                  (exists)
    try_screenshot.py     try a screenshot by hand: the text read, then the drafts    (exists)
    try_assistant.py      try the assistant by hand: every step, with the fake ledger (exists)
data/                     run-time output: the book, the export files and the assistant's record; never in Git
src/ledger_hand/
    core/                 core rules: no network, database or user interface          (exists)
        ledger_limits.py      the ledger's limits, and its way of measuring them      (exists)
        arithmetic.py         the decimal contexts every calculation runs in          (exists)
        trade.py              what one trade looks like; drafts may have blanks       (exists)
        coins.py              a small table of common coins                           (exists)
        assets.py             the asset table: what may be traded, the money to price it in (exists)
        ledger_table.py       the asset table and the asset names the ledger's own list makes (exists)
        numbers.py            reads number phrases; writes numbers for the ledger     (exists)
        time_wording.py       which known parts a time phrase is made of              (exists)
        timeparse.py          time phrases to exact moments ("now" is passed in)      (exists)
        time_range.py         a stretch of time named in words to two exact moments   (exists)
        spoken_text.py        words said tidied: number words and a time in digits, each change checked (exists)
        validation.py         validation; which fields are still missing              (exists)
        zones.py              which time zone names are taken                         (exists)
        stored.py             a saved trade: record, identifier, two moments          (exists)
        book.py               what the book keeps beside a saved trade; listings      (exists)
        passage_form.py       a passage in the form it is compared in                 (exists)
        followup.py           what to ask next when something is missing or wrong     (exists)
        fee_cost.py           whether the ledger counts a trade's fee in the cost     (exists)
        ledger_records.py     what the ledger port hands back: assets, trades, sums, holdings (exists)
        proposals.py          the ledger's answer to a proposal, and where one stands (exists)
    ports.py              the three ports: model, storage and ledger                  (exists)
    extraction/           a passage of text to drafts                                 (exists)
        extractor.py          the entry point: one passage in, drafts and issues out  (exists)
        reply_table.py        the flat table the model fills, as a JSON schema        (exists)
        reply_parser.py       reads a reply against the table; survives a garbled one (exists)
        passage.py            finds a copied phrase in the passage                    (exists)
        passage_numbers.py    the numbers written in a text                           (exists)
        longer_numbers.py     whether a copied number is part of a longer one         (exists)
        row_draft.py          one row of the table to one draft                       (exists)
        unit_currency.py      which currency a unit word names                        (exists)
        issues.py             what was left empty and what to look at                 (exists)
        prompting.py          what a prompt version is, its reply table; its messages (exists)
        prompts/              prompt versions, one file per version, examples beside  (exists)
            first.py              extraction, few-shot: the version the product uses  (exists)
            first_examples.py     the ten invented examples of `first`                (exists)
            zero_shot.py          extraction, zero-shot: `first` with no example      (exists)
            persona.py            extraction, persona: a role before `first`'s words  (exists)
            stepwise.py           extraction, chain of thought: analysis before the rows (exists)
            price_total.py        extraction: `first` and one rule, a total is never the price (exists)
            second.py             extraction: `first`, two more rules, six more examples, for experiments (exists)
            second_examples.py    the ten examples of `first` and the six `second` adds (exists)
            third.py              extraction: `first` and the two rules of `second`, for experiments (exists)
            fourth.py             extraction: `first`, the two rules of `second`, seven more examples, for experiments (exists)
            fourth_examples.py    the ten examples of `first` and the seven `fourth` adds (exists)
            split.py              splitting a passage, few-shot, for experiments      (exists)
            screen.py             judging a passage, zero-shot                        (exists)
            screen2.py            judging, `screen`'s words for shares as well: the assistant's (exists)
            first2.py             extraction: `first` for shares as well, one rule more, for experiments (exists)
            first2_examples.py    the ten examples of `first` and the three with shares `first2` adds (exists)
            first3.py             extraction: `first2`, the quantity copied whole: the assistant's (exists)
            first3_examples.py    the ten examples of `first` and the three with shares `first3` adds (exists)
            answer.py             reading an answer, zero-shot                        (exists)
            read.py               reading a screenshot out as text, zero-shot         (exists)
        passage_check.py      a passage that must not be sent: empty, too long, not text (exists)
        screen_table.py       the list of kinds the model fills when judging a passage (exists)
        screening.py          judging a passage: stopped, no trade, or on to extraction (exists)
        answer_words.py       the fixed word lists an answer is read against          (exists)
        answer_table.py       what the model copies out of an answer; its reply       (exists)
        answer_phrase.py      reading an answer: rules first, the model only to copy  (exists)
        split_table.py        the pieces the model copies for each trade when splitting (exists)
        segments.py           those pieces put back together, one segment per trade   (exists)
        splitting.py          split first, then extract each segment; for experiments (exists)
        picture_prompt.py     what a version of the prompt that reads a screenshot is (exists)
        picture_reading.py    reading a screenshot: the text the model reads off it   (exists)
    asking/               wording a follow-up question                                (exists)
        question_text.py      the facts, the model's sentence and its checks, the label (exists)
        templates.py          the program's own sentence for every question           (exists)
        prompts/              the persona prompt                                      (exists)
            bookkeeper.py         wording a question, persona: a meticulous bookkeeper (exists)
    llm/                  plugs for the model port: a local model server and a cloud service (exists)
        ollama.py             the local plug: one chat call to Ollama, one try        (exists)
        ollama_request.py     what is sent: the body of one chat request              (exists)
        ollama_reply.py       what comes back: the reply, or the kind of failure      (exists)
        ollama_tool_reply.py  what comes back to a call with tools: text and tool calls (exists)
        cloud.py              the cloud plug: one call to an OpenAI-style chat endpoint (exists)
        cloud_request.py      what it sends: the body of one chat request             (exists)
        cloud_reply.py        what comes back: the reply, or the kind of failure      (exists)
        request_body.py       what both plugs share in writing a request              (exists)
        reply_json.py         what both plugs share in reading a reply                (exists)
        exchange.py           one HTTP exchange; sorts failed connections and statuses (exists)
        error_text.py         a server's words made safe to show, the key hidden      (exists)
        key_forms.py          where a key stands in a text, in any known way written  (exists)
        retry_after.py        how long a rate-limited server asks to wait             (exists)
        retry.py              tries again after failures that may pass on their own   (exists)
        connect.py            the plug the settings choose, checked, with retries     (exists)
        local.py              the local plug alone, assembled with retries            (exists)
        ollama_identity.py    the server's version and the model's fingerprint        (exists)
    storage/              plug for the storage port: SQLite, with numbered upgrade scripts (exists)
        sqlite_store.py       the plug: every operation of the port, one connection each (exists)
        book_file.py          opening a book: its mark, its version, upgrading it     (exists)
        rows.py               a saved trade as the values of a row, and back          (exists)
        failures.py           SQLite's failures as the port's kinds                   (exists)
        upgrades/             the numbered upgrade scripts, never changed once committed (exists)
            upgrade_0001.py       an empty file becomes a book of version 1           (exists)
    ledger/               plugs for the ledger port: the fake ledger and the real one (exists)
        link_ledger.py        the real ledger's plug, through its assistant link      (exists)
        link_client.py        starts the ledger's assistant link and talks to it      (exists)
        link_failures.py      how the link can fail; the token, never printed         (exists)
        link_tools.py         the eight tools this program expects of the link        (exists)
        fake_ledger.py        the fake ledger: an invented book in memory; save, reject (exists)
        invented_book.py      the invented book: assets, trades, market prices, "now"  (exists)
        moving_average.py     the fake ledger's own way of working out cost and profit (exists)
        fake_sums.py          the fake ledger's sums of a stretch of time and holdings (exists)
    assistant/            what the assistant's model is handed, and how its calls are judged (exists)
        tools.py              the eight tools; every argument a choice or copied words (exists)
        judging.py            one tool call taken, or a wrong step and why            (exists)
        narrowing.py          whether a lookup's asset and side are ones the user asked for (exists)
        lookups.py            what a read tool found, as the ledger gave it; its header and table (exists)
        explanation.py        whether the model's words beside a table, or without one, may be shown (exists)
        results.py            what is handed back for a call, as JSON text            (exists)
        outcome.py            how one turn went: the chat, the steps, the ending      (exists)
        edit_calls.py         a change or a deletion judged: asset apart, `trade` dropped (exists)
        new_values.py         a change's new value read, and put into the trade found (exists)
        picking.py            which listed trade, or which amount follows, the user said (exists)
        edit_words.py         the program's words and tables for a change or a deletion (exists)
        period_cuts.py        whether a copied period is cut out of a longer time said (exists)
        prompting.py          what a version of the system prompt is; its message     (exists)
        prompts/              the system prompt versions                              (exists)
            assistant_first.py    the assistant's rules, no example                   (exists)
            assistant_second.py   the first's rules and a paragraph on asking the ledger (exists)
            assistant_third.py    the first's words and short rules on asking          (exists)
            assistant_fourth.py   the first's words with two rules changed: the default (exists)
    export/               writes the ledger's backup format as text                   (exists)
        backup.py             the whole file; refuses what the ledger would refuse    (exists)
        trade_entry.py        one saved trade in the ledger's fields                  (exists)
        coin_card.py          one coin in the ledger's fields                         (exists)
        moments.py            creation, change and export moments, in UTC             (exists)
        file_name.py          the name of an export file                              (exists)
    flows/                strings the parts into one task: record, save, export      (exists)
        recording.py          a passage from start to records, one question at a time (exists)
        screenshot.py         a passage from a screenshot: the text read, then the note (exists)
        uploading.py          an uploaded screenshot checked step by step, then read  (exists)
        progress.py           where it stands: one value that never changes           (exists)
        questions.py          putting a question together: facts and notes            (exists)
        filling.py            putting an answer back into a trade                     (exists)
        assisting.py          one turn of the assistant: ask the model, judge, run, again (exists)
        asking.py             the four read tools: the period read, asset and side checked, the ledger asked (exists)
        conversation.py       one thing said to the assistant, tidied first: answer, model, recording, a change, a screenshot (exists)
        standing.py           where a proposal stands; the demo ledger's save and reject (exists)
        editing.py            one trade changed or deleted: found, picked, read, proposed (exists)
        proposing.py          a settled passage's trades sent to the ledger as one proposal (exists)
        recorded.py           how recording through the assistant ended this time     (exists)
        record_words.py       the program's own words about that, one for each ending (exists)
        reminder_words.py     one reminder of extraction in words, for both pages     (exists)
        saving.py             the final records kept in the book                      (exists)
        identifiers.py        a new identifier for a saved trade                      (exists)
        fingerprint.py        a passage's fingerprint, worked out in one place        (exists)
        coin_book.py          the confirmed coins between the book and the coin table (exists)
        exporting.py          the trades not exported yet, written as one file, marked (exists)
        export_file.py        a new file, whole, never replacing another              (exists)
        assistant_record.py   the assistant's record: one versioned line per thing said (exists)
    settings.py           the only place that reads settings; why each default, as data (exists)
    wiring.py             builds the parts from the settings, page changes, the clock and the zone (exists)
    ui/                   the user interface; the only place that may use Streamlit   (exists)
        app.py                the entry Streamlit runs: the title, Record, Settings and Assistant (exists)
        record_page.py        the Record page: chat and screenshot beside the table, Export (exists)
        settings_page.py      the Settings page: every setting, its value, default and why (exists)
        settings_form.py      changing the settings for this browser tab              (exists)
        chat.py               the chat so far and the one input                       (exists)
        preview.py            the table of what will be recorded, and its buttons     (exists)
        export_panel.py       Export, the warning always beside it, and its outcome   (exists)
        screenshot_panel.py   the upload box, the text read and the note, Continue, Drop (exists)
        turns.py              a message, an upload or a click handed to the flows     (exists)
        sayings.py            what the program says, read off the progress            (exists)
        failure_words.py      one plain sentence for every kind of failure            (exists)
        setting_text.py       a setting's value as it would be typed; the key as set or not (exists)
        notes.py              the last word after Export or on the settings page, shown (exists)
        session.py            what lasts between reruns: parts, progress, chat, a reading (exists)
        assistant_page.py     the Assistant page: which ledger, the chat, the cards, a screenshot (exists)
        assistant_view.py     each exchange: the reply, its failures, tables, answer buttons (exists)
        assistant_tables.py   the tables laid out from a result, cell by cell          (exists)
        assistant_how.py      who wrote a reply, what was sent, how it was done        (exists)
        assistant_cards.py    a card for each proposal sent; the demo buttons          (exists)
        assistant_turns.py    a message, a button or an upload handed to the flows     (exists)
        assistant_numbers.py  how the Assistant page writes a number                   (exists)
        assistant_failure_words.py  one plain sentence for every failure on the Assistant page (exists)
        assistant_session.py  what the Assistant page keeps between reruns             (exists)
        assistant_record_words.py  what the pages say about the assistant's record     (exists)
        record_panel.py       the Settings page's part on the assistant's record; clearing it (exists)
evals/                    prompt experiments: test sentences, scoring, runner, results (exists)
    sets/                 the test sentences with gold answers: debug, final, writings, voice, tools, asks, asks_times, edits, stocks (exists)
    gold.py               the shapes of a sentence and its gold answer             (exists)
    coverage.py           what the sentences cover                                 (exists)
    writings.py           the writings set: hard ways of writing a number          (exists)
    voice.py              the voice set: passages in the owner's own voice         (exists)
    cells.py              one field judged against the gold answer                 (exists)
    matching.py           drafts paired with gold trades, in any order             (exists)
    scoring.py            the scores of one sentence and of many                   (exists)
    records.py            the results file, line by line                           (exists)
    tables.py             the summary of a run and its tables                      (exists)
    run.py                the runner                                               (exists)
    summarize.py          the summary worked out again from a results file         (exists)
    extra_counts.py       three more counts beside the summary                     (exists)
    compare.py            prompt versions side by side; the rule that picks one    (exists)
    same_replies.py       two runs compared sentence by sentence                   (exists)
    methods.py            the two ways of reading a passage: one list, split first (exists)
    reads.py              every reply read for a passage, matched to its drafts    (exists)
    compare_methods.py    the two ways side by side; the rule that picks one       (exists)
    compare_models.py     two models side by side on one set                       (exists)
    compare_sets.py       prompt versions side by side on each set; the rule for a candidate (exists)
    results/              one results file per run, with its summary               (exists)
    tool_set.py           the assistant's sentences; the measure of its first step (exists)
    tool_run.py           the runner of that measure                               (exists)
    ask_set.py            the questions about the ledger; one answer judged against the gold (exists)
    ask_run.py            the runner of that measure, each question to the end    (exists)
    edit_set.py           the sentences that change or delete a trade; one judged against the gold (exists)
    edit_run.py           the runner of that measure, answering the program's question with the gold's words (exists)
    stock_set.py          the sentences recording a share bought with dollars; judged by code (exists)
    stock_run.py          the runner of that measure, each sentence said once     (exists)
    judged_run.py         the extraction sets (and the voice set) through the start of recording, judging and all; tidied first on request (exists)
    tool_results/         one results file per run of those measures, and the recording runs (exists)
    RESULTS.md            the results record                                       (exists)
tests/                    mirrors src; also holds the guardrails, fakes and golden samples  (exists)
    conftest.py           stops every test but the live ones from reaching the network (exists)
    guardrails/           the layering check, the hygiene scan and their gate tests   (exists)
    core/                 tests of the core rules                                     (exists)
    export/               tests of the backup format; the golden sample               (exists)
    llm/                  tests of both plugs against fake servers; attacks on them   (exists)
    ledger_check/         what the ledger tier checks, and tests of its logic         (exists)
    fakes/                stand-ins for the outside world: scripted models, a book in memory (exists)
    ledger/               tests of the ledger port against every plug                 (exists)
    assistant/            tests of the tools, the judging, the prompt and the results (exists)
    storage/              tests of the storage port against every plug; the golden book (exists)
    live/                 the live check against a real model, run by hand only; the sentences for a demo (exists)
    extraction/           tests of extraction against the scripted model              (exists)
    asking/               tests of wording a question                                 (exists)
    flows/                tests of recording a passage, of the assistant, and of their scripts; the golden record (exists)
    ui/                   the pages run headless against fakes; the plain words; the settings file (exists)
    evals/                tests of the experiment kit and the test sentences          (exists)
```

A **port** is an interface that the inner code talks to ("ask the model",
"save a trade"). A **plug** is one implementation of a port (a local model
server, a SQLite file). There are exactly three ports: model, storage and
ledger.

## Who may import whom

| Part | May import | May not import |
| --- | --- | --- |
| `core/` | the standard-library modules on the core allow-list (below); `core/` itself | everything else |
| `ports.py` | `core/`; standard-library modules of the annotation kind (below) | third-party libraries; every other part |
| `extraction/`, `asking/`, `export/` | `core/`, `ports.py` | `llm/`, `storage/`, `settings.py`, `flows/`, `ui/` |
| `llm/`, `storage/` (the plugs) | `core/`, `ports.py`, `settings.py` | `extraction/`, `export/`, `flows/`, `ui/`, each other |
| `ledger/` (the ledger's plugs) | `core/`, `ports.py` | everything else |
| `assistant/` | `core/`, `ports.py`, `extraction/` (to judge a copied phrase) | everything else |
| `settings.py` | the standard library | every other part of the package |
| `flows/` | everything except `ui/` and the wiring module | `ui/`, the wiring module |
| the wiring module `wiring.py` | everything except `ui/` | `ui/` |
| `ui/` | everything | nothing is closed to it |
| outside the package: `scripts/`, `evals/`, `tests/` | anything in the package | the package never imports them back |

How the check reads this table:

- A part may always import itself.
- The list for `flows/` is written out part by part in the check, so a part
  added later is closed to the flows until it is added to that list.
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
| `tzlocal` | the wiring module, `wiring.py`, alone; scripts outside the package may import it too. |

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

### The wiring module and `ui/`

The wiring module, `wiring.py` at the top of the package, builds the parts
the flows are handed: the model plug from the model settings, the book from
the data settings, the asset table, a function that reads the clock, and the
machine's zone, read with tzlocal. With the local plug it also builds the
two parts a screenshot needs: the vision model (`connect_vision_model`,
from the same settings) and a way to ask the model server whether it has
that model (`llm/ollama_identity.py`'s `ask_identity`, with the vision
model's name); with the cloud plug, which sends no pictures, neither.
Building opens and sends nothing; the server is asked about the vision
model only when a screenshot comes. It is
the one place in the package that reads the machine's zone, and it may read
the clock, as its job is to hand both to the flows. Only `ui/` may import
it; the flows never do, since it imports them.

`ui/` is three Streamlit pages, Record, Settings and Assistant. It makes no business
decision: what to ask, whether a passage is settled, whether it can be
saved, which trade can be left out and which cannot be recorded all come
from the flow's `Progress`; whether an export can be written, and what
became of it, from the export flow; which fees the ledger leaves out of the
cost from the core (`core/fee_cost.py`). The Record page also takes a
screenshot: whether an uploaded file can be read (the plug, the size, a PNG
or a JPEG by its first bytes, the vision model on the server), and what was
read or why not, come from `flows/uploading.py`; the text read waits in a
box the person checks and changes before Continue starts the passage with
`flows/screenshot.py`. The pages lay them out and hand the person's words,
files and clicks to the flows. Every failure is said in one
plain sentence looked up in `ui/failure_words.py`, one entry for each kind
of each failure, so a new kind cannot go without one.

The settings page shows every model setting, its value, its default and
why, all read from the settings module (`settings.ABOUT`); it changes
them for the browser tab only. The page never reads the environment: it
hands the changes, variable to text, to the wiring module, which reads the
environment first and puts them in with `settings.apply_changes`, the
same reading and checks the environment's values get, then builds every
part again from the result. Nothing is written back to the environment or
to a file, and the key cannot be changed there.
The Assistant page hands what the person types, a button's answer and a
screenshot's text to `flows/conversation.py` (`say`, `say_from_reading`)
and draws what comes back: the reply, who wrote it (`Said.words_by`), the
failures it rests on, the tables laid out from the result's own values,
and what reached the ledger. It never calls the ledger port itself: where
a proposal stands, and the demo ledger's save and reject, go through
`flows/standing.py`, which does nothing with any ledger but the demo one.
Each thing the flows hand back is added to the assistant's record
(`flows/assistant_record.py`) where the data places say
(`DataPlaces.assistant_record`), at the moment handed to the flows; the
page only says when it was not kept, and why. The Settings page shows the
record and clears it through the same module (`ui/record_panel.py`),
drawn only once the parts are built.
Which kind of ledger the parts hold is a named value the wiring module
sets (`LedgerKind`), not something the page guesses. The wiring module
builds the demo ledger and reads how many steps the assistant may take
(`LEDGER_HAND_ASSISTANT_STEPS`); when the settings page builds the parts
again, the demo ledger of the parts kept is carried over, so proposals
sent before a change are still there after it. The two pages that take a
screenshot keep it under keys of their own (`session.Spot`), so one never
sees the other's. Numbers on the Assistant page are written by one
function (`ui/assistant_numbers.py`), in full, with thousands marks; the
Record page keeps the ledger's way.

It is the only part that keeps anything between reruns (Streamlit's
`session_state`), and it imports nothing third-party but Streamlit itself,
not what Streamlit brings along (pandas, numpy and the like). Two gates
check the real package straight from its source, without the table:
`tests/guardrails/test_repo_wiring_boundaries.py` (only the wiring module
imports tzlocal; only `ui/` imports the wiring module; the flows import
neither it nor `ui/`) and `tests/guardrails/test_repo_interface_boundaries.py`
(only `ui/` imports Streamlit; `ui/` imports no other third-party module;
`session_state` is named nowhere else).

### What `asking/` and `flows/` may not do

`asking/` is handed the facts of a question and reads neither the clock nor
the machine's zone; the layering check reports in it the same reads as in
`extraction/`. `flows/` is handed the current moment and the zone by whoever
starts it (a script, or the interface through the wiring module) and passes
them on; it never reads them itself. The identifiers it gives saved trades are random UUIDs
(version 4), never ones made from the clock. A gate,
`tests/guardrails/test_repo_clock_free_parts.py`,
checks the real source of both straight, without the table: neither imports
the `time` module, calls a method that reads the clock or the machine's zone,
or names an environment variable, and `asking/` imports only the standard
library, the core and the ports file.

The layering check's rules about the clock and the machine's zone cover
`core/`, `extraction/`, `asking/`, `flows/`, `ledger/` and `assistant/`: in `flows/` it reports the
same reads as in `extraction/` and `asking/`, those through the `time`
module among them. The gate above is a second guard beside it. Its judging
is one function that its own tests feed every form the layering tests list,
and it sees the forms it once missed: the methods `now`, `utcnow` and
`today` of `datetime` or `date` named without being called, and
`astimezone(None)` or `astimezone(tz=None)`.

## The eleven rules

| # | Rule | Why |
| --- | --- | --- |
| 1 | `core/` holds only pure computation and the shapes of data. It does not touch the network, a database or the user interface, and it never reads the clock itself. | It can be tested with no setup, and it can be carried anywhere, forever. |
| 2 | Outer layers use inner layers, never the reverse: interface, then flows, then core. An automated check enforces it. | Changing the model or the database does not touch the core. |
| 3 | There are only three ports: model, storage and ledger. Everywhere else the code just says "ask the model", "save a trade" or "list the ledger's trades". | This is what keeps the program from bloating: a different storage, a cloud model or the real ledger changes one piece. |
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

The model port in `ports.py` is a `ModelPort` with three methods. `chat`:
messages in (each with a role and its text), optionally a JSON schema the
reply has to follow and a set of `ModelParameters`; a `ModelReply` out (the
text and a `ReplyRecord`). `chat_with_pictures`: the same messages, one or
more `Picture`s (the bytes of a PNG or JPEG file and which of the two it is,
`PictureKind`, refused when the bytes do not start as a file of that kind
does) attached to the last message, which must be the user's, and
optionally the parameters; no reply schema, because what is asked of a
picture is its text as it stands. Without parameters the plug uses the
defaults it was built with from the settings. Every failure is a
`ModelError` whose `kind` is one of six (`ModelErrorKind`):

| Kind | Raised when |
| --- | --- |
| `UNREACHABLE` | The connection cannot be made (refused, or the name does not resolve), or the address is one httpx cannot use. |
| `TIMED_OUT` | Connecting, sending or a wait for the answer passed the time allowed, or the answer was not complete once that time had passed. |
| `MODEL_NOT_FOUND` | Ollama answers 404 with a JSON `error` text that says "not found" and names a model; a cloud service answers 404 with a JSON `error` object whose `code` is `model_not_found`, or whose `message` names a model and says "not found" or "does not exist"; or the model is not in the local server's list when its fingerprint is asked for. A 404 that does not say so (`{"error": "Not Found"}` from something else at the address) is a `SERVER_ERROR`. |
| `RATE_LIMITED` | The server answers 429. The error carries the wait the server's `Retry-After` header asks for (seconds or a date), when it has one, as `retry_after_seconds`. |
| `SERVER_ERROR` | The server answers 500 to 599. Also every failure that fits no other kind, with the raw status, error and start of the answer attached: any other status (among them a key refused with 401 or 403 and a request refused with 400, which the interface says by status), a connection that breaks off mid-answer, broken HTTP. |
| `MALFORMED_REPLY` | Status 200, but the answer is not UTF-8, not JSON, not an object, has no message or no text (for the cloud plug: no choices, or a first choice without them), has blank text or text that is not valid Unicode, is not marked done (the local plug), or is longer than the cap. |

Each kind is recognised by what it positively looks like; what is not
recognised falls to `SERVER_ERROR` (or, for an answer with status 200, to
`MALFORMED_REPLY`), never to an exception of another type. Errors in the
program itself (a call in the wrong shape, a bug) are not model failures and
are not turned into one.

`llm/retry.py` tries a call again after `TIMED_OUT`, `RATE_LIMITED` and
`SERVER_ERROR`, a limited number of times, each wait twice the one before.
A `SERVER_ERROR` whose status is 400 to 499 is not tried again: the server
said the request itself is wrong (a key refused, a field not taken), and
the same request will be wrong again. A `RATE_LIMITED` error that carries
the wait its server asked for is waited for that long instead of the
doubling wait, up to `LONGEST_ASKED_WAIT_SECONDS` (a minute); a longer wait
is not sat through, and the error is raised at once with the wait, so that
the person can be told when to try again. Every wait counts as one retry.
The other three kinds are raised at once: waiting does not mend them, and
on this machine `UNREACHABLE` means the server is not running, which the
person at the keyboard should hear straight away.

There are two plugs. The local plug (`llm/ollama.py`) talks to Ollama's own
chat endpoint; the cloud plug (`llm/cloud.py`) talks to the OpenAI-style
chat endpoint most cloud services offer, `POST <address>/chat/completions`,
with the key as a bearer token and a reply schema as a strict JSON schema in
`response_format`. Both go through `llm/exchange.py`, so the cap on the
answer, the time allowed, no proxy from the environment, no redirect
followed and the key hidden in every error hold for both. Which plug is
used is a setting, `LEDGER_HAND_MODEL_PLUG` (`local` by default, or
`cloud`). `llm/connect.py` builds the plug it chooses, wrapped in the
retries, and checks first that the settings fit a cloud plug: an address of
its own, and off this machine https and a key. That check is made where the
plug is built rather than where the settings are read, so that every
variable is still read on its own; settings that do not fit are a
`SettingsError` naming the variable to set. The experiment tools keep using
the local plug alone (`llm/local.py`), because they ask Ollama for the
model's fingerprint; with the cloud plug set they refuse to start, before
anything is sent, with a `SettingsError` that names `LEDGER_HAND_MODEL_PLUG`.

Pictures are sent by the local plug only. It puts them in the `images`
field of the last message, as the standard base64 of their bytes, and reads
the answer as any other; a model that cannot see pictures is turned down by
Ollama with status 400, a `SERVER_ERROR`. The cloud plug refuses a call with
pictures before anything is sent, as the caller's mistake (`ValueError`,
naming `LEDGER_HAND_MODEL_PLUG`), not as one of the six kinds: none of them
says "this plug sends no pictures", so a caller that reads pictures checks
the plug setting before it asks. `llm/connect.py` builds the plug that
reads a screenshot, `connect_vision_model`: the local plug with the vision
model the settings name (`LEDGER_HAND_MODEL_VISION_NAME`), and a
`SettingsError` naming `LEDGER_HAND_MODEL_PLUG` when the settings choose the
cloud plug.

Whether the model is asked to think before it answers is a setting of the
plug, not a parameter of the call: `LEDGER_HAND_MODEL_THINK`, read when the
plug is built. The local plug sends it as Ollama's top-level `think` field,
true for `on` and false for `off`, with every call, and leaves the field out
for `model`, the default, so that the model does as its own default says.
The cloud plug never sends it. `ModelParameters` stays as it is: the field
has no counterpart in the cloud plug's request, and every parameter is
either sent in Ollama's `options` or is the time allowed.

The third method, `chat_with_tools`, hands the model a list of tools
(`ToolSpec`: a name, what it does, the JSON schema of its arguments) with
the conversation. The conversation may hold, besides messages, the model's
earlier tool-call turns (`ToolCallTurn`) and what the program handed back
for each (`ToolResult`); `Role`, `Message` and `FinishReason` are the same
as for the other two calls, and only this call takes the two new shapes.
The reply is a `ToolReply`: its text, the tool calls it asks for (`ToolCall`:
a name and arguments as plain JSON values), or both, and the record. The
local plug sends the tools in Ollama's `tools` field and reads the calls
from `message.tool_calls`; an answer whose calls cannot be read (a name that
is not text, arguments that are not a JSON object) is a `MALFORMED_REPLY`.
Whether the tool is on the list and its arguments follow its schema is not
the plug's to judge (`assistant/judging.py` does). The cloud plug refuses a
call with tools before sending anything, as it refuses pictures
(`ValueError` naming `LEDGER_HAND_MODEL_PLUG`); the retries treat a call
with tools as any other.

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
| `NEWER_VERSION` | The book was written by a newer version of this program. Nothing is written to it, unless SQLite first rolled back a write cut off part way (see below); the message then says so. |
| `NOT_A_DATABASE` | The file is not a SQLite database at all. Nothing is written to it, unless SQLite first rolled back a write cut off part way; the message then says so. |
| `NOT_THIS_PROGRAMS` | The file is a database without this program's mark, or its tables are not exactly those of its version. Nothing is written to it, unless SQLite first rolled back a write cut off part way; the message then says so. |
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

One exception lets the book be written before it is checked: a write cut
off part way leaves SQLite's journal beside the book, and a connection that
cannot write cannot roll it back (SQLite says `SQLITE_READONLY_ROLLBACK`).
Only then, and only when the first 100 bytes of the file, read straight from
the disk, are SQLite's header with this program's mark and a version from 1
to `BOOK_VERSION`, the file is opened once for writing, so that SQLite rolls
the write back and removes the journal; the program never touches the
journal itself. The file is then checked again from the start, once: empty
again (a new book cut off while it was being made), it becomes a new book.
A file refused on that second look has been written by the rollback, and its
refusal says so. Any other file with a journal beside it is refused, and
neither file is written. The journal itself is not read: whatever journal
lies beside the book under its name is rolled back, even one another book
left (`docs/known-gaps.md`, "The book after a write was cut off").

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

**The assistant's record** is a second local file with a version
number, apart from the book: `assistant-record.jsonl` in the data folder,
one line of JSON for each thing said to the assistant
(`flows/assistant_record.py`). Every entry carries `format_version`, a
named constant (`RECORD_VERSION`, now 3; version 2 gave each trade sent a
line of its own in `sent`, and version 3 added `read_as`, the words tidied
and each change), which is none of the ledger's
four version numbers and not the book's. A file holding an entry of a
newer version, or a line that cannot be read, is never written, cut or
deleted by the program: nothing is added and the pages say why. Only a
last line cut off half-way, with no line end, is passed over and cut off
before the next entry. The file keeps the most recent `KEPT_AT_MOST`
entries; dropping older ones writes a new file beside it that then takes
its name (`os.replace`). The file is plain text with the person's words in
it; it is never in Git. Its golden samples,
`tests/flows/golden/assistant-record-v1.jsonl` (four invented entries),
`tests/flows/golden/assistant-record-v2.jsonl` (three) and
`tests/flows/golden/assistant-record-v3.jsonl` (three), each made by the
code itself at its version, are checked by their digests, copied to a
temporary folder before they are read, and never edited; a test sees that
an entry made now has the same names as the newest golden ones (and those
of the older versions without `read_as`), so a change to what an entry
holds comes with a new version and a new sample. Entries of all three
versions in one file are read alike.

`tests/fakes/memory_store.py` is the port's stand-in for tests: it keeps
everything in memory, does what the port promises the way the SQLite plug
does, passes the same tests of the port, and can be made to fail.

## The ledger port

The ledger port in `ports.py` is a `LedgerPort`: the person's own ledger,
reached by the assistant. Its shapes are declared in
`core/ledger_records.py` and `core/proposals.py` and only named in the
ports file.

| Method | What it does |
| --- | --- |
| `list_assets()` | The ledger's assets: name, code, kind, identifier, whether it can price a trade, and the money it is itself priced in. |
| `list_trades(TradeFilter)` | The trades of a stretch of days (both ends counted, each trade on the day of its own offset), of an asset, on a side, each part optional; oldest first, at most `MOST_TRADES_LISTED` (2000) of the latest, and whether older ones were cut (`TradeList`). Each trade names its money, its fee's asset, its time zone, whether only its day is known, its rate between moneys, and whether it is dated after today; a sell carries its profit or loss and why it is not exact when it is not. |
| `period_summary(PeriodRequest)` | The sums of a stretch of days: one group for each money, with its count of buys and sells, what they paid and brought in (or why that was not added up), its fees, its profit or loss with the part transfers took apart, and one row an asset. Never added across moneys. |
| `positions()` | What is held, one holding for each asset, in the asset's own money; none sold out, and no cash. |
| `propose_add`, `propose_update`, `propose_delete` | Propose to record, change or delete trades, with what the user said this time. Each trade is checked on its own: passed, it waits under a proposal identifier of its own; failed, it has a code and the ledger's sentence. A call may be taken in part. Nothing is written: a proposal waits for the person on the ledger's own page. |
| `proposal_status(id)` | Where a proposal stands (`ProposalState`): pending, saved (with the trade written), rejected or void (with why). |

Every failure is a `LedgerError` with one of seven kinds (`LedgerErrorKind`:
`UNREACHABLE`, `UNKNOWN_ASSET`, `ASSET_IS_CURRENCY`, `NOT_FOUND`,
`TIMED_OUT`, `RESULT_UNKNOWN`, `OTHER`), a fixed code and a sentence. A
trade that fails the ledger's check is not a failure. A proposal that
timed out is never sent again (it may have reached the ledger), and one
the ledger forgot is never said to be unsaved. No trade has a default
money: the money it is priced in and what its fee was taken in are always
named. The shapes follow what the real ledger hands back (68B2,
2026-11-25; the ledger's answers are kept in `tests/ledger/samples/`).

Two plugs:

- `ledger/fake_ledger.py`: an invented book in memory, which reads no
  file, no clock and no network, with its own simple way of working out
  cost and profit (a moving average, which says nothing about the real
  ledger's). It answers the way the real ledger does: one proposal per
  trade, taken in part, days counted on each trade's own clock. It offers
  two things outside the port, for tests, the try-out script and the
  Assistant page's demo buttons (through `flows/standing.py` only):
  saving and rejecting a proposal. `tests/ledger/test_ledger_port.py` runs
  the port's tests against it.
- `ledger/link_ledger.py`: the real ledger, through its assistant link.
  `ledger/link_client.py` starts the ledger's own `assistant-link/main.ts`
  as a child process and speaks JSON-RPC with it; the plug turns the
  port's shapes into the ledger's eight tools and back: assets by their
  internal identifier, days both ends counted, every page of trades read,
  a change sent whole with the time, platform, note and rate kept as last
  listed, the sums of one asset added up here from the money each of its
  trades moved. Two named tables sort every error code of the ledger
  (`CALL_FAILURES`, `TRADE_REFUSALS`); the ledger tier checks them against
  the ledger's README. It reads no environment variable and no clock: the
  model's name and today's date are handed in. `tests/ledger/
  test_link_ledger.py` runs it on the ledger's recorded answers, and
  `scripts/walk_ledger_plug.py` walks it through a real ledger page. The
  Assistant page still reaches the fake ledger; choosing the real one on
  the page is the third part of batch 68.

## The assistant

The assistant turns one thing the user says into work through the tools
(`flows/assisting.py`, `take_turn`). The model is handed the eight tools
(`assistant/tools.py`) and the system prompt (`assistant/prompts/`). Every
argument of a tool is either a choice from a fixed list or the user's own
words copied, never a number or a date the model writes. Each call is judged
before the ledger is asked (`assistant/judging.py`): a tool not on the list,
an argument a tool with arguments does not take, a required one left out, a choice not on
its list, or a copied argument that is not a piece of what the user said
(judged as extraction judges a copy, `extraction/passage.py`) is a wrong
step, not run, and the model is shown why. The asset given to
`list_trades` or `get_period_summary` is taken out before judging and
checked apart, against what the user said (see below). A period that is
not the user's words is a wrong step like any other copy, handed back
with what the user just said, word for word, and asked to be copied in
the user's language. With no period from the model the lookup covers all
time. Arguments given to one of the
four tools that take none (`list_assets`, `get_positions`,
`get_proposal_status`, `propose_trade_add`) are dropped unread instead, and
the step records their names. The program asks the model at
most `LEDGER_HAND_ASSISTANT_STEPS` times a turn (six by default); two wrong
steps in a row stop the turn. The chat handed to the next turn holds every
call and result, so what the user says next can be tied to what was listed;
a call to one of the four tools that take none is kept in it with its
arguments emptied, so that figures the model wrote never reach it again.
The four read tools, where a proposal stands, and changing and deleting
one trade reach the ledger. The assistant runs on the local plug only.

Asking the ledger is the program's as well (`flows/asking.py`). The model
picks a read tool and copies the user's words for the period; the program
turns them into days (`core/time_range.py`), and words it cannot read, that
mean more than one stretch of time, or that lie wholly in the future are
not guessed at: the ledger is not asked, and the program tells the user
which words and why (`Ending.ANSWERED_BY_PROGRAM`). The asset and the side
the model gives are checked against what the user said
(`assistant/narrowing.py`); one the user did not ask for is not used and
not a wrong step, and an asset the user named that the ledger lacks ends in
the program's words too. What the ledger hands back is kept as a `Lookup`
on the call (`assistant/lookups.py`) and laid out by the program as a
header, which names the days, the asset and the side looked up with, and a
table, every figure the ledger's own; money of two kinds is never added
together. The model only writes a sentence or two beside it, and they are
checked first (`assistant/explanation.py`): a number that is not in what
the ledger returned, the table or what the user just said, or, with no
lookup, a figure that looks like an amount, and the program's fixed words
are shown instead, the chat keeping those.

Recording a trade is the program's (`flows/conversation.py`, `say`, the
entry for each thing the user says). What the user says is tidied first
(`core/spoken_text.py`): number words, and a time said in Chinese, are
written in digits, each change checked by the readers of numbers and of
times, and what cannot be checked is left as said. The words tidied are
what the model sees and what the program checks its copies against; the
words as said go to the ledger with each trade (`Progress.raw_text`). When
the model asks to record a trade,
its turn ends there (`Ending.RECORDING`), and what the user said, word for
word, is handed once to the recording flow that the Record page uses
(`flows/recording.py`), with no book: the flow judges it, extracts the
trades and asks what is missing. While its question waits, what the user
says next is the answer, and the model is not asked. Once every trade is
settled, `flows/proposing.py` sends them to the ledger as one proposal,
every figure as the flow gave it and the user's words with each trade; a
trade known only to the day, or naming an asset the ledger does not have,
is left out with its reason. A trade whose quantity was said in a unit
that is not the asset traded ("25U" of ETH) is held back when the flow
starts (`recording.start`, `hold_other_unit`, which only the assistant
turns on), asked nothing about and left out, its reply saying the number
read and the unit; the Record page keeps the number and only reminds.
When a proposal was sent, turned down, or nothing was sent, the reply
also says each reminder of extraction whose kind is on
`record_words.SPOKEN_REMINDERS`, in the Record page's own words
(`flows/reminder_words.py`). The program, not the model, tells the user
the question, that a proposal was sent, or why nothing was
(`flows/record_words.py`), and every thing said carries the program's own
word on what reached the ledger. When the model goes wrong two steps in a
row, the program hands what was said to the recording flow once before it
gives up. The money a proposal is priced in is, for now, the ledger's USDT;
this is the one place the new parts name the extraction's single money.

Changing or deleting one trade is the program's too (`flows/editing.py`).
The model says only which trade (the user's words for the time, the asset
and the side), which part (a choice) and the new value (the user's words);
the call is judged with the asset kept apart, as for the read tools, and
the `trade` argument dropped unread (`assistant/edit_calls.py`), so a time
the model wrote itself is a wrong step; so is a time cut out of a longer
one the user said ("9月" out of "9月13号", `assistant/period_cuts.py`),
which is checked for the read tools too. A taken call ends the model's turn
(`Ending.EDITING`), and every other call of that step is not run: one
change or deletion at a time. The program then finds the trade itself,
every time, with the read tools' own conditions (`asking.find_conditions`):
with no condition at all it looks through nothing and asks which trade;
with none found it says so and what it looked for, and does not look again
more widely; with more than one found it lists them, numbered from 1 in
time order, and asks which (`assistant/picking.py`, `MOST_LISTED`). The new
value is read by the field (`assistant/new_values.py`): numbers by
`core/numbers.py`, a unit beside one only when it names what the field is
in now; a time by `core/timeparse.py`, and only a moment with no caution;
assets from the ledger's own list. A new quantity, price or total that
leaves the three out of step makes the program ask which of the other two
follows; each way is worked out by the recording check's own rules
(`core/validation.py`, `third_amount`). The whole trade is then proposed,
every other part as the ledger holds it, the user's words untouched
(`propose_update`, `propose_delete`); the ledger checks it, and the program
gives its reason when it turns it down. While a question waits
(`flows/conversation.py`, `AssistantChat.editing`), the next words are read
by the program, and the trade is looked up again by the same conditions
before anything is sent, so only the trade found alone, or the one whose
number the user gave, is ever changed. The program's words and tables are
in `assistant/edit_words.py`; what reached the ledger is kept apart from a
recording's (`Said.edit_sent`). When the model goes wrong twice and its
second try is a change, the program goes on from that call alone: a time
or a new value that is not the user's words is said in a fixed sentence,
and nothing is looked for.

## The asset table

Recording a trade keeps asking four things: which asset a word names, which
money a word names, what becomes of an asset nobody has heard of, and which
words may stand after a number as its unit. Every part that asks (the check
of a draft, extraction, reading an answer, the questions, the recording
flow) asks the asset table it is handed (`core/assets.py`), never a fixed
list. A finished record says the money it is priced in (`TradeRecord.quote`).

A word is one of four things as money to a table: exactly one money the
table prices trades in; more than one such money, so not clear which;
money the table does not price trades in; or not money. When a trade's
money is not said or not clear, a table with one money takes it, and a
table with several asks which (`Missing.QUOTE`, the cell `Cell.QUOTE`). An
unseen asset is either confirmed on the spot or refused (`UnknownAssets`),
an enumeration rather than a switch. The extra unit words go to the number
reader only, never to the reading of a currency, so "2 股" is not taken for
a money.

Two tables are handed in today. The Record page, the scripts and the
experiment tools hand in the built-in table, `BUILT_IN_ASSETS`: the
built-in coins, USDT the one money, every word for USDT (USD, "$", "刀",
"美元" among them) naming it, unseen coins confirmed on the spot, no extra
unit words. With it every output is the one the fixed USDT rules gave: the
same questions and reasons in the same words, the same export files and the
same words sent to every model. The reasons added for other tables
(`COIN_IS_PRICING_MONEY`, `QUOTE_CANNOT_PRICE`, `ASSET_NOT_IN_LEDGER`,
`FEE_ASSET_NOT_IN_LEDGER`) and the question which money never come up with
it; a test walks the built-in table through many drafts to hold that.

The assistant hands in the table the ledger's own list of assets makes
(`core/ledger_table.py`, `table_of`), asked for once when recording begins
(`flows/conversation.py`); the proposal at the end of that turn uses the
same list. Its money is every asset of the kind "cash" and every asset the
ledger prices trades in, each going by its code, its name and the
nicknames of `MONEY_NICKNAMES` that point to its code ("刀" to both USDT
and USD); its assets are the ledger's others, each by its code and name and
the built-in coin table's other names for that code; an asset the ledger
lacks is refused; with a share in the ledger, "股" and "shares" are read
after a number. Such a table never speaks the older words that name USDT
(`from_ledger`), and it holds the built-in names of the coins the ledger
lacks apart (`shields`): they are never an asset, so "狗狗币" is said to be
missing from the ledger, not asked about. With it, a price or a total is
asked in the trade's own money (the money is asked first when it is not
clear), a price and a total said in two moneys are not settled for the
user, and money traded as an asset is said to be an exchange, which the
assistant does not record. A ledger that prices trades in no money ends it
before the model is asked anything. Asking the ledger and changing a trade
find assets by the same names (`names_of`), at the time they always did,
and do not use the money's nicknames. The assistant also judges and
extracts with prompt versions of its own (`screen-2`, `first-3`, named in
`flows/conversation.py`), handed to `recording.start`; a caller that names
none gets the first versions, as before.

The proposal (`flows/proposing.py`) prices each trade in the money its
record names, and checks each trade again against the ledger's list before
sending: the asset, the fee's asset and the money must be the ledger's, and
the money one it prices trades in. A trade the flow found cannot be
recorded for one of the ledger's reasons is told with the word the user
said.

The book and the export still keep USDT alone: the book has no column for
the money and gives USDT to a trade read back, and the export writes USDT
into every trade and coin card. Both refuse a trade priced in anything
else, the book as a conflict, the export by naming the trade. The built-in
table never makes one.

## Deliberately left out

Too heavy for a program of this size: wrapper frameworks around language
models, evaluation frameworks as the main harness, database abstraction
layers, data-validation libraries, plug-in systems, dependency-injection
frameworks, containers, multiple packages, coverage thresholds, and a second
formatting tool.

## Where a new feature goes

- **Screenshot input:** in place. The model port has its call with pictures
  (`chat_with_pictures`); reading a screenshot is
  `extraction/picture_reading.py`, with the prompt `extraction/prompts/read.py`;
  the passage from a screenshot is `flows/screenshot.py`, and the checks an
  uploaded file goes through before it is read are `flows/uploading.py`;
  `scripts/try_screenshot.py` tries one by hand, and the Record page takes an
  upload (`ui/screenshot_panel.py`), with the vision model and its check
  built in `wiring.py`. A new check on an uploaded file goes in
  `flows/uploading.py`, as one more `UploadProblem` with its sentence in
  `ui/failure_words.py`.
- **Voice input:** a new folder of its own that turns speech into text; the
  text then takes the existing path.
- **Asking questions about the ledger:** in place (`flows/asking.py`). A
  new wording of a period goes in `core/time_range.py`, with tests that
  name its dates; a new read tool is one more case in `flows/asking.py`,
  one more layout in `assistant/lookups.py`, and what it hands the model in
  `assistant/results.py`.
- **Changing and deleting through the assistant:** in place
  (`flows/editing.py`). A new way it can end is one more `EditEnding`, its
  words in `assistant/edit_words.py`; a new part to change is one more
  field in `assistant/tools.py` and a case in `assistant/new_values.py`; a
  new way of saying which trade is one more rule in `assistant/picking.py`.
- **Tidying what is said:** in place (`core/spoken_text.py`). A new way of
  saying a number, a time or a zone goes in the tidying module, with a row
  in its table of examples (`tests/core/test_spoken_text_examples.py`); a
  new spoken zone is one more row of `SPOKEN_ZONES`. Every change keeps its
  check: what cannot be checked is left as it was said.
- **Recording through the assistant:** in place. A new way it can end is
  one more `RecordEnding`, and a new reason a trade is not sent one more
  `LeftOut` (`flows/recorded.py`), each with its sentence in
  `flows/record_words.py`; the money a proposal is priced in moves from the
  one place in `flows/proposing.py` to the ledger's assets.
- **The real ledger on the page:** the plug is `ledger/link_ledger.py`.
  Give it a value of its own in `flows/standing.py`'s `LedgerKind`, so the
  Assistant page shows it by name and draws no demo button for it.
- **Something more on the Assistant page:** a new table is one more
  function in `ui/assistant_tables.py`, laid out from the result's own
  values; a new failure is one more entry in `ui/assistant_failure_words.py`.
- **Another kind of model server:** one more plug in `llm/`, one more value
  of `Plug` in the settings, and one more branch in `llm/connect.py`.
- **Another model in an experiment:** no change to the code. Pull it into
  Ollama by hand and name it with `--model` (`evals/run.py`); the run
  records its name and fingerprint.
- **A new folder or top-level module:** add its row to the layering table in
  `tests/guardrails/layering.py`, to the expected table in the tests next to
  it, and to the table above.

## Changing the rules

Adding a rule, a check or a test is always welcome. Loosening one is a design
decision for the project owner and never a routine edit. That covers widening
a cell of the import table, switching off a lint rule, raising a threshold,
granting a new run-time dependency, adding another port, and changing or
removing an existing test.

The tests of the layering check write the table out a second time by hand, so
a check that has been loosened without touching them fails.
