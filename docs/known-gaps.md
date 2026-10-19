# Known gaps

Known limits of this program as it stands: places where a trade it
accepts and exports may still be refused by the ledger, where two guards
stand in for each other, where a step that asks the model has a weakness
that is known but not mended, and where the book, the export or the
interface has a rough edge that is known but not yet changed. Each one is
described with the trades or passages it affects; where a choice is needed,
it waits for the project owner. How the model did in the experiments, and
what was not measured, is in `docs/project-report.md`.

## Time zone database versions

**What it is.** A trade known to the minute or second is written with its
offset from UTC and the name of its time zone, for example
`2026-10-05T05:46:00+00:00` in `Africa/Casablanca`. This program works the
offset out from Python's time zone database. The ledger checks it against the
offset its own runtime works out for that zone at that instant, and refuses
the trade when the two differ. The two databases are separate copies of the
same public data, and they are updated at different times. When one copy has
a rule change that the other does not have yet, the two offsets differ for
the zones and moments that change touches.

On the machine this was found on, Python read version 2026c of the database
and the ledger's Node runtime carried 2026a. They differed for
`Africa/Casablanca` and `Africa/El_Aaiun` from 5 October 2026 on, and for
`America/Vancouver`, `America/Edmonton`, `America/Yellowknife` and their old
names `Canada/Pacific` and `Canada/Mountain` from 2 November 2026 on.

**Which trades it affects.** Only trades known to the minute or the second,
recorded in a zone whose rules differ between the two copies at that moment.
Such a trade is accepted by this program and exported, and the ledger refuses
it with "offset must match occurredTimeZone at its instant".

**Which trades it does not affect.** Trades known only to the day: they carry
no offset, and the ledger does not check one. Trades in every zone and at
every moment where the two copies agree, which is nearly all of them.

**Why it is not fixed here.** This program cannot know which copy the ledger
will run with when the file is imported: it depends on the ledger's Node
version or browser. Each way to close the gap needs the project owner's
decision: accepting it as a known limitation, writing no time zone name (and
so losing it), or tying this program to one version of the database.

**How to see the two versions.** The ledger tier of the checks
(`scripts/check.sh ledger`) asks both sides for the offset of every timed
trade in two of its samples, reports where they differ and prints both
versions in a notice marked `!!!`. It does not count those refusals as a
failure, and it counts every other refusal as one. By hand:

```sh
cat /usr/share/zoneinfo/+VERSION                        # Python's copy, on macOS and Linux
node -e 'console.log(process.versions.tz, process.versions.icu)'   # Node's copy
```

When Python uses the `tzdata` package instead of the system's copy,
`python -c 'import tzdata; print(tzdata.IANA_VERSION)'` gives its version.

**One sample of the ledger tier that does not pass on the machine the checks
run on now.** There, Python reads the system's copy of the database, version
2026e, and the ledger's Node runtime (v25.9.0) carries tz 2026a, with ICU
78.2. In Python's copy `EST5EDT`, `CST6CDT`, `MST7MDT` and `PST8PDT` are
zones of their own, whose offsets in the year 1 are whole hours (-05:00,
-06:00, -07:00 and -08:00). Node takes the four names for
`America/New_York`, `America/Chicago`, `America/Denver` and
`America/Los_Angeles`, which before 18 November 1883 kept the local mean
time of those cities, an offset with seconds in it (-04:56:02, -05:50:36,
-06:59:56 and -07:52:58 in the year 1). For a trade at such a moment the
ledger's validator throws an error instead of refusing the trade ("Could
not resolve an offset for time zone: EST5EDT"). The ledger tier exports a
sample with a trade at noon on 2 January of the year 1 in every zone whose
offset is then a whole number of minutes on Python's side
(`attack-earliest-moments.json`, made by `earliest_moments()` in
`tests/export/attack.py` and listed in `tests/ledger_check/cases.py`). The
four names are among those zones, so the validator throws on the whole
sample, which the tier counts as a failure. It takes both at once: Python's
copy holding the four names as zones of their own, and Node's taking them
for the four cities, with offsets in seconds before 1883. With the versions
of the paragraph above, Python reading 2026c and Node carrying 2026a, this
sample was accepted.

It touches only a trade recorded in one of these four zones at a moment
before 18 November 1883, and no crypto trade is that old. The sample and the
tests are left as they are: taking the four names out of the sample would
hide the one place found where the ledger throws instead of refusing, and
finding where the two part ways is what the tier is for. Closing it needs
the project owner's decision: the ledger refusing such an offset instead of
throwing, this program not taking the four names, or the tier announcing
this case as a known difference. The offsets each side gives, from the top
of the repository:

