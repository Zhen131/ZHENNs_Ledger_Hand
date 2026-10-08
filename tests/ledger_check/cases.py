"""What the ledger tier checks: the sample files, what each should get, and the export's limits.

``scripts/ledger_check.py`` reads these cases and does the checking; this
module only says what to check, as plain data, beside the invented trades it
is made from.

- ``light_cases``: sample files for the ledger to judge, each with what it
  should get and the date the ledger is to take as today.
- ``heavy_cases``: one sample file exactly as large as the ledger reads, built
  only when the tier runs.
- ``limit_refusals``: inputs one past the ledger's limits of one file, which
  the export itself must refuse, built only when the tier runs.
- ``zone_agreed_cases``: the trades of the two samples that allow for the gap
  between the two time zone databases, to be judged strictly once the trades
  the two databases disagree on are left out. Which trades those are is
  known only when the tier runs and asks both sides, so the tier builds these
  samples itself.

One sample is not exported directly: ``flow_export_text`` saves invented
trades in a book in a temporary folder and takes the file the export flow
writes, so that what the flow writes is judged by the ledger too.

Most samples are exported with the same today they are judged on, because
that is the promise: what the export lets through on a given day, the ledger
accepts on that day. One sample is judged a day earlier on purpose, to show
that the ledger really is given the today it is meant to be given.
"""

from __future__ import annotations

import enum
import json
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from ledger_hand.core.book import ConfirmedCoin, PassageSave
from ledger_hand.core.coins import BUILT_IN_TABLE, CoinTable
from ledger_hand.core.ledger_limits import MAX_COINS_PER_FILE, MAX_FILE_BYTES, MAX_TRADES_PER_FILE
from ledger_hand.core.stored import StoredTrade
from ledger_hand.core.trade import Side, TradeDraft
from ledger_hand.export.backup import ExportProblem, ExportRefused, export_backup
from ledger_hand.flows.exporting import ExportResult
from ledger_hand.flows.exporting import export as export_from_the_book
from ledger_hand.flows.fingerprint import passage_fingerprint
from ledger_hand.storage.sqlite_store import SqliteStore
from tests.export import attack, samples
from tests.export.samples import APP_NAME, APP_VERSION, BUDAPEST, CREATED, EXPORTED_AT, TODAY

HAND_WRITTEN_EXAMPLE = Path(__file__).parent / "hand_written_example.json"
DAY_BEFORE_ACROSS = attack.ACROSS_TODAY - timedelta(days=1)


class Expect(enum.Enum):
    """What the ledger should say about a sample file."""

    ACCEPTED = "accepted with no error"
    HOLDINGS_ONLY = "refused only for selling more than is held"
    ACCEPTED_EXCEPT_ZONE_DATA = "accepted, except offsets where the two zone databases disagree"
    PLANTED = "refused with exactly the planted errors"


@dataclass(frozen=True)
class Case:
    """One sample file. ``planted`` lists (code, path, a piece of the message) for ``PLANTED``."""

    name: str
    build: Callable[[], str]
    expect: Expect
    today: date = TODAY
    planted: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True)
class AgreedCase:
    """The trades of the sample named ``source``, without those the two databases disagree on.

    Judged strictly: accepted with no error. ``trades`` are exported again,
    on ``today``, once the tier knows which of them to leave out.
    """

    name: str
    source: str
    trades: Callable[[], list[StoredTrade]]
    today: date
    coins: CoinTable = BUILT_IN_TABLE


@dataclass(frozen=True)
class LimitRefusal:
    """An input the export must refuse for one of the ledger's limits, with the number found."""

    name: str
    build: Callable[[], str | ExportRefused]
    problem: ExportProblem
    subject: str


def export(
    trades: list[StoredTrade], coins: CoinTable = BUILT_IN_TABLE, today: date = TODAY
) -> str | ExportRefused:
    return export_backup(
        trades,
        coins,
        exported_at=EXPORTED_AT,
        today=today,
        app_name=APP_NAME,
        app_version=APP_VERSION,
    )


def text_of(
    trades: list[StoredTrade], coins: CoinTable = BUILT_IN_TABLE, today: date = TODAY
) -> str:
    result = export(trades, coins, today)
    if isinstance(result, ExportRefused):
        raise AssertionError(f"the export refused a sample: {result}")
    return result


