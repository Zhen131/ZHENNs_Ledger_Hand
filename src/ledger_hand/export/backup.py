"""Saved trades as the text of a ledger backup file.

``export_backup`` takes the trades to export, the coin table, the moment of
the export and the name and version of this program. It gives back the text
of the file, or ``ExportRefused`` listing every reason it cannot be written.
It writes no file; the text is the whole result.

The file is a backup in the ledger's format that holds only these trades:

- Five fields on the outside, in the ledger's order: the backup format
  version, the program's name and version, the export moment, the ledger
  schema version, and the ledger data.
- The ledger data: the schema version again, then six lists. ``assets``
  holds a card for every coin the trades use: the coin traded, and the coin
  a fee was paid in unless that was USDT; each coin once, in the order of
  their symbols. ``trades`` holds the trades in the order they happened: a
  trade known to the minute or second at its instant, and a trade known only
  to the day at the start of that day in its own time zone, which is where
  the ledger puts it too; two at the same instant in the order of their
  identifiers. The other four lists (cash events, transfers, price snapshots,
  fee rules) are empty.

It is refused, with nothing written, when:

- there is no trade at all;
- an identifier is empty, has whitespace at either end, or is longer than the
  ledger allows;
- an identifier is used twice. The ledger requires every identifier in a file
  to be different, the coins' included, so a trade may not use a coin card's
  identifier either;
- a trade names a coin the coin table does not hold, so that its card cannot
  be written.

The same trades, in any order, with the same coin table, moment, name and
version, always give the same text, byte for byte. It is laid out the way the
ledger lays out its own backups: indented by two spaces, letters of every
language as they are, and a line break at the end. A lone half of a surrogate
pair, which cannot be written as UTF-8, is written as an escape instead, as
the ledger does.

The trades' own soundness was settled before they became records and is not
checked again. Neither are holdings: this program does not know what the
ledger already holds.

Names defined here: ``export_backup``, ``ExportProblem``, ``ExportIssue``,
``ExportRefused``, ``BACKUP_FORMAT_VERSION`` and ``LEDGER_SCHEMA_VERSION``.
"""

from __future__ import annotations

import enum
import json
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from ledger_hand.core.coins import CoinTable
from ledger_hand.core.ledger_limits import (
    APP_VERSION_MAX_LENGTH,
    ID_MAX_LENGTH,
    QUOTE_CURRENCY,
    text_length,
    trim,
)
from ledger_hand.core.stored import StoredTrade
from ledger_hand.export.coin_card import coin_card, coin_card_id
from ledger_hand.export.moments import write_moment
from ledger_hand.export.trade_entry import trade_entry

# The versions of the ledger's formats this program writes. A change to
# either is a new format, and comes with a golden sample of its own.
BACKUP_FORMAT_VERSION = 3
LEDGER_SCHEMA_VERSION = 5

# Characters that are half of a surrogate pair. In a Python string they can
# only stand alone, since a whole pair is held as one character.
_SURROGATE_HALF = re.compile("[\ud800-\udfff]")


class ExportProblem(enum.Enum):
    """Why a set of trades cannot be written as a file."""

    NO_TRADES = "there is no trade to export"
    ID_EMPTY_OR_PADDED = "an identifier is empty or has whitespace at either end"
    ID_TOO_LONG = "an identifier is longer than the ledger allows"
    ID_USED_TWICE = "an identifier is used twice, by two trades or by a trade and a coin"
    COIN_NOT_IN_TABLE = "a trade names a coin the coin table does not hold"


@dataclass(frozen=True)
class ExportIssue:
    """One reason for a refusal; ``subject`` is the identifier or coin symbol concerned."""

    problem: ExportProblem
    subject: str


@dataclass(frozen=True)
class ExportRefused:
    """Why nothing was exported: every issue found, in the order of ``ExportProblem``."""

    issues: tuple[ExportIssue, ...]


