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

**From a screenshot.** A passage that starts from a screenshot of an order
has one more step, before step 1: the model that can see pictures
(`qwen3-vl:8b` by default) reads the order on the screenshot out as text,
each value with the label the screen gives it, as it stands (the zero-shot
prompt `read-1`, `src/ledger_hand/extraction/prompts/read.py`;
`src/ledger_hand/extraction/picture_reading.py`). A reading cut off at the
longest reply is not passed on. The note the person types beside the
screenshot is put after the text read, and the two are one passage, which
then goes through the same seven steps, extracted by the default model
(`src/ledger_hand/flows/screenshot.py`). What the model reads off the
picture cannot be checked against it the way a copied phrase is checked
against a typed passage (section 8). This path runs on the Record page,
where an uploaded file is checked first, step by step (the plug, the size, a
PNG or a JPEG by its first bytes, the vision model on the server;
`src/ledger_hand/flows/uploading.py`), and the person sees the text read,
can change it, and adds the note before Continue
(`src/ledger_hand/ui/screenshot_panel.py`); and at the command line
(`scripts/try_screenshot.py`).

Steps 1 to 5 are strung together in `src/ledger_hand/flows/recording.py`.
Each step hands back the whole state as one value that never changes
(`src/ledger_hand/flows/progress.py`): the stage, every trade, the question
waiting, the records, the reminders and the prompt version used for each
step. The interface (`src/ledger_hand/ui/`) and the command-line script
(`scripts/record_trades.py`) only show that state and pass on what the
person types or clicks; neither decides anything itself. A screenshot
uploaded in the interface is first read out as text, which the person sees
and can change, and then takes the same path as a typed passage.

**The assistant.** A third page, Assistant, and the script
`scripts/try_assistant.py` keep the ledger by talking. The model is handed
eight tools (list the assets, list the trades, sum a stretch of time, the
holdings, propose to record, change or delete trades, and where a
proposal stands) and picks one; every argument is a choice from a list or
the user's own words copied, and the program judges each call before it
runs it (`src/ledger_hand/flows/assisting.py`,
`src/ledger_hand/assistant/judging.py`). Before anything else, the program
tidies what is said: number words and a time said in Chinese are written
in digits, each change checked by its own readers of numbers and times,
and what cannot be checked is left as said
(`src/ledger_hand/core/spoken_text.py`); the model sees the words tidied,
the ledger keeps the words as said. Recording goes through steps 1 to 5
above; a question is answered with a table the
program lays out from what the ledger returned; a change or a deletion is
found by the program, never picked by the model. Nothing is written: each
proposal waits in the ledger to be confirmed there. A new tab reaches a
demo ledger, an invented book in memory
(`src/ledger_hand/ledger/fake_ledger.py`), which every measure below uses;
a block at the top of the page switches it to the person's own ledger
page, reached through the ledger's assistant link
(`src/ledger_hand/ledger/link_ledger.py`, `src/ledger_hand/ledger/link_keeper.py`;
`src/ledger_hand/ui/assistant_link_panel.py`): the person starts the link,
connects the ledger page with the port and token it shows, and saves each
proposal on the ledger page itself (section 8).

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
passage, to read an answer and to read a screenshot, few-shot to extract, persona to word a
follow-up question. Chain of thought, and the zero-shot and persona
versions of extraction, were tried in experiments only. **The product
extracts with `first` (few-shot) and reads a passage in one call (one
list); in the experiments the rules fixed beforehand picked one other
version, `fourth`, which did not pass the final set, and no other way.**

| Technique | Prompt version | File | Step | In the product | Measured |
| --- | --- | --- | --- | --- | --- |
| Zero-shot | `screen-1` | `src/ledger_hand/extraction/prompts/screen.py` | Judging a passage | Yes | Debug set only (see section 8): the 4 sentences not to record were stopped with the kind they were written as; the 23 with trades all went on; of the 3 with no trade, 2 were judged to hold none and 1 was stopped as a plan (`docs/known-gaps.md`, "Judging a passage has no score on the final set") |
| Zero-shot | `answer-1` | `src/ledger_hand/extraction/prompts/answer.py` | Reading an answer the rules could not read | Yes | Not scored; the piece it copies must be a piece of the answer and is read by the program's rules |
| Zero-shot | `read-1` | `src/ledger_hand/extraction/prompts/read.py` | Reading a screenshot out as text, before extraction | Yes, on the Record page and at the command line (`scripts/try_screenshot.py`) | Not measured: no real screenshot has been read with it yet |
| Zero-shot | `zero_shot` | `src/ledger_hand/extraction/prompts/zero_shot.py` | Extraction | Experiments only | Debug set: 19 / 34 whole trades right |
| Few-shot | `first` | `src/ledger_hand/extraction/prompts/first.py`, examples in `src/ledger_hand/extraction/prompts/first_examples.py` | Extraction | Yes | Debug set: 31 / 34; final set: 22 / 22 |
| Few-shot | `split-1` | `src/ledger_hand/extraction/prompts/split.py` | Splitting a passage into one segment per trade before extraction | Experiments only | With `first`, debug set: 31 / 34, with 2 extra trades |
| Chain of thought | `stepwise` | `src/ledger_hand/extraction/prompts/stepwise.py` | Extraction | Experiments only | Debug set: 25 / 34 |
| Persona | `bookkeeper-1` | `src/ledger_hand/asking/prompts/bookkeeper.py` | Wording a follow-up question | Yes | Not scored; every sentence is checked by the program and replaced when it strays |
| Persona | `persona` | `src/ledger_hand/extraction/prompts/persona.py` | Extraction | Experiments only | Debug set: 29 / 34 |
| (A changed rule) | `price_total` | `src/ledger_hand/extraction/prompts/price_total.py` | Extraction | Experiments only | Debug set: 29 / 34 |
| Few-shot, with more examples and two more rules | `second` | `src/ledger_hand/extraction/prompts/second.py`, examples in `src/ledger_hand/extraction/prompts/second_examples.py` | Extraction | Experiments only | Debug set: 29 / 34; voice set: 6 / 10 |
| (Two more rules) | `third` | `src/ledger_hand/extraction/prompts/third.py` | Extraction | Experiments only | Debug set: 30 / 34; voice set: 2 / 10 |
| Few-shot, with other examples and two more rules | `fourth` | `src/ledger_hand/extraction/prompts/fourth.py`, examples in `src/ledger_hand/extraction/prompts/fourth_examples.py` | Extraction | Experiments only | Debug set: 33 / 34; voice set: 8 / 10; final set: 18 / 22 |

The extraction scores are "whole trades right" from `evals/RESULTS.md`,
section "2026-10-09: prompt experiment one", table "The five versions on
the debug set"; the final set's from "Final exam: final set, prompt
`first`"; `split-1`'s from "2026-10-09: prompt experiment two", "The two ways
on the debug set"; `second`'s and `third`'s from "2026-10-18: prompt
experiment three, more examples for the owner's way of writing,
`qwen2.5:7b`", "The versions on the debug set" and "The versions on the
voice set"; `fourth`'s from "2026-10-19: prompt experiment four, new
examples with English passages and Chinese numbers, `qwen2.5:7b`", "The
versions on the debug set", "The versions on the voice set" and "The final
set". Section 6 has the tables.

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
- **`read-1`, zero-shot.** Instructions only, shown with the screenshot: one
  line for each value the order shows, the label the screen gives it and the
  value, both copied as they stand, in the language they are written in,
  every number as written, with nothing translated, calculated or added.
  The labels stay, so that extraction can tell a price from a total.
- **`bookkeeper-1`, persona.** "A meticulous bookkeeper" who asks for one
  thing at a time, given the facts the program settled. The persona sets the
  tone of the question; the program fixes what is asked, writes the label
  that says which trade and field it is about, and replaces any sentence
  that is not one plain question or that brings in a number, a coin or a
  word not among the facts (`src/ledger_hand/asking/question_text.py`).