def _future_on_the_day_before(text: str) -> tuple[tuple[str, str, str], ...]:
    """The errors the ledger gives for ``text`` judged on the day before its today."""
    trades = json.loads(text)["ledgerData"]["trades"]
    return tuple(
        ("LEDGER_IMPORT_FUTURE_FACT", f"trades[{place}].occurredAt", trade["occurredAt"][:10])
        for place, trade in enumerate(trades)
        if trade["occurredAt"][:10] > DAY_BEFORE_ACROSS.isoformat()
    )


def light_cases() -> list[Case]:
    """Every sample file but the very large one, in the order they are reported."""
    broken = samples.broken_texts()
    across = text_of(attack.across_zones(), today=attack.ACROSS_TODAY)
    at_limit = text_of(attack.coins_at_limit(), attack.coins_at_limit_coins())
    return [
        Case(
            "hand-written-example.json",
            lambda: HAND_WRITTEN_EXAMPLE.read_text(encoding="utf-8"),
            Expect.ACCEPTED,
        ),
        Case(
            samples.GOLDEN_FILE.name,
            lambda: samples.GOLDEN_FILE.read_text(encoding="utf-8"),
            Expect.ACCEPTED,
        ),
        Case("edges.json", samples.edge_text, Expect.ACCEPTED),
        Case("third-coin-fee.json", samples.third_coin_fee_text, Expect.ACCEPTED),
        Case("every-zone.json", samples.every_zone_text, Expect.ACCEPTED),
        Case(
            "attack-first-days.json",
            lambda: text_of(attack.first_days()),
            Expect.ACCEPTED,
        ),
        Case(
            "attack-earliest-moments.json",
            lambda: text_of(attack.earliest_moments()),
            Expect.ACCEPTED,
        ),
        Case(
            "attack-last-days.json",
            lambda: text_of(attack.last_days(), today=attack.LAST_TODAY),
            Expect.ACCEPTED_EXCEPT_ZONE_DATA,
            today=attack.LAST_TODAY,
        ),
        Case(
            "attack-characters.json",
            lambda: text_of(attack.characters(), attack.characters_coins()),
            Expect.ACCEPTED,
        ),
        Case(
            "attack-numbers.json",
            lambda: text_of(attack.numbers(), attack.numbers_coins()),
            Expect.ACCEPTED,
        ),
        Case(
            "attack-full-run.json",
            lambda: text_of(attack.full_run(), attack.full_run_coins()),
            Expect.ACCEPTED,
        ),
        Case("across-zones.json", lambda: across, Expect.ACCEPTED, today=attack.ACROSS_TODAY),
        Case(
            "attack-every-zone-on-the-day.json",
            lambda: text_of(attack.every_zone_on_the_day(), today=attack.ACROSS_TODAY),
            Expect.ACCEPTED_EXCEPT_ZONE_DATA,
            today=attack.ACROSS_TODAY,
        ),
        Case(
            "across-zones-judged-a-day-early.json",
            lambda: across,
            Expect.PLANTED,
            today=DAY_BEFORE_ACROSS,
            planted=_future_on_the_day_before(across),
        ),
        Case(f"coins-at-limit-{MAX_COINS_PER_FILE}.json", lambda: at_limit, Expect.ACCEPTED),
        Case(
            f"broken-coins-{MAX_COINS_PER_FILE + 1}.json",
            lambda: attack.with_one_more_coin_card(at_limit),
            Expect.PLANTED,
            planted=(
                (
                    "LEDGER_RESOURCE_COLLECTION_LIMIT_EXCEEDED",
                    "assets",
                    f"{MAX_COINS_PER_FILE + 1} > {MAX_COINS_PER_FILE}",
                ),
            ),
        ),
        Case("sell-only.json", samples.sell_only_text, Expect.HOLDINGS_ONLY),
        Case(
            "broken-total-off.json",
            lambda: broken["total-off"],
            Expect.PLANTED,
            planted=(
                ("LEDGER_DATA_INVALID_ENTITY", "trades[0].totalValue", "TOTAL_VALUE_MISMATCH"),
            ),
        ),
        Case(
            "broken-fee-coin-missing.json",
            lambda: broken["fee-coin-missing"],
            Expect.PLANTED,
            planted=(
                (
                    "LEDGER_DATA_INVALID_REFERENCE",
                    "trades[0].feeCurrency",
                    "Unknown fee asset: BNB",
                ),
            ),
        ),
        Case("flow-export.json", flow_export_text, Expect.ACCEPTED),
        Case(
            "broken-zone-disagrees.json",
            lambda: broken["zone-disagrees"],
            Expect.PLANTED,
            planted=(
                (
                    "LEDGER_DATA_INVALID_ENTITY",
                    "trades[2].occurredAt",
                    "offset must match occurredTimeZone",
                ),
            ),
        ),
    ]


