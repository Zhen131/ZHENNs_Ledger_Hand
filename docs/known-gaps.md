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
question, never a wrong time. No prompt version measured so far mended it.

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
Three rough edges remain.

- **Refused after the rollback.** When the check after the rollback refuses
  the book (its tables are not those of its version, or SQLite finds it
  damaged), the rollback has already written to it: what the tables are
  cannot be read before the journal is rolled back. The book's own message
  then says that SQLite first rolled back a write cut off part way, but the
  page's sentence for the kind, shown beside it, is the usual one: for a
  file that is not this program's book it says the file "was left as it
  is", and for a damaged book that the program "does not write to it".
- **A folder that cannot be written.** SQLite rolls the book back, but
  cannot remove the journal, which takes a folder it may write to. The book
  is then refused as inaccessible (SQLite's `SQLITE_IOERR_DELETE`), and the
  journal stays; each later opening rolls the book back again, to the same
  bytes, and fails the same way, until the folder can be written.
- **A file this program does not read.** A file that is not a database, or
  not this program's book, or a book of a newer version, is refused with
  its journal left beside it; this program never rolls back a journal it
  cannot first show to belong to one of its own books.

**What it affects.** Nothing that was saved is lost in any of these: a
rollback only takes the book back to what it held before the write that was
cut off.

**What the user can do.** For a folder that cannot be written, make it
writable and open the book again. For a file this program does not read,
keep a copy of the file and its journal together; do not delete the
journal file.

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