- **The experiment versions.** Four each differ from `first` in one thing
  only: `zero_shot` has no example; `persona` puts the bookkeeper's role
  before the instructions; `stepwise` asks for a step-by-step analysis,
  written in a field `steps` of its own reply table before the rows;
  `price_total` adds one rule, that an amount said as a total never goes
  under price. A test checks that each is `first` with its one declared
  change (`tests/extraction/test_prompt_versions.py`). `second` and `fourth`
  each differ from `first` in two things: two rules after `first`'s
  instructions (the owner's words for a buy; an amount with U right after
  it is the total), and more examples after `first`'s ten, six in `second`
  and seven others in `fourth`; `third` adds the two rules only. Tests check
  each against what it declares it adds
  (`tests/extraction/test_second_prompt_version.py`,
  `tests/extraction/test_third_prompt_version.py`,
  `tests/extraction/test_fourth_prompt_version.py`), and another that no
  prompt holds a test sentence or a clause of one
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
with `answer-1` (`src/ledger_hand/flows/recording.py` names the four), and,
for a passage from a screenshot, reading it with `read-1`
(`src/ledger_hand/extraction/picture_reading.py`). The
rules fixed before the first two experiments picked `first` and one list
(section 6), which is what the product already used. The rule fixed before
the third prompt experiment picked neither of the two versions written for
the owner's way of writing, `second` and `third`, so the final set was not
run for them and extraction still uses `first`. The rule fixed before the
fourth prompt experiment picked `fourth`, which then got 18 / 22 on the
final set against 22 / 22 for `first`, so it did not pass and extraction
still uses `first`. Its defaults have not been
changed, and any change is the project owner's decision.

**Examples chosen by the language of the passage.** The assistant can
extract with one version for words that hold a Chinese character and
another for words that hold none (`src/ledger_hand/extraction/prompt_language.py`,
one function, asked by the assistant and by every measure). The project
owner decided that, where both cannot be served, the way he speaks comes
first: Chinese gets examples written his way, English keeps `first-3`,
which was measured on English and is not touched. Three versions for
Chinese were written on the practice half of an exam said his way
(`spoken-1` to `spoken-3`): `first-3`'s words and examples, then a few
rules and examples in his way of speaking, written as the program hands
them to the model, already tidied. A gate checks that none copies a
sentence of the exam (`tests/extraction/test_spoken_prompts_copy_no_exam_sentence.py`).
Two did not pass the final set, and the third, on the hidden half, sent
more wrong figures without a mark than `first-3`, so by the rule fixed
beforehand the assistant still extracts with `first-3` (section 6).

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
| The model that reads a screenshot | `LEDGER_HAND_MODEL_VISION_NAME` | qwen3-vl:8b | A model on this machine that can see pictures; qwen2.5:7b, the model the program extracts with, cannot. |
| Whether the model thinks before it answers | `LEDGER_HAND_MODEL_THINK` | model (nothing sent) | Model: nothing is sent, so each model answers as its own default says. Measured with qwen3-vl:8b on the debug set (see "2026-10-19: the thinking switch, `qwen3-vl:8b`" in evals/RESULTS.md), off got fewer trades whole than nothing sent, and every reply it gave was empty, so off is not the default; nor is on, which qwen2.5:7b, the model the program extracts with, cannot do. |
| The largest screenshot taken | `LEDGER_HAND_MODEL_SCREENSHOT_MAX_MB` | 20 MB | Above any phone's screenshot, so none is turned away: the largest phone screens, 1320 by 2868 pixels, come to about 14.4 MB even with no compression at all, four bytes to a pixel, and a PNG of an order page, mostly flat colour, is far smaller. A file larger than that, such as a camera's photo or a file chosen by mistake, is turned away at once rather than after a long wait for the vision model. |

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
side waits. The local plug also sends the thinking setting, when it is on
or off, as Ollama's top-level `think` field, true or false, and leaves the
field out by default; the cloud plug never sends it.

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
| The model is not there | `src/ledger_hand/llm/ollama_reply.py`, `src/ledger_hand/llm/cloud_reply.py` (kind `model_not_found`) | The model's name and the address; with the local plug, check the name or install the model with `ollama pull`; with the cloud plug, check the name against the service's own list of models, with nothing said of Ollama | `tests/llm/test_ollama_not_found.py`, `tests/llm/test_cloud_failures.py`, `tests/ui/test_failure_words_by_plug.py`, `tests/live/test_live_model_not_found_by_plug.py` |
| Key or request refused (401, 403, 400) | `src/ledger_hand/llm/exchange.py` (kind `server_error` with its status); `src/ledger_hand/llm/retry.py` does not try it again | A sentence of its own for each status | `tests/llm/test_cloud_retry.py`, `tests/ui/test_page_cloud.py` |
| The server fails (500 to 599) | `src/ledger_hand/llm/exchange.py` (kind `server_error`); tried again | Its status code; try again, or look at the server's log | `tests/llm/test_exchange.py`, `tests/ui/test_failure_words.py` |
| An answer not in the agreed form (not JSON, no text, too long) | `src/ledger_hand/llm/reply_json.py`, `src/ledger_hand/llm/ollama_reply.py` (kind `malformed_reply`) | The reply could not be used; try again, or put the passage another way | `tests/llm/test_ollama_reply.py`, `tests/llm/test_attack.py` |
| A reply that is not the table (or cut off at the longest reply) | `src/ledger_hand/extraction/reply_parser.py`; extraction asks again once, saying what was wrong | Said apart from the above: the replies could not be read as the table | `tests/extraction/test_reply_parser.py`, `tests/extraction/test_extractor.py` |
| A phrase that is not in the passage, or a number or time the rules are unsure of | `src/ledger_hand/extraction/passage.py`, `src/ledger_hand/extraction/row_draft.py` | The field stays empty, with the reason, and becomes a follow-up question | `tests/extraction/test_extractor.py`, `tests/extraction/test_attack.py` |
| The model fails while wording a question | `src/ledger_hand/asking/question_text.py` | The program's own sentence, behind the same label | `tests/asking/test_question_text.py` |
| A setting refused | `src/ledger_hand/settings.py` (`SettingsError`, naming the variable and its rule); `src/ledger_hand/wiring.py` | Which setting and its rule; a change on the Settings page changes nothing | `tests/test_settings.py`, `tests/ui/test_page_wiring.py`, `tests/ui/test_page_settings.py` |
| The book fails (newer version, not a database, not this program's, damaged, locked, inaccessible, conflict, unexpected) | `src/ledger_hand/storage/book_file.py`, `src/ledger_hand/storage/failures.py` | What happened and what can be done; a refused file is left as it is, without one byte written, except that a file whose header shows a book of this program's, with SQLite's journal beside it, is first rolled back by SQLite, once, and checked again, which may still refuse it (`docs/known-gaps.md`) | `tests/storage/test_sqlite_store.py`, `tests/storage/test_book_journal.py`, `tests/flows/test_book_failures.py`, `tests/ui/test_page_failures.py` |
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
one list on whole trades and lost on extra trades, so one list stayed. A
second model, `qwen3-vl:8b`, under the same prompt and parameters, got
3 / 34 and 5 / 22 where `qwen2.5:7b` got 31 / 34 and 22 / 22: most of its
replies came back empty. Two versions written for the owner's way of
writing, `second` and `third`, got 6 / 10 and 2 / 10 on the voice set where
`first` got 1 / 10, and 29 / 34 and 30 / 34 on the debug set where it got
31 / 34; the rule fixed beforehand picked neither, so the final set was not
run for them. One more, `fourth`, got 8 / 10 on the voice set and 33 / 34 on
the debug set, and the rule picked it; on the kept-back set it got 18 / 22,
below the 22 / 22 of `first`, so it did not pass and the product still
extracts with `first`. With thinking off, `qwen3-vl:8b` got 0 / 34 on the
debug set where it got 3 / 34 with nothing sent, every reply empty, so the
plug still sends nothing about thinking by default. The assistant, at its
latest runs: the first step right on 19 / 19, 23 / 27 questions looked up
right, 13 / 17 changes and deletions done right and 16 / 18 sentences
recording a share done right, none of the last two sending a wrong
proposal ("The assistant, measured", below).

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
`94，900`) and is reported apart. A fourth, `evals/sets/voice.json` (10
sentences: 9 to record, with 10 gold trades, and 1 not to record), holds
passages in the owner's own voice, with invented numbers, and is reported
apart too: it is never merged into the debug set.

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

