// Checks backup files with the ledger's own validator, `parseBackupJson`.
//
//   tsx --no-cache --tsconfig <config> scripts/ledger_validate.ts <ledger checkout> <file>...
//
// scripts/ledger_check.py runs this from inside a checkout of the
// Local-First Trading Ledger, with the tsx of that checkout and a configuration
// that extends the ledger's own. It only imports and reads the ledger's
// modules; it writes nothing, anywhere.
//
// It prints one line on standard output: a marker, then a JSON document with
// the ledger's two format version constants and, for each file, whether the
// ledger accepted it and every error the ledger reported. A file whose check
// throws instead of returning is reported with what was thrown.
//
// Exit status: 0 the files were checked, whatever the ledger said about them;
// 1 the ledger's modules could not be loaded; 2 wrong usage.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const MARKER = "LEDGER_HAND_RESULT ";

type LedgerError = { code: string; path: string; message: string };
type ParseResult = { ok: true } | { ok: false; errors: LedgerError[] };
type FileResult = {
  file: string;
  ok: boolean;
  errors: LedgerError[];
  thrown?: string;
};

async function importFromLedger(
  ledger: string,
  relative: string,
): Promise<Record<string, unknown>> {
  return import(pathToFileURL(join(ledger, relative)).href);
}

function checkFile(
  parse: (text: string) => ParseResult,
  file: string,
): FileResult {
  try {
    const result = parse(readFileSync(file, "utf8"));
    const errors = result.ok
      ? []
      : result.errors.map(({ code, path, message }) => ({ code, path, message }));
    return { file, ok: result.ok, errors };
  } catch (error) {
    return { file, ok: false, errors: [], thrown: String(error) };
  }
}

async function main(): Promise<void> {
  const [ledger, ...files] = process.argv.slice(2);
  if (ledger === undefined || files.length === 0) {
    console.error("usage: ledger_validate.ts <ledger checkout> <file>...");
    process.exit(2);
  }
  const backup = await importFromLedger(ledger, "src/features/backup/backupEnvelope.ts");
  const contract = await importFromLedger(ledger, "src/platform/files/ledgerFileContract.ts");
  const parse = backup.parseBackupJson as (text: string) => ParseResult;
  const report = {
    backupFormatVersion: backup.BACKUP_FORMAT_VERSION,
    ledgerSchemaVersion: contract.SUPPORTED_LEDGER_SCHEMA_VERSION,
    results: files.map((file) => checkFile(parse, file)),
  };
  console.log(MARKER + JSON.stringify(report));
}

main().catch((error: unknown) => {
  console.error(error);
  process.exit(1);
});
