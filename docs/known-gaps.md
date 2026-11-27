# Known gaps

Known limits of this program as it stands: places where a trade it
accepts and exports may still be refused by the ledger, where two guards
stand in for each other, where a step that asks the model has a weakness
that is known but not mended, and where the book, the export or the
interface has a rough edge that is known but not yet changed. Each one is
described with the trades or passages it affects; where a choice is needed,
it waits for the project owner. How the model did in the experiments, and
what was not measured, is in `docs/project-report.md`.

## What you will meet (the assistant, at the end of the round, 2026-11-26)

A summary only, the most costly first: what a user of the assistant will
see. Each item's detail stays in the section it points to.

- **A wrong figure can still reach a card with no mark of its own.** On
  the exam said the owner's way, hidden halves, at the end of the round
  (totals only): as said, 2 wrong figures with no mark, where the line is
  none, and 33.3% of 12 trades saved with no cell changed (no line); a
  little tidier, none, but 63.6% of 11, under its line of 80%; tidy, none
  and 100% of 8, both lines met (`evals/RESULTS.md`, "The hidden halves,
  three tiers, at the end of the round"). The kinds seen on the practice
  halves, with made-up figures: a number the user said that the model did
  not copy, the cell worked out from the other two a hair off it (150 said,
  150.00078 sent; 0.2314547 said, 0.23145469 sent), marked only "worked
  out by the program"; and what was paid in all copied as the price (950
  U for 0.301823 ETH sent as a price of 950), which is less than five
  times off the market price and so not marked suspicious ("The assistant:
  recording a trade", "A figure worked out a hair off the one said keeps
  the figure worked out" and "Figures copied into the wrong field, with
  nothing to say"). Comparing other local models is left to the owner.
- **A time said in another zone is written in the ledger's zone, marked,
  not converted.** When the words name another zone and the time is
  written so the model can read it, the trade is sent with that clock time
  in the ledger's zone (Budapest): "按北京时间算，2026年11月20号下午3点在OKX买了0.1个ETH，成交价2700 USDT，手续费0.1 USDT"
  (invented; by Beijing time, 3 p.m.) is sent as 2026-11-20 15:00
  +01:00, and so is the same with the date and time in Chinese number
  words ("二零二六年十一月二十号下午三点"). Since 2026-11-27 its time cell is
  marked suspicious, the reason naming the words said ("北京时间") and the
  ledger's zone, and the reply says the time was not converted; the user
  fixes it on the ledger's page. The program still converts nothing. A
  zone said with neither 时间, 时区 nor a Latin name ("按国内算", "北京下午三点")
  is not seen, and gets no mark ("A time said with another zone is not
  tidied").
- **Buy or sell the model filled in itself is not marked.** Words that say
  neither are sometimes sent as a buy, with no mark on that cell ("The
  assistant: recording a trade").
- **Euros and dollars both said as the total, with no FX fee, are
  recorded in dollars, unmarked.** "128欧元（约139美元）" may be sent as
  paid 139 USD, so the ledger would take dollars, not euros; at most a
  reminder names 128 as a number not used. The share price said with
  "每股" instead of "一股" was sent in dollars the same way, its fee in
  euros marked suspicious ("The assistant: trades paid in
  another money", "Euros and dollars both said as the total").
- **A share's Chinese name is asked about once, then matched by the
  answer kept; the table is off.** "微软", "可口可乐" get "which asset was
  it?" once, and the code answered is kept for the next time. The
  program's table of about eighty common companies is off by default:
  with it on, "2股微软和英特尔" was sent as two shares. The step that lets the model pick from the
  ledger's list stays off, since it picked listed shares for names the
  ledger lacks ("The assistant: recording a trade", "A share's Chinese
  name is matched by a table and by answers kept").
- **The owner's long euro sentences are asked twice before a card.** On
  the practice halves, four of five were first asked buy or sell, then
  which asset; the fifth came back empty from the model. A sentence with
  the code and "买了" (the euro sentence for a demo in the README) goes
  through at once ("The assistant: trades paid in another money", "The
  owner's long euro sentences are first asked buy or sell").
- **The first trade paid in euros has no rate to be compared with.** A
  euro amount said one place wrong (128 said as 12.8) is then not marked;
  the reply says nothing was compared ("The rate's reference is the
  ledger's latest such trade, as listed").
- **After a share was bought for euros, "美金" for it is taken as the
  share's own currency, a guess.** Since 2026-11-27, once the last KO trade
  was paid in euros, "一股70美金" for KO is taken as KO's own currency in the
  ledger (US dollars), marked assumed, the reason naming that currency and
  the last KO trade's EUR, and the reply says it is a guess; a new KO trade
  paid in euros with "一股70美金" goes with its rate the same way. Only when
  the ledger names the asset's own currency and it is USDT or the US dollar
  the ledger prices in: an asset with no own currency named, or one priced
  in another money (DOT in EUR, invented), is left as before (money empty
  and marked suspicious, or asked which money). With no trade of the asset,
  or two moneys on its last day, nothing changes ("\"美金\" for the share
  price follows the asset's last trade").
- **One go and two answers can record different moneys, with a ledger
  that takes no cards.** "每股400刀" with the fee "1 USDT" said in the same
  sentence is all USDT; with the fee given only as an answer to the
  question for it, the price stays the guessed US dollar and the fee is
  USDT, its money marked suspicious ("the fee is in USDT, but this trade
  is recorded as paid in USD"). A ledger that takes cards (the demo ledger,
  and the real one now) asks no fee: the fee is sent empty, so this is not
  met there ("Vague words for money: what the rule does not cover").
- **A time said with "时间" or "时区" in the sentence may be left empty.**
  "成交的时间是二六年十一月二十号下午三点，……" keeps its Chinese time as said;
  when the model cannot read it, the card is sent with its date empty, and
  the reply names it, to be filled in on the ledger's page (a ledger that
  takes no cards asks for the time instead). "匈牙利时间" and a time with
  neither word are read ("A time said with another zone is not tidied").
- **Some money moved is not recognised.** "把0.1个ETH提到了钱包" is not
  read as a withdrawal and goes to the model like any sentence; a deposit
  or a dividend that names a coin or share ("入金了0.5个BTC", "KO分红了2.1美元")
  goes to the model too, which may propose a buy, and the reply ends
  with the line to record the rest by hand ("The assistant: money
  recorded by hand", "Moving a coin in is handed to the model").
- **The real ledger was not tried this round.** The ledger tier of the
  checks (`scripts/check.sh ledger`) was not run in this round, and the
  plug's changes of the round (market prices asked, a day sent alone,
  cells left empty and their marks, cash balances, the rate) were tried
  only against answers written from the ledger's README and tests, never
  on a running ledger page ("The real ledger's plug" and "The assistant
  page and your ledger page").

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
- **The line of 95% for choosing what to do is measured on recording
  only.** Whether the model picks the right kind of work (record, ask,
  change or delete, or nothing) for at least 95% of new sentences is
  judged on the exam said the owner's way, whose hidden halves nobody
  looked at while writing the prompts: the first tool was right on 35 of
  35 enabled recording sentences there, once, and the line is reported,
  not held (`evals/RESULTS.md`, "At the end" and "The hidden halves, three
  tiers, at the end of the round"). The nineteen sentences of the first
  step were seen while the prompt was written; they are not that test.
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

- **A change of a trade known only to its day sends the day alone.**
  When a trade in the real ledger holds only its day and the user changes
  its day, the plug sends `occurredDate` alone; before, it refused. The
  ledger's README does not say how a trade with a day alone is changed,
  and no test covers this path yet.
- **A trade in another money than the asset's own goes only with its
  rate.** The ledger then needs the rate between the two moneys
  (`costRate`). Since 2026-11-26 the assistant works one out for a trade
  that goes the way of "The assistant: trades paid in another money"
  below, and the plug sends it as it is; any other trade in another money
  than the asset's own reaches the plug with no rate, and the plug still
  says so for that trade (`HAND_NEEDS_COST_RATE`), sending the others. Its
  words still say the program "does not ask for" the rate, which is no
  longer true of every such trade; the words were left as they were, the
  plug being another session's file. The plug's samples for a trade paid
  in euros were written from the ledger's README and tests, not captured
  (`tests/ledger/samples/*-euro-*-documented.json`).
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
- **Cash balances are read, never worked out.** Since 2026-11-26 the plug
  reads the ledger's cash balances (`get_cash_balances`), and an older
  ledger with no such tool is said to have none (`NO_CASH_TOOL`); it works
  no balance out from trades, and a holding of an asset the ledger lists as
  cash is left out. What the user is told is under "The assistant: cash".
- **The cost of a holding marked not exact carries a sentence of this
  program's.** The ledger says only that it is not exact; the reason
  shown is taken from the ledger's README (a fee paid in another asset).

## The assistant: cash

The model cannot look up a cash balance, a deposit or a withdrawal: none
of the eight tools handed to it reads one. The program itself reads the
ledger's cash balances (its tool `get_cash_balances`, added on
2026-11-25) when a question about cash is caught, and lays them out as
the ledger gave them (decided on 2026-11-26). What is still not there:

- **Balances only, no deposits one by one.** The ledger hands back each
  money's balance and nothing of the deposits, withdrawals or exchanges
  that made it, so "我一共入了多少金" gets words saying so, and no table
  (a balance is not a sum of deposits).
- **An older ledger has no such tool.** Asked, it answers `UNKNOWN_TOOL`;
  the program then says the fixed words of before (`CASH_WORDS`), word for
  word. The fake ledger made with no `cash` is such a ledger, so the
  question about cash's own set (`evals/sets/cash.json`) and its ruler
  measure that case still; the balances are measured by
  `evals/sets/cash/cash-balances.json` against the demo ledger with cash.
- **Asked and told in one sentence.** "我今天入金了500 USDT，现在还有多少？"
  is a question: the question about cash decides its kind (here money put
  in), so it gets the words that the ledger gives only balances, and
  neither a table nor a word that the deposit is recorded by hand.
- **The words standing in for a made-up figure.** When the model, having
  looked nothing up, says a number beside a money, its words give way to
  `CASH_WORDS` when the ledger has no tool for cash, and to other fixed
  words (`WITHHELD_WORDS`: no figure not read from the ledger; ask how
  much of a money is left) when it has. That check knows only the
  nicknames of a money and the ledger's cash codes and names: "你还有 250
  欧元" is not stopped, "欧元" being none of them (as before).
- **The real ledger's plug is tried on written answers only.** Its cash
  balances, an empty list and `UNKNOWN_TOOL` are tried on answers written
  from the ledger's README and its own tests
  (`tests/ledger/samples/cash-balances-*-documented.json`), never captured
  from a running ledger.
- **`ledger/link_tools.py` still names eight tools.** The program now uses
  nine, but the list the ledger tier compares stays at eight, and
  `get_cash_balances` is still reported as a tool the program does not
  use; a change of that tool's fields on the ledger's side would not turn
  the ledger tier red. (Left so, to change no test of the session that
  connected the real ledger.)
- **How the page knows.** Whether the ledger has the tool is asked when a
  reply is made, and only when it matters; a reply made against an older
  ledger keeps its old line under a table of holdings even after the
  ledger is upgraded.
- **The model may call USDT dollars.** Repeating a holding, the model
  wrote a profit of USDT as "美元" or "USD" (measured 2026-11-26: "未实现利润为
  6919.59984044美元", "unrealized profit of 1170.41008219 USD"); the table
  under the reply names USDT, which is the right money. Not mended here.
- **`Route.CASH` keeps its words.** Its value still reads "which it cannot
  look up"; it is kept as it was, since pages and records hold it.

What follows is how a question about cash is caught, as before:

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

## The assistant: money recorded by hand

The assistant proposes buys and sells only. A deposit, a withdrawal, an
exchange of moneys or a dividend, said rather than asked, is answered by
the program before the model is asked: it does not record that, nothing
was sent, please record it in the ledger yourself
(`core/money_asks.py`, 2026-11-26). What it knows:

- **The words.** A deposit: "入金", "充值", "存入", "入了…金" with up to
  eight signs between ("我入了500美金"), "转入了500U", "deposit", "top up";
  not "买入金额", "收入", "投入", "买入了30美金". A withdrawal: "出金",
  "提现", "取现", "出了…金", "withdraw", "cash out"; not "卖出", "支出". An
  exchange: "换成", "兑换", "换了", "换汇", "convert", "exchange", with a
  money named and no coin or share named at all ("换了300欧元"); "换汇费", "FX fee",
  "exchange fee" and "汇率转换的费用" are a trade's fee, not an exchange. A
  dividend: "分红", "派息", "股息", "dividend".
- **Said, not asked.** A sentence with the shape of a question or a request
  ("多少", "几", "吗", "什么", "?", "how", "what", "did I", "查", "看",
  "告诉我", "show", "list", "tell me") is no statement, and goes to the
  question about cash, or to the model, as before.
- **Beside a trade.** Only a statement that names no coin or share (the
  ledger's own assets that are not money, and the built-in coins) and says
  no buy or sell ("买", "卖", "购", "bought", "sold", "buy", "sell") is
  answered whole by the program (rework of 2026-11-26: a list of verbs is
  never whole, and "股息再投资了0.1股KO", "Dividend reinvested into 0.1 KO",
  "入金后上车了0.01个BTC", "Deposited 500 USDT and went long 0.01 BTC" were
  swallowed). Any other goes to the model as usual, and the reply ends with
  "Please record that part in the ledger yourself"; when no trade was
  recorded (the model did not ask to record, or no trade was found), a
  line says the trade was not recorded either. "入金500U，打算下周买BTC"
  goes to the model, which should record nothing for a plan, and the reply
  ends with both lines.
- **Moving a coin in is handed to the model.** "入金了 0.5 个 BTC" (a coin
  moved into the account, not bought) names BTC, so it goes to the model,
  which may propose a buy of 0.5 BTC. The reply ends with the line that the
  deposit is to be recorded by hand, and the card waits to be confirmed on
  the ledger's page, but the user has to see that this one is not to be
  confirmed. So does "Got a 2.1 USD dividend from KO today" when the ledger
  holds KO: it goes to the model, which may propose a KO buy.
- **A trade taken for a question about cash.** The question about cash
  (another session's, unchanged) catches some trades: "今天现金买了2股KO",
  "用U剩下的500买了3个SOL", "Bought 0.01 BTC with cash today",
  "入金500U到现金账户，然后…买了0.01个BTC". It lays out the cash balances, and
  when the words were said, not asked, and name a coin or share, the reply
  ends with "This was taken as a question about cash. If you meant to
  record a trade, please say the trade again on its own." Nothing of the
  trade is recorded, and a deposit said beside it gets no line of its own.
- **An exchange beside a trade is not seen.** "今天把500欧元换成了540美元，然后
  下午4点买了2股AAPL" names AAPL, so no exchange is read; the model may
  take the exchange for a trade and ask whether it was a buy or a sell, and
  no line says the exchange is to be recorded by hand.
- **A failed deposit is still told to be recorded.** "出金失败了" or "入金失败"
  is read as money moved and answered "Please record it in the ledger
  yourself", though a failed one is recorded nowhere.
- **What it does not catch.** Other words ("往账户里打了500U", "转了500U进来",
  "领了股息" is caught but "收到了可口可乐给的钱" is not), and an exchange
  that names a coin ("把100U换成了比特币" is a buy, as before). Such a
  sentence goes to the model as before. Measured on 2026-11-26 before
  this reading was added, a dividend said went to the model, which asked
  for the details of a trade, and "我入了500美金" got the model's words
  that it answers only about the ledger.
- **The dividend sentence.** It says "Please record it in the ledger
  yourself" for a dividend too. The ledger records dividends on its own
  page under Record, Dividend (since its `dev` of 2026-11-26); a ledger
  older than that has no place for one, which these words do not say.
- **None of the sets is caught.** Every sentence of `evals/sets/` (the
  hidden halves left out) and the demo sentences goes through this
  reading and the reading of a balance of any money with no model; none
  is caught (`tests/evals/test_money_asks_not_misread.py`).

## The assistant: trades paid in another money

Since 2026-11-26 a trade paid in one money for an asset the ledger prices
in another ("今天15:30花了128欧元买了2股KO，一股69.5美元，换汇费0.19欧元") is
sent paid in that money, with the rate between the two worked out from the
price said in the asset's own money (`flows/paid_apart.py`,
`core/cost_rate.py`; README, "The assistant page"). What it does not do:

- **Only when the ledger names the asset's own money.** An asset whose
  `priceCurrencyCode` the ledger leaves empty (an older ledger, the fake
  ledger's invented book, and the four assets the demo book takes from it:
  BTC, ETH, ADA, MSFT) goes on as before: euros paid for Microsoft in the
  demo are asked which money.
- **The total must name the money paid itself.** "花了128，……，换汇费0.19欧元"
  is not taken as paid in euros: the money is never read from the fee.
- **"美金" for the share price follows the asset's last trade, then its
  own currency.** When the asset's last trade used USDT or the US dollar,
  "美金" is that money, a guess. When it used neither (KO last bought for
  euros), "美金" is the asset's own currency in the ledger, a guess, if the
  ledger names it and it is USDT or the US dollar it prices in (the
  product owner's decision of 2026-11-27): the euro trade "花了210欧元买了3股
  KO，一股70美金，……" (invented) is sent paid in EUR with its rate, the
  rate marked assumed from KO's own currency, and a plain trade "一股70美金"
  is sent in USD, marked the same. An asset with no own currency named, or
  one priced in another money, is asked which money (a euro trade) or sent
  with its money empty and marked suspicious, as before; with no trade of
  the asset, or two moneys on its last day, the own currency is not looked
  at. The record kept by the assistant writes the guessed source of such a
  rate as the last trade (its EUR), and the reason in its marks names the
  own currency.
- **USDT and the US dollar are never set against each other.** Dollars
  paid for a coin priced in USDT, or USDT for a share priced in dollars,
  go on as before (asked which money, or the three amounts in doubt).
- **"一" of "一股" is said as a number not used.** "……买了2股 KO，一股69.5美元，……"
  (the euro sentence for a demo) is sent as it should be, but the reply
  ends with a reminder that a number of what was said was not used and a
  trade may be missing: "一". It is the "one" of "one share", not a trade
  left out. Not mended here.
- **One price a trade.** "一股64欧元，也就是69.5美元" keeps only the number
  the model put in the price cell: the dollars, or, with the euros there,
  the user is asked the price in dollars. The other number is not looked
  for in what was said.
- **The euro amount is taken without the FX fee.** The FX fee is the fee,
  and the reply says so each time. If the amount said already holds the
  fee, the ledger takes the fee from the euro cash a second time (0.19
  euros in the example), and the rate is a little off (139 ÷ 127.81 ≈
  1.0875 instead of 1.0859375).
- **A fee in a third money is not taken from any cash.** "换汇费0.2美元" on
  a trade paid in euros is sent as a fee of 0.2 USD; the ledger then marks
  the trade's cost as not exact and moves no cash for the fee.
- **The rate's reference is the ledger's latest such trade, as listed.**
  It is looked for among the asset's own trades as listed for its money,
  then among one page of the ledger's trades asked with no condition (the
  latest 2000 at most). With none, nothing is compared, and the reply says
  so; the first trade paid in euros has no guard but the market price of
  the share. The demo book has no trade paid in euros, so its rates are
  never compared. Ten in a hundred has no source behind it
  (`LEDGER_HAND_RATE_GAP_PERCENT`).
- **A blank is asked where it would be worked out across two moneys.** A
  quantity, price or total missing beside a price and a total said in two
  moneys is asked, even though the ledger takes cards, and so is the
  quantity of a trade paid in another money; such a trade sends nothing
  until it is answered. A trade whose money was named only in the price
  cell by the model, with no unit beside the price ("用欧元买了2股KO，一股
  69.5美元" with no money copied), is read as priced in dollars, its total
  worked out as 139 USD: what was said there is not known to the program.
- **Changing, deleting and asking do not show the rate.** A change of a
  trade paid in another money sends its rate as listed; the tables of
  trades do not show it.
- **The fake ledger keeps one pool for each asset and money.** Selling
  KO for euros there needs KO bought for euros; the real ledger holds the
  asset as one.
- **Euros and dollars both said as the total: marked, not settled.**
  "今天15:30花了128欧元买了2股KO，合139美元，……换汇费0.19欧元": when the
  model copies the dollars as the total, the trade does not go this way: it
  is sent paid in USD, 139 USD, and the ledger would take the dollars from
  the US dollar cash. Its fee in euros then marks the fee's money suspicious
  ("the fee is in EUR, but this trade is recorded as paid in USD"), and the
  reply says so; nothing is changed or asked. With no fee in euros ("128欧元
  （约139美元）" and no FX fee), there is no mark at all: at most a reminder
  that a number of what was said was not used (128). The same was seen with
  the share price said with "每股" (each share) instead of "一股":
  "2026年11月20号15点30分在IBKR花了128欧元买了2股 KO，每股69.5美元，换汇费0.19欧元"
  (invented) was sent, five times of five on 2026-11-26, as 2 KO at 69.5
  USD, total 139 USD, its fee's money marked suspicious, and the reminder
  naming 128; with "一股" it went the euro way each time.
- **A rate of 0 in the ledger stops the sentence.** An earlier trade whose
  rate is 0 is taken as the reference, and comparing with it raises an
  error, so what was said ends in a failure. The real ledger keeps no rate
  of 0 or below, so it is not met there.
- **The owner's long euro sentences are first asked buy or sell.** On the
  practice halves' four such sentences the model reached, extraction left
  the side empty ("……还花了0.46欧买了0.0061629股"), so the program asks
  whether it was a buy or a sell, then which asset ("可口可乐"): two
  questions before a card. Answered ("买", then the code), each was sent as
  its gold answer says (`evals/RESULTS.md`, "The five
  sentences of euros paid"). The fifth (R80-23) comes back empty from the
  model, as it has since `assistant-5`. The prompts are not changed here.
- **The hidden halves' sentences of euros paid are not enabled.** See
  "The assistant: recording a trade".

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
- **A share's Chinese name is matched by a table and by answers kept.**
  A name of an asset the ledger's list does not hold as it is
  ("微软的股票", "英特尔") is matched by the program itself: first by the
  user's earlier answers kept in `asset-names.json`, then by its table of
  common companies (`core/stock_names.py`), when it is turned on
  (`LEDGER_HAND_NAME_TABLE=on`; it is off by default, see below). A name
  the table holds is sent as its code when the ledger has it, marked as assumed with where
  it came from; a name the table does not hold is asked about ("which
  asset was it?") once, and the code answered is kept and used the next
  time. The step that hands such a name to the model to pick from the
  list (`extraction/asset_picking.py`) stays off
  (`ASSISTANT_PICKS_ASSETS`): measured on the names set on 2026-11-25,
  each of three prompt versions picked a listed asset for names the
  ledger lacks ("雪碧" as PepsiCo or Coca-Cola, "谷歌" and "亚马逊" as
  Apple, "柚子币" as SOL, "可口可乐装瓶公司" as Coca-Cola), and the whole
  assistant sent two shares for "2股微软和英特尔"; the checks of the words
  left over cannot catch a name picked whole. Turned on, a pick is said
  in the reply and marked as assumed on the trade's card.
- **The table is off by default: one sentence naming two companies is
  sent as two shares.** Measured on 2026-11-27 on the practice half of the
  names set, "买了2股微软和英特尔" was split by the extraction into two
  trades, and the table matched each name, so two shares were sent where
  the user may have meant something else; the names set counts it as
  wrong. On the hidden halves of the exam said the owner's way, with the
  table on, four trades had their asset matched by the table as another
  asset than the gold one (counts alone are known). That count also takes
  in a name matched in a sentence not enabled whose gold has no trade, so
  how many of the four are truly wrong is not checked. As the way back says,
  the table is off until a way passes; the answers kept stay on.
- **The table holds only common companies listed in the United States,
  matched whole.** About eighty companies, by the Chinese name people
  call them, chosen as large companies and household brands; a company
  listed only in Hong Kong or Shanghai ("腾讯", "小米", "美团") is not in
  it, nor a product ("iPhone", "雪碧", "百事可乐"). A name is matched only
  whole once a trailing "的股票", "股票", "的股份", "股份", "的公司", "公司"
  or "集团" is cut off: "微软A股", "微软的期权" and "可口可乐装瓶公司" are
  asked about as before. A name the table holds whose codes the ledger
  lacks ("特斯拉" with no TSLA) is not sent, and the user is told to add
  it in the ledger first.
- **A name the extraction leaves out cannot be kept.** When the model
  leaves the asset cell empty, there is no name to keep with the code
  answered; the trade is recorded, and the next time the same words are
  asked about again.
- **Answers kept are apart for the demo ledger and the ledger page, not
  for each ledger.** A name answered on the demo ledger is used only on
  the demo ledger, and one answered on the ledger page only there; but
  the ledger page is not told apart by which ledger it reaches, so if
  another ledger is ever reached, the names answered before go with it,
  as long as that ledger has the same code.
- **The answers kept were not measured with the real model.** Every
  measure says each sentence with no file of answers, so that one
  sentence's answer cannot change the next; the answers are checked by
  tests with a scripted model, and by one walk through by hand.
- **Answering "which asset" with a Chinese name is not understood.** Once
  the program asks which asset a trade was, the answer is read as before:
  answer with the asset's code as the ledger lists it ("MSFT"); "微软" is
  not matched there.
- **Asking, changing and deleting do not match Chinese names.** Only
  recording matches a name by the table or by an answer kept; a question
  about "微软的交易", or a change of "微软那笔", finds no asset by that name.
- **A fee taken in an asset named in Chinese is not matched.** Only the
  asset traded is matched or handed over; a fee said as "手续费0.1个英伟达"
  is not.
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
- **How well names are picked, or matched by the table, was measured on
  one set.** The names set (`evals/sets/stock_names.json`) and its
  results are in `evals/RESULTS.md`; names said otherwise may fare
  otherwise.
- **Changing the subject while a question waits.** While the recording
  flow's question waits, whatever the user says next is read as its
  answer. A question about the holdings at that moment is taken as an
  answer that cannot be used, and the same question is asked again. Saying
  "cancel" drops the passage, and the next thing said goes to the model.
- **A trade said with its day only is sent with its day alone.** The
  recording flow keeps a trade said with a day and no time of day
  ("11月20号买了0.1个ETH", "bought 0.5 ETH yesterday") as known to the day.
  It is sent with its day alone (`date_only`), no time of day made up, as
  the real ledger takes it (sample `propose-add-date-only`); the card says
  `none` for its time of day, with no mark. What is left: the ledger then
  holds no time of day for it, so two trades of one day keep no order of
  their own. `LeftOut.DAY_ONLY` and its
  sentence stay in the code, which no path reaches now.
- **What is marked suspicious, and what is not.** A price at least
  `LEDGER_HAND_PRICE_GAP_TIMES` times (five by default) the ledger's market
  price of the asset, or at most that part of it; quantity, price and total
  said that do not agree (all three); and, on a card sent with cells left
  empty, a cell said but wrong in itself (`core/card_record.py`, `Doubt`)
  and a vague word for money the ledger's last trade cannot settle. Nothing
  else is: a quantity far from what is held, or a fee far too large for
  the trade, is not marked. Five was chosen with no source behind it, and
  the bounds of the setting (above 1, at most 1000) and the line at which
  the times apart are shown whole (ten) wait for a reason.
- **The ledger turns down a whole card whose figures do not agree, so the
  total is left empty.** When quantity, price and total are all said and
  do not agree, the ledger (72B, 2026-11-25) takes no trade with every
  cell given; the quantity and the price go as said, the total empty, all
  three marked suspicious, the total's reason holding the total said. If
  the ledger comes to take such a card, the three can go as said, each
  marked, with no cell empty; only the sending and that one reply line
  change.
- **A ledger whose tools do not take cells left empty is asked every gap
  as before.** Whether the ledger takes cards is read once from its list
  of tools (`allowUnfinished` on `propose_trade_add`). The fake ledger is a
  ledger from before unless made to take cards (the demo ledger, the
  try-out script's and the exam book are). The real plug reads the list
  from the link (the link kept by the Assistant page hands it on, since
  2026-11-26); while no link runs it is not read and asked again next
  time. A ledger page from before 2026-11-25 is asked each gap as before.
- **A vague word for money that no rule names is still asked.** Besides
  "the ledger has no trade of the asset" and "the ledger cannot be asked"
  (both asked, as the product owner's rule says), a vague word is still
  asked about when the trade itself names two moneys beside it
  (`MONEY_NOT_CLEAR`), or when the asset's last trade used USDT or the US
  dollar but that money prices nothing in the ledger now. Neither is in
  the rules for cards, and both are still asked, as decided on 2026-11-26.
- **A figure worked out a hair off the one said keeps the figure worked
  out.** When the user says a number the model does not copy, and the
  program works that cell out from the other two (a total of 150 said,
  150.00078 worked out), the card shows the figure worked out, marked
  "worked out by the program", not the number said. Putting the number
  said back was tried on 2026-11-26 and withdrawn: picked from every
  number no cell used, it could move a time, a fee or another trade's
  number into the cell, and it took that number off the reminder that a
  trade may be missing.
- **Buy or sell the model filled in itself is sent unmarked.** When the
  words say neither buy nor sell ("今天上午10点0.1个ETH，成交价2700 USDT，
  手续费0", invented), the model sometimes fills in buy, and the card is
  sent with `type` buy and no mark on it. The program asks buy or sell
  only when the model left it empty.
- **A cell the model wrote that is not in the words is left empty, unmarked.**
  On a card, a figure or a time the model wrote that is not a piece of what
  was said, or that could not be read as a number, is left empty with no
  mark, as any cell not said; the reply names it among the empty cells. A
  time refused for lying after today is the one such cell marked (with the
  day it names).
- **A quantity said in another unit that is not money is still held back.**
  "25U" of ETH is taken as the total once the ledger takes cards; a
  quantity whose unit is an asset other than the one traded, or names two
  moneys, is held back and said as before. With a price said as well
  ("Bought 30 USDT of ADA at 0.31 …", a sentence for a demo), the quantity
  is worked out and marked worked out, but the total taken from the
  quantity carries no "assumed" mark, which only a card with an empty cell
  gets; and the reply still ends with the reminder that the quantity
  carries a unit that is not the asset, as if nothing had been done with
  it. Not mended here.
- **A price is never compared across two moneys.** When the trade is in
  USDT and the ledger's market price of its asset is in US dollars, or the
  other way round, nothing is compared and nothing converted; the reply
  says the price was not compared, and the card has a plain line saying
  why, but no mark. The same holds when the ledger cannot be asked for its
  market prices (the trade is still sent) and when the asset has no market
  price (then nothing is said in the reply, only the line under the card).
  A card with no mark is therefore not a card that was checked.
- **A wrong figure with no mark on it.** When the user says the quantity
  and the price, not the total, and the quantity is out by a power of ten
  (a zero too many or too few, as a speech transcript may write it), the
  total is worked out from it and marked only as worked out; the price is
  as said, and near the market price. Neither kind of suspicious mark
  catches it: the card shows a wrong total marked "worked out by the
  program", and nothing in red.
- **What the program fills in itself is not marked.** The time zone, the
  year or "today" the program fills in from the clock and the machine are
  on nearly every trade, and marking them all would leave the marks unread;
  only the money guessed from the last trade, an asset the model matched,
  and the amount worked out are marked as not said.
- **The marks' reasons are in English.** On a ledger page in Chinese the
  reasons still read in English, as every word of this program does.
- **The marks reach the ledger only when it takes cards.** A ledger that
  takes cells left empty is sent each trade's marks after the guard; one
  from before is sent none, and they are shown only on this side.
- **The day of a market price fetched online may be a day early.** The
  day said beside a market price is the first ten characters of what the
  ledger gives; a price fetched online carries a moment in UTC
  (`2026-11-24T23:30:00Z`), which in Budapest is already the 25th. Only
  the day written in the reply and on the card is off; the comparison is
  not.
- **"About 1.0 times" and "about 5.0 times" can be read the wrong way.**
  Below ten times the times apart are shown to one place, so a price near
  the market price reads "about 1.0 times lower" in the try-out script and
  the assistant's record, and one 4.99 times off reads "about 5.0 times
  higher" though it is not far. The reply and the card never say this for
  a price within reach.
- **A trade the ledger turned down still gets its card.** The card is
  drawn, with its marks, for every trade sent; that the ledger did not
  take it is said in the table beside it, not on the card.
- **A refused price-gap setting can name a number that is in range.**
  `LEDGER_HAND_PRICE_GAP_TIMES=00005` is refused (leading zeros), and the
  sentence says "a number above 1 and at most 1000", which 5 is.
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
  - a guess is said in the reply, and marked assumed on the money's cells
    of the card sent to a ledger that takes cards (and in the assistant's
    record, "marks"); a ledger that takes no cards gets no mark of it;
  - only the first thing said counts as the same trade: said in one go
    ("买了3股MSFT，每股400刀，手续费1 USDT"), the price follows the fee's
    USDT; said in two ("买了3股MSFT，每股400刀", then "1 USDT" when the fee
    is asked, as only a ledger that takes no cards asks it), the price
    was already guessed from the last MSFT trade (US dollars, said as a
    guess), the fee is in USDT, and the fee's money is marked suspicious
    as paid in another money than the trade; a ledger that takes cards
    sends the fee empty instead, and the case is not met;
  - the question asked while a guessed trade still lacks a figure names
    the guessed money ("in USDT?") without saying it is a guess;
  - with the real ledger: a trade's time may be known only to the day,
    which is why days are compared; and one code may name both a coin and
    a share, so the trades should be asked for by the asset's identifier,
    not its code, once the real ledger is connected;
  - a trade paid in euros for a share priced in US dollars ("花了0.46欧
    ……一股81.13美金"): with no euro in the ledger it is not sent; with one,
    and the ledger naming the share's own money, it is sent paid in euros
    with its rate since 2026-11-26 (see "The assistant: trades paid in
    another money"); otherwise the user is asked which money it was in.
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
- **Money said where the quantity goes is not sent to a ledger that
  takes no cards.** (A ledger that takes cards, as the demo ledger and
  the real one do now, takes it as the total; see "A quantity said in
  another unit that is not money is still held back" above.) "25U买了点ETH"
  says what was paid in all, not how many ETH. Without cards, the
  assistant does not guess it is the total: that trade is not sent and nothing is asked
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
- **A time said with another zone is not tidied, and may still be read in
  the ledger's zone.**
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
  keeps its Chinese time as said. A list of words let through was tried
  and dropped (2026-11-25): every word on it let some zone through
  ("时间是美东", "按纽约那个时间"). So a time is sometimes held back that
  need not be. What then happens depends on whether the model can read the
  time as said, and was tried with `qwen2.5:7b` on the demo ledger, which
  takes cards (2026-11-26, invented figures):
  - the model cannot read it
    ("成交的时间是二六年十一月二十号下午三点，在OKX买了0.1个ETH，成交价2700 USDT，手续费0.1 USDT"):
    the card is sent with its
    date empty, and the reply names it, to be filled in on the ledger's
    page; a ledger that takes no cards asks "When did the trade happen?";
  - the model reads it, the zone being another
    ("按北京时间算，二零二六年十一月二十号下午三点……", or the same with
    "2026年11月20号下午3点"): the trade is
    sent at 2026-11-20 15:00 +01:00, the ledger's zone, hours off the
    time meant. Since 2026-11-27 the time cell (the day, for a trade sent
    with its day alone) is marked suspicious, its reason naming the words
    said and the ledger's zone, and the reply says the time was not
    converted (`core/other_zone.py`): a place with 时间 or 时区 in the
    same clause, at most three characters apart with no digit between
    ("北京时间", "按纽约那个时间", "北京的成交时间"; "Beijing time" in English),
    东X区 or 西X区, a Latin name other than the two the ledger's own zone
    goes by (CET and CEST for Budapest), or 时区 and 当地时间 with no place
    of the ledger's zone beside them. Every trade of the passage with a
    time is marked, since which trade the zone was said for cannot be
    told. The program still converts nothing: that needs the reading of
    times to learn zones. A zone said only in the answer to a question
    ("下午3点，北京时间", given when the time was asked) is not read: the
    answer is not kept with the passage. A share's name that holds a place
    and stands four or more characters before 时间 ("中国平安成交时间") is not
    taken for a zone.
  The ledger's own zone
  said apart from the time ("按匈牙利时间算，……") is kept in the words, and
  the time is tidied. To take another zone, the reading of times has to
  learn zones. A zone said with neither 时间 nor 时区 nor a Latin name
  ("按国内算下午三点", by home reckoning three in the afternoon; "北京下午三点",
  Beijing three in the afternoon) is not seen at all: the time is tidied and
  read in the ledger's zone, hours off, with no mark. That wording is not
  dealt with here.
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
- **The owner's way of speaking, measured before any tuning
  (2026-11-26).** On the exam's three tiers (`evals/sets/spoken/`), with
  the prompts as they stand: a wrong figure with no mark of its own went
  to the ledger once on the hidden half as said, and once each on the
  practice halves a little tidier and tidy (an amount put as the price; a
  total the program worked out, 150.00078, where 150 was said). Saved
  with no cell changed, of the trades that could be: as said 60% and 33%,
  a little tidier 36% and 64%, tidy 92% and 100% (practice and hidden;
  `evals/RESULTS.md`, "2026-11-26: the owner's way of speaking, three
  tiers, `qwen2.5:7b`"). One ③ of the hidden half came with a reminder
  about the whole passage only, which marks no cell.
- **The owner's way of speaking, after tuning: two lines not met
  (2026-11-26).** Three versions of the extraction prompt for words with
  Chinese in them, with rules and examples written the owner's way
  (`spoken-1` to `spoken-3`), were measured; two did not pass the final
  set (a remark about the market copied as the trade's opinion), and the
  third sent two wrong figures with no mark on the hidden halves against
  one for `first-3`, so the assistant still extracts with `first-3`. At
  the end of that tuning, on the hidden halves: as said, one wrong figure
  with no mark (the line is none), 33.3% saved with no cell changed (two
  wrong figures with no mark since cards with empty cells are sent, and so
  at the end of the round; see "What you will meet" above); a little tidier,
  none, but 63.6% saved against a line of 80%; tidy, none and 100%, both
  lines met (`evals/RESULTS.md`, "Three versions for Chinese, and the
  pick" and "At the end"). The rules that helped on the practice halves
  (money spent on a coin is a buy; money spent after the quantity is the
  total) were not kept steadily by `qwen2.5:7b` once more rules were
  added: `spoken-3` put "花了…U" into the price again on two practice
  sentences that `spoken-1` and `spoken-2` had right.
- **A cell that should be empty was asked about at the baseline.** A
  fee not looked at, or a time with no time of day, was asked about
  rather than sent empty, before the exam book took cards with empty
  cells; since 2026-11-26 it takes them, and such a cell is sent empty
  (`evals/RESULTS.md`, "2026-11-26: cards with empty cells; the practice
  halves, three tiers"). The exam counted a draft cell wrong and unmarked
  apart, and found none at the baseline.
- **A fee said to be none is often not copied.** "没有手续费" and
  "都没有手续费" are left out by the model on four practice sentences;
  the program asked for the fee before cards, and now sends the fee
  empty, to be filled in on the ledger's page. A sentence with no "买" before the
  amounts ("在OKX，…个SOL，花了…U") is asked whether it was a buy or a sell.
- **A payment in euros is measured on the practice halves only.** Against
  the exam book, which has no euro, a share bought with euros is not sent,
  and the reply says the ledger has no currency EUR. Since 2026-11-26 the
  practice halves' five such sentences are enabled and said against the
  exam book with a euro (`exam_ledger_with_euro`); the hidden halves' are
  not enabled yet, and wait for a helper who writes their gold answers
  without the rest being seen. Dividends, deposits and withdrawals are not
  in the practice halves.
- **The tools' words still say to list trades before a change.** The
  system prompt's rule and `list_trades`'s own words both say to find the
  trade first; the tools that change and delete say to call them straight
  away. `list_trades`'s words are not changed. The system prompt's rule is
  changed in `assistant-5`, the default since 2026-11-26 (see "The
  assistant: changing and deleting").

## The assistant: changing and deleting

- **A date the model put this year to is let through; any other date not
  copied is said.** Since 2026-11-27, when the model writes the user's
  date with this year put to it ("2026年8月3号" for "把8月3号那笔BTC删掉",
  "August 3, 2026" for "August 3"), the change or deletion goes on with the
  user's own words, and the reply ends "The date was read as this year
  (2026)." once the trade was looked for. Only when: the year is this year
  in the ledger's zone; once that year is taken off (written before the
  date as "2026年", "2026 年", "2026-", "2026/", "2026.", "26年",
  "二〇二六年", "二零二六年", or after it as ", 2026" or " 2026"), the rest is
  the user's words; no sentence it is found in says a year anywhere
  ("去年", "last year's", "2025", "3年"); and the user's words read as the
  same days. "12月5号" before 5 December, and "2月29号" in a year with no
  29 February, are read by the program as some other day or not at all,
  so they are not let through. Anything else not copied (another year, a
  day changed, "2026-8-3" for "8月3号") is held back as before; after two
  such tries, or when the model then answers in its own words, the user
  is told: 'I could not use the date: the assistant wrote "2025年8月3号",
  but you said "8月3号". Dates are taken only as you said them. ...', with
  an example of the latest past year ("2026年8月3号"; for "12月5号",
  "2025年12月5号"); the model's own answer is kept before it. In tries with
  `qwen2.5:7b` on 2026-11-27 the model put no year to a date in any of
  eleven changes and deletions tried (in two English ones it wrote the
  month in Chinese instead), so no year it puts to a date has been seen
  with the real model; the list of year forms above is not checked
  against one. Asking the ledger ("我8月3号买了哪些BTC") is not let through
  this way; the model copied the date there too in both tries.
- **One trade and one part at a time, and the rest not always told.** A
  change or a deletion touches one trade, and a change one part of it.
  Changing many trades at once is not built. When one thing said asks for
  two (two trades, two parts, or a change and a deletion), only one is
  done. The program says what else was not done only when the model asked
  for it as a second call in the same step. More often the model makes one
  call only ("删掉10月6号和10月21号那两笔BTC" gives one call, for 10月6号;
  "数量改成0.0081，成交价改成62000" one call, for the quantity), and then
  nothing is said about the other one.
- **Measured: 13 of 17 done right with `assistant-4`, none done wrong;
  14 with `assistant-5`, the default (next item).** On the set of
  changes and deletions (`evals/sets/edits.json`), at the latest run with
  `assistant-4`, 13 of 17 sentences ended with the right proposal or the right refusal and
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
  first time, and the user is asked back or told to say it again. The
  second of the four is done with `assistant-5`, whose line on listing
  first was changed (next item); the other three are not.
- **`assistant-5` says to call the tools straight away, and is the
  default (2026-11-26).** Its one changed line says what the tools that
  change and delete say. Measured against `assistant-4` it did 14 of the
  17 changes right instead of 13 (N8, where the model listed the trades
  and asked in words, is now done), none sent wrong on any set, recording
  and the first tool the same, and no question answered off
  (`evals/RESULTS.md`, "The system prompt's rule on changes, before and
  after"). With it, one question that had got a table got none. N4, N9
  and N10 are still not done with either.
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

- **Cash balances only from a ledger that has the tool.** The ledger
  tried here (`dev@a6ba639`) has no tool for a cash balance, so with it
  the assistant says it cannot look one up. The ledger's `dev` has since
  added one (`5762751`), and since 2026-11-26 the plug reads it (see "The
  real ledger's plug" and "The assistant: cash"); that was tried only
  against answers written from the ledger's README, never on a running
  ledger page.
- **A trade in another money than the asset's own goes only with its
  rate.** The assistant works the rate out only for a trade that goes the
  way of "The assistant: trades paid in another money"; any other such
  trade is not sent (see "The real ledger's plug"). Tried only on answers
  written from the ledger's README, never on a running ledger.
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
