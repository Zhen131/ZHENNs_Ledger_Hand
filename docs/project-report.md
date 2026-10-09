# Ledger Hand: project report

This report is for a reader who reads code but has not followed the
project: what problem Ledger Hand solves, how it works, which prompt
techniques it uses and where, how its parameters were chosen, how it
handles errors, what the experiments measured, the design decisions behind
it and what it does not do yet. The last section maps the course's
checklist onto the repository, row by row.

Every number about how well the model reads is copied from
`evals/RESULTS.md`, which names the results file of each run; the section
of that record a number comes from is named beside it. How to install and
run the program is in `README.md`; how the code is divided is in
`docs/architecture.md`.

## 1. The problem

**In short:** writing down a crypto trade for a ledger means filling in
about a dozen exact fields; saying it takes one sentence. Ledger Hand turns the
sentence into checked records, asks about what is missing instead of
guessing, and hands the ledger a file in its own import format.

The project owner records their own spot trades in the Local-First Trading
Ledger, a ledger application that runs on their own machine (a separate
project). For every trade the ledger wants the coin, buy or sell, the
quantity, the price, the total, the fee and the coin it was paid in, the
time with its time zone, the platform and a note. Amounts are exact
decimals, a time may not lie in the future, and the fee must be stated even
when it is zero.

Typed into a form, that is about a dozen fields per trade. Said, it is one
sentence, often in a mix of Chinese and English, often with several trades
in it: "昨天晚上在 OKX 买了 0.3 个 ETH，又卖了 50 个 SOL", or "bought 0.02 BTC
at 94,900 at 9:40, fee 2 USDT, I think it's going up".

What makes this more than a chat: the result goes into a ledger, so it has
to be exact. A price the model made up, "about 95k" taken as 95,000, or a
date one day off changes the cost of a holding without anyone noticing.
The program therefore has to find every trade in a passage, take the facts
the person said and nothing else, turn number and time phrases into exact
values, ask about anything missing or contradictory, and only then write
the file. A language model can be trusted with the first two only if its
work is checked, and not at all with the rest; the design follows that
split (section 2).

Trades are personal financial data, so by default the model runs on the
same machine and nothing typed leaves it (section 7).

## 2. How it works

**In short:** a passage goes through seven steps. The model takes part in
three of them, and there it only judges or copies words; everything that
calculates, checks, decides or writes is the program. *The model only
copies; the program calculates.*

| # | Step | Who | What happens | Where |
| --- | --- | --- | --- | --- |
| 1 | Check the passage | Program | An empty passage, one longer than the 16,384 characters the ledger keeps as original text, or one that is not valid text is never sent. | `src/ledger_hand/extraction/passage_check.py` |
| 2 | Judge the passage | Model, then program | The model says which kinds of thing the passage reports, from one fixed list (a filled spot trade; futures or leverage; one coin swapped for another; an order not filled yet; a plan), quoting the words that show each. The program decides: a passage that reports only kinds the ledger does not record is stopped, with the reasons; one that reports nothing has no trade; otherwise it goes on, and the rest is set aside as a caution. | `src/ledger_hand/extraction/screening.py` |
| 3 | Extract | Model, then program | The model copies the phrases of each trade into a flat table, one row per trade: buy or sell, and every other cell a piece of the passage or empty. The program checks that every phrase really is a piece of the passage (otherwise the field stays empty, with the reason) and turns number and time phrases into exact values by its own rules. | `src/ledger_hand/extraction/extractor.py`, `src/ledger_hand/core/numbers.py`, `src/ledger_hand/core/timeparse.py` |
| 4 | Check each draft | Program | Works out the third of quantity, price and total when two are given; lists what is missing (the fee always, even as zero) and what breaks a rule (a time in the future, an unknown coin to confirm, amounts that disagree, a price not in USDT). | `src/ledger_hand/core/validation.py` |
| 5 | Ask about what is missing | Program; the model words the question and may copy a piece of the answer | The program picks the next question from one fixed order of every problem, one trade and one field at a time. The model words it as a meticulous bookkeeper, behind the program's own label; a sentence that strays is replaced by the program's. The answer is read by rules first; only when they cannot read it does the model copy the one piece that answers, which the program checks and reads by the same rules. | `src/ledger_hand/core/followup.py`, `src/ledger_hand/asking/question_text.py`, `src/ledger_hand/extraction/answer_phrase.py` |
| 6 | Preview and save | Program and person | The interface shows one row per trade, price and total side by side, with an amount the program worked out marked. The person can leave a trade out or drop the passage; only Save writes, into the program's own SQLite file, the book (by default `data/ledger-hand-book.sqlite3`, which Git never sees). A passage saved before is pointed out. | `src/ledger_hand/ui/preview.py`, `src/ledger_hand/flows/saving.py`, `src/ledger_hand/storage/sqlite_store.py` |
| 7 | Export | Program | The saved trades not exported yet are written into a new JSON file in the ledger's backup format, then marked as exported. | `src/ledger_hand/flows/exporting.py`, `src/ledger_hand/export/backup.py` |

Steps 1 to 5 are strung together in `src/ledger_hand/flows/recording.py`.
Each step hands back the whole state as one value that never changes
(`src/ledger_hand/flows/progress.py`): the stage, every trade, the question
waiting, the records, the reminders and the prompt version used for each
step. The interface (`src/ledger_hand/ui/`) and the command-line script
(`scripts/record_trades.py`) only show that state and pass on what the
person types or clicks; neither decides anything itself.