def export_backup(
    trades: Iterable[StoredTrade],
    coins: CoinTable,
    *,
    exported_at: datetime,
    app_name: str,
    app_version: str,
) -> str | ExportRefused:
    """The text of a backup file holding ``trades``, or why it cannot be written.

    ``coins`` must hold every coin the trades use, including the coins the
    user confirmed. ``exported_at`` must carry an offset. The program's name
    and version are written as one text, joined by a hyphen
    (``ledger-hand-0.1.0``). A moment without an offset, or a name or version
    the ledger would refuse, is a mistake of the calling code and raises
    ``ValueError``.

    ``trades`` may be any collection, or a generator: it is read once.
    """
    app = _app_text(app_name, app_version)
    moment = write_moment(exported_at)
    # Read once into a tuple: a generator would look non-empty when it is
    # empty, and would be used up after the first of the passes below.
    trades = tuple(trades)
    if not trades:
        return ExportRefused((ExportIssue(ExportProblem.NO_TRADES, ""),))
    issues: list[ExportIssue] = []
    symbols = _coins_used(trades)
    cards = _coin_cards(symbols, coins, issues)
    _check_identifiers(trades, symbols, issues)
    if issues:
        return _refusal(issues)
    document = {
        "backupFormatVersion": BACKUP_FORMAT_VERSION,
        "appVersion": app,
        "exportedAt": moment,
        "ledgerSchemaVersion": LEDGER_SCHEMA_VERSION,
        "ledgerData": {
            "schemaVersion": LEDGER_SCHEMA_VERSION,
            "assets": cards,
            "trades": [trade_entry(trade) for trade in sorted(trades, key=_order)],
            "cashEvents": [],
            "assetTransfers": [],
            "priceSnapshots": [],
            "feeRules": [],
        },
    }
    return _as_text(document)


def _app_text(name: str, version: str) -> str:
    for part in (name, version):
        if not part or trim(part) != part:
            raise ValueError(f"the program's name and version must be trimmed text, not {part!r}")
    text = f"{name}-{version}"
    if text_length(text) > APP_VERSION_MAX_LENGTH:
        raise ValueError(f"{text!r} is longer than the ledger allows")
    return text


def _coins_used(trades: Sequence[StoredTrade]) -> list[str]:
    """The symbols of the coins traded and of the fee coins other than USDT, in order."""
    used = {trade.record.coin for trade in trades}
    used |= {trade.record.fee_coin for trade in trades if trade.record.fee_coin != QUOTE_CURRENCY}
    return sorted(used)


def _coin_cards(
    symbols: Sequence[str], coins: CoinTable, issues: list[ExportIssue]
) -> list[dict[str, object]]:
    cards = []
    for symbol in symbols:
        coin = coins.find(symbol)
        if coin is None or coin.symbol != symbol:
            issues.append(ExportIssue(ExportProblem.COIN_NOT_IN_TABLE, symbol))
        else:
            cards.append(coin_card(coin))
    return cards


def _check_identifiers(
    trades: Sequence[StoredTrade], symbols: Sequence[str], issues: list[ExportIssue]
) -> None:
    counts = Counter(trade.id for trade in trades)
    card_ids = {coin_card_id(symbol) for symbol in symbols}
    for identifier, count in sorted(counts.items()):
        if not identifier or trim(identifier) != identifier:
            issues.append(ExportIssue(ExportProblem.ID_EMPTY_OR_PADDED, identifier))
        if text_length(identifier) > ID_MAX_LENGTH:
            issues.append(ExportIssue(ExportProblem.ID_TOO_LONG, identifier))
        if count > 1 or identifier in card_ids:
            issues.append(ExportIssue(ExportProblem.ID_USED_TWICE, identifier))


def _refusal(issues: list[ExportIssue]) -> ExportRefused:
    rank = {problem: place for place, problem in enumerate(ExportProblem)}
    ordered = sorted(issues, key=lambda issue: (rank[issue.problem], issue.subject))
    return ExportRefused(tuple(ordered))


def _order(trade: StoredTrade) -> tuple[datetime, str]:
    """When ``trade`` happened, as an instant in UTC, and then its identifier."""
    occurred = trade.record.occurred
    if isinstance(occurred.value, datetime):
        start = occurred.value
    else:
        start = datetime.combine(occurred.value, time(), tzinfo=ZoneInfo(occurred.time_zone))
    return start.astimezone(timezone.utc), trade.id


def _as_text(document: dict[str, object]) -> str:
    text = json.dumps(document, ensure_ascii=False, indent=2)
    return _SURROGATE_HALF.sub(lambda found: f"\\u{ord(found.group()):04x}", text) + "\n"