def zone_agreed_cases() -> list[AgreedCase]:
    """The two samples that allow for the zone-data gap, again, without the trades it touches."""
    return [
        AgreedCase(
            "attack-last-days-where-zone-data-agree.json",
            "attack-last-days.json",
            attack.last_days,
            attack.LAST_TODAY,
        ),
        AgreedCase(
            "attack-every-zone-on-the-day-where-zone-data-agree.json",
            "attack-every-zone-on-the-day.json",
            attack.every_zone_on_the_day,
            attack.ACROSS_TODAY,
        ),
    ]


def flow_trades() -> tuple[list[StoredTrade], CoinTable]:
    """The golden sample's trades and one in a coin the user confirmed, with the coin table."""
    coins = BUILT_IN_TABLE.with_confirmed("PIKA")
    pika = samples.saved(
        "flow-pika",
        TradeDraft(
            side=Side.BUY,
            coin="PIKA",
            quantity=samples.number("1000"),
            price=samples.number("0.05"),
            fee=samples.number("0"),
            fee_coin="USDT",
            occurred=samples.wall(BUDAPEST, (2026, 10, 3, 20, 15)),
            raw_text="昨晚 8 点 15 买了 1000 个 PIKA，0.05 一个，没有手续费",
        ),
        coins,
    )
    return [*samples.golden_trades(), pika], coins


def flow_export_text() -> str:
    """The file the export flow writes from a book of invented trades, in a temporary folder.

    Each trade is saved as a passage of its own, the coin the user confirmed
    with the trade that uses it; the export runs at the samples' export
    moment in Budapest, so its today is the samples' today.
    """
    trades, _ = flow_trades()
    with tempfile.TemporaryDirectory(prefix="ledger-hand-flow-") as scratch:
        folder = Path(scratch)
        book = SqliteStore(folder / "book.sqlite3")
        for trade in trades:
            confirmed = trade.record.coin == "PIKA"
            book.save(
                PassageSave(
                    fingerprint=passage_fingerprint(trade.record.raw_text),
                    saved_at=CREATED,
                    trades=(trade,),
                    coins=(ConfirmedCoin(symbol="PIKA", confirmed_at=CREATED),)
                    if confirmed
                    else (),
                )
            )
        outcome = export_from_the_book(book, folder / "exports", now=EXPORTED_AT, zone=BUDAPEST)
        if outcome.result is not ExportResult.EXPORTED or outcome.path is None:
            raise AssertionError(f"the export flow did not write the sample: {outcome}")
        return outcome.path.read_text(encoding="utf-8")


def _size_of(trades: list[StoredTrade]) -> int:
    result = export(trades)
    if isinstance(result, ExportRefused):
        (issue,) = result.issues
        assert issue.problem is ExportProblem.FILE_TOO_LARGE
        return int(issue.subject)
    return len(result.encode("utf-8"))


def heavy_cases() -> list[Case]:
    """A file exactly as large as the ledger reads; about 128 MiB, so built only when run."""
    return [
        Case(
            f"file-of-{MAX_FILE_BYTES}-bytes.json",
            lambda: text_of(attack.file_trades(MAX_FILE_BYTES, _size_of)),
            Expect.ACCEPTED,
        )
    ]


def limit_refusals() -> list[LimitRefusal]:
    """One past each of the ledger's limits of one file; the export itself must refuse each."""
    many_coins = MAX_COINS_PER_FILE + 1
    return [
        LimitRefusal(
            f"{many_coins} coins",
            lambda: export(
                attack.coins_at_limit(many_coins), attack.coins_at_limit_coins(many_coins)
            ),
            ExportProblem.TOO_MANY_COINS,
            str(many_coins),
        ),
        LimitRefusal(
            "one trade more than one file may hold",
            lambda: export(attack.too_many_trades()),
            ExportProblem.TOO_MANY_TRADES,
            str(MAX_TRADES_PER_FILE + 1),
        ),
        LimitRefusal(
            "one byte more than the ledger reads",
            lambda: export(attack.file_trades(MAX_FILE_BYTES + 1, _size_of)),
            ExportProblem.FILE_TOO_LARGE,
            str(MAX_FILE_BYTES + 1),
        ),
    ]
