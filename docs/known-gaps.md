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

## The assistant: what is not there yet

- **The cloud model does not run the assistant.** The cloud plug refuses a
  call with tools before sending anything, naming `LEDGER_HAND_MODEL_PLUG`.
  Whether it should hand tools to a cloud service is a later choice.
- **The demo ledger is still where a new tab starts.** It is an invented
  book in memory with its own way of working out cost and profit, which
  says nothing about the real ledger's. The try-out script, the tests of
  the flows, the measured results and the sentences for a demo all reach
  it. The Assistant page can reach the user's own ledger page instead
  (third part of batch 68; see "The assistant page and your ledger page"
  below), chosen in each tab; `LEDGER_HAND_ASSISTANT_LEDGER=page` makes it
  the first. A proposal on the demo ledger is "confirmed" only by the
  try-out script's `--save` or the page's demo buttons, which work on the
  demo ledger alone. The invented book gives ADA no market price on
  purpose, so its profit on paper is always "not worked out".
- **The line of 95% for choosing what to do is not measured.** Whether
  the model picks the right kind of work (record, ask, change or delete,
  or nothing) for at least 95% of new sentences is to be judged on
  sentences the owner says in their own way, which nobody has looked at
  while writing the prompts. Those sentences have not been written yet, so
  this line has no number. The nineteen sentences of the first step were
  seen while the prompt was written; they are not that test.
- **The model fills the recording tool with arguments it does not take.**
  Measured on the nineteen sentences, the model asks for the right tool
  first every time, but on every trade it records it also hands over the
  trade's figures, which the recording tool does not take. The program
  drops them unread, as it does for every tool that takes no argument, and
  records which were dropped; the call is not a wrong step, and no figure
  the model wrote reaches the ledger. See the last section of
  `evals/RESULTS.md`.
- **Another name for an asset is taken by the program, never the model.**
  For `list_trades` and `get_period_summary` the program checks the asset
  against what the user said, so "比特币" and "BTC" are the same, and so
  for changing, deleting and recording; the names come from one place
  (`core/ledger_table.py`), and the coin table's other names count only
  for a code the ledger has. A time is never taken in another language:
  the user writes "this year" and the model fills "今年", which is a wrong
  step.

## The real ledger's plug (68B2, 2026-11-25)

The plug for the real ledger (`ledger/link_ledger.py`) is built and walked
through a real ledger page by a script with no model, and since the third
part of batch 68 the Assistant page reaches it too. What it does not do:

- **A trade with only its day is not sent, though the ledger takes one.**
  See "A trade said with its day only is not sent" under "The assistant:
  recording a trade": that one entry says it all.
- **A trade in another money than the asset's own is not sent.** The
  ledger then needs the rate between the two moneys (`costRate`), which
  the assistant does not ask for; the plug says so for that trade
  (`HAND_NEEDS_COST_RATE`) and sends the others.
- **A time with seconds is not sent.** The ledger takes a time to the
  minute; the plug says so (`HAND_TIME_HAS_SECONDS`).
- **"bought_with" keeps its old name for the model.** For a holding it now
  holds the asset's own money, which every figure of the holding is in,
  not the money it was bought with; the name is left for the batch that
  changes the prompts.
- **The sums of one asset do not split its profit.** The ledger's sums
  cannot be narrowed to one asset, so the plug adds up what the asset's
  trades paid and brought in itself and takes the asset's profit or loss
  from the ledger's row for it; the ledger gives no split of that row into
  sells and transfers, so both parts are "not worked out".
- **After a timeout or a reload, the plug does not look for itself.** A
  proposal the ledger did not answer in time is never sent again, and one
  the ledger forgot is never called unsaved; in both cases the user is
  asked to look at the ledger. Looking through the trades to guess what
  became of it is not done (68B-R, suggestion 2).
- **A change needs the trade listed first in the same session.** The plug
  keeps the trades as last listed to copy back what did not change; the
  change flow always lists first, so this holds for the assistant.
- **Cash is never handed back.** The plug uses no tool for cash balances
  and works none out from trades; a holding of an asset the ledger lists as
  cash is left out as well. What the user is told is under "The
  assistant: cash".
- **The cost of a holding marked not exact carries a sentence of this
  program's.** The ledger says only that it is not exact; the reason
  shown is taken from the ledger's README (a fee paid in another asset).

## The assistant: cash

The assistant cannot look up a cash balance, a deposit or a withdrawal:
none of the eight tools it hands the model reads one. The ledger added a
ninth tool for cash balances on 2026-11-25; connecting it changes the
tools handed to the model and is left for a batch of its own. Until then:

- **A question about cash is caught from the user's words alone.** Before
  the model is asked, `core/cash_words.py` looks for four kinds: cash or a
  balance named ("现金", "余额", "可用资金", "cash", "balance", "buying
  power"; not "rebalance"; a sentence with a balance in it is judged by
  three rules, see below); how much of a money is still had ("还有多少",
  "还剩", "剩下", "有多少" or "how much ... have", "left", "remaining",
  with a money right beside: a nickname of a money such as "U", "美元",
  "刀", "$", "钱", "money", or the code or name of an asset the ledger
  lists as cash); money put in ("入金", "入了多少金", "充值", "存入",
  "deposit", "top up"; not "买入金额"); money taken out ("出金", "提现",
  "取现", "withdraw"; not "卖出金额"). Every sentence and passage of the
  sets in `evals/sets/` and the demo sentences is tried against it with no
  model, and none may be caught (`tests/evals/test_cash_set.py`).
- **What it does not catch.** It knows only the words above, written as
  above. Measured on 2026-11-25 by the independent check, eighteen
  questions about cash in other words, 4 were caught. Not caught, among
  others: "账户里可用的资金还有多少" (only "可用资金" written together is
  known), "手头还有多少闲钱", "往账户里打了多少钱进去", "提走的那笔钱",
  "充了几次值" (split apart, "充值" is not seen), "我钱包里还躺着多少U",
  "how much money I transferred into the account", "how much did I take out
  of the exchange", "uh how much usdt i got rn", "what's left in my wallet
  in USD", "How many dollars are sitting in my account", and words spelt
  wrong ("现今", "cassh", "balanse"). Also not: "我还能买多少BTC", "how much
  do I have left", "我的U够不够". Such a question goes to the model as
  before.