```sh
.venv/bin/python -c 'from zoneinfo import ZoneInfo; from datetime import datetime; [print(z, datetime(1,1,2,12,tzinfo=ZoneInfo(z)).utcoffset()) for z in ("EST5EDT","CST6CDT","MST7MDT","PST8PDT")]'
node -e 'for (const z of ["EST5EDT","CST6CDT","MST7MDT","PST8PDT"]) { const d = new Date(Date.UTC(2000,0,2,17)); d.setUTCFullYear(1); console.log(z, new Intl.DateTimeFormat("en",{timeZone:z,timeZoneName:"longOffset"}).formatToParts(d).find(p=>p.type==="timeZoneName").value) }'
```

## Offsets with seconds in them

**What it is.** Before the 1970s many zones had offsets that were not a whole
number of minutes, such as `+01:16:20` in Budapest in 1890. The ledger's way
of writing a time cannot hold such an offset.

**Which trades it affects.** Only a time built directly with such an offset;
reading a time phrase never produces one. A time known only to the day
carries no offset and is not affected: 1 June 1890 in Budapest is accepted
and exported as `1890-06-01`.

**How it is handled.** The check of a draft refuses such a moment, with the
reason `OFFSET_HAS_SECONDS`, so it never becomes a record. The export keeps
its own refusal, `OFFSET_NOT_WHOLE_MINUTES`, as a second guard: a record
built some other way is refused there instead of failing while it writes.
This is no longer a gap between this program and the ledger; it stays listed
here because the two guards are easy to take for one.

## Judging a passage can stop a real trade

**What it is.** Before extraction, the model judges which kinds of thing a
passage reports (`extraction/screening.py`). When it judges that a passage
reports only things the ledger does not record (futures or leverage, one
coin swapped for another, an order not filled yet, a plan), the whole
passage is stopped and nothing is extracted. The program never lets
through a kind the model named as not recorded.

**Which passages it affects.** A passage about a real, filled spot trade
that the model takes for one of those kinds, for example because it
mentions a plan or an order in passing in a way the model reads as the
whole of it. A passage that the model judges to report a filled spot trade
as well goes on, with the rest shown as a caution.

**What the user can do.** Say it again in other words, so that the filled
trade stands out. There is no way to say "this is a spot trade, record it
anyway": whether to offer one is a decision for the project owner.

## Judging a passage has no score on the final set

**What it is.** The judging step was written and checked against the debug
set only. With `qwen2.5:7b`, the four debug sentences that report only what
the ledger does not record were each stopped, with the kind they were
written as; the 23 debug sentences with trades all went on to extraction;
of the 3 with no trade, two were judged to hold none and one was stopped as
a plan. The final set is kept for the last run of an experiment, and that
run measures extraction only, so this step has no score on sentences it
was not checked against.

**What follows from it.** Its rate of stopping a real trade, or of letting
through what is not recorded, on new passages is not measured. The live
tier of the checks runs the debug set again (`tests/live/test_live_screening.py`).

## Extraction: an English time written in Chinese

**What it is.** Asked to copy the time of an English passage, the model
sometimes writes it in Chinese: `yesterday` as `昨天`. It is the most
common reason a trade did not come out whole in the experiments
(`evals/RESULTS.md`).

