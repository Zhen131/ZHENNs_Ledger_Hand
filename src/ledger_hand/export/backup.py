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
  identifier either. Identifiers are compared as the ledger compares them, by
  their UTF-16 code units;
- a trade names a coin the coin table does not hold, so that its card cannot
  be written;
- a trade's time is a moment whose offset from UTC is not a whole number of
  minutes, which some zones had before the 1970s. The ledger's way of writing
  a time cannot hold such an offset. The check of a draft does not refuse one
  yet, so the export refuses it instead of failing while it writes;
- a trade's date, in its own time zone, is after the today handed in. The
  ledger refuses a trade dated after its own today, and it compares the date
  on the trade's own wall clock, not the instant.
- there are more trades, or more coins, than one ledger file may hold, or the
  text would be larger than one file may be (its UTF-8 bytes, counted the way
  the ledger counts them). These limits are the ledger's; ``ExportLimits``
  may lower them, never raise them. The size is known only once the text is
  written, so it is looked at only when nothing else stands in the way.

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
``ExportRefused``, ``ExportLimits``, ``LEDGER_LIMITS``,
``BACKUP_FORMAT_VERSION`` and ``LEDGER_SCHEMA_VERSION``.
"""

from __future__ import annotations

import enum
import json
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from ledger_hand.core.coins import CoinTable
from ledger_hand.core.ledger_limits import (
    APP_VERSION_MAX_LENGTH,
    ID_MAX_LENGTH,
    MAX_COINS_PER_FILE,
    MAX_FILE_BYTES,
    MAX_TRADES_PER_FILE,
    QUOTE_CURRENCY,
    text_length,
    trim,
)
from ledger_hand.core.stored import StoredTrade
from ledger_hand.core.zones import zone_named
from ledger_hand.export.coin_card import coin_card, coin_card_id
from ledger_hand.export.moments import write_moment
from ledger_hand.export.trade_entry import trade_entry

# The versions of the ledger's formats this program writes. A change to
# either is a new format, and comes with a golden sample of its own.
BACKUP_FORMAT_VERSION = 3
LEDGER_SCHEMA_VERSION = 5

_ONE_MINUTE = timedelta(minutes=1)

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
    OFFSET_NOT_WHOLE_MINUTES = (
        "a trade's time has an offset from UTC that is not a whole number of minutes"
    )
    DATED_AFTER_TODAY = "a trade's date, in its own time zone, is after today"
    TOO_MANY_COINS = "the trades use more coins than one ledger file may hold"
    TOO_MANY_TRADES = "there are more trades than one ledger file may hold"
    FILE_TOO_LARGE = "the file would be larger than the ledger reads"


@dataclass(frozen=True)
class ExportIssue:
    """One reason for a refusal.

    ``subject`` is the identifier or coin symbol concerned; for a limit, the
    number found (coins, trades or bytes); for no trades at all, empty.
    """

    problem: ExportProblem
    subject: str


@dataclass(frozen=True)
class ExportRefused:
    """Why nothing was exported: every issue found, in the order of ``ExportProblem``."""

    issues: tuple[ExportIssue, ...]


@dataclass(frozen=True, kw_only=True)
class ExportLimits:
    """How much one file may hold. Each may be lowered, never raised above the ledger's."""

    max_coins: int = MAX_COINS_PER_FILE
    max_trades: int = MAX_TRADES_PER_FILE
    max_bytes: int = MAX_FILE_BYTES

    def __post_init__(self) -> None:
        for name, ceiling in (
            ("max_coins", MAX_COINS_PER_FILE),
            ("max_trades", MAX_TRADES_PER_FILE),
            ("max_bytes", MAX_FILE_BYTES),
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= ceiling:
                raise ValueError(f"{name} must be a whole number from 1 to {ceiling}")


LEDGER_LIMITS = ExportLimits()


def export_backup(
    trades: Iterable[StoredTrade],
    coins: CoinTable,
    *,
    exported_at: datetime,
    today: date,
    app_name: str,
    app_version: str,
    limits: ExportLimits = LEDGER_LIMITS,
) -> str | ExportRefused:
    """The text of a backup file holding ``trades``, or why it cannot be written.

    ``coins`` must hold every coin the trades use, including the coins the
    user confirmed. ``exported_at`` must carry an offset. The program's name
    and version are written as one text, joined by a hyphen
    (``ledger-hand-0.1.0``). A moment without an offset, or a name or version
    the ledger would refuse, is a mistake of the calling code and raises
    ``ValueError``.

    ``today`` is the date on this machine, handed in by the caller. A trade
    whose date, in its own time zone, is after it is not exported: the ledger
    compares exactly that date with its own today, and a file it would read as
    holding a trade from the future is never written. A ``datetime``, or
    anything else that is not a plain date, raises ``TypeError``.

    ``limits`` are the ledger's own unless lower ones are handed in.

    ``trades`` may be any collection, or a generator: it is read once.
    """
    if isinstance(today, datetime) or not isinstance(today, date):
        raise TypeError(f"today must be a date, not {type(today).__name__}")
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
    _check_offsets(trades, issues)
    _check_dates(trades, today, issues)
    _check_counts(len(trades), len(symbols), limits, issues)
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
    text = _as_text(document)
    size = len(text.encode("utf-8"))
    if size > limits.max_bytes:
        return ExportRefused((ExportIssue(ExportProblem.FILE_TOO_LARGE, str(size)),))
    return text


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
    # Identifiers are compared as the ledger compares them, as UTF-16 code
    # units: a face held as one character and the same face held as its two
    # halves are different texts here and one identifier there.
    counts = Counter(_as_the_ledger_sees_it(trade.id) for trade in trades)
    card_ids = {_as_the_ledger_sees_it(coin_card_id(symbol)) for symbol in symbols}
    for identifier in sorted({trade.id for trade in trades}):
        seen = _as_the_ledger_sees_it(identifier)
        if not identifier or trim(identifier) != identifier:
            issues.append(ExportIssue(ExportProblem.ID_EMPTY_OR_PADDED, identifier))
        if text_length(identifier) > ID_MAX_LENGTH:
            issues.append(ExportIssue(ExportProblem.ID_TOO_LONG, identifier))
        if counts[seen] > 1 or seen in card_ids:
            issues.append(ExportIssue(ExportProblem.ID_USED_TWICE, identifier))


def _as_the_ledger_sees_it(text: str) -> bytes:
    """``text`` as UTF-16 code units, which is how the ledger holds and compares text."""
    return text.encode("utf-16-le", "surrogatepass")


def _check_offsets(trades: Sequence[StoredTrade], issues: list[ExportIssue]) -> None:
    for trade in trades:
        value = trade.record.occurred.value
        offset = value.utcoffset() if isinstance(value, datetime) else None
        if offset is not None and offset % _ONE_MINUTE:
            issues.append(ExportIssue(ExportProblem.OFFSET_NOT_WHOLE_MINUTES, trade.id))


def _check_dates(trades: Sequence[StoredTrade], today: date, issues: list[ExportIssue]) -> None:
    for trade in trades:
        if trade.record.occurred.calendar_date > today:
            issues.append(ExportIssue(ExportProblem.DATED_AFTER_TODAY, trade.id))


def _check_counts(trades: int, coins: int, limits: ExportLimits, issues: list[ExportIssue]) -> None:
    if coins > limits.max_coins:
        issues.append(ExportIssue(ExportProblem.TOO_MANY_COINS, str(coins)))
    if trades > limits.max_trades:
        issues.append(ExportIssue(ExportProblem.TOO_MANY_TRADES, str(trades)))


def _refusal(issues: list[ExportIssue]) -> ExportRefused:
    rank = {problem: place for place, problem in enumerate(ExportProblem)}
    ordered = sorted(issues, key=lambda issue: (rank[issue.problem], issue.subject))
    return ExportRefused(tuple(ordered))


def _order(trade: StoredTrade) -> tuple[timedelta, str]:
    """When ``trade`` happened, as a span since the first moment there is, then its identifier.

    The span is worked out from the wall clock and the offset, never by
    moving a time to UTC: the start of 1 January of the year 1 east of UTC,
    or of 31 December 9999 west of it, lies outside the years a ``datetime``
    can hold, and a span has room for both.
    """
    occurred = trade.record.occurred
    value = occurred.value
    if isinstance(value, datetime):
        wall = value.replace(tzinfo=None)
        offset = value.utcoffset()
    else:
        wall = datetime.combine(value, time())
        offset = zone_named(occurred.time_zone).utcoffset(wall)
    return wall - datetime.min - (offset or timedelta(0)), trade.id


def _as_text(document: dict[str, object]) -> str:
    text = json.dumps(document, ensure_ascii=False, indent=2)
    return _SURROGATE_HALF.sub(lambda found: f"\\u{ord(found.group()):04x}", text) + "\n"
