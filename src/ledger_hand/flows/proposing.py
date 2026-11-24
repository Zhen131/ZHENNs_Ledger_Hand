"""Sending the trades of a settled passage to the ledger, as one proposal to record them.

``propose`` takes a passage whose every trade is settled (``recording``) and
the ledger port. It makes the records final, sorts out the trades it cannot
send, each with its reason, and sends the rest as one proposal; nothing is
asked of the user again here, since the user confirms or changes a
proposal on the ledger's own page.

Each trade is filled from the flow's record as it stands: its moment,
side, quantity, price, total and fee, the platform and the note. No figure
is worked out, rounded or converted here; a platform or note the flow left
out (``None``) is sent as empty text. The user's words, as they were said,
go into every trade (``raw_text``).

A trade is left out, and the others still sent, when:

- the user said to skip it, or the flow found it cannot be recorded;
- only its day was said: the ledger needs a moment, and no time of day is
  made up for it;
- the asset, or the asset its fee was taken in, is not in the ledger, by
  its code: the user adds it there first; the assistant never does.

The money the trades are priced in comes from the ledger's own list: the
asset whose code is the extraction's one money. Without it in the ledger,
nothing is sent. A ledger that turns the proposal down keeps nothing; a
ledger that cannot be asked ends it with its failure.

Names defined here: ``propose``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from ledger_hand.core import ledger_limits
from ledger_hand.core.ledger_records import Asset, TradeFacts
from ledger_hand.core.trade import TimePrecision, TradeRecord
from ledger_hand.flows.progress import Progress, Stage, TradeStatus
from ledger_hand.flows.recorded import LeftOut, LeftOutTrade, Recorded, RecordEnding, Sent
from ledger_hand.flows.recording import finish
from ledger_hand.ports import LedgerError, LedgerPort

# For now only: the flow's records carry no money they are priced in, since
# extraction knows one. Remove this once the money comes from the ledger.
_PRICED_IN = ledger_limits.QUOTE_CURRENCY

type _Numbered = tuple[int, TradeRecord]


def propose(progress: Progress, ledger: LedgerPort) -> Recorded:
    """Send the settled trades of ``progress`` to ``ledger`` as one proposal, as far as can be."""
    if progress.stage is Stage.REVIEWING:
        progress = finish(progress)
    if progress.stage is not Stage.DONE:
        raise ValueError(f"only settled trades are proposed: {progress.stage.value}")
    left_out, records = _flow_left_out(progress)
    if not records:
        return Recorded(ending=RecordEnding.NOTHING_TO_SEND, progress=progress, left_out=left_out)
    try:
        assets = {asset.code: asset for asset in ledger.list_assets()}
    except LedgerError as error:
        return Recorded(ending=RecordEnding.LEDGER_FAILED, progress=progress, failure=error)
    if _PRICED_IN not in assets:
        return Recorded(
            ending=RecordEnding.NO_QUOTE_IN_LEDGER, progress=progress, missing_money=_PRICED_IN
        )
    numbers, trades, not_sent = _sendable(records, assets, assets[_PRICED_IN], progress.passage)
    left_out = tuple(sorted((*left_out, *not_sent), key=lambda trade: trade.number))
    if not trades:
        return Recorded(ending=RecordEnding.NOTHING_TO_SEND, progress=progress, left_out=left_out)
    return _sent(progress, ledger, numbers, trades, left_out)


def _sent(
    progress: Progress,
    ledger: LedgerPort,
    numbers: tuple[int, ...],
    trades: tuple[TradeFacts, ...],
    left_out: tuple[LeftOutTrade, ...],
) -> Recorded:
    try:
        result = ledger.propose_add(trades)
    except LedgerError as error:
        return Recorded(ending=RecordEnding.LEDGER_FAILED, progress=progress, failure=error)
    if result.proposal_id is None:
        return Recorded(
            ending=RecordEnding.LEDGER_REFUSED,
            progress=progress,
            trades=trades,
            numbers=numbers,
            left_out=left_out,
            checks=result.checks,
        )
    return Recorded(
        ending=RecordEnding.SENT,
        progress=progress,
        trades=trades,
        numbers=numbers,
        left_out=left_out,
        sent=Sent(proposal=result.proposal_id, trades=len(trades)),
    )


def _flow_left_out(progress: Progress) -> tuple[tuple[LeftOutTrade, ...], tuple[_Numbered, ...]]:
    """The trades the flow left out, with why, and its records, each with its number."""
    left_out: list[LeftOutTrade] = []
    records: list[_Numbered] = []
    for number, trade in enumerate(progress.trades, start=1):
        if trade.status is TradeStatus.RECORDED and trade.record is not None:
            records.append((number, trade.record))
        elif trade.status is TradeStatus.CANNOT_RECORD:
            reason = trade.reason.value if trade.reason is not None else None
            left_out.append(LeftOutTrade(number=number, why=LeftOut.CANNOT_RECORD, reason=reason))
        else:
            left_out.append(LeftOutTrade(number=number, why=LeftOut.SKIPPED))
    return tuple(left_out), tuple(records)


def _sendable(
    records: Sequence[_Numbered], assets: Mapping[str, Asset], priced_in: Asset, said: str
) -> tuple[tuple[int, ...], tuple[TradeFacts, ...], tuple[LeftOutTrade, ...]]:
    """The records that can be sent, as trades, with their numbers; the rest, with why."""
    numbers: list[int] = []
    trades: list[TradeFacts] = []
    not_sent: list[LeftOutTrade] = []
    for number, record in records:
        why = _why_not(number, record, assets)
        if why is not None:
            not_sent.append(why)
            continue
        numbers.append(number)
        trades.append(_facts(record, assets, priced_in, said))
    return tuple(numbers), tuple(trades), tuple(not_sent)


def _why_not(number: int, record: TradeRecord, assets: Mapping[str, Asset]) -> LeftOutTrade | None:
    if record.occurred.precision is TimePrecision.DAY or not isinstance(
        record.occurred.value, datetime
    ):
        return LeftOutTrade(number=number, why=LeftOut.DAY_ONLY, code=record.coin)
    for code in (record.coin, record.fee_coin):
        if code not in assets:
            return LeftOutTrade(number=number, why=LeftOut.NOT_IN_LEDGER, code=code)
    return None


def _facts(
    record: TradeRecord, assets: Mapping[str, Asset], priced_in: Asset, said: str
) -> TradeFacts:
    """The record as the ledger takes it: every figure as the flow gave it."""
    moment = record.occurred.value
    if not isinstance(moment, datetime):
        raise ValueError("a trade known only to the day is never sent")
    return TradeFacts(
        occurred=moment,
        side=record.side,
        asset=assets[record.coin].code,
        quantity=record.quantity,
        price=record.price,
        total=record.total,
        quote=priced_in.code,
        fee=record.fee,
        fee_asset=assets[record.fee_coin].code,
        platform=record.platform if record.platform is not None else "",
        note=record.note if record.note is not None else "",
        raw_text=said,
    )
