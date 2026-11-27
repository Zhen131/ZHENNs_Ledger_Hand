// Checks backup files the way the ledger checks a backup it is asked to restore:
// its import preflight, `preflightBackupJson`.
//
//   tsx --no-cache --tsconfig <config> scripts/ledger_validate.ts <ledger checkout> <today> <file>...
//
// scripts/ledger_check.py runs this from inside a checkout of the
// Local-First Trading Ledger, with the tsx of that checkout and a configuration
// that extends the ledger's own. It only imports and reads the ledger's
// modules; it writes nothing, anywhere.
//
// Why the preflight and not `parseBackupJson` alone: since 2026-11-17 the
// ledger reads a file of schema 5, 6 or 7 with `parseBackupJson` checking only
// that version's envelope, and leaves selling more than is held, its limits
// and its import rules (a day after today) to the preflight run before an
// import (its `backupEnvelope.ts`, `validateUpgradableEnvelope`, and
// `backupImportPreflight.ts`). This program writes schema 5.
//
// The preflight is asked as the ledger's "restore a backup" asks it
// (`backupControlsActions.ts`, `BackupControls.tsx`): raw text not required
// (`requireHistoricalRawText: false`), with the language of the page handed in
// as `t`. Here that is English, the language the expected errors of
// tests/ledger_check/cases.py are written in. `selectionGeneration` only tells
// one file chosen on the page from the next; 1 is a test value.
//
// <today> (YYYY-MM-DD) is handed to the ledger as the date it takes to be
// today, so that whether a trade lies in the future does not depend on the
// clock or the time zone of the process.
//
// It prints one line on standard output: a marker, then a JSON document with
// the ledger's two format version constants and, for each file, whether the
// ledger would take it (no hard error and no check left undone), every hard
// error it reported, every check it could not do and why, and how many groups
// of trades it found that may be the same trade twice. Those groups are a
// reminder on the ledger's page, not a refusal. A file whose check throws
// instead of returning is reported with what was thrown.
//
// Exit status: 0 the files were checked, whatever the ledger said about them;
// 1 the ledger's modules could not be loaded; 2 wrong usage.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const MARKER = "LEDGER_HAND_RESULT ";
// Only tells one file chosen on the ledger's page from the next; a test value.
const SELECTION_GENERATION = 1;

type LedgerError = { code: string; path: string; message: string };
type Detail = { kind: string; code?: string; path?: string; message?: string };
type Skipped = { check: string; reason: string };
type PreflightResult = {
  hardErrorCount: number;
  suspiciousGroupCount: number;
  retainedDetails: readonly Detail[];
  skippedChecks: readonly Skipped[];
};
type Translate = (key: string) => string;
type Preflight = (
  text: string,
  options: {
    todayKey: string;
    selectionGeneration: number;
    requireHistoricalRawText: boolean;
    t: Translate;
  },
) => Promise<PreflightResult>;
type FileResult = {
  file: string;
  ok: boolean;
  errors: LedgerError[];
  skipped: Skipped[];
  suspiciousGroups: number;
  thrown?: string;
};

async function importFromLedger(
  ledger: string,
  relative: string,
): Promise<Record<string, unknown>> {
  return import(pathToFileURL(join(ledger, relative)).href);
}

async function checkFile(
  preflight: Preflight,
  t: Translate,
  today: string,
  file: string,
): Promise<FileResult> {
  try {
    const result = await preflight(readFileSync(file, "utf8"), {
      todayKey: today,
      selectionGeneration: SELECTION_GENERATION,
      requireHistoricalRawText: false,
      t,
    });
    const errors = result.retainedDetails
      .filter((detail) => detail.kind === "hard-error")
      .map(({ code, path, message }) => ({
        code: String(code),
        path: String(path),
        message: String(message),
      }));
    if (errors.length !== result.hardErrorCount) {
      throw new Error(
        `the ledger kept ${errors.length} of ${result.hardErrorCount} hard errors`,
      );
    }
    const skipped = result.skippedChecks.map(({ check, reason }) => ({ check, reason }));
    return {
      file,
      ok: errors.length === 0 && skipped.length === 0,
      errors,
      skipped,
      suspiciousGroups: result.suspiciousGroupCount,
    };
  } catch (error) {
    return { file, ok: false, errors: [], skipped: [], suspiciousGroups: 0, thrown: String(error) };
  }
}

async function main(): Promise<void> {
  const [ledger, today, ...files] = process.argv.slice(2);
  if (ledger === undefined || today === undefined || files.length === 0) {
    console.error("usage: ledger_validate.ts <ledger checkout> <today> <file>...");
    process.exit(2);
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(today)) {
    console.error(`today must be written YYYY-MM-DD, not ${today}`);
    process.exit(2);
  }
  const backup = await importFromLedger(ledger, "src/features/backup/backupEnvelope.ts");
  const preflightModule = await importFromLedger(
    ledger,
    "src/features/backup/backupImportPreflight.ts",
  );
  const words = await importFromLedger(ledger, "src/ui/i18nTranslate.ts");
  const contract = await importFromLedger(ledger, "src/platform/files/ledgerFileContract.ts");
  const preflight = preflightModule.preflightBackupJson as Preflight;
  const translate = words.translate as (language: string, key: string) => string;
  const english: Translate = (key) => translate("en", key);
  const results: FileResult[] = [];
  for (const file of files) results.push(await checkFile(preflight, english, today, file));
  const report = {
    backupFormatVersion: backup.BACKUP_FORMAT_VERSION,
    ledgerSchemaVersion: contract.SUPPORTED_LEDGER_SCHEMA_VERSION,
    results,
  };
  console.log(MARKER + JSON.stringify(report));
}

main().catch((error: unknown) => {
  console.error(error);
  process.exit(1);
});