**Why the model only copies.** The baseline run shows the reason
(`evals/RESULTS.md`, "2026-10-05: baseline"): asked to copy the time of an
English passage, the model twice wrote it in Chinese (`yesterday` as
`昨天`). Had the model also turned the phrase into a date, a wrong value
could have gone through unseen. Because it may only copy, the program sees
that `昨天` is not a piece of the passage, leaves the time empty with that
reason, and asks. A mistake of the model costs a question, not a wrong
record. In the same way the model never adds up a total, converts "8万刀",
or decides which day "上周五" is: `src/ledger_hand/core/` does, with rules
that each have tests.

## 3. Prompt techniques

**In short:** four techniques are used: zero-shot, few-shot, chain of
thought and persona. Three of them are in the product: zero-shot to judge a
passage and to read an answer, few-shot to extract, persona to word a
follow-up question. Chain of thought, and the zero-shot and persona
versions of extraction, were tried in experiments only. **The product
extracts with `first` (few-shot) and reads a passage in one call (one
list); in the experiments `first` also did best.**

| Technique | Prompt version | File | Step | In the product | Measured |
| --- | --- | --- | --- | --- | --- |
| Zero-shot | `screen-1` | `src/ledger_hand/extraction/prompts/screen.py` | Judging a passage | Yes | Debug set only (see section 8): the 4 sentences not to record were stopped with the kind they were written as; the 23 with trades all went on; of the 3 with no trade, 2 were judged to hold none and 1 was stopped as a plan (`docs/known-gaps.md`, "Judging a passage has no score on the final set") |
| Zero-shot | `answer-1` | `src/ledger_hand/extraction/prompts/answer.py` | Reading an answer the rules could not read | Yes | Not scored; the piece it copies must be a piece of the answer and is read by the program's rules |
| Zero-shot | `zero_shot` | `src/ledger_hand/extraction/prompts/zero_shot.py` | Extraction | Experiments only | Debug set: 19 / 34 whole trades right |
| Few-shot | `first` | `src/ledger_hand/extraction/prompts/first.py`, examples in `src/ledger_hand/extraction/prompts/first_examples.py` | Extraction | Yes | Debug set: 31 / 34; final set: 22 / 22 |
| Few-shot | `split-1` | `src/ledger_hand/extraction/prompts/split.py` | Splitting a passage into one segment per trade before extraction | Experiments only | With `first`, debug set: 31 / 34, with 2 extra trades |
| Chain of thought | `stepwise` | `src/ledger_hand/extraction/prompts/stepwise.py` | Extraction | Experiments only | Debug set: 25 / 34 |
| Persona | `bookkeeper-1` | `src/ledger_hand/asking/prompts/bookkeeper.py` | Wording a follow-up question | Yes | Not scored; every sentence is checked by the program and replaced when it strays |
| Persona | `persona` | `src/ledger_hand/extraction/prompts/persona.py` | Extraction | Experiments only | Debug set: 29 / 34 |
| (A changed rule) | `price_total` | `src/ledger_hand/extraction/prompts/price_total.py` | Extraction | Experiments only | Debug set: 29 / 34 |

The extraction scores are "whole trades right" from `evals/RESULTS.md`,
section "2026-10-09: prompt experiment one", table "The five versions on
the debug set"; the final set's from "Final exam: final set, prompt
`first`"; `split-1`'s from "2026-10-09: prompt experiment two", "The two ways
on the debug set". Section 6 has the tables.

What each prompt looks like:

- **`first`, few-shot.** What each of the eleven fields of the table is,
  five rules (copy, never rewrite or translate; leave a field empty when the
  passage does not say it; each field one unbroken piece of the passage;
  and so on) and ten invented examples, each a passage and the rows it
  gives. The reply is held to a JSON schema of the table, which is sent
  with the request (`src/ledger_hand/extraction/reply_table.py`).
- **`screen-1` and `answer-1`, zero-shot.** Instructions only. Judging
  needs no example because the program, not the model, decides what
  follows; reading an answer is a small copy task on a short answer.
- **`bookkeeper-1`, persona.** "A meticulous bookkeeper" who asks for one
  thing at a time, given the facts the program settled. The persona sets the
  tone of the question; the program fixes what is asked, writes the label
  that says which trade and field it is about, and replaces any sentence
  that is not one plain question or that brings in a number, a coin or a
  word not among the facts (`src/ledger_hand/asking/question_text.py`).
- **The experiment versions** each differ from `first` in one thing only:
  `zero_shot` has no example; `persona` puts the bookkeeper's role before
  the instructions; `stepwise` asks for a step-by-step analysis, written in a
  field `steps` of its own reply table before the rows; `price_total` adds
  one rule, that an amount said as a total never goes under price. A test
  checks that each is `first` with its one declared change
  (`tests/extraction/test_prompt_versions.py`), and another that no prompt
  holds a test sentence or a clause of one
  (`tests/extraction/test_new_prompts_hold_no_test_sentence.py`).

**Where chain of thought ended up.** When the project was planned, chain of
thought was meant for ambiguous details such as which coin a fee is paid in
or which day "last night" is. In the program these are not the model's to
work out: every time and number is converted by the program's rules, and a
fee coin is copied, not inferred. So chain of thought was tried where the
model does do the work, in extraction. It did worse than `first` there (25 /
34 against 31 / 34 whole trades right) and took longer (177.8 seconds
against 115.9 for the debug set), so the product does not use it.

**What the product uses.** Judging with `screen-1`, extraction with `first`
in one call for the whole passage, questions with `bookkeeper-1`, answers
with `answer-1` (`src/ledger_hand/flows/recording.py` names the four). The
rules fixed before the two experiments picked `first` and one list (section
6), which is what the product already used; its defaults have not been
changed, and any change is the project owner's decision.

Every measured prompt version is a file of its own and is never changed
once measured; a new wording is a new version. The state of every recorded
passage names the version used for each step.

## 4. Parameters

