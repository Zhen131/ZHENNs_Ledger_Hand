# Known gaps

Known limits of this program: places where a trade it accepts and exports
may still be refused by the ledger, where two guards stand in for each
other, and where a step that asks the model has a weakness that is known
but not mended. Each one is described with the trades or passages it
affects; where a choice is needed, it waits for the project owner.

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

