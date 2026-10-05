// Asks the ledger what offset from UTC each time zone has at each instant.
//
//   tsx --no-cache --tsconfig <config> scripts/ledger_offsets.ts <ledger checkout> <probes file>
//
// scripts/ledger_check.py runs this from inside a checkout of the
// Local-First Trading Ledger, the same way as ledger_validate.ts. The probes
// file is a JSON list of [instant, time zone] pairs, the instant written as
// in a trade ("2026-10-05T05:46:00+00:00"). For each pair the ledger's own
// getTimeZoneOffsetAt answers, which is what its validator compares a trade's
// offset with. Comparing those answers with Python's shows where the two time
// zone databases disagree.
//
// It prints one line on standard output: a marker, then a JSON document with
// the time zone database and ICU versions of this Node runtime, and one offset
// (such as "+01:00") per pair, or null where the ledger could not tell.
//
// Exit status: 0 the pairs were answered; 1 the ledger's modules could not be
// loaded; 2 wrong usage. It only reads; it writes nothing, anywhere.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const MARKER = "LEDGER_HAND_OFFSETS ";

type OffsetAt = (instant: Date, timeZone: string) => string;

function offsetOrNull(offsetAt: OffsetAt, instant: string, zone: string): string | null {
  try {
    return offsetAt(new Date(instant), zone);
  } catch {
    return null;
  }
}

async function main(): Promise<void> {
  const [ledger, probesFile] = process.argv.slice(2);
  if (ledger === undefined || probesFile === undefined) {
    console.error("usage: ledger_offsets.ts <ledger checkout> <probes file>");
    process.exit(2);
  }
  const shared = await import(pathToFileURL(join(ledger, "src/core/shared/index.ts")).href);
  const offsetAt = shared.getTimeZoneOffsetAt as OffsetAt;
  const probes = JSON.parse(readFileSync(probesFile, "utf8")) as [string, string][];
  const report = {
    tz: process.versions.tz ?? null,
    icu: process.versions.icu ?? null,
    offsets: probes.map(([instant, zone]) => offsetOrNull(offsetAt, instant, zone)),
  };
  console.log(MARKER + JSON.stringify(report));
}

main().catch((error: unknown) => {
  console.error(error);
  process.exit(1);
});