**In short:** judging, extraction and reading an answer run at temperature
0, so the same text gives the same answer; only wording a follow-up
question runs warmer, at 0.7, because the program fixes every fact of the
question and checks the sentence. Every parameter is a setting with a
default and a written reason.

The defaults are named constants in `src/ledger_hand/settings.py`; what
each setting does and why its default is what it is are kept there once,
as data (`ABOUT`). The README's table of settings and the interface's
Settings page show them as written there, and a test checks the README
against them (`tests/test_settings_readme.py`). Every setting but the key
can be changed on the Settings page for the browser tab.

| Parameter | Variable | Default | Why this default (as `ABOUT` gives it) |
| --- | --- | --- | --- |
| Temperature | `LEDGER_HAND_MODEL_TEMPERATURE` | 0 | Extraction has to give the same answer to the same text, so the model always takes its likeliest word. |
| Top p | `LEDGER_HAND_MODEL_TOP_P` | 1 | Keeps every word in play, so the temperature alone says how adventurous the model is; at temperature 0 it changes nothing. |
| Longest reply | `LEDGER_HAND_MODEL_MAX_REPLY_TOKENS` | 1024 tokens | Room for a JSON list of about ten trades. A reply that reaches it is marked as cut off rather than passed on as if it were whole. |
| How much the model reads at once | `LEDGER_HAND_MODEL_CONTEXT_TOKENS` | 16384 tokens | Ollama's own default (2048 or 4096, depending on the version) is too short for a prompt with examples and a schema, and Ollama drops the start of a prompt that does not fit, without an error. Measured with qwen2.5:7b, which reads up to 32768: the first prompt with its examples is about 1,750 tokens, and the longest passage the ledger keeps, 16,384 characters of Chinese, about 11,600 (English text takes fewer). With a full reply that is about 14,400, which leaves some 2,000 to spare; a longer window costs memory. |
| Time allowed | `LEDGER_HAND_MODEL_TIMEOUT_SECONDS` | 120 seconds | Leaves room for loading the model into memory on the first call (a cold start takes seconds to tens of seconds) and then writing a full-length reply. |
| Retries | `LEDGER_HAND_MODEL_RETRIES` | 2 | Three tries in all, for the failures that may pass on their own, without keeping the person waiting for long. |
| Wait before the first retry | `LEDGER_HAND_MODEL_RETRY_WAIT_SECONDS` | 1 second | A second gives a busy server a moment to recover, and with each wait twice the one before, two retries add three seconds at most when the server does not say how long to wait. |
| Temperature for wording a question | `LEDGER_HAND_MODEL_QUESTION_TEMPERATURE` | 0.7 | Wording a follow-up question is the one call where some variety reads more naturally than the same sentence every time. What is asked, and every fact the question may use, are fixed by the program before the model writes, and a sentence that strays is replaced by the program's own, so a higher temperature changes only the wording. Judging a passage, extraction and reading an answer keep LEDGER_HAND_MODEL_TEMPERATURE, 0 by default. |