**How it is handled.** The phrase is not a piece of the passage, so the
program leaves the time empty, says why, and asks for it. It costs a
question, never a wrong time. `fourth` wrote no English time in Chinese on
the debug and the writings set, but it did not pass the final set, so the
product still extracts with `first`, which does (`evals/RESULTS.md`,
"2026-10-19: prompt experiment four, new examples with English passages and
Chinese numbers, `qwen2.5:7b`").

## Extraction: a total put as the price

**What it is.** When a passage gives what was paid in all, the model
sometimes copies that amount under price as well as, or instead of, under
total. With `first` this happened twice on the debug set, with no issue
about the field (`evals/RESULTS.md`, "A total put as the price").

**Which trades it affects.** When the draft also has a quantity and a
total, the check finds that the amounts disagree and asks which one is
wrong. When the price is the only amount, the check asks for one more of
quantity, price and total, and an answer can then make a record with that
price.

**What the user can do.** The table on the Record page shows the price and
the total side by side, so a total under price shows; "Don't save" leaves
that trade out. The prompt version `price_total` removed this error on the
debug set but lost two other trades, so the rule fixed before the
experiment did not pick it.

## Extraction: the owner's own way of writing

**What it is.** On the ten passages of the voice set, written the way the
owner writes, the prompt the product extracts with, `first`, gets 1 of 10
trades whole with `qwen2.5:7b` (`evals/RESULTS.md`, "2026-10-18: prompt
experiment three, more examples for the owner's way of writing,
`qwen2.5:7b`", "The versions on the voice set"). Its errors there are of
these kinds:

- an amount with U right after it, which is the total, copied as the
  quantity (u02, u10) or as the fee (u06);
- an opinion of several clauses copied in part (u01, u03) or with the mark
  that sets it apart from the trade (u05), another piece of the passage
  copied as the opinion (u09, its first trade), and the opinion of a second
  trade left empty (u09);
- a quantity written right against the Chinese copied with a space added
  (u01);
- the side left empty for a buy said with 买到 or 买了点 (u07, u10).

**Which of them come with no issue.** The amount copied as the quantity has
an issue about it, the quantity with a space added is left empty by the
program, and an empty side is asked for. Six values are wrong with no issue
about them, so nothing is asked about them: the four opinions of u01, u03,
u05 and u09 (its first trade), and u06's fee and its currency.

**What was tried.** Two prompt versions written for these kinds were
measured beside `first`: `second` got 6 of 10 trades whole on the voice set
and `third` 2 of 10, but each got fewer trades whole than `first` on the
debug set, 29 and 30 of 34 against 31, so the rule fixed beforehand picked
neither and the product still extracts with `first` (same section, "The
rule applied to `second`" and "The rule applied to `third`"). One more,
`fourth`, written after their errors as well, got 8 of 10 trades whole on
the voice set and 33 of 34 on the debug set, and the rule fixed before it
picked it; on the final set it got 18 of 22 against 22 for `first`, so it
did not pass, and the product still extracts with `first`
(`evals/RESULTS.md`, "2026-10-19: prompt experiment four, new examples with
English passages and Chinese numbers, `qwen2.5:7b`", "The rule applied to
`fourth`" and "The final set").

## Reading an answer: a word such as "about" may be dropped

**What it is.** When the rules cannot read an answer, the model copies the
piece of it that gives the value. It may leave out a word that makes the
value approximate when the word does not touch the number ("大概买了 2 个"
copied as "2 个"); the program then takes the amount as exact.

**Why it stands.** Nothing catches it: the piece is only checked to be a
piece of the answer. The prompt asks the model to keep such a word when it
stands right next to the value, and the number reader is unsure of an
amount that keeps it. How often it happens is not measured.

## The book after a write was cut off

**What it is.** When the program stops in the middle of writing the book
(the power fails, the process is killed), SQLite leaves a journal file
beside it, `ledger-hand-book.sqlite3-journal`, holding what the book was
before that write. The program's first look at the book cannot write, so it
cannot roll the journal back. When that is the only reason the book cannot
be read, and the file's header, read straight from the disk, is SQLite's
with this program's mark and a version it knows, the program opens the book
once for writing: SQLite rolls the unfinished write back and removes the
journal, and the book is then checked again from the start. That is the one
case in which a file is written to before it is checked; any other file
with a journal beside it is refused as before, and neither is written to.
Four rough edges remain.

- **Refused after the rollback.** The check after the rollback can refuse
  the book for any reason the first look can (a book of a newer version, a
  file that is not this program's book or whose tables are not those of its
  version, a file that is not a database, a damaged book), and the rollback
  has then already written to it: what the file holds cannot be read before
  the journal is rolled back. The book's own message then says that SQLite
  first rolled back a write cut off part way, but the page's sentence for
  the kind, shown before it, is the usual one, and three of them read as if
  nothing had been written: for a book of a newer version it says that this
  program "does not touch it", for a file that is not a database that it
  "was left as it is", and for a damaged book that the program "does not
  write to it". For a file that is not this program's book it says that
  this program does not use it, which holds either way.
- **A folder that cannot be written.** SQLite rolls the book back, but
  cannot remove the journal, which takes a folder it may write to. The book
  is then refused as inaccessible (SQLite's `SQLITE_IOERR_DELETE`), and the
  journal stays; each later opening rolls the book back again, to the same
  bytes, and fails the same way, until the folder can be written.
- **A file this program does not read.** A file whose header, read
  straight from the disk, is not SQLite's with this program's mark and a
  version it knows (a file that is not a database, not this program's book,
  or a book of a newer version) is refused with its journal left beside it,
  and neither is written to.
- **A journal from another book.** Only the book's header is read before the
  rollback, not the journal: SQLite rolls back whatever journal lies beside
  the book under its name, and nothing shows which book wrote it. A journal
  left by another book and put beside a book of this program's is rolled
  back into it all the same, which writes the other book's pages into this
  one; when the result is a sound book, nothing is said.

**What it affects.** When the journal is the book's own, nothing that was
saved is lost: a rollback only takes the book back to what it held before
the write that was cut off. A journal from another book can overwrite what
the book holds.

**What the user can do.** For a folder that cannot be written, make it
writable and open the book again. For a file this program does not read,
keep a copy of the file and its journal together; do not delete the
journal file. A journal belongs to its own book only: when a book is moved
or copied, move or copy its journal with it, and never put a journal beside
another book.

## A change in the time zone database can stop listing and exporting

**What it is.** A trade known to the minute or second is kept with its
offset from UTC and its zone. Reading it back checks the offset against the
zone's rules in the time zone database Python uses then. If a later version
of that database changes the rules of that zone at that moment, the trade no
longer reads back, and every reading of the book that reaches that trade
reports the book damaged: no trade can be listed, and while that trade is
not exported yet, nothing can be exported either. Saving new trades, the
reminder of a passage saved before and the coins confirmed still work, and
once that trade has been exported, the trades not exported yet are exported
as usual.

**Which trades it affects.** Only trades known to the minute or second,
recorded in a zone to which a later version of the database gives another
offset at that moment than the version they were recorded with. Trades
known only to the day carry no offset and are not affected.

**Why it is not fixed here.** Reading such a trade back with a caution,
instead of failing every reading that reaches it, changes what the book
promises about the trades it keeps; the project owner has left it for
later. It shares its root with "Time zone database versions" above.

## Exporting needs hard links

**What it is.** An export file is written under a temporary name and then
given its own name with a hard link, which fails instead of replacing a
file of that name. On a file system without hard links (some removable
drives and network drives), every export fails as not written.

**What it affects.** Nothing is marked as exported when the file is not
written, so nothing is lost; the trades wait for the next export.

**What the user can do.** Point `LEDGER_HAND_DATA_DIR` at a folder on a disk
that has hard links.

## The interface: two sentences that could be better

- **The model failing while it reads an answer.** The page says the kind
  of failure in plain words and asks the question again, but it goes by the
  kind alone: the flow keeps the kind, not the status code or the wait the
  server asked for. So a key refused (401, 403), a request refused (400) and
  a rate limit with its wait are each said there in their kind's general
  sentence, not in the sentence the page uses for them elsewhere. The
  command line (`scripts/record_trades.py`) still prints the reason with the
  kind's code word, such as `(timed_out)`.
- **A setting refused in the environment.** The Settings page opens and
  names the setting and its rule, but the setting cannot be corrected there:
  the environment variable has to be corrected and the program started
  again.

## The experiment tools measure local models only

**What it is.** The experiment tools (`evals/run.py`) use the local plug
only, because they ask Ollama itself for the model's fingerprint, which a
cloud service has no way of giving. So a model on a cloud service cannot be
measured with them. With the cloud plug set (`LEDGER_HAND_MODEL_PLUG=cloud`)
they refuse to start, before anything is sent, and say why.

**What the user can do.** Unset `LEDGER_HAND_MODEL_PLUG`, or set it to
`local`, before running an experiment.

## Reading a screenshot: no guard that the model only copies

**What it is.** When a passage is typed, every phrase the model copies is
checked to be a piece of the passage, so a value the model made up never
reaches a draft. When a screenshot is read, the model writes out the text
it reads off the picture (`src/ledger_hand/extraction/picture_reading.py`),
and that text is the passage extraction then checks against. A value
misread, changed or made up while reading the picture (a digit dropped, a
total read under the price's label, the phone's clock read as the time of
the order) is already in that text, and extraction can only check what was
read against what was read, never against the picture itself.

**What stands in for it.** Nothing in the program can compare text with a
picture. The text read is shown to the person before going on: on the
Record page it waits in a box the person checks and can change before
Continue (`src/ledger_hand/ui/screenshot_panel.py`), and
`scripts/try_screenshot.py` prints it. The check of each draft asks when
the quantity times the price does not make the total. How often a
screenshot is misread is not measured: no real screenshot has been tried
yet, not even by hand.

There is one thinking setting (`LEDGER_HAND_MODEL_THINK`) for both models:
the model that reads a screenshot takes the same as the one that extracts.
Its default was set from `qwen3-vl:8b` extracting the debug set
(`evals/RESULTS.md`, "2026-10-19: the thinking switch, `qwen3-vl:8b`");
whether thinking helps or hurts reading a screenshot is not measured.

## Recording from a screenshot on the page

- **Only PNG and JPEG.** A file is taken by its first bytes; HEIC, WebP and
  any other kind are said to be neither, and nothing is sent. Screenshots
  are PNG on most phones, JPEG on some.
- **One file at a time.** A second screenshot waits until the first is
  recorded or dropped; the upload box is greyed out meanwhile.
- **The limit is the file's size.** `LEDGER_HAND_MODEL_SCREENSHOT_MAX_MB`
  (20 MB by default) is compared with the file's bytes, not with its pixels.
- **The browser does not sort files by kind.** Any file can be chosen, so
  that the program, which reads what the file holds, is the one that says
  whether it is a picture; and the upload box shows Streamlit's own limit of
  200 MB per file, not the program's, which is in the box's help and in the
  sentence said when a file is larger.
- **The uploaded file stays in memory until the browser tab is closed.**
  The picture is never written to disk and is not kept once read, but
  Streamlit keeps each uploaded file in the program's memory until the
  browser session ends. The page empties the upload box by drawing a new
  one, because Streamlit lets no program empty it, and that does not let go
  of the file.
- **The page waits while the picture is read.** Reading can take a minute,
  the first time longer while the model is loaded; only Streamlit's own
  mark at the top of the page shows that it is working.
- **The server is asked for the vision model on every upload.** Two short
  requests (`/api/version`, `/api/tags`) come before each picture is sent,
  so that a vision model that is not there is named before a long wait.
- **A plain picture may be read as nothing, or as a sentence about it.**
  A picture of one colour, uploaded once with the default settings and once
  with a longest reply of 4,096 tokens, came back as an empty reply both
  times, which the page says as "read nothing". How a real screenshot fares
  is not measured. Another picture of one colour, uploaded once more with
  the default settings, was read as one sentence saying that the picture
  shows no order information. Such a sentence is taken as text read, like
  any other: it waits in the box of the text read, and Continue sends it on,
  with the note, unless the person deletes it.

## Extracting with `qwen3-vl:8b`: most replies empty

**What it is.** `qwen3-vl:8b` thinks before it replies, by its own default,
and the plug leaves that default alone unless the thinking setting is
changed. Extracting with it under the settings' defaults, the server's
answer held no text, only the model's thinking beside it, in 25 of the 30
sentences of the debug set and in 9 of the 10 of the voice set; with
thinking off, in every sentence of both (`evals/RESULTS.md`, "2026-10-19:
the thinking switch, `qwen3-vl:8b`"). Such an answer is an empty reply, a
model failure (`malformed_reply`), and nothing of the passage is kept.

**Which passages it affects.** Only passages extracted with `qwen3-vl:8b`,
chosen with `LEDGER_HAND_MODEL_NAME`, on the Settings page or with `--model`
in an experiment; the default, `qwen2.5:7b`, does not think. Reading a
screenshot is another call, with no reply table, and there the reply's text
comes back beside the thinking (next section).

**Why it stands.** The product extracts with `qwen2.5:7b`. Neither the
prompt nor any other setting was tuned for `qwen3-vl:8b`, and with thinking
off every reply was empty, so off did not become the default.

## Thinking off, as Ollama 0.34.3 takes it with `qwen3-vl:8b`

**What it is.** Measured with Ollama 0.34.3 by calls made by hand to its
chat endpoint, with invented questions: `think` set to false does not stop
`qwen3-vl:8b` from thinking. Ollama leaves the opening of the thinking out
of the prompt, but the model writes its thinking anyway, and the server
still hands it back as thinking, about as long as with nothing sent. With a
reply schema (`format`), which every call to judge a passage, extract its
trades or read an answer sends, the whole reply then comes back as thinking,
and the reply's text is empty: so every such call is an empty reply with
thinking off, as every sentence of the two runs in "2026-10-19: the
thinking switch, `qwen3-vl:8b`" was. Without a schema, as a screenshot is
read, the reply's text comes back beside the thinking. `think` set to true
gave the same as nothing sent. `qwen2.5:7b` turns true down with status 400,
saying it does not support thinking, and takes false.

The thinking and the reply also share the longest reply (`num_predict`):
without a schema, a call that thinks long reaches it and comes back cut off,
with its text short or empty. How the record of such a call reads is in
`src/ledger_hand/llm/ollama_reply.py`.

**Why it stands.** It is how the server and the model behave: the plug
sends the field as the setting says and reads the answer as it reads any
other. The default sends nothing, so it applies only when the setting is
changed.
