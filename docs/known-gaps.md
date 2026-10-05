# Known gaps

Places where a trade this program accepts and exports is still refused by the
ledger, or is refused by the export instead of being caught earlier. Each one
is known, is shown by the checks, and waits for a decision by the project
owner. None of them is fixed here on purpose.

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
reading a time phrase never produces one. The check of a draft still accepts
it, and the export then refuses the trade with the reason
`OFFSET_NOT_WHOLE_MINUTES` instead of failing while it writes.

**Why it is not fixed here.** Refusing it already in the check of a draft
means adding a reason to the check's list of violations, which one of the
check's own tests pins down exactly; changing that test waits for the project
owner's decision.