Two more numbers are fixed in code rather than settings: a reply that
misses its table is asked for again once (`DEFAULT_ASKS_AGAIN` in
`src/ledger_hand/extraction/extractor.py`: "a second chance for a slip,
without making a model that never fits cost many calls"), and a server's
own request to wait (its Retry-After header) is honoured up to a minute
(`LONGEST_ASKED_WAIT_SECONDS` in `src/ledger_hand/llm/retry.py`).

The local plug sends temperature, top p, the longest reply and the context
size as Ollama's `temperature`, `top_p`, `num_predict` and `num_ctx`
(`src/ledger_hand/llm/ollama_request.py`); the cloud plug sends the first
three as `temperature`, `top_p` and `max_tokens`
(`src/ledger_hand/llm/cloud_request.py`); the time allowed is how long this
side waits.

**Two parameters were measured** (`evals/RESULTS.md`, "Parameter
comparisons"), each changing one parameter of one version:

| Run | Whole trades right | What changed |
| --- | --- | --- |
| `first`, temperature 0.0 | 31 / 34 (91.2%) | The main run |
| `first`, temperature 0.7 | 30 / 34 (88.2%) | One trade fewer, one made-up value fewer |
| `stepwise`, longest reply 1,024 tokens | 25 / 34 (73.5%) | The main run; its longest reply was 297 tokens |
| `stepwise`, longest reply 256 tokens | 19 / 34 (55.9%) | The three passages with three trades were cut off, asked again, cut off again, and gave no draft: 9 trades missed |

The first changes little on a set this small, so temperature 0 stays for
the reason in the table above: the same text gives the same answer, and a
run can be repeated. The second shows what the longest reply guards
against, and that 1,024 tokens leave room even for the longest replies
measured.

## 5. Error handling

**In short:** every failure has one named kind, is caught where it
happens, is told to the person in one plain sentence that says what can be
done, and leaves nothing half done: nothing is recorded, saved or marked by
the step that failed. A test walks every kind, so a new kind cannot go
without a sentence.

The model plugs turn every failure into one `ModelError` with one of six
kinds (`src/ledger_hand/ports.py`); the book turns every failure into one
`StorageError` with one of eight. The interface looks each kind up in
`src/ledger_hand/ui/failure_words.py`. No test reaches the network
(`tests/conftest.py`): the plugs are tested against fake servers and fake
transports (`tests/llm/fake_server.py`, `tests/llm/fake_cloud.py`), and the
pages are run headless (`tests/ui/`).

| Failure | Caught where | What the person sees | Tests |
| --- | --- | --- | --- |
| Empty passage (also: too long, not valid text) | `src/ledger_hand/extraction/passage_check.py`, before anything is sent | "Nothing was sent to the model: the passage is empty." A passage too long names the limit, 16,384 characters | `tests/extraction/test_extractor.py`, `tests/flows/test_recording.py`, `tests/ui/test_page_failures.py` |
| The model takes too long | `src/ledger_hand/llm/exchange.py` (kind `timed_out`); tried again by `src/ledger_hand/llm/retry.py` with doubling waits | The time allowed; the first call has to load the model and can be slow; try again or allow more time on the Settings page | `tests/llm/test_exchange.py`, `tests/llm/test_retry_rules.py`, `tests/ui/test_page_failures.py` |
| Rate limited (status 429) | `src/ledger_hand/llm/exchange.py` (kind `rate_limited`, with the wait read by `src/ledger_hand/llm/retry_after.py`); `src/ledger_hand/llm/retry.py` waits as asked, up to a minute, or doubles its waits | The server turned the call away; wait, then try again; when the server said how long, that many seconds | `tests/llm/test_retry_after.py`, `tests/llm/test_retry_rules.py`, `tests/llm/test_cloud_retry.py`, `tests/ui/test_page_cloud.py` |
| No model server answers | `src/ledger_hand/llm/exchange.py` (kind `unreachable`); not tried again | The address asked; whether Ollama is running; where to change the address | `tests/llm/test_exchange.py`, `tests/llm/test_retry.py`, `tests/live/test_live_settings_page.py` |
| The model is not there | `src/ledger_hand/llm/ollama_reply.py`, `src/ledger_hand/llm/cloud_reply.py` (kind `model_not_found`) | The model's name and the address; check the name or install the model | `tests/llm/test_ollama_not_found.py`, `tests/llm/test_cloud_failures.py` |
| Key or request refused (401, 403, 400) | `src/ledger_hand/llm/exchange.py` (kind `server_error` with its status); `src/ledger_hand/llm/retry.py` does not try it again | A sentence of its own for each status | `tests/llm/test_cloud_retry.py`, `tests/ui/test_page_cloud.py` |
| The server fails (500 to 599) | `src/ledger_hand/llm/exchange.py` (kind `server_error`); tried again | Its status code; try again, or look at the server's log | `tests/llm/test_exchange.py`, `tests/ui/test_failure_words.py` |
| An answer not in the agreed form (not JSON, no text, too long) | `src/ledger_hand/llm/reply_json.py`, `src/ledger_hand/llm/ollama_reply.py` (kind `malformed_reply`) | The reply could not be used; try again, or put the passage another way | `tests/llm/test_ollama_reply.py`, `tests/llm/test_attack.py` |
| A reply that is not the table (or cut off at the longest reply) | `src/ledger_hand/extraction/reply_parser.py`; extraction asks again once, saying what was wrong | Said apart from the above: the replies could not be read as the table | `tests/extraction/test_reply_parser.py`, `tests/extraction/test_extractor.py` |
| A phrase that is not in the passage, or a number or time the rules are unsure of | `src/ledger_hand/extraction/passage.py`, `src/ledger_hand/extraction/row_draft.py` | The field stays empty, with the reason, and becomes a follow-up question | `tests/extraction/test_extractor.py`, `tests/extraction/test_attack.py` |
| The model fails while wording a question | `src/ledger_hand/asking/question_text.py` | The program's own sentence, behind the same label | `tests/asking/test_question_text.py` |
| A setting refused | `src/ledger_hand/settings.py` (`SettingsError`, naming the variable and its rule); `src/ledger_hand/wiring.py` | Which setting and its rule; a change on the Settings page changes nothing | `tests/test_settings.py`, `tests/ui/test_page_wiring.py`, `tests/ui/test_page_settings.py` |
| The book fails (newer version, not a database, not this program's, damaged, locked, inaccessible, conflict, unexpected) | `src/ledger_hand/storage/book_file.py`, `src/ledger_hand/storage/failures.py` | What happened and what can be done; a refused file is left as it is, without one byte written | `tests/storage/test_sqlite_store.py`, `tests/flows/test_book_failures.py`, `tests/ui/test_page_failures.py` |
| An export refused | `src/ledger_hand/export/backup.py` lists every issue; `src/ledger_hand/flows/exporting.py` | Every reason, one to a line; nothing is written or marked | `tests/export/test_backup.py`, `tests/flows/test_exporting.py`, `tests/ui/test_page_export.py` |
| An export file not written, or written but not marked | `src/ledger_hand/flows/export_file.py`, `src/ledger_hand/flows/exporting.py` | Why, and that nothing was marked; or where the file is and that the next export writes its trades again | `tests/flows/test_exporting.py`, `tests/ui/test_page_export.py` |

Two more guards: the key is never shown, in any error, however a server
writes it back (`src/ledger_hand/llm/error_text.py`,
`tests/llm/test_key_never_shown.py`); and when the model fails while
judging or extracting, nothing of the passage is kept
(`tests/flows/test_recording.py`).

A rate limit is not expected from the model on this machine, so it is
tested against fake servers only; the cloud plug, which a rate limit would
come from, has never called a real cloud service (section 8).

## 6. Experiments and results

**In short:** a yardstick of 50 invented sentences with gold answers, 30
to tune against and 20 kept back for the last run of an experiment. The
first prompt scored 29 / 34 whole trades right on the debug set; after a
fix in the program, 31 / 34. Four versions, each one technique away from
it, did not beat it, and the rule fixed beforehand picked `first`, which
then got 22 / 22 on the kept-back set. Splitting a passage first tied with
one list on whole trades and lost on extra trades, so one list stayed.

### The yardstick

`evals/sets/debug.json` (30 sentences) and `evals/sets/final.json` (20) hold
50 invented passages, in Chinese, English and both mixed, each with a fixed
"now" and time zone so that a gold time never depends on when it is run.
Each has a gold answer, field by field: the piece of the passage the value
comes from, and the value the draft should hold. 26 debug sentences (34
gold trades) and 16 final ones (22 gold trades) are scored: passages with
one trade, with several, and with none (talk). Four of each set are
passages the ledger does not record (futures, a coin paid with another
coin, an order not filled yet, a plan); they are reported apart and count
in no score. What the sentences cover (the languages, the number of trades,
what is missing, how numbers and times are written, the fee's coin) is
worked out per sentence (`evals/coverage.py`) and checked by tests
(`tests/evals/test_coverage.py`, `tests/evals/test_sets.py`).

The debug set is for tuning. The final set is run only with `--final-exam`,
once, after the prompt is settled, so that the score is not tuned to it. A
third set, `evals/sets/writings.json` (20 sentences, 22 gold trades), holds
the hard ways of writing a number (`3 w`, `100 万`, `94 900`, `0.02 94900`,
`94，900`) and is reported apart.

The scores (`evals/scoring.py`): **well-formed** (the reply could be read as
the table); each field right; **whole trades right**, the main score (all
eleven fields of a trade right, a missed trade counting as wrong); trades
**missed and extra**; values **made up** where the gold answer is empty; and
**no-trade sentences right**. Every field that came out wrong is sorted by
kind: left empty by the program with a reason, left empty by the model, a
wrong value with or without an issue about it, made up.
`evals/RESULTS.md` holds the tables of every run; a test checks that they
are exactly what the results files give (`tests/evals/test_results_record.py`).

### The baseline

`first` with `qwen2.5:7b` on the debug set (`evals/RESULTS.md`,
"2026-10-05: baseline, debug set, prompt `first`, `qwen2.5:7b`"; results
file `evals/results/run-20261005T150537Z-debug-first.jsonl`):

| Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 26 / 26 (100.0%) | 29 / 34 (85.3%) | 13 / 15 (86.7%) | 16 / 19 (84.2%) | 0 | 0 | 2 / 140 (1.4%) | 3 / 3 (100.0%) |

The errors were of four sorts: English times written in Chinese, and one
phrase written in another order (`TON 卖了 200 个` as `200 个 TON`), both
left empty by the program as not a piece of the passage; a full-width
comma between two numbers (`63,000，1.5`) read by the program as a
thousands separator; and a total put under price.

### Experiment one: five prompt versions

Five extraction versions, each one technique away from `first`, on the
debug set, under the same model and parameters (`evals/RESULTS.md`,
"2026-10-09: prompt experiment one", "The five versions on the debug
set"):

| Version | Technique | Whole trades right | One trade | Several trades | Made up | Wrong values with no issue | A total put as the price | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first` | few-shot | 31 / 34 (91.2%) | 13 / 15 (86.7%) | 18 / 19 (94.7%) | 2 / 140 (1.4%) | 2 | 2 | 115.9 |
| `zero_shot` | zero-shot | 19 / 34 (55.9%) | 8 / 15 (53.3%) | 11 / 19 (57.9%) | 5 / 140 (3.6%) | 5 | 0 | 116.2 |
| `persona` | persona | 29 / 34 (85.3%) | 12 / 15 (80.0%) | 17 / 19 (89.5%) | 3 / 140 (2.1%) | 3 | 2 | 119.3 |
| `stepwise` | chain of thought | 25 / 34 (73.5%) | 10 / 15 (66.7%) | 15 / 19 (78.9%) | 1 / 140 (0.7%) | 0 | 0 | 177.8 |
| `price_total` | content iteration | 29 / 34 (85.3%) | 12 / 15 (80.0%) | 17 / 19 (89.5%) | 0 / 140 (0.0%) | 0 | 0 | 127.6 |

Every version was well-formed on 26 / 26, missed and added no trade, and
was right on 3 / 3 no-trade sentences. The results files are
`evals/results/run-20261009T023225Z-debug-first.jsonl`,
`evals/results/run-20261009T023459Z-debug-zero_shot.jsonl`,
`evals/results/run-20261009T023708Z-debug-persona.jsonl`,
`evals/results/run-20261009T023913Z-debug-stepwise.jsonl` and
`evals/results/run-20261009T024223Z-debug-price_total.jsonl`.

The rule, written down before any version was run (`evals/compare.py`):
the most whole trades right; then the fewest wrong values with no issue;
then the fewest trades missed and extra; then the first in the order
`first`, `price_total`, `persona`, `zero_shot`, `stepwise`, so that a new
version is picked only when it does strictly better than `first`. **Picked:
`first`, at step 1.**

On the writings set (`evals/RESULTS.md`, "The writings set") the whole
trades right were `first` 15 / 22 (68.2%), `zero_shot` 14 / 22 (63.6%),
`persona` 15 / 22 (68.2%), `stepwise` 12 / 22 (54.5%), `price_total` 15 / 22
(68.2%). In these 100 sentence runs the model never copied only part of a
hard number (`3` of `3 w`, `900` of `94 900`); most trades not whole there
were English times written in Chinese.

**The final set** was then run once, with `first` (`evals/RESULTS.md`,
"Final exam: final set, prompt `first`"; results file
`evals/results/run-20261009T030436Z-final-first.jsonl`):

| Well-formed | Whole trades right | One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 16 / 16 (100.0%) | 22 / 22 (100.0%) | 9 / 9 (100.0%) | 13 / 13 (100.0%) | 0 | 0 | 0 / 89 (0.0%) | 2 / 2 (100.0%) |

The 20 sentences took 79.7 seconds, one call each.

### Experiment two: one list or split first

The second experiment kept `first` and changed how a passage with several
trades is read (`evals/RESULTS.md`, "2026-10-09: prompt experiment two",
"The two ways on the debug set"). **One list** sends the whole passage in
one call. **Split first** (`src/ledger_hand/extraction/splitting.py`) first
asks the model, with `split-1`, to copy out the pieces of the passage each
trade needs, builds one segment per trade from the passage's own text,
extracts each segment on its own, and reads all the rows once more against
the whole passage; when the split lists fewer than two trades, or goes
wrong, the passage is read in one call.

| Way | Well-formed | Whole trades right | One trade | Two trades | Three or more | Missed | Extra | Made up | Calls | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| one list | 26 / 26 (100.0%) | 31 / 34 (91.2%) | 13 / 15 (86.7%) | 10 / 10 (100.0%) | 8 / 9 (88.9%) | 0 | 0 | 2 / 140 (1.4%) | 30 | 115.8 |
| split first | 26 / 26 (100.0%) | 31 / 34 (91.2%) | 13 / 15 (86.7%) | 10 / 10 (100.0%) | 8 / 9 (88.9%) | 0 | 2 | 2 / 140 (1.4%) | 64 | 182.8 |

Results files: `evals/results/run-20261009T055241Z-debug-first.jsonl` and
`evals/results/run-20261009T055442Z-debug-first-split_first.jsonl`. The
rule, fixed before the two runs (`evals/compare_methods.py`), is the same
as above with one list last, so splitting is picked only when it does
strictly better. **Picked: one list, at step 3** (fewest trades missed and
extra). Of the 8 passages with several trades, the split cut 3 into
segments; in 4 a piece the model copied was not a piece of the passage, so
they were read in one call; in 1 it listed one trade.

The final set was not run again: with one list, the prompt, the way of
reading and the model (same fingerprint, temperature 0) are those of the
first experiment's final run, so that run stands for this one too
(`evals/RESULTS.md`, "The final set").

**A second model: not obtained.** The machine the experiments ran on has
one model, `qwen2.5:7b`, and no other has been chosen yet. The runner takes
another by name (`--model`), records its name and fingerprint, and stops
before writing anything when the server does not have it
(`tests/evals/test_run_second_model.py`, `tests/live/test_live_second_model.py`).

### The iteration trace

Every measured version is kept as its own file under
`src/ledger_hand/extraction/prompts/`, and every run as its own results
file under `evals/results/`, with the commit, the prompt files'
fingerprints, the model's fingerprint and every parameter in its first
line.

| Step | What changed | What it showed |
| --- | --- | --- |
| 1 | `first` written: field descriptions, rules, ten invented examples. While trying it by hand, before any measurement, a rule was added: never translate, copy times in the passage's own words (commit `dd83094`) | The baseline: 29 / 34 |
| 2 | Not the prompt: the program's reading of a full-width comma between two numbers was fixed | The same 30 raw replies; d23 went from 0 to 2 whole trades, so `first` became 31 / 34 (`evals/RESULTS.md`, "`first` against the baseline, sentence by sentence") |
| 3 | `zero_shot`: the ten examples taken out | 19 / 34: the examples carry most of the work; without them 9 times and 1 fee were left out with no issue, and 5 values were made up |
| 4 | `persona`: a bookkeeper's role before the instructions | 29 / 34: no gain |
| 5 | `stepwise`: a written step-by-step analysis before the rows | 25 / 34 and slower: no wrong value with no issue, but sides and times left out |
| 6 | `price_total`: one rule against a total put as the price, the error the baseline found | 29 / 34: the error and every made-up value gone, two other trades lost |
| 7 | Temperature 0.7, and a longest reply of 256 tokens | 30 / 34 and 19 / 34 (section 4) |
| 8 | Final set, `first`, once | 22 / 22 |
| 9 | `split-1`: split a passage first, then extract each segment | Tied on whole trades, 2 extra trades, about twice the calls |

`answer-1`, the prompt that copies a piece of an answer, was reworded once
after a trial by hand, before anything measured it (commit `b345470`).

One caveat on step 7: `stepwise` asks again with `first`'s words, which ask
for `{"trades": [...]}`, while its own table puts `steps` first. In the
main run nothing was asked again; with 256 tokens the three cut-off passages
were.

## 7. Design decisions

**In short:** the model is a replaceable part behind a narrow port, kept
away from anything it could get wrong silently; the rules of the ledger
live in pure code with tests; nothing is written without the person's
confirmation, and every file written carries its version.

| Decision | Why | Where |
| --- | --- | --- |
| A model on this machine by default, a cloud service one setting away | Trades are personal financial data: by default nothing typed leaves the machine, nothing is paid and no key is needed. Setting an address or a key never switches to a cloud service; only `LEDGER_HAND_MODEL_PLUG` does, and off this machine it insists on https and a key. | `src/ledger_hand/settings.py`, `src/ledger_hand/llm/connect.py` |
| Two ports and no more: the model and the storage | The rest of the program only says "ask the model" or "save a trade". A plug (Ollama, a cloud service, SQLite, a stand-in for tests) is replaced without touching the rest, and a third port would be a design decision, not an edit. | `src/ledger_hand/ports.py`, `src/ledger_hand/llm/`, `src/ledger_hand/storage/`, `tests/fakes/` |
| The model only copies; the program converts and checks | A model miscalculates and invents (section 2). Its reply is untrusted input: every phrase must be found in the passage, every number and time is converted by tested rules, and the reply is held to a JSON schema and still read against it. | `src/ledger_hand/core/`, `src/ledger_hand/extraction/` |
| Ask, never guess; preview before saving | A guessed value is a silent error in a ledger. A missing fee, an unknown coin or amounts that disagree become questions; only Save writes; a trade can be left out after seeing it, and price and total sit side by side so a total put as the price shows. | `src/ledger_hand/core/followup.py`, `src/ledger_hand/ui/preview.py` |
| Incremental export, named so, with a warning | The ledger's present import replaces the whole ledger, so a file of a few new trades must never be taken for a full backup: its name carries `incremental`, and a red line beside Export says not to import it yet. A file is written whole under a temporary name and never replaces another; trades are marked only after it is written. | `src/ledger_hand/export/file_name.py`, `src/ledger_hand/ui/export_panel.py`, `src/ledger_hand/flows/export_file.py` |
| The book carries its version and a mark | A file ten years old must still be read. The version and the mark are read before anything else; a newer or foreign file is refused without one byte written; numbered upgrade scripts are never changed once committed, and each version has a golden sample. | `src/ledger_hand/storage/book_file.py`, `src/ledger_hand/storage/upgrades/`, `tests/storage/golden/` |
| The core touches nothing outside | The rules (a trade, numbers, times, the check of a draft) use only a short list of standard-library modules, read no clock and no machine time zone, and use no floating-point numbers. They can be tested with no setup and moved anywhere; the layering check enforces this on every run. | `src/ledger_hand/core/`, `tests/guardrails/layering.py` |
| No wrapper framework around the model (such as LangChain) | The request, its parameters and its failures are what this project is about, and a wrapper would hide them. The calls are a thin layer over `httpx`; the run-time dependencies are three (httpx, Streamlit, tzlocal). Also left out: data-validation libraries, database abstraction layers, evaluation frameworks. | `src/ledger_hand/llm/exchange.py`, `pyproject.toml`, `docs/architecture.md` |
| Rules fixed before measuring | A rule chosen after seeing the numbers picks the numbers. Both experiments wrote their rule down before running, and the final set is run once, at the end. | `evals/compare.py`, `evals/compare_methods.py` |
| One plain sentence for every failure | The interface never shows a raw error; every kind has a sentence, and a test walks every kind. | `src/ledger_hand/ui/failure_words.py`, `tests/ui/test_failure_words.py` |

## 8. Known limitations

**In short:** the measurements are small and use one model; the step that
judges a passage has no score on unseen sentences; screenshot input is not
built; and a handful of rough edges are known and listed, each with why it
stands.

| Limitation | Why it stands |
| --- | --- |
| A second model was not compared | Only `qwen2.5:7b` is installed on the machine it was built on, and no second model has been chosen; the runner is ready for one (section 6). |
| The samples are small | 30 debug, 20 final and 20 writings sentences, one model, one run each at temperature 0: a difference of one or two trades between versions is one or two sentences, so close results say little. |
| Judging a passage was tuned on the debug set only, and has no score on the final set | The final set is kept for extraction's last run, so how often judging stops a real trade, or lets through what is not recorded, on new passages is not measured (`docs/known-gaps.md`). |
| Judging can stop a real trade | When the model takes a filled trade for a plan or an order, the passage is stopped; there is no "record it anyway", which is a decision for the project owner (`docs/known-gaps.md`). |
| Screenshot input is not built | It is planned for a later stage; where it would go is in `docs/architecture.md`. So nothing multimodal is in this version. |
| An English time is often written in Chinese by the model | The most common reason a trade is not whole in the experiments. The program catches it (the phrase is not a piece of the passage) and asks, so it costs a question, not a wrong record; no prompt version mended it. |
| A total put as the price can reach the records | `first` did so twice on the debug set, with no issue about the field (`evals/RESULTS.md`). The table shows price and total side by side and a trade can be left out; `price_total` removed it but lost two other trades, so the rule did not pick it. |
| An "about" not right next to a number may be dropped | When the model copies a piece of an answer it may leave out a word such as "大概" that does not touch the number, and the program then takes the amount as exact. Seen in trials by hand, not measured. |
| Time zone databases of different versions | The ledger and this program each use their own copy; where they differ, the ledger refuses a timed trade this program exports. Closing it needs a decision (`docs/known-gaps.md`). |
| The book after a crash in the middle of a write | SQLite leaves a journal file, which its read-only first look cannot roll back, so the book is refused as inaccessible until it is opened for writing once; no data is lost (`docs/known-gaps.md`). Opening for writing would bend the rule that a refused file is never written to; the choice is the project owner's. |
| A change of the time zone database can make the whole book unreadable | A timed trade whose kept offset no longer matches its zone makes the book report itself damaged, so nothing can be listed or exported (`docs/known-gaps.md`). Marking only those trades is a change still to be decided. |
| Export needs a file system with hard links | The file is given its name with a hard link so that it never replaces another; where links are not supported, every export is "not written" (nothing is marked). |
| The cloud plug has never called a real cloud service | No key is used and nothing is paid. Its requests are tested against fake answers and once against the local Ollama's OpenAI-style endpoint (`tests/live/test_live_cloud_plug.py`). |
| The experiment tools always use the local plug | They ask Ollama for the model's fingerprint, so with cloud settings left in the shell they knock on the cloud address with Ollama's paths; the README says to unset them first. Refusing outright is a change still to be made. |
| "Model not found" names `ollama pull` for the cloud plug too | The sentence is shared by both plugs; saying it per plug is a change still to be made. |
| A model failure while reading an answer is told with its kind's code word | The question is asked again and nothing breaks, but the sentence ends with, say, `(timed_out)` rather than a plain sentence; the kind is not yet kept in the flow's state for the interface to look up. |
| A model setting refused in the environment cannot be corrected on the Settings page | The page opens and names the setting and its rule; the environment has to be corrected and the program started again. |
| The flows are not yet in the layering check's clock-free list | Adding them means changing two older tests that use a flows path as their example of a part the rule spares, which waits for the project owner. Meanwhile a gate test checks the real `src/ledger_hand/flows/` source for reads of the clock and of the machine's zone (`tests/guardrails/test_repo_clock_free_parts.py`); it misses three rare forms the layering check would see, none of which the code uses. |

## 9. Requirements map

The course's checklist for the top grade, row by row, then its three marks
of extra effort. Each row names where the requirement is met: a file, a
section of the README or of this report, a test.

| Requirement | Where | Status |
| --- | --- | --- |
| A working application with a frontend | Streamlit interface, two pages (Record, Settings): [`src/ledger_hand/ui/app.py`](../src/ledger_hand/ui/app.py); how to start it: README, "Starting the interface"; run headless in tests: [`tests/ui/`](../tests/ui/); against the real model: [`tests/live/test_live_page.py`](../tests/live/test_live_page.py) | Done |
| API usage | The model's HTTP chat API, called with httpx: local Ollama [`src/ledger_hand/llm/ollama.py`](../src/ledger_hand/llm/ollama.py) (the default), OpenAI-style cloud endpoint [`src/ledger_hand/llm/cloud.py`](../src/ledger_hand/llm/cloud.py); behind the port in [`src/ledger_hand/ports.py`](../src/ledger_hand/ports.py); one real call checked in [`tests/live/test_live_model.py`](../tests/live/test_live_model.py) | Done |
| Solves a real-world problem | Recording one's own trades in a ledger from plain sentences: section 1; README, "What this is" | Done |
| Substantive processing, not just question and answer | Seven steps, three with the model: section 2; [`src/ledger_hand/flows/recording.py`](../src/ledger_hand/flows/recording.py) | Done |
| Parameterization, and why | Every parameter a setting with a default and its reason: [`src/ledger_hand/settings.py`](../src/ledger_hand/settings.py) (`ABOUT`); the Settings page [`src/ledger_hand/ui/settings_page.py`](../src/ledger_hand/ui/settings_page.py); README, "Model settings"; section 4; two parameter comparisons in [`evals/RESULTS.md`](../evals/RESULTS.md) | Done |
| At least two prompt techniques | In the product: zero-shot [`src/ledger_hand/extraction/prompts/screen.py`](../src/ledger_hand/extraction/prompts/screen.py) and [`src/ledger_hand/extraction/prompts/answer.py`](../src/ledger_hand/extraction/prompts/answer.py), few-shot [`src/ledger_hand/extraction/prompts/first.py`](../src/ledger_hand/extraction/prompts/first.py), persona [`src/ledger_hand/asking/prompts/bookkeeper.py`](../src/ledger_hand/asking/prompts/bookkeeper.py). In experiments only: chain of thought [`src/ledger_hand/extraction/prompts/stepwise.py`](../src/ledger_hand/extraction/prompts/stepwise.py), zero-shot [`src/ledger_hand/extraction/prompts/zero_shot.py`](../src/ledger_hand/extraction/prompts/zero_shot.py) and persona [`src/ledger_hand/extraction/prompts/persona.py`](../src/ledger_hand/extraction/prompts/persona.py) for extraction. Section 3 | Done: four techniques, three of them in the product |
| Error handling: API timeout, empty input, rate limit | Timeout: [`src/ledger_hand/llm/exchange.py`](../src/ledger_hand/llm/exchange.py), [`tests/llm/test_exchange.py`](../tests/llm/test_exchange.py). Empty input: [`src/ledger_hand/extraction/passage_check.py`](../src/ledger_hand/extraction/passage_check.py), [`tests/ui/test_page_failures.py`](../tests/ui/test_page_failures.py). Rate limit: [`src/ledger_hand/llm/retry_after.py`](../src/ledger_hand/llm/retry_after.py), [`src/ledger_hand/llm/retry.py`](../src/ledger_hand/llm/retry.py), [`tests/llm/test_cloud_retry.py`](../tests/llm/test_cloud_retry.py). Every failure in one plain sentence: [`src/ledger_hand/ui/failure_words.py`](../src/ledger_hand/ui/failure_words.py). Section 5 | Done; a rate limit is tested against a fake server only (section 8) |
| Documentation | [`README.md`](../README.md), this report, [`docs/architecture.md`](architecture.md), [`docs/known-gaps.md`](known-gaps.md), [`evals/RESULTS.md`](../evals/RESULTS.md) | Done |
| GitHub repository | This repository with its Git history; it has a GitHub remote, and publishing to it is done by the project owner | Done |
| Prompt experiments, with the trace of iteration | Every run's results file in [`evals/results/`](../evals/results/), the record in [`evals/RESULTS.md`](../evals/RESULTS.md), every measured version kept as its own file in [`src/ledger_hand/extraction/prompts/`](../src/ledger_hand/extraction/prompts/), the rules in [`evals/compare.py`](../evals/compare.py) and [`evals/compare_methods.py`](../evals/compare_methods.py); section 6 | Done |
| Extra: a custom database | The book, a versioned SQLite file with numbered upgrade scripts and a golden sample: [`src/ledger_hand/storage/sqlite_store.py`](../src/ledger_hand/storage/sqlite_store.py), [`src/ledger_hand/storage/upgrades/`](../src/ledger_hand/storage/upgrades/), [`tests/storage/golden/`](../tests/storage/golden/) | Done |
| Extra: combining multiple models | Not done: no second model has been compared, because only one is installed and none has been chosen. The runner takes one by name: [`evals/run.py`](../evals/run.py), [`tests/evals/test_run_second_model.py`](../tests/evals/test_run_second_model.py) | Not done |
| Extra: multimodal | Not done: screenshot input is planned for a later stage; where it would go: [`docs/architecture.md`](architecture.md), "Where a new feature goes" | Not done |