**A second model** was not obtained in this experiment; it was measured
later, in "Experiment three: a second model" below.

### Experiment three: a second model

The third experiment changed only the model (`evals/RESULTS.md`,
"2026-10-13: second model, `qwen2.5:7b` and `qwen3-vl:8b`"):
`qwen3-vl:8b` beside `qwen2.5:7b`, both on this machine, with `first`, one
list and the settings' defaults, on the debug set, the final set and the
voice set, one run each. It picks nothing: the default model is still
`qwen2.5:7b`. The two runs of each set are laid side by side, from their
results files, by `evals/compare_models.py`; the numbers below are copied
from the record's three tables.

| Set | Model | Well-formed | Whole trades right | Missed | Seconds per sentence | Longest sentence, seconds |
| --- | --- | --- | --- | --- | --- | --- |
| debug | `qwen2.5:7b` | 26 / 26 (100.0%) | 31 / 34 (91.2%) | 0 | 4.04 | 8.894 (d22) |
| debug | `qwen3-vl:8b` | 5 / 26 (19.2%) | 3 / 34 (8.8%) | 31 | 42.74 | 52.573 (d30) |
| final | `qwen2.5:7b` | 16 / 16 (100.0%) | 22 / 22 (100.0%) | 0 | 3.86 | 10.111 (f14) |
| final | `qwen3-vl:8b` | 4 / 16 (25.0%) | 5 / 22 (22.7%) | 17 | 39.75 | 48.593 (f06) |
| voice | `qwen2.5:7b` | 9 / 9 (100.0%) | 1 / 10 (10.0%) | 0 | 4.50 | 8.731 (u09) |
| voice | `qwen3-vl:8b` | 1 / 9 (11.1%) | 0 / 10 (0.0%) | 9 | 46.03 | 54.74 (u04) |

`qwen3-vl:8b` gave no draft in 25 of the 30 debug sentences, 15 of the 20
final ones and 9 of the 10 voice ones, each of them an empty reply: the
model thinks before it replies (on by default for it in Ollama; the plug
sends nothing to turn it off), and the server's answer held an empty reply
beside its thinking. In the pairs it did make, every field was right on the
debug and the final set. With a longer reply allowed, in two parameter
comparisons on the debug set, it answered 14 of the 30 sentences at 2,048
tokens (15 / 34 whole) and 17 at 4,096 tokens (18 / 34 whole); at 4,096,
the other 13 got no complete answer within the 120 seconds a call is given.
On the voice set `qwen2.5:7b` got 1 of 10 trades whole; the fields it got
right least often there were the opinion (5 of 10), and the quantity, the
total and the price currency (7 of 10 each). Its runs of the debug and the
final set gave the same raw replies, sentence by sentence, as its earlier
runs of those sets.

### Experiment four: more examples in the owner's way of writing

The fourth experiment changed the prompt again, for the owner's own way of
writing (`evals/RESULTS.md`, "2026-10-18: prompt experiment three, more
examples for the owner's way of writing, `qwen2.5:7b`": the third
experiment on the prompt, the fourth in all), where `first` had got 1 of 10
trades whole on the voice set. Two candidates ran beside `first`, with
`qwen2.5:7b`, one list and the settings' defaults, on the debug, the voice
and the writings set, one run each, and a rule fixed before the first run
judged each against `first`: a candidate is picked only with more trades
whole on the voice set, and with no fewer trades whole, no more wrong values
with no issue and no more trades missed and extra on the debug set, and no
more wrong values with no issue on the voice set; the writings set is shown
and judged by none of these. `second`
(`src/ledger_hand/extraction/prompts/second.py`) changes two things at
once: two more rules after `first`'s instructions (the owner's words for a
buy; an amount with U right after it, said neither as the fee nor as the
price of one coin, is the total) and six more examples after `first`'s ten,
written the way the owner writes, in
`src/ledger_hand/extraction/prompts/second_examples.py`. `third`
(`src/ledger_hand/extraction/prompts/third.py`) has the two rules without
the six examples. **Neither was picked: each got fewer trades whole than
`first` on the debug set. So the final set was not run for them, and the
product still extracts with `first`.** The numbers below are copied from
the record's three tables, "The versions on the debug set", "… on the voice
set" and "… on the writings set".

| Set | Version | Whole trades right | Wrong values with no issue | Missed | Extra | Seconds per sentence |
| --- | --- | --- | --- | --- | --- | --- |
| debug | `first` | 31 / 34 (91.2%) | 2 | 0 | 0 | 3.95 |
| debug | `second` | 29 / 34 (85.3%) | 2 | 0 | 0 | 4.08 |
| debug | `third` | 30 / 34 (88.2%) | 1 | 0 | 0 | 4.22 |
| voice | `first` | 1 / 10 (10.0%) | 6 | 0 | 0 | 4.53 |
| voice | `second` | 6 / 10 (60.0%) | 1 | 0 | 0 | 4.41 |
| voice | `third` | 2 / 10 (20.0%) | 5 | 0 | 0 | 4.71 |
| writings | `first` | 15 / 22 (68.2%) | 0 | 0 | 0 | 3.36 |
| writings | `second` | 13 / 22 (59.1%) | 0 | 0 | 0 | 3.54 |
| writings | `third` | 15 / 22 (68.2%) | 0 | 0 | 0 | 3.45 |

On the debug set `second` lost d04, d08 and d11: in each its reply held a
phrase that is not a piece of the passage, a Chinese number written in
digits, "this morning" written as "今天早上", and a quantity with "个比特币"
after it, and the program left that field empty and said why. `third` lost
d19, writing "两千四百五" as "2,450". On the writings set `second` wrote two
English times in Chinese. On the voice set `second` got u01, u02, u05, u07
and u10 whole besides u04, which `first` got as well; u03, u06 and u09 kept
an opinion wrong or empty.

Two facts bear on these numbers. The new examples were written after the
errors of `first` on the voice set, and `third` after the errors of
`second` on the debug and the writings set, so their scores there are not
scores on passages they had not seen; the only passages they had not seen
are those of the final set and of the owner's later use. And `first`
already gets every trade of the final set whole, so the final set could
show only whether a candidate falls behind, not whether it does better.

### Experiment five: new examples with English passages and Chinese numbers