- **When it is not caught, there is no promise of the fixed words.** What
  stops a made-up figure then is what stood before this catch: the model's
  words beside a table are not shown when they are longer than 300
  characters or hold a number the table does not; with no lookup, a
  figure that looks like an amount is not shown; and the check below. In
  the eighteen above, 8 were stopped by those older checks, none by this
  catch. The holdings and the sums may be laid out instead, each table
  saying under it that it holds no cash balance; the model may also ask
  back, or promise to look up money moved in or out, which it cannot.
- **The check of the model's own words.** With nothing looked up, words
  that name a money anywhere (a code or nickname of a money, "现金", "余额",
  "cash", "balance") and hold any number the user never said in this chat
  give way to the fixed words; the number need not stand beside the money
  ("你的 USDT 余额是 50", "Your cash balance is 50.", "你还有1万美元",
  "You still have fifty dollars.", "USDT 还剩 50 个"; second rework,
  2026-11-25). Numbers are compared by value on both sides: digits
  ("1,000", "1.0"), Chinese numerals ("一千", "五十", "1万", read by
  `core/numbers.py`) and English words for 0 to 99 with "hundred",
  "thousand" and "million" ("fifty", "a thousand", "twenty-five"). A
  figure the user said, in this sentence or earlier in the chat, is let
  through, so a question back ("手续费是 1 USDT 吗？", "你是说一千 USDT
  吗？" after "1000") stays.
- **What that check does not know.** English number words beyond those
  ("one point five", "a dozen", "billion", "1.5 thousand" written apart)
  are not read; nor numbers in other scripts. A number the user said for
  something else passes: after "买了 50 个 ADA", "你还有 50 USDT" is shown
  (not mended in this round). Words naming no money at all ("你还剩 50")
  are not checked. Numbers with three digits or more, or with a point, are
  stopped earlier by the older check of words with no lookup, so a
  question back such as "你是说 1,000 USDT 吗？" is still not shown.
- **That check also turns away good words.** Any answer with nothing
  looked up that names a money and holds a number the user never said
  gives way to the words about cash: a date ("10 月的交易"), a count
  ("一笔", "3 笔交易"), or "one" in "one of them" counts as a number. It
  errs on the side of saying nothing made up.
- **A balance: three rules (second rework, 2026-11-25).** A sentence with
  "余额" or "balance" asking whether the money is enough to buy ("够不够",
  "够…买", "enough … buy", "afford") is cash, whatever it names. Else, if
  it names anywhere an asset of the ledger that is not cash (its code or
  name, letter case aside, or a built-in coin name the ledger's code
  lends, such as "比特币") or holds a word that counts an asset ("股",
  "股票", "币", "个", "枚", "份", "shares", "coins", "stocks", "tokens"),
  it goes to the model as a holding ("余额里 ETH 还有几个", "英伟达的余额还剩
  多少股", "what is the balance on my bitcoin"). Else it is cash ("余额是
  多少", "what's my balance", "USDT 余额"). Only the ledger's own names and
  the coin table's are known: a share the ledger calls MSFT or Microsoft,
  asked as "微软的余额" without "股" or "股票", is taken for cash; so is
  "英伟达的余额" when the ledger's name for it is not "英伟达". A balance
  asked with a counter about cash ("USDT 余额还有多少个") goes to the model.
- **A coin still held is not cash.** "我还有多少BTC" and "我的 ETH 余额还有
  多少个" ask for a holding and go to the model as before.
- **It reads the words tidied.** What the user said is tidied first
  (number words written in digits); the catch reads the tidied words, the
  ones the model would read. The check of the model's words counts as
  said both the tidied words of the chat and the words as said of the
  sentence just said; earlier sentences are kept only tidied, which keeps
  their numbers' values.
- **While a question waits, the words are its answer.** As for every other
  subject ("Changing the subject while a question waits"), a question about
  cash said while a recording question waits is read as its answer.
- **The words for a money are asked of the ledger.** For a sentence shaped
  like asking what is still had, or naming a balance, the ledger's list of
  assets is asked for, once, to know its cash assets and the names of the
  others; when it cannot be asked, the nicknames and the built-in coins'
  names alone are used.

## The assistant: recording a trade

- **No reminder that the same words were recorded before.** The assistant
  hands what the user said to the recording flow without the program's own
  book, since what it records goes to the ledger, not to the book. So the
  reminder the Record page gives ("these words were saved before") is not
  there.
- **An asset the ledger lacks is never added from the assistant.** The
  assistant records only the ledger's own assets: a coin or a share it
  lacks ("TSLA", "狗狗币") is not sent, with the word the user said, and the
  user adds it in the ledger first. No coin is confirmed on the spot, as
  the Record page lets one be.
- **A share's Chinese name is not matched; the user answers with the
  code.** A name of an asset the ledger's list does not hold as it is
  ("微软的股票", "英特尔") is asked about ("which asset was it?"), and the
  user answers "MSFT". The step that hands such a name to the model to
  pick from the list (`extraction/asset_picking.py`) is off
  (`ASSISTANT_PICKS_ASSETS`): measured on the names set on 2026-11-25,
  each of three prompt versions picked a listed asset for names the
  ledger lacks ("雪碧" as PepsiCo or Coca-Cola, "谷歌" and "亚马逊" as
  Apple, "柚子币" as SOL, "可口可乐装瓶公司" as Coca-Cola), and the whole
  assistant sent two shares for "2股微软和英特尔"; the checks of the words
  left over cannot catch a name picked whole. Turned on, a pick is said
  only in the reply; the proposal carries no mark of it.
- **Answering "which asset" with a Chinese name is not understood.** Once
  the program asks which asset a trade was, the answer is read as before:
  answer with the asset's code as the ledger lists it ("MSFT"); "微软" is
  not matched there.
- **Asking, changing and deleting do not match Chinese names.** Only
  recording hands a name to the model to pick from the list; a question
  about "微软的交易", or a change of "微软那笔", finds no asset by that name.
- **A fee taken in an asset named in Chinese is not matched.** Only the
  asset traded is handed over; a fee said as "手续费0.1个英伟达" is not.
- **A ledger of more than 500 assets that can be traded is not handed
  over.** The whole list goes to the model each time; past 500 lines the
  program does not ask, and such a name is asked about as before. 500 was
  set by reckoning, not measured.
- **An English short name that can be written as a code is never handed
  over.** "Pepsi", "Coke" or "Google" can be codes, so the program says at
  once that the ledger has no such asset and asks the user to add it,
  even when the ledger holds PEP under "PepsiCo"; adding it as told would
  make a second asset for the same company.
- **Words left around a picked name are checked only when the model
  leaves them out.** When the model picks out a name and words are left
  around it that are not on the short list of filler words ("的",
  "股票", "公司" and the like), nothing is taken, and the program asks
  which asset it was. When the model copies the whole of what was said
  instead, nothing is left to check: with the step turned on,
  "2股微软A股" was sent as 2 MSFT on 2026-11-25, the model having picked
  out "微软A股" whole.
- **How well names are picked was measured on one set.** The names set
  (`evals/sets/stock_names.json`) and its results are in
  `evals/RESULTS.md`; names said otherwise may fare otherwise.
- **Changing the subject while a question waits.** While the recording
  flow's question waits, whatever the user says next is read as its
  answer. A question about the holdings at that moment is taken as an
  answer that cannot be used, and the same question is asked again. Saying
  "cancel" drops the passage, and the next thing said goes to the model.
- **A trade said with its day only is not sent.** The recording flow keeps a
  trade said with a day and no time of day ("昨天买了 0.5 ETH", "bought
  0.5 ETH yesterday") as known to
  the day, and asks nothing more. Rather than
  make up a time of day, the program leaves that trade out and asks the user
  to say it again with the time it was made (`LeftOut.DAY_ONLY`); the other
  trades of the same words are sent. The real ledger, as connected on
  2026-11-25, does take a trade with its day alone (sample
  `propose-add-date-only`), so leaving it out is no longer for the
  ledger's sake; whether to send such trades is for the product owner to
  decide, and until then they are left out. Such a trade is
  still asked about first like any other: "昨天买了 0.5 ETH，价格 2700"
  ("bought 0.5 ETH yesterday at 2700") asks for the fee, and only once it
  is answered is the user told that the trade lacks its time and is not
  sent, so that answer was given for nothing. Asking for the time first
  would change the order of the recording flow's questions, which this
  round left as it was.
- **Figures copied into the wrong field, with nothing to say.** When the
  model copies an amount into another field and the figures still agree
  with each other, the program has no reminder to give, and the trade is
  sent wrong. Seen with the real model: "今天上午11点在币安0.01个BTC 花了
  950U，手续费0" ("0.01 BTC on Binance for 950 U in all, fee 0") was sent
  as a price of 950 and a total of 9.5 USDT; "今天下午3点在OKX买了0.5 ETH的
  BTC，价格95000U，手续费0" ("bought BTC worth 0.5 ETH") was sent as a buy of
  0.5 ETH. Nothing in the reply warns of it. It waits in the ledger as a
  proposal, which shows the quantity, the price and the total: look at
  the three before confirming. Mending it needs the extraction prompt
  tuned on the owner's own sentences, or a check of the price against the
  day's market price, which the fake ledger does not have.
- **The answer to a question about the fee may not be read.** "手续费1.5
  USDT" ("fee 1.5 USDT") given as an answer was once not read, and the
  same question came again; "1.5 USDT" alone was read. Answers are read by
  the recording flow, the same as on the Record page, which the
  assistant's work did not change; why this one was not read is not yet
  looked into.
- **The question does not show the money already read.** While a trade's
  figures are asked about, the facts listed beside the question leave out
  the money the trade is priced in, even when it was read from the words.
  They are left out so that the facts handed to the model that words the
  question stay as they were for the Record page.
- **Vague words for money: what the rule does not cover.** "美金", "刀",
  "美刀", "$", "buck" and "bucks" may each mean USDT or USD. Such a word
  follows the money the same trade names outright on its own price, total
  or fee; otherwise it is the money of the asset's last trade in the
  ledger, marked as a guess; otherwise the user is asked. Left as it is:
  - only the trade's own price, total and fee count: a money said
    elsewhere in the words ("账户里还剩500 USDT", another trade, the
    model's copy in the currency cells) is not followed, even when the
    user meant it;
  - days are compared, not moments: when the asset's latest day of trades
    used both moneys, the user is asked, whichever came last;
  - a price said with no word for money at all ("价格2400") is asked about
    as before when the ledger prices in two moneys; the last trade is not
    used for it;
  - changing and deleting a trade, and asking the ledger, do not use the
    lists of words for money: there "U" and "刀" are not read as a money;
  - a guess is said in the reply only; the proposal sent to the ledger
    carries no mark of it, and the assistant's record does not keep it;
  - the question asked while a guessed trade still lacks a figure names
    the guessed money ("in USDT?") without saying it is a guess;
  - with the real ledger: a trade's time may be known only to the day,
    which is why days are compared; and one code may name both a coin and
    a share, so the trades should be asked for by the asset's identifier,
    not its code, once the real ledger is connected;
  - a trade paid in euros for a share priced in US dollars ("花了0.46欧
    ……一股81.13美金") cannot be recorded yet: with no euro in the ledger it
    is not sent; with one, the user is asked which money it was in.
- **One more question when the ledger prices in two moneys.** With USDT
  and USD both pricing trades, a price said with no money ("价格94900") is
  asked about ("Which currency was this trade priced in?") before anything
  is sent, and so are a price and a total in two different moneys
  ("90000U", "900美元"). With one money to price in, nothing more is asked
  for a price with no money; a vague word is still never read as that
  money by itself.
- **A share whose code has a point in it cannot be recorded.** A code such
  as "BRK.B" cannot be written as a symbol by the rules this program keeps,
  so the asset is left out of the table, and a trade of it is not sent.
  The same holds for an asset whose code or name is also a word for money,
  such as a share whose code is "U": it is left out, and the rest kept.
- **Money written after a number is read only for the words on the two
  lists.** The words of `MONEY_WORDS` and `VAGUE_MONEY_WORDS` in
  `core/ledger_table.py` are read after a number ("410美元", "100U",
  "60000欧元", "30 bucks"). A money written another way ("60000块",
  "¥60000", "5000 Ft") is not read: the price is left empty and asked
  for, never taken as USDT or USD. "块", "元" and "¥" are left off on
  purpose, since each is said of more than one money. A money the ledger
  lacks is read and the trade is not sent, with the reason.
- **A fee may be taken in money the ledger does not price trades in.** A fee
  in such money (a fee of "1 EUR" with the euro in the ledger) is recorded
  in it; the ledger checks the proposal.
- **Money said where the quantity goes is not sent.** "25U买了点ETH"
  says what was paid in all, not how many ETH. The assistant does not
  guess it is the total: that trade is not sent and nothing is asked
  about it, and the reply says the number and the unit read ("25 U") and
  asks for the trade to be said again with the money as the total
  ("... for 25 U in total"). The other trades of the same words are sent.
  The Record page still keeps 25 as the quantity and only shows the
  reminder that the unit is not the coin. Said again as the reply asks,
  in English ("... for 100 USDT in total"), the trade goes through; in
  Chinese, "今天下午3点在OKX买了ETH，一共花了25U，2388一个，手续费0" ("25 U
  in all, 2388 each") was answered with a question for the quantity
  instead of the quantity worked out from the total and the price, and
  "不知道多少个" ("I don't know how many") could not be read as an answer.
  That is the extraction prompt's way of copying numbers, left to be tuned
  on the owner's own sentences. When the unit holds the coin's name as
  well ("30U ETH"), the reason reads oddly: "its quantity
  was said as 30 U ETH, and U ETH is not ETH"; its wording is not yet
  looked into.
- **A coin asked for after a quantity in another coin.** When the coin is
  left empty and the quantity was said as "0.1个BTC" ("0.1 BTC"), the program asks
  which coin; whatever the user answers is taken, so answering "ETH" sends
  a buy of 0.1 ETH. The reply then says the reminder that the unit is not
  the coin, even when the answer was "BTC" and the reminder no longer
  holds. Holding a trade back was built to leave this case to the question
  as before, since the user answers it; checking the unit again against
  the answer is not built, and the Record page shows the same reminder
  before it asks.
- **Every reminder is said, even one of no use.** Once a proposal is sent,
  turned down, or nothing is sent, the assistant says each reminder of
  extraction, one line each. A normal sentence can raise one: in
  "410美元一股" the "一" is a number no trade used, so a line saying a trade
  may be missing follows. Which kinds are said is one list
  (`SPOKEN_REMINDERS` in `flows/record_words.py`); taking a kind off it
  stops it. In English, when the time was asked for and answered
  ("15:00"), the numbers of the time left in the first words ("15", "00")
  are said as numbers no trade used. On the Assistant page the "一" ("one") of
  such a line, after English words, looks like a dash. Whether to take
  that kind off the list is the owner's call: without it, a trade the
  model leaves out of a passage would go unmentioned too.
- **The Record page still prices every trade in USDT.** Only the assistant
  takes its assets and its money from the ledger's list; the Record page,
  the book and the export keep the built-in coins and USDT.
- **Two sentences about shares are not done.** The assistant judges and
  extracts what the user said with its own prompt versions (`screen-2`,
  `first-3`), written so that a share bought with dollars is read as a
  trade; the Record page keeps the first ones. On the share set
  (`evals/sets/stocks.json`) 16 of 18 sentences are done right and none is
  recorded wrong; the two not done are the open orders below. See the
  share set's section of `evals/RESULTS.md`.
- **The model may answer an open order itself.** Told an order that is not
  filled yet ("在IBKR挂了个MSFT限价单"), the model answered in its own words
  both times on the share set instead of asking
  to record it, so the program's own sentence ("reports only things the
  ledger does not record") is not said; nothing is sent either way.
- **The program cannot stop the model from saying it recorded something.**
  When the model asks to record a trade, the program takes over and the
  model says nothing more in that turn. But a model that does not ask, and
  writes "recorded" in its own answer, cannot be stopped from writing it.
  So every thing said carries the program's own word on what reached the
  ledger, which the script prints as one line each time ("sent to the
  ledger: nothing"), and which an interface is to show the same way.
- **A time said with another zone is not tidied, and is asked about.**
  What is said is tidied before the model sees it (`core/spoken_text.py`).
  When a sentence says, anywhere in it and not only beside a time, a zone
  other than the one trades are recorded in, no time in that sentence is
  tidied (its other numbers still are). That is a zone in `SPOKEN_ZONES`
  that is not the ledger's ("按北京时间算，……", by Beijing time, when the
  ledger's zone is Budapest); 时区 (time zone), 东X区 or 西X区 (the zone X
  hours east or west); a Latin name such as UTC, GMT, EST, CET or JST; and
  every 时间 (time), unless it is the ledger's own zone as the table says
  it ("匈牙利时间", Hungary time; "布达佩斯时间", Budapest time), with 的
  (of), 那边的 or 这边的 (over there, over here) allowed between ("匈牙利的
  时间"). Any other 时间, a place or not, holds every time of the sentence
  back: "北京的时间" (Beijing's time), "美股交易时间" (US stock trading
  hours), and also "成交的时间是……" (the time it was filled is ...) or
  "下午时间" (afternoon time), which name no zone. **This is a price paid on
  purpose:** a sentence with 时间 in it, other than the ledger's own zone,
  has its Chinese time read as before, not at all, and the user is asked
  for it. A list of words let through was tried and dropped (2026-11-25):
  every word on it let some zone through ("时间是美东", "按纽约那个时间").
  So a time is sometimes held back that need not
  be. The program does not read a zone said in words, so tidying the year
  alone would let the model copy the clock time without the zone, and the
  time would be read in the ledger's zone, hours off. Left as said, the time
  is not read and the user is asked for it, as before. The ledger's own zone
  said apart from the time ("按匈牙利时间算，……") is kept in the words, and
  the time is tidied. To take another zone, the reading of times has to
  learn zones. A zone said with neither 时间 nor 时区 nor a Latin name
  ("按国内算下午三点", by home reckoning three in the afternoon; "北京下午三点",
  Beijing three in the afternoon) is not seen at all: the time is tidied and
  read in the ledger's zone, hours off. That wording is not dealt with here.
- **Some numbers are not tidied, and stay as said.** These are left as
  they were said, and read as before or asked about:
  a number ending in 一 that may be the start of the next word ("三十万一个",
  three hundred thousand, or three hundred thousand and ten thousand, each;
  "零点零一五一个BTC", 0.0151 BTC or 0.015 BTC each; even "二十一个BTC",
  21 BTC, which was read already); a number with a unit and then more of
  the amount ("二十块五", twenty and a half; "十二个半", twelve and a half;
  "410美元一股", 410 dollars a share, since a number word follows the
  unit); a decimal with exactly three digits after the point ("一点二三四",
  1.234, which may be a thousands mark); a point that may be a clock or a
  decimal ("八点二五", 8:25 or 8.25); a minute of one word without 分
  ("三点五", 3:05 or 3:50); a rough amount ("大概五十", about fifty) and a
  share ("百分之三十", thirty percent); a number with a unit, a gap and more
  of the amount ("二十块 五", "二十U五"). A time is left as said when a
  minute follows past a filler ("三点的五十分", three o'clock and fifty
  minutes), and a clock of one word after 点 with 分 and nothing else of a
  time ("零点五分", which may be half a cent; "二十点五分钟", twenty and a half
  minutes). The first two kinds are the ones
  that most often reach the ledger's flow as said; a later step is to mark
  them.
- **Seconds are dropped from what is said in Chinese, not from English.**
  A time said in Chinese reaches the ledger to the minute: "十二分三十一秒"
  (twelve minutes thirty-one seconds) is tidied to "12分", and "14:12:31"
  to "14:12", when said among Chinese words. Words with no Chinese
  character are not tidied at all, so "9:40:15" in an English sentence
  still reaches the ledger with its seconds.
- **A screenshot's text is not tidied.** The text read off a screenshot and
  the note typed beside it are recorded as they are; only words typed or
  answered to the assistant are tidied.
- **A note or a platform copied from the words tidied keeps the digits.**
  The model copies from the words tidied, so a note said as "第二十一次加仓"
  (the twenty-first addition to the position) reaches the ledger as
  "第21次加仓". The words as said, kept with each trade, are not touched.

## The assistant: changing and deleting

- **One trade and one part at a time, and the rest not always told.** A
  change or a deletion touches one trade, and a change one part of it.
  Changing many trades at once is not built. When one thing said asks for
  two (two trades, two parts, or a change and a deletion), only one is
  done. The program says what else was not done only when the model asked
  for it as a second call in the same step. More often the model makes one
  call only ("删掉10月6号和10月21号那两笔BTC" gives one call, for 10月6号;
  "数量改成0.0081，成交价改成62000" one call, for the quantity), and then
  nothing is said about the other one.
- **Measured: 13 of 17 done right, none done wrong.** On the set of
  changes and deletions (`evals/sets/edits.json`), at the latest run, 13
  of 17 sentences ended with the right proposal or the right refusal and
  none sent a wrong one (`evals/RESULTS.md`, "2026-11-25: a cut period
  judged by the sentence just said first"). The four not done, each
  sending nothing: a month copied out of a day ("把11月3号那笔ADA的备注改成
  补仓", "change the note of the ADA trade of 3 November", the model
  copying "11月", "November"), where the program asks for the date
  again; the model listing the trades and asking in its own words instead
  of calling the tool ("把10月卖出的那笔删掉", "delete the one sold in October"), which the system prompt's
  line on listing before a change invites; an English day written in
  Chinese ("Delete the BTC sell from October 21", copied as "10月21号");
  and a time of the model's own where none was said ("把ADA那笔的平台改成
  Binance", "change the ADA trade's platform to Binance", copied as
  "今天", "today"). So about one change in four is not done the
  first time, and the user is asked back or told to say it again. Not
  mended in this round: raising it needs a new version of the system
  prompt (without its line on listing first, and asking for the whole
  time), which changes two tests that hold the default version and means
  measuring every ruler again; that is left for tuning on the owner's own
  sentences.
- **A time cut short is a wrong step, not a narrower lookup.** A period
  the model copied that stands cut out of a longer time in the sentence
  just said ("9月", September, out of "9月13号", 13 September) is not
  taken. For a lookup it is a
  wrong step, handed back to the model; for a change or a deletion the
  program looks nothing up and says at once its fixed sentence asking for
  the date again. Only when the copied words are not in the sentence just
  said are the sentences before looked at, and there a period that stands
  alone counts as copied. Nothing in the user's words is looked for in its
  place, so the model has to copy the whole time. "10月6" copied out of
  "10月6号" ("6 October") is taken as cut too, and gets that fixed sentence. It also
  stops one that should go through: after "9月我买的BTC" ("the BTC I bought in
  September"), "把那笔BTC的时间改成9月13号上午10点" ("change its time to 13 September, 10 a.m.") with the
  model's "9月" is asked again, since the only "9月" in it is part of the
  new time; the user has to say it once more. Left as it is: the only
  cost is saying it again, and nothing wrong is proposed.
- **A longer time the program cannot read is not seen as cut.** The check
  stretches the copied words and reads the stretch as a time; when the
  longer words are ones it cannot read ("11月下旬", late November; "10月初", early October; "9月底", the end of
  September), no
  stretch reads, and a month the model copied out of them ("11月") is
  taken as it stands. "把11月下旬那笔ADA删掉" ("delete the ADA trade of late November") with
  the model's "11月" then
  finds the only ADA trade of November, on 3 November, and proposes to
  delete it. The user sees which trade: the program's reply shows its day
  and figures, and so does the proposal waiting in the ledger, which does
  nothing until the user confirms it on the ledger's own page. Telling
  these words apart would need a list of words such as "下旬" (the last
  third of a month), "月初" (the start of a month), "月底" (the end of a
  month), one word at a time, and is not built: such a list is never
  complete, as the same attempt for questions showed. Three more ways of saying
  it can let a month the model copies stand, and send the change for the
  only trade of that month whatever day the user meant; they were made
  with a scripted model, not seen with the real one: a sentence with the
  month said alone a second time ("把9月13号那笔BTC的备注改成9月定投",
  "change the note of the BTC trade of 13 September to 'September
  plan'", "9月" also in the new note); the month said alone two sentences before
  and the day in the sentence between ("9月我买了什么", "what did I buy in
  September"; "9月13号那笔是什么", "what is the one of the 13th";
  "把那笔BTC删掉", "delete that BTC trade"); and the month and the day said in two sentences ("9月我
  都买了什么", "what did I buy in September", then "把13号那笔BTC删掉",
  "delete the BTC trade of the 13th"). The same safeguard holds: the reply
  and the waiting proposal show which trade. They are not mended for the
  same reason: the check cannot tell them from a month said on purpose
  without more rules of that kind.
- **A side the model picks wrong is taken as it stands.** The side is a
  choice from a list, so it is never refused: "把9月25号那笔ADA删掉" ("delete the ADA
  trade of 25 September") for a buy
  was once given `sell` by the model. Then no trade matches, and the user
  is told so with the side looked for. The program does not look again
  more widely when nothing matches, so as never to find a trade the user
  did not name; the model's choice of side cannot be checked against the
  words.
- **A day copied from the new time, not from the trade's.** In
  "把9月13号那笔BTC的时间改成9月12号上午10点" the model may copy "9月12号",
  the day of the new time, as the day of the trade to find. The words are
  the user's and are taken; the trade of 12 September is found and the
  change proposed for it. Again the reply and the waiting proposal show
  which trade, and nothing changes until the user confirms it.
- **Changing the subject while a question waits.** While the program waits
  for which trade, or which amount follows, whatever the user says next is
  read as the answer. A question about the holdings at that moment is not
  an answer the program can read, and the same question is asked again.
  Saying "cancel" drops the change.
- **Ways of saying which trade that are not read.** Only a number ("2"),
  "第" and a number with or without "笔", "个", "条" or "项", English
  ordinals to the tenth ("second", "2nd", "the second one") and the last
  one ("最后一笔", "the last one") are read. "BTC那笔", "早上那笔", "the one
  from Binance" and "两笔都删" are not, and the question is asked again.
  At most ten trades are listed to choose from; with more, the program asks
  the user to say more and waits for nothing.
- **A time of day with no half of the day is not taken.** "10月2号9:25" is
  read with a caution (no morning or afternoon was said), and a time read
  with a caution is not put into a trade; "10月2号上午9:25" or "21:25" is.
- **"U", "刀" and "美元" are not taken for USDT beside a new value.** A unit
  counts only when it is the ledger's own code, name or another name the
  coin table gives that asset. Whether these words name USDT is not
  settled, so "手续费改成0.3U" changes nothing on a fee taken in USDT.
- **A unit the model leaves out is not seen.** The program reads the new
  value the model copied. When the user wrote "0.4U" and the model copies
  "0.4", the unit is gone before the program reads it, and the number is
  put in as it stands.
- **The model often answers in words instead.** Measured on the set of
  sentences that change or delete, the model sometimes writes a time of its
  own ("今天" where none was said), is told, and then asks the user in
  words instead of calling again. See the last section of
  `evals/RESULTS.md`.

## The assistant: asking the ledger

- **What it cannot answer.** Only four kinds of question are answered: the
  trades, the sums of a stretch of time, what is held now, and the assets.
  The ledger does not hand over, and the program does not work out, how
  much the holdings grew between two days ("我11月底的资产比11月初多了多少"),
  what was held on a past day, a price to come, or whether to buy or sell.
  The model is told to say so and call nothing; it does not always, and it
  may call a tool with words the program cannot read, which the program
  then says.
- **Time words it does not read.** The program reads one day (what the
  time reader takes as a day), a month, a year, a week from Monday, days
  counted back ("最近7天", "last 7 days") and a start and an end of those.
  It does not read "月初", "月底", "上半年", "Q3", "this quarter", "最近一周",
  "最近一个月", "past week", "since October", "10月以来", "至今", or a time
  of day ("昨天晚上9点"); each is answered "I could not read". "12月" said
  in November is not guessed at: the user is asked to say the year. "10/6"
  is not read either, as month and day differ by place. Four digits alone
  ("2026") are not read as a year, since a price or a quantity looks the
  same ("我有1000个ADA", "bought at 2446"); a year needs "年" after it or
  "in", "during" or "year" before it, or a month before it ("Oct 2026").
  "May" and "March" alone are not read as months ("May I see ..."); they
  need a year or a day after them, or "in", "during", "last" or "this"
  before them, or a range that begins with "from" or "between". So "March
  to April" is read as April only, and "since May" not at all.
- **A time asked in English and translated by the model gets no table.**
  The time is taken only from the model's copy of the user's own words. Asked
  "How much did I spend on ETH this year?", the model copies "今年", which is
  not the user's words: it is a wrong step, the ledger is not asked, and
  what the model is handed back holds the user's sentence and asks for the
  time in the user's language. When the model writes it wrongly again, or
  answers in words instead, the turn ends with a sentence and no table.
  "Oct 1 to Oct 15" and "September" go the same way, and so did "Which
  trades did I make on 6 October 2026?", whose day the model wrote as
  "6十月2026" (the month in Chinese characters). The sentence it ends with may be the program's own "I can
  only answer from your ledger ...", which reads as if the question were
  not about the ledger at all; or the model may pass on to the user the
  words it was handed ("Copy the time from your question exactly as it is
  written there ..."). With no time from the model the lookup covers all
  time. Asked in English, a question with no time, or with the time in
  Chinese, is the way to get a table; the demo sentences in the README
  are chosen so. Not mended: having the program find the time in the
  user's sentence itself was tried in this round and taken out again,
  because each check found words it took for a time that were none
  ("1000个ADA", "1000 ADA"; "May I"; "until October"). Another way, such as tuning the
  prompt or reading the time back to the user first, is the owner's call.
- **Measured: 23 of 27 questions looked up right.** At the latest run of
  the twenty-seven questions (`evals/sets/asks.json`), 23 came back with
  the right table, and none with a table narrower than asked or off
  (`evals/RESULTS.md`, "2026-11-25: a cut period judged by the sentence
  just said first"). The four with no table: two English times the model
  translated ("How much did I spend on ETH this year?", "How much profit
  did I make in September?"), and two where the model asked back in words
  instead of calling a tool ("去年我交易了几笔", "how many trades last
  year"; "今天我买了什么", "what did I buy today"). On eleven more questions
  written to try times and numbers (`evals/sets/asks_times.json`), 2 of 11
  came back with a table at their last run, none narrower or off
  (`evals/RESULTS.md`, "2026-11-24: after taking the finding of a time in
  the sentence out"): most of them name no time but hold a price or a
  quantity, which the model copied as the time or answered in words.
  Both are the model's part, left for tuning the prompt on the owner's own
  sentences, or for another model.
- **A price copied as the time is said as a time not read.** "Which ETH
  did I buy at 2010 USDT?" got "I could not read '2010 USDT' as a stretch
  of time", which says nothing about the price the user meant. The
  program does not guess what words it cannot read are; telling a price
  from a time in what the model copied is not built.
- **A time said in an earlier sentence is taken.** A period counts as
  copied when it is in anything the user said in this chat. Asked on, a
  model that copies the "10月" (October) of the question before, where this
  one says "9月" (September), looks up October; the header shows which
  month. The rule lets a question asked on use the time said before;
  preferring a time in the sentence just said would change that rule, and
  was left for a later decision.
- **A question none of the four answers may be met with "say it another
  way".** "我11月底的资产比11月初多了多少" ("how much more did I hold at the
  end of November than at its start") may get "I could not read '11月初'
  ..., please say it another way", which suggests that other words would
  get an answer; none would. Adding what can be answered to that sentence
  was suggested and not done in this round; not yet looked into further.
- **A tool's name written out as the answer.** Now and then the model
  writes a tool's name, or "call list_trades with ...", as its reply
  instead of calling it. Under the default prompt this is rare; the user
  then sees that line and nothing done. Taking such a reply for the call
  would change what the program does with the model's words, which the
  work on asking left out.
- **A word the model copies as a time is taken as one.** When the model
  copies a word of the user's as the time and the program can read it, the
  table is narrowed by it and the header shows the days. In "我一月一次定投
  BTC，一共买了多少" ("once a month"), a model that copies "一月" gets
  January; in "How much ETH did I buy until October?", a model that copies
  "October" gets October alone, not everything up to it. Not mended: no
  rule on the program's side tells these words from a time asked for.
- **The side is kept from the time before only one step back.** "那ETH呢",
  asked after "10月我卖了哪些BTC", names no side, so the side of the
  sentence before is kept, as the asset is. A side said two sentences back,
  or in a sentence that named both sides, is not.
- **The model's words often give way to the program's.** Beside a table
  the model tends to add numbers up, round them or say them again wrongly
  (adding two moneys together, writing a fee ten times too large); every
  number it writes must be in the table, the ledger's answer or what the
  user said, or the program's words "Here is what the ledger returned."
  are shown instead. Words longer than 300 characters are not shown
  either. A numbered list counts too: the "1" of "1." is a number not in
  the table, so a list the model writes is often replaced by those words.
  The check takes every number written in digits, as it was built to;
  leaving a list's numbering out of it is not built.
- **A loss written as a gain is not caught.** The check looks at the
  numbers only: not at a sign before them, and not at words such as
  "赚", "亏", "profit" or "loss". So "你赚了 12.5 USDT" passes beside a
  table whose realized figure is -12.5 USDT. The table itself is always
  the ledger's own. With no table, any figure with a
  decimal point or three digits or more ("2026") turns the answer away.
- **A general word that is a code.** "coin", "crypto", "token", "stock"
  and a few more are never taken for an asset's code, so a ledger asset
  with one of them as its code cannot be named by it.
- **An English code beside a digit is not found.** An asset code in Latin
  letters is found only as a whole word, with no letter or digit beside
  it, so "0.5BTC" does not name BTC.
- **Only the latest twenty trades are shown.** A longer list shows the
  latest twenty and says how many there are; the model is handed the same
  twenty.


## The assistant page and your ledger page (68B3, 2026-11-25)

What reaching the ledger page from the Assistant page does not do yet:

- **No cash.** The ledger tried here (`dev@a6ba639`) has no tool for a
  cash balance, so the assistant says it cannot look one up (see "The
  assistant: cash"). The ledger's `dev` has since added one (`5762751`);
  this program does not use it yet.
- **A trade in another money than the asset's own is not sent.** The
  ledger then needs the rate between the two moneys, which the assistant
  does not ask for (see "The real ledger's plug").
- **A trade said with its day only is not sent, though the ledger takes
  one.** See "A trade said with its day only is not sent".
- **After a timeout or a reload, the assistant only says it cannot tell.**
  The ledger's rules for an assistant (its `assistant-link/README.md`,
  "Rules an assistant must keep", 4 and 5) ask it to look through the
  trades with `list_trades` itself before telling the user anything when a
  proposal timed out or is "not found" after a reload. This program does
  not: on the card, and in the chat, it says that the proposal may already
  be there, or that its result can no longer be looked up, and asks the
  user to look at the ledger. What is missing is that one look by the
  program; the user is never told a proposal was not saved.
- **A ledger page left in the background overnight was not tried.** The
  ledger warns that the browser may pause a background tab, which drops
  the connection; the block then says the page disconnected. Whether a
  page left a whole night still answers was not tried.
- **"bought_with" keeps its old name for the model.** See "The real
  ledger's plug"; left for the batch that changes the prompts.
- **A fee paid in the asset itself can be said oddly in a sum.** In the
  sums of two moneys, the fees of each group now handed to the model made
  one reply say "spent 0.0000082 BTC on BTC" for a fee paid in BTC (seen
  in the second part's acceptance). This is the model's wording; mending
  it means changing the words sent to the model, left for the batch that
  changes the prompts (file 69 of the owner's notes).
- **One link for the whole program.** The link's port is fixed, so every
  tab shares one; Stop in one tab stops it for all, and the others say so.
  Two copies of this program on one computer find the port taken; the
  second says so and starts nothing.
- **The state of the link is read when the page is drawn.** It is not
  pushed to the page: a disconnection is seen the next time the page is
  drawn, or when Refresh is pressed.

## The assistant page

- **The chat is forgotten when the tab closes.** The Assistant page keeps
  its chat, what was said in it and its proposal cards for as long as the
  browser tab is open; only the assistant's record (below) keeps what was
  said on disk, and the page cannot be filled again from it. A new tab, a restart
  or New chat starts from nothing; the proposals already sent stay in the
  ledger. On the demo ledger they then wait unseen, and saving another
  proposal can make them void; pressing New chat several times in a demo
  leaves several such proposals behind. Not changed in this round, with
  the other rough edges of the page below; it touches no figure.
- **A proposal is confirmed only on the ledger's own page.** The page shows
  where each proposal of its chat stands (with the demo ledger asked each
  time it is drawn, with the ledger page only when "Check with the ledger"
  is pressed), but it cannot save or reject a proposal in a real ledger,
  and has no form to change a proposal's figures: a wrong one is rejected
  and said again.
- **The demo buttons work on the demo ledger alone.** "Save in the demo
  ledger" and "Reject in the demo ledger" are drawn only when the parts say
  the ledger is the demo ledger (an invented book in memory), so the whole
  path can be tried before the real ledger is connected. Whether they stay
  is the owner's call; removing them changes one place of the page. The
  demo ledger lives as long as the browser tab: it is kept when a setting
  is changed, and starts again from the invented book in a new tab.
- **The cloud model does not run the assistant.** With the cloud plug set,
  the page says so in one fixed sentence, greys the input out and sends
  nothing; a screenshot is turned down as on the Record page.
- **What a tool handed back is cut short under "How this was done".** Each
  result is shown as one line of at most 160 characters with how long it is
  in all; the tables above it show what the ledger found in full.
- **How many times the model was asked is not exact.** The count under a
  reply leaves out a call to word a question that failed (the program's
  own question is used then), and for a screenshot it counts the reading
  of the picture with the recording's calls. The count is the recording
  flow's own record of its calls, which the assistant's work was not to
  change.
- **Words that can be read two ways.** After "Save in the demo ledger",
  the chat line still says the proposal was sent "waiting for you to
  confirm", which was so when it was sent, while its card beside it says
  saved. A card names a trade by the demo ledger's own number ("delete of
  trade t-03"), not by its day and asset. In the sums of a stretch of time,
  the fees' line stands in the column of realized profit or loss, under a
  money, so it can look like a second line of that money. The question for
  the money a trade is priced in has no buttons for USDT and USD; the answer
  is typed. None of these changes a figure. Mending them means changing
  the fixed sentences of asking, changing and deleting, already checked,
  or how the page looks, each to be checked again; they are left for the
  owner to pick from.
- **The English is not checked by a native speaker.** Every sentence the
  program says, on the pages and in the scripts, was written by this
  project; none has been read by a native speaker of English. Why not:
  not yet looked into.
- **A screenshot may need a longer reply to be read.** With the longest
  reply at its default, 1,024 tokens, the vision model read nothing off a
  clear, invented picture of an order, on the Record page and the Assistant
  page alike, also with thinking off; at 4,096 it read it. That was one
  picture, tried once: it does not promise that every screenshot is read
  at 4,096. Before recording from a screenshot, try setting
  `LEDGER_HAND_MODEL_MAX_REPLY_TOKENS` to 4096 on the Settings page. The
  default, 1,024, was set for extraction's reply and was left as it was;
  whether to raise it for reading screenshots is not yet looked into.

## The assistant's record

- **The record is plain text.** `assistant-record.jsonl` in the data folder
  holds what was said to the assistant, word for word, with its numbers,
  and is not encrypted. It stays on this computer and out of Git; the
  Settings page and the README say so. Whether it should be encrypted, or
  kept at all, is the owner's call.
- **Two tabs writing at the same moment may lose one entry.** Adding an
  entry reads the whole file first, and when the most kept is reached, the
  entries kept are written to a new file that then takes the old one's
  name. When another browser tab adds its entry between the read and the
  new name, that entry is lost. One person on one computer seldom says two
  things in two tabs in the same instant, so this is accepted; the file is
  never left half-written by it.
- **It cannot be looked through on a page.** The Settings page shows where
  the file is and how many entries it holds, and clears it; reading the
  entries means opening the file.
- **A last entry with no line end is dropped.** The program writes each
  entry with its line end in one write, so an entry with none is taken for
  a line cut off half-way and cut off before the next entry, even when it
  is whole. That happens only when a write is cut off at the very end, or
  when the file was edited by hand; the entry is then lost without a word.
  Only a last line cut off half-way was to be cut, and a line with no end
  is taken for one; keeping a whole entry with no line end instead is the
  owner's call.
- **The record says how a proposal stood when it was sent, not after.**
  Each entry keeps the proposals sent as waiting; whether one was later
  saved or rejected is the ledger's to say.