The fifth experiment (`evals/RESULTS.md`, "2026-10-19: prompt experiment
four, new examples with English passages and Chinese numbers,
`qwen2.5:7b`": the fourth experiment on the prompt, the fifth in all) tried
one more version for the owner's way of writing, after `second` and `third`
had lost English passages and Chinese numbers on the debug set. `fourth`
(`src/ledger_hand/extraction/prompts/fourth.py`) changes two things from
`first` at once: the two rules of `second` after `first`'s instructions, and
seven more examples after `first`'s ten, in
`src/ledger_hand/extraction/prompts/fourth_examples.py`: five written the
way the owner writes, one of them with a price in Chinese numbers, and two
in English only, each with an English time and a quantity written as a bare
number or with an English coin name. It differs from `third` only in those
examples. It ran on the debug, the voice and the writings set, one run each,
with `qwen2.5:7b`, one list and the settings' defaults, and was set beside
the runs of `first` and `third` of the fourth experiment ("prompt
experiment three" in `evals/RESULTS.md`), which were not made again: the model server, the model, the parameters, the sets and the
program were the same. The rule of the fourth experiment judged it against
`first`. **The rule picked `fourth`: on the debug set it got 33 / 34 against
31 / 34, on the voice set 8 / 10 against 1 / 10, with fewer wrong values
with no issue on both, and its prompt fits in the context with the longest
passage and the longest reply, with 644 tokens left against 2,003 for
`first`. On the final set, run once, it got 18 / 22 against 22 / 22 for
`first`, with one wrong value with no issue against none, so it did not pass,
and the product still extracts with `first`.** The numbers below are copied
from the record's tables "The versions on the debug set", "… on the voice
set", "… on the writings set" and "The final set".

| Set | Version | Whole trades right | Wrong values with no issue | Missed | Extra | Seconds per sentence |
| --- | --- | --- | --- | --- | --- | --- |
| debug | `first` | 31 / 34 (91.2%) | 2 | 0 | 0 | 3.95 |
| debug | `fourth` | 33 / 34 (97.1%) | 0 | 0 | 0 | 4.23 |
| voice | `first` | 1 / 10 (10.0%) | 6 | 0 | 0 | 4.53 |
| voice | `fourth` | 8 / 10 (80.0%) | 1 | 0 | 0 | 4.43 |
| writings | `first` | 15 / 22 (68.2%) | 0 | 0 | 0 | 3.36 |
| writings | `fourth` | 21 / 22 (95.5%) | 0 | 0 | 0 | 3.49 |
| final | `first` | 22 / 22 (100.0%) | 0 | 0 | 0 | 3.86 |
| final | `fourth` | 18 / 22 (81.8%) | 1 | 0 | 0 | 4.15 |

On the debug and the writings set `fourth` wrote no English time in
Chinese, where `first` wrote 2 and 7; it got more trades whole than `first`
in d05 and d13 and in six sentences of the writings set, and fewer in w06,
copying "5 万 个" as "5 万个". On the voice set it got every scored sentence
whole but u03, whose opinion leaves out its first clause, and u06, whose
opinion joins two parts of the passage. On the final set it got fewer trades
whole than `first` in f04, f08 and f12: an opinion made up in f04, with no
issue about it, a quantity made up and the total and its currency left
empty in f08, and both fees left empty in f12.

Two facts bear on these numbers. The new examples were written after the
errors of `first` on the voice set and those of `second` and `third` on the
debug and the writings set, so the scores of `fourth` on all three are not
scores on passages it had not seen; the only passages it had not seen are
those of the final set and of the owner's later use. And `first` already
gets every trade of the final set whole, so the final set could show only
whether a candidate falls behind, which `fourth` did.

### Experiment six: the thinking switch

The sixth experiment (`evals/RESULTS.md`, "2026-10-19: the thinking
switch, `qwen3-vl:8b`") changed one parameter of the second model: whether
the local plug asks it to think before it answers
(`LEDGER_HAND_MODEL_THINK`, section 4). `qwen3-vl:8b` ran the debug and the
voice set with thinking off, with `first`, one list and the settings' other
defaults, one run each, and each run was set beside the run of the same set
in "Experiment three: a second model", which sent nothing about thinking.
The rule, fixed before the runs, judged the debug set only: with at least
as many trades whole with thinking off as with nothing sent, the default
would become off, after a guard run of `qwen2.5:7b` with thinking off had
shown that the default model fails no more often and gets no fewer trades
whole; with fewer, the default stays nothing sent; never on, which
`qwen2.5:7b`, the model the program extracts with, cannot do. **With
thinking off `qwen3-vl:8b` got 0 / 34 on the debug set against 3 / 34 with
nothing sent, so the default stays nothing sent (`model`), and the guard
run was not made.** The numbers below are copied from the record's tables
"The debug set, thinking not sent and off" and "The voice set, thinking not
sent and off".

| Set | Thinking | Well-formed | Whole trades right | Missed | Seconds per sentence | Longest sentence, seconds |
| --- | --- | --- | --- | --- | --- | --- |
| debug | not sent | 5 / 26 (19.2%) | 3 / 34 (8.8%) | 31 | 42.74 | 52.573 (d30) |
| debug | off | 0 / 26 (0.0%) | 0 / 34 (0.0%) | 34 | 4.48 | 10.574 (d01) |
| voice | not sent | 1 / 9 (11.1%) | 0 / 10 (0.0%) | 9 | 46.03 | 54.74 (u04) |
| voice | off | 0 / 9 (0.0%) | 0 / 10 (0.0%) | 10 | 4.85 | 8.563 (u09) |

With thinking off every sentence of both sets ended in an empty reply, and
the message of each failure says that the model wrote only its thinking;
why, with Ollama 0.34.3, is in `docs/known-gaps.md`, "Thinking off, as
Ollama 0.34.3 takes it with `qwen3-vl:8b`". The default was set from
`qwen3-vl:8b` extracting the debug set; whether thinking helps or hurts
reading a screenshot is not measured.

### The iteration trace

Every measured version is kept as its own file under
`src/ledger_hand/extraction/prompts/`, and every run as its own results
file under `evals/results/`, with the commit, the prompt files'
fingerprints, the model's fingerprint and every parameter in its first
line.

| Step | What changed | What it showed |
| --- | --- | --- |
| 1 | `first` written: field descriptions, rules, ten invented examples. Before the first measurement, one rule was added: never translate, and copy times in the passage's own words (commit `dd83094`) | The baseline: 29 / 34 |
| 2 | Not the prompt: the program's reading of a full-width comma between two numbers was fixed | The same 30 raw replies; d23 went from 0 to 2 whole trades, so `first` became 31 / 34 (`evals/RESULTS.md`, "`first` against the baseline, sentence by sentence") |
| 3 | `zero_shot`: the ten examples taken out | 19 / 34: the examples carry most of the work; without them 9 times and 1 fee were left out with no issue, and 5 values were made up |
| 4 | `persona`: a bookkeeper's role before the instructions | 29 / 34: no gain |
| 5 | `stepwise`: a written step-by-step analysis before the rows | 25 / 34 and slower: no wrong value with no issue, but sides and times left out |
| 6 | `price_total`: one rule against a total put as the price, the error the baseline found | 29 / 34: the error and every made-up value gone, two other trades lost |
| 7 | Temperature 0.7, and a longest reply of 256 tokens | 30 / 34 and 19 / 34 (section 4) |
| 8 | Final set, `first`, once | 22 / 22 |
| 9 | `split-1`: split a passage first, then extract each segment | Tied on whole trades, 2 extra trades, about twice the calls |
| 10 | A second model, `qwen3-vl:8b`, with the same prompt, way and parameters; and a fourth set, the voice set | 3 / 34 on the debug set, 5 / 22 on the final set and 0 / 10 on the voice set, against 31 / 34, 22 / 22 and 1 / 10 for `qwen2.5:7b`; 25 of its 30 debug sentences ended in an empty reply |
| 11 | `second`: two more rules and six more examples in the owner's way of writing; `third`: the two rules alone | 6 / 10 and 2 / 10 on the voice set against 1 / 10 for `first`, and 29 / 34 and 30 / 34 on the debug set against 31 / 34: neither picked, the final set not run |
| 12 | `fourth`: the two rules of `second` and seven other examples, two of them in English and one with a price in Chinese numbers | 8 / 10 on the voice set and 33 / 34 on the debug set against 1 / 10 and 31 / 34 for `first`: picked; then 18 / 22 on the final set against 22 / 22: not passed, `first` kept |
| 13 | Not the prompt: thinking off for `qwen3-vl:8b`, the second model, on the debug and the voice set | 0 / 34 on the debug set against 3 / 34 with nothing sent, every reply empty: the default stays nothing sent |

`answer-1`, the prompt that copies a piece of an answer, has been reworded
once (commit `b345470`): it now says what the piece to copy is, so that the
words leading up to it are left out. No measured run uses it.

One caveat on step 7: `stepwise` asks again with `first`'s words, which ask
for `{"trades": [...]}`, while its own table puts `steps` first. In the
main run nothing was asked again; with 256 tokens the three cut-off passages
were.

### The assistant, measured

The assistant (section 2) has rulers of its own, each with its sentences
and gold answers committed before its first run, each run with
`qwen2.5:7b` at temperature 0, the demo ledger and the invented book's
fixed moment. None of these sentences is a hidden test: all were seen
while the prompts were written. The numbers below are those of the latest
run of each, at the end of the round; earlier runs, and every change
between them, are in `evals/RESULTS.md`. "Silently wrong" is a proposal
sent that is not the gold one.

| Ruler | Sentences | Done right | Silently wrong | Not done right | Source |
| --- | --- | --- | --- | --- | --- |
| The first step: which tool the model asks for first | 19 (`evals/sets/tools.json`) | 19 | not counted: only the tool's name is judged | none | `evals/tool_results/run-20261125T003833Z-tools-assistant-4.jsonl`; `evals/RESULTS.md`, "2026-11-25: a cut period judged by the sentence just said first" |
| Asking the ledger, to the end | 27 (`evals/sets/asks.json`) | 23 | 0 tables narrower or off | Q6 and A13, an English time the model wrote in Chinese; A15 and A18, the model asked back in words; each with no table | `evals/tool_results/run-20261125T003433Z-asks-assistant-4.jsonl`; the same section |
| Asking, with numbers and times that are easy to mistake | 11 (`evals/sets/asks_times.json`) | 2 | 0 tables narrower or off | T1 to T6 and T9 to T11, each with no table | `evals/tool_results/run-20261124T220740Z-asks_times-assistant-4.jsonl`; `evals/RESULTS.md`, "2026-11-24: after taking the finding of a time in the sentence out" |
| Changing and deleting one trade | 17 (`evals/sets/edits.json`) | 14 | 0 | N4, a month copied out of a day; N9, an English day written in Chinese; N10, a time of the model's own; each sent nothing (N8, the model listing the trades and asking in words, was not done with `assistant-4` either) | `evals/tool_results/run-20261126T024548Z-edits-assistant-5.jsonl`; `evals/RESULTS.md`, "The system prompt's rule on changes, before and after" |
| Recording a share bought with dollars | 18 (`evals/sets/stocks.json`) | 16 | 0 | K14 and K15, open orders the model answered in words, sending nothing without saying why | `evals/tool_results/run-20261125T041238Z-stocks-assistant-4.jsonl`, its last line; the same 16 and 0 with the prompt versions picked, in `evals/RESULTS.md`, "2026-11-25: recording a share bought with dollars, with the ledger's own assets, `qwen2.5:7b`" |
| Picking an asset named the way people say it from the ledger's list, the locked half | 22 (half of `evals/sets/stock_names.json`) | on the list 11 directly, 9 through the whole assistant | 5 each way: names the ledger lacks picked as listed assets | N10 and N22 not matched through the whole assistant; the step is off on the assistant | `evals/tool_results/run-20261125T184313Z-stock_names-asset-pick-1-direct-locked.jsonl` and `evals/tool_results/run-20261125T184335Z-stock_names-asset-pick-1-whole-locked.jsonl`; `evals/RESULTS.md`, "2026-11-25: picking an asset named the way people say it from the ledger's list, `qwen2.5:7b`" |
| Matching a name by the program's own table of company names, the locked half | 22 (half of `evals/sets/stock_names.json`) | on the list 9 directly, 7 through the whole assistant | 0 each way | on the list 2 directly and 4 through the whole assistant not matched; on the practice half one sentence naming two companies was sent as two shares, so the table is off on the assistant | `evals/tool_results/run-20261127T154247Z-stock_names-table-direct-hidden.jsonl` and `evals/tool_results/run-20261127T154253Z-stock_names-table-whole-hidden.jsonl`; `evals/RESULTS.md`, "2026-11-27: names of assets matched by the program's table and by answers kept, `qwen2.5:7b`" |
| The seven recording sentences, through the try-out script | 7 (R1 to R7 of `evals/sets/tools.json`) | no gold answer; R1, R3 and R4 sent as said | not judged | R2 and R5 ask which money (the demo ledger prices in USDT and USD); R6, an open order, the model answered itself; R7 not sent, its quantity said in money, with the reason | `evals/tool_results/record-20261125T041523Z-seven-through-the-assistant.txt` |
| The final set, through the start of recording with the assistant's prompt versions | 20 sentences, 22 trades (`evals/sets/final.json`) | 22 trades whole | 0 fields wrong with nothing said | none | `evals/tool_results/judged-20261125T042503Z-final-screen-2-first-3.jsonl`, its last line |
| The debug set, the same way | 30 sentences, 34 trades (`evals/sets/debug.json`) | 30 trades whole | 1 field wrong with nothing said, in d23 | d05, d09, d11 and one trade of d23 | `evals/tool_results/judged-20261125T041721Z-debug-screen-2-first-3.jsonl`, its last line |
| The exam said the owner's way, recording as said, before tuning | practice 15, hidden 15 sentences; 12 and 17 gold trades (`evals/sets/spoken/spoken-r100-practice.json`, `evals/sets/spoken/spoken-r100-hidden.json`) | saved with no cell changed: practice 6, hidden 4 | a wrong figure with no mark: practice 0, hidden 1 | the rest asked a question (practice 5, hidden 10) or were not sent (1, 2); 3 euro sentences not enabled, each said it cannot be recorded | `evals/tool_results/spoken-20261125T225944Z-spoken-r100-practice-first-3-assistant-4.jsonl`, `evals/tool_results/spoken-20261125T230244Z-spoken-r100-hidden-first-3-assistant-4.jsonl`; `evals/RESULTS.md`, "2026-11-26: the owner's way of speaking, three tiers, `qwen2.5:7b`" |
| The same, a little tidier | practice 13, hidden 12; 13 and 11 gold trades (`evals/sets/spoken/spoken-r80-practice.json`, `evals/sets/spoken/spoken-r80-hidden.json`) | practice 4, hidden 7 | practice 1, hidden 0 | asked: practice 8, hidden 4; 3 euro sentences not enabled | `evals/tool_results/spoken-20261125T230554Z-spoken-r80-practice-first-3-assistant-4.jsonl`, `evals/tool_results/spoken-20261125T230917Z-spoken-r80-hidden-first-3-assistant-4.jsonl`; the same section |
| The same, tidy | practice 13, hidden 12; 14 and 9 gold trades (`evals/sets/spoken/spoken-r70-practice.json`, `evals/sets/spoken/spoken-r70-hidden.json`) | practice 12, hidden 8 (of them 3 and 2 once the asset's code was given) | practice 1, hidden 0 | asked: practice 1, hidden 1; 3 euro sentences not enabled | `evals/tool_results/spoken-20261125T231209Z-spoken-r70-practice-first-3-assistant-4.jsonl`, `evals/tool_results/spoken-20261125T231520Z-spoken-r70-hidden-first-3-assistant-4.jsonl`; the same section |
| The exam's hidden halves, three tiers, with `spoken-3`, the one version for Chinese left after the final set | 35 enabled sentences, 37 gold trades | saved with no cell changed: 19, and 1 once the code was given (`first-3`: 17 and 2) | 2 (`first-3`: 1) | the rest asked or not sent | `evals/tool_results/spoken-20261126T014525Z-spoken-r100-hidden-spoken-3-assistant-4.jsonl` and the two after it; `evals/RESULTS.md`, "Three versions for Chinese, and the pick" |
| The exam's hidden halves at the end (`first-3`, `assistant-5`), against their lines | as said 15, a little tidier 11, tidy 9 enabled sentences | as said 33.3% of 12, a little tidier 63.6% of 11 (line 80%), tidy 100.0% of 8 (line 90%) | as said 1, a little tidier 0, tidy 0 (line 0 each) | tidy met both lines; a little tidier missed its share; as said missed the line of no ③ | `evals/tool_results/spoken-20261126T023911Z-spoken-r100-hidden-first-3-assistant-5.jsonl` and the two after it; `evals/RESULTS.md`, "At the end" |
| The system prompt's rule on changes, `assistant-4` against `assistant-5` | the three sets of changes (17, 4 and 4), the three of questions (27, 6 and 6), `evals/sets/tools.json` (19) and the exam's recording | changes 19 against 20 right; questions 32 against 31; first tool 19 against 19; recording the same | changes 0 sent wrong either way; questions 0 off either way | `assistant-5` met every line and is the default | `evals/tool_results/run-20261126T021802Z-edits-assistant-4.jsonl`, `evals/tool_results/run-20261126T024548Z-edits-assistant-5.jsonl` and the runs beside them; `evals/RESULTS.md`, "The system prompt's rule on changes, before and after" |

What did not pass its own line: on the twenty-seven questions, "Q1 to Q6
all right" (Q6 is not); on the eleven, 80% right; on the changes and
deletions, 80% right, which since the cut periods is reported as it comes
rather than held as a line (`evals/RESULTS.md`, the same sections). On the
debug set the assistant's versions get one trade fewer whole than the
Record page's `screen-1` and `first` (31 of 34, with 2 fields wrong and
nothing said), and one field fewer wrong with nothing said
(`evals/tool_results/judged-20261125T024652Z-debug-screen-1-first.jsonl`).
That run's first line says the work tree was not clean
(`worktree_clean: false`); which changes were not committed then is not
recorded in the file. The final and debug sets were also run once more
with a quantity in another unit held back, and gave the same counts, with
nothing held back
(`evals/tool_results/judged-20261125T042710Z-final-screen-2-first-3-hold.jsonl`,
`evals/tool_results/judged-20261125T042134Z-debug-screen-2-first-3-hold.jsonl`).

Whether the model picks the right kind of work, on new sentences said the
owner's way: the first tool was the right one on 35 of 35 enabled
sentences of the exam's hidden halves, which no prompt was written
against (`evals/RESULTS.md`, "At the end"); the line of 95% is reported,
not held. Not measured: how the assistant does with the real ledger,
which the Assistant page can reach but no measure does. The sentences for a demo in the README are
checked by `tests/live/test_live_demo_sentences.py`; that they come out
the same again shows nothing about other words for the same thing.

## 7. Design decisions

**In short:** the model is a replaceable part behind a narrow port, kept
away from anything it could get wrong silently; the rules of the ledger
live in pure code with tests; nothing is written without the person's
confirmation, and every file written carries its version.

| Decision | Why | Where |
| --- | --- | --- |
| A model on this machine by default, a cloud service one setting away | Trades are personal financial data: by default nothing typed leaves the machine, nothing is paid and no key is needed. Setting an address or a key never switches to a cloud service; only `LEDGER_HAND_MODEL_PLUG` does, and off this machine it insists on https and a key. | `src/ledger_hand/settings.py`, `src/ledger_hand/llm/connect.py` |
| Three ports and no more: the model, the storage and the ledger | The rest of the program only says "ask the model", "save a trade" or "propose to the ledger". A plug (Ollama, a cloud service, SQLite, the demo ledger, a stand-in for tests) is replaced without touching the rest, and a fourth port would be a design decision, not an edit. | `src/ledger_hand/ports.py`, `src/ledger_hand/llm/`, `src/ledger_hand/storage/`, `src/ledger_hand/ledger/`, `tests/fakes/` |
| The model only copies; the program converts and checks | A model miscalculates and invents (section 2). Its reply is untrusted input: every phrase must be found in the passage, every number and time is converted by tested rules, and the reply is held to a JSON schema and still read against it. | `src/ledger_hand/core/`, `src/ledger_hand/extraction/` |
| Ask, never guess; preview before saving | A guessed value is a silent error in a ledger. A missing fee, an unknown coin or amounts that disagree become questions; only Save writes; a trade can be left out after seeing it, and price and total sit side by side so a total put as the price shows. | `src/ledger_hand/core/followup.py`, `src/ledger_hand/ui/preview.py` |
| Incremental export, named so, with a warning | The ledger's present import replaces the whole ledger, so a file of a few new trades must never be taken for a full backup: its name carries `incremental`, and a red line beside Export says not to import it yet. A file is written whole under a temporary name and never replaces another; trades are marked only after it is written. | `src/ledger_hand/export/file_name.py`, `src/ledger_hand/ui/export_panel.py`, `src/ledger_hand/flows/export_file.py` |
| The book carries its version and a mark | A file ten years old must still be read. The version and the mark are read before anything else; a newer or foreign file is refused without one byte written; numbered upgrade scripts are never changed once committed, and each version has a golden sample. | `src/ledger_hand/storage/book_file.py`, `src/ledger_hand/storage/upgrades/`, `tests/storage/golden/` |
| The core touches nothing outside | The rules (a trade, numbers, times, the check of a draft) use only a short list of standard-library modules, read no clock and no machine time zone, and use no floating-point numbers. They can be tested with no setup and moved anywhere; the layering check enforces this on every run. | `src/ledger_hand/core/`, `tests/guardrails/layering.py` |
| No wrapper framework around the model (such as LangChain) | The request, its parameters and its failures are what this project is about, and a wrapper would hide them. The calls are a thin layer over `httpx`; the run-time dependencies are three (httpx, Streamlit, tzlocal). Also left out: data-validation libraries, database abstraction layers, evaluation frameworks. | `src/ledger_hand/llm/exchange.py`, `pyproject.toml`, `docs/architecture.md` |
| Rules fixed before measuring | A rule chosen after seeing the numbers picks the numbers. Every experiment that picks a version or a way wrote its rule down before running, and the final set is run once, at the end. | `evals/compare.py`, `evals/compare_methods.py`, `evals/compare_sets.py` |
| One plain sentence for every failure | The interface never shows a raw error; every kind has a sentence, and a test walks every kind. | `src/ledger_hand/ui/failure_words.py`, `tests/ui/test_failure_words.py` |

## 8. Known limitations

**In short:** the measurements are small, and the second model measured
mostly gave empty replies under the settings' defaults, and every reply
empty with thinking off; the prompt the product extracts with gets few
trades whole in the owner's own way of writing; the step that judges a
passage has no score on unseen sentences; no real screenshot has been
tried yet, so how well screenshots are read is not known; and a handful of
rough edges are known and listed, each with why it stands.

| Limitation | Why it stands |
| --- | --- |
| The second model was measured mostly under the settings' defaults | `qwen3-vl:8b` ran the debug, final and voice sets once each with the parameters `qwen2.5:7b` ran with; a longer reply was tried on the debug set only, in two parameter comparisons, and thinking off on the debug and voice sets, once each; neither the prompt nor any other setting was tuned for it (`evals/RESULTS.md`, "2026-10-13: second model, `qwen2.5:7b` and `qwen3-vl:8b`", and "2026-10-19: the thinking switch, `qwen3-vl:8b`"). |
| `qwen3-vl:8b` thinks before it replies, and the thinking can use up the reply | With the longest reply at 1,024 tokens, 25 of its 30 debug sentences ended in an empty reply, which the program takes as a model failure (`malformed_reply`) and does not try again; at 4,096 tokens, 13 got no complete answer within 120 seconds (`timed_out`). By default the plug does not say whether the model should think (`LEDGER_HAND_MODEL_THINK` is `model`), so the model's own default, on, applies (`evals/RESULTS.md`, "2026-10-13: second model, `qwen2.5:7b` and `qwen3-vl:8b`"). With thinking off, every sentence of the debug and voice sets ended in an empty reply as well, so off did not become the default (`evals/RESULTS.md`, "2026-10-19: the thinking switch, `qwen3-vl:8b`"; `docs/known-gaps.md`, "Extracting with `qwen3-vl:8b`: most replies empty" and "Thinking off, as Ollama 0.34.3 takes it with `qwen3-vl:8b`"). |
| The samples are small | 30 debug, 20 final, 20 writings and 10 voice sentences, one run each at temperature 0 (two models on the debug, final and voice sets): a difference of one or two trades between versions is one or two sentences, so close results say little. |
| Judging a passage was tuned on the debug set only, and has no score on the final set | The final set is kept for extraction's last run, so how often judging stops a real trade, or lets through what is not recorded, on new passages is not measured (`docs/known-gaps.md`). |
| Judging can stop a real trade | When the model takes a filled trade for a plan or an order, the passage is stopped; there is no "record it anyway", which is a decision for the project owner (`docs/known-gaps.md`). |
| Screenshot input is not measured | A screenshot is read by `qwen3-vl:8b` on the Record page, where the person checks the text read before it is extracted, and with `scripts/try_screenshot.py`; no real screenshot has been tried yet, not even by hand, so how well screenshots are read is not known. What the model reads off a picture has no words of the person's own to be checked against (`docs/known-gaps.md`). |
| Recording from a screenshot has rough edges | Only PNG and JPEG, one file at a time, and a limit on the file's size, not its pixels; the upload box shows Streamlit's own limit of 200 MB per file; the uploaded file stays in memory until the browser tab is closed; while the picture is read only Streamlit's own mark shows that the page is working; a sentence the vision model writes about a picture with no order on it is taken as text read (`docs/known-gaps.md`, "Recording from a screenshot on the page"). |
| The owner's own way of writing is extracted poorly | On the ten passages of the voice set `first` gets 1 of 10 trades whole with `qwen2.5:7b`, with six values wrong and no issue about them (`evals/RESULTS.md`, "2026-10-18: prompt experiment three, more examples for the owner's way of writing, `qwen2.5:7b`", "The versions on the voice set"). `fourth` got 8 of 10 there but did not pass the final set, so the product keeps `first` (`docs/known-gaps.md`, "Extraction: the owner's own way of writing"). |
| An English time is often written in Chinese by the model | The most common reason a trade is not whole in the experiments. The program catches it (the phrase is not a piece of the passage) and asks, so it costs a question, not a wrong record; `fourth` did not do it on the debug and the writings set but did not pass the final set, so the product keeps `first` (`docs/known-gaps.md`). |
| A total put as the price can reach the records | `first` did so twice on the debug set, with no issue about the field (`evals/RESULTS.md`). The table shows price and total side by side and a trade can be left out; `price_total` removed it but lost two other trades, so the rule did not pick it (`docs/known-gaps.md`). |
| An "about" not right next to a number may be dropped | When the model copies a piece of an answer it may leave out a word such as "大概" that does not touch the number, and the program then takes the amount as exact: the piece is only checked to be a piece of the answer. Not measured (`docs/known-gaps.md`). |
| Time zone databases of different versions | The ledger and this program each use their own copy; where they differ, the ledger refuses a timed trade this program exports. On the machine the checks run on now, Python's copy (2026e) holds `EST5EDT`, `CST6CDT`, `MST7MDT` and `PST8PDT` as zones of their own, and the ledger's Node (tz 2026a) takes them for four American cities, whose offsets before 1883 have seconds in them; with both, the ledger throws instead of refusing for trades in those zones in the year 1, so one sample of the ledger tier, listed in `tests/ledger_check/cases.py`, fails. Closing it needs a decision (`docs/known-gaps.md`). |
| The book after a crash in the middle of a write | For a file whose header shows a book of this program's, SQLite rolls the cut-off write back from its journal, once, and the book is checked again. A book refused on that second check has already been written by the rollback; in a folder that cannot be written the journal cannot be removed, so the book stays inaccessible; any other file keeps its journal and is not written to. Only the book's header is read before the rollback, so a journal from another book beside it is rolled back into it all the same; with the book's own journal no saved trade is lost (`docs/known-gaps.md`). |
| A change of the time zone database can stop listing and exporting | A timed trade whose kept offset no longer matches its zone fails every reading that reaches it as damaged: nothing can be listed, and nothing exported while that trade is not exported yet; saving, and exporting once that trade has been exported, still work (`docs/known-gaps.md`). Marking only those trades is left for later. |
| Export needs a file system with hard links | The file is given its name with a hard link so that it never replaces another; where links are not supported, every export is "not written" and nothing is marked (`docs/known-gaps.md`). |
| The cloud plug has never called a real cloud service | No key is used and nothing is paid. Its requests are tested against fake answers and once against the local Ollama's OpenAI-style endpoint (`tests/live/test_live_cloud_plug.py`). |
| The experiment tools measure local models only | They ask Ollama for the model's fingerprint, so a model on a cloud service cannot be measured with them; with the cloud plug set they refuse to start, before anything is sent, and say why (`docs/known-gaps.md`). |
| A model failure while reading an answer is said by its kind only | The page says the kind in plain words and asks the question again, but not by status code or wait, so a refused key or a rate limit's wait is said there in the kind's general sentence. The command line still prints the kind's code word, such as `(timed_out)` (`docs/known-gaps.md`). |
| A model setting refused in the environment cannot be corrected on the Settings page | The page opens and names the setting and its rule; the environment has to be corrected and the program started again (`docs/known-gaps.md`). |
| The measures use the demo ledger only | The Assistant page can reach the person's own ledger page (walked through once by hand with `qwen2.5:7b`, 2026-11-25), but every measure, the script and the tests use the invented book in memory; what reaching the ledger page leaves out (cash balances and rates tried only against answers written from the ledger's README, looking through the trades after a timeout or a reload) is in `docs/known-gaps.md`, "The assistant page and your ledger page". |
| Choosing what to do is measured on few new sentences | On the exam's hidden halves the first tool was right on 35 of 35 enabled recording sentences; only recording sentences, and one run ("The assistant, measured"). |
| The owner's way of speaking does not meet its lines | On the exam's hidden halves at the end of the round, the tier as said sent two wrong figures with no mark (one before cards with empty cells were sent), and the tier a little tidier saved 63.6% with no cell changed against a line of 80%; three versions with examples in the owner's way did not beat `first-3` (`evals/RESULTS.md`, "Three versions for Chinese, and the pick", "At the end" and "The hidden halves, three tiers, at the end of the round"). Trying another local model is the step set for this case. |
| A time said with a zone other than the ledger's is recorded in the ledger's zone | The program converts no zone said in words, so such a time is left as said, not tidied. When the model can still read it ("按北京时间算，2026年11月20号下午3点……", invented), the trade is sent at that clock time in the ledger's zone, hours off; since 2026-11-27 its time cell is marked suspicious with the words said and the ledger's zone, and the reply says the time was not converted. A zone said with neither 时间, 时区 nor a Latin name ("北京下午三点") is not seen and gets no mark; when the model cannot read the time, the card is sent with its date empty, or, to a ledger that takes no cards, the time is asked (`docs/known-gaps.md`, "What you will meet" and "A time said with another zone is not tidied, and may still be read in the ledger's zone"). |
| An English question with a time in it often gets no table | The model writes the time in Chinese, which is not the user's words, so nothing is looked up; two of the four questions not right are of this kind (`docs/known-gaps.md`). |
| About one change or deletion in six is not done the first time | 14 of 17 with `assistant-5`, none sent wrong; the rest ask back or ask for the date again ("The assistant, measured"; `docs/known-gaps.md`). |
| Figures copied into the wrong field can be sent with no warning | When the copied figures still agree with each other the program has nothing to say (an amount paid in all copied as the price); the proposal waits to be confirmed, showing quantity, price and total (`docs/known-gaps.md`). |

## 9. Requirements map

The course's checklist for the top grade, row by row, then its three marks
of extra effort. Each row names where the requirement is met: a file, a
section of the README or of this report, a test.

| Requirement | Where | Status |
| --- | --- | --- |
| A working application with a frontend | Streamlit interface, three pages (Record, Settings, Assistant): [`src/ledger_hand/ui/app.py`](../src/ledger_hand/ui/app.py); how to start it: README, "Starting the interface"; run headless in tests: [`tests/ui/`](../tests/ui/); against the real model: [`tests/live/test_live_page.py`](../tests/live/test_live_page.py) | Done |
| API usage | The model's HTTP chat API, called with httpx: local Ollama [`src/ledger_hand/llm/ollama.py`](../src/ledger_hand/llm/ollama.py) (the default), OpenAI-style cloud endpoint [`src/ledger_hand/llm/cloud.py`](../src/ledger_hand/llm/cloud.py); behind the port in [`src/ledger_hand/ports.py`](../src/ledger_hand/ports.py); one real call checked in [`tests/live/test_live_model.py`](../tests/live/test_live_model.py) | Done |
| Solves a real-world problem | Recording one's own trades in a ledger from plain sentences: section 1; README, "What this is" | Done |
| Substantive processing, not just question and answer | Seven steps, three with the model: section 2; [`src/ledger_hand/flows/recording.py`](../src/ledger_hand/flows/recording.py). From a screenshot, one more step before them, the vision model reading it out as text: [`src/ledger_hand/flows/screenshot.py`](../src/ledger_hand/flows/screenshot.py) | Done |
| Parameterization, and why | Every parameter a setting with a default and its reason: [`src/ledger_hand/settings.py`](../src/ledger_hand/settings.py) (`ABOUT`); the Settings page [`src/ledger_hand/ui/settings_page.py`](../src/ledger_hand/ui/settings_page.py); README, "Model settings"; section 4; two parameter comparisons in [`evals/RESULTS.md`](../evals/RESULTS.md) | Done |
| At least two prompt techniques | In the product: zero-shot [`src/ledger_hand/extraction/prompts/screen.py`](../src/ledger_hand/extraction/prompts/screen.py), [`src/ledger_hand/extraction/prompts/answer.py`](../src/ledger_hand/extraction/prompts/answer.py) and [`src/ledger_hand/extraction/prompts/read.py`](../src/ledger_hand/extraction/prompts/read.py), few-shot [`src/ledger_hand/extraction/prompts/first.py`](../src/ledger_hand/extraction/prompts/first.py), persona [`src/ledger_hand/asking/prompts/bookkeeper.py`](../src/ledger_hand/asking/prompts/bookkeeper.py). In experiments only: chain of thought [`src/ledger_hand/extraction/prompts/stepwise.py`](../src/ledger_hand/extraction/prompts/stepwise.py), zero-shot [`src/ledger_hand/extraction/prompts/zero_shot.py`](../src/ledger_hand/extraction/prompts/zero_shot.py) and persona [`src/ledger_hand/extraction/prompts/persona.py`](../src/ledger_hand/extraction/prompts/persona.py) for extraction. Section 3 | Done: four techniques, three of them in the product |
| Error handling: API timeout, empty input, rate limit | Timeout: [`src/ledger_hand/llm/exchange.py`](../src/ledger_hand/llm/exchange.py), [`tests/llm/test_exchange.py`](../tests/llm/test_exchange.py). Empty input: [`src/ledger_hand/extraction/passage_check.py`](../src/ledger_hand/extraction/passage_check.py), [`tests/ui/test_page_failures.py`](../tests/ui/test_page_failures.py). Rate limit: [`src/ledger_hand/llm/retry_after.py`](../src/ledger_hand/llm/retry_after.py), [`src/ledger_hand/llm/retry.py`](../src/ledger_hand/llm/retry.py), [`tests/llm/test_cloud_retry.py`](../tests/llm/test_cloud_retry.py). Every failure in one plain sentence: [`src/ledger_hand/ui/failure_words.py`](../src/ledger_hand/ui/failure_words.py). Section 5 | Done; a rate limit is tested against a fake server only (section 8) |
| Documentation | [`README.md`](../README.md), this report, [`docs/architecture.md`](architecture.md), [`docs/known-gaps.md`](known-gaps.md), [`evals/RESULTS.md`](../evals/RESULTS.md) | Done |
| GitHub repository | This repository with its Git history; it has a GitHub remote, and publishing to it is done by the project owner | Done |
| Prompt experiments, with the trace of iteration | Every run's results file in [`evals/results/`](../evals/results/), the record in [`evals/RESULTS.md`](../evals/RESULTS.md), every measured version kept as its own file in [`src/ledger_hand/extraction/prompts/`](../src/ledger_hand/extraction/prompts/), the rules in [`evals/compare.py`](../evals/compare.py), [`evals/compare_methods.py`](../evals/compare_methods.py) and [`evals/compare_sets.py`](../evals/compare_sets.py), and the rule of the thinking switch, applied again to its runs' summaries by [`tests/evals/test_thinking_switch_record.py`](../tests/evals/test_thinking_switch_record.py); section 6 | Done |
| Extra: a custom database | The book, a versioned SQLite file with numbered upgrade scripts and a golden sample: [`src/ledger_hand/storage/sqlite_store.py`](../src/ledger_hand/storage/sqlite_store.py), [`src/ledger_hand/storage/upgrades/`](../src/ledger_hand/storage/upgrades/), [`tests/storage/golden/`](../tests/storage/golden/) | Done |
| Extra: combining multiple models | Two local models, `qwen2.5:7b` and `qwen3-vl:8b`, measured side by side on the same yardstick (the debug, final and voice sets) with the same prompt, way of reading and parameters: [`evals/RESULTS.md`](../evals/RESULTS.md), "2026-10-13: second model, `qwen2.5:7b` and `qwen3-vl:8b`"; section 6, "Experiment three: a second model". The comparison is worked out from the results files by [`evals/compare_models.py`](../evals/compare_models.py) and checked against the record by [`tests/evals/test_model_comparison_record.py`](../tests/evals/test_model_comparison_record.py). The model is a setting (`LEDGER_HAND_MODEL_NAME`; `--model` in experiments). In the path from a screenshot the two work one after the other in one pipeline: `qwen3-vl:8b` (`LEDGER_HAND_MODEL_VISION_NAME`) reads the screenshot out as text and `qwen2.5:7b` extracts the trades from it: [`src/ledger_hand/flows/screenshot.py`](../src/ledger_hand/flows/screenshot.py), [`scripts/try_screenshot.py`](../scripts/try_screenshot.py) | Done |
| Extra: multimodal | A screenshot of an order as input: uploaded on the Record page ([`src/ledger_hand/ui/screenshot_panel.py`](../src/ledger_hand/ui/screenshot_panel.py)), checked and read by the vision model ([`src/ledger_hand/flows/uploading.py`](../src/ledger_hand/flows/uploading.py)), shown to the person to check and change, then recorded with the note as a typed passage ([`src/ledger_hand/flows/screenshot.py`](../src/ledger_hand/flows/screenshot.py)); at the command line, [`scripts/try_screenshot.py`](../scripts/try_screenshot.py); README, "Recording from a screenshot". Run headless in tests: [`tests/ui/test_page_screenshot.py`](../tests/ui/test_page_screenshot.py), [`tests/ui/test_page_screenshot_failures.py`](../tests/ui/test_page_screenshot_failures.py); against the real vision model: [`tests/live/test_live_vision.py`](../tests/live/test_live_vision.py) | Done; how well real screenshots are read is not measured: none has been tried yet (section 8) |
