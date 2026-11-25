"""Sending the trades of a settled passage to the ledger, as one proposal to record them.

``propose`` takes a passage whose every trade is settled (``recording``),
the ledger port and, when the caller already has it, the ledger's list of
assets asked for at the start of the same turn. It makes the records
final, sorts out the trades it cannot send, each with its reason, and sends
the rest as one proposal; nothing is asked of the user again here, since
the user confirms or changes a proposal on the ledger's own page. Without
a list handed in, the ledger is asked for one, once.

Each trade is filled from the flow's record as it stands: its moment,
side, quantity, price, total and fee, the platform and the note. No figure
is worked out, rounded or converted here; a platform or note the flow left
out (``None``) is sent as empty text. The user's words, as they were said,
go into every trade (``raw_text``).

A trade is left out, and the others still sent, when:

- the user said to skip it, or the flow found it cannot be recorded;
- the flow held it back at the start, its quantity said in a unit that is
  not the asset traded ("25U" of ETH); it is told by that unit and the
  number as read, before any other reason it may also have;
- only its day was said: the ledger needs a moment, and no time of day is
  made up for it;
- the asset, the asset its fee was taken in, or the money it is priced in
  is not in the ledger, by its code, or that money is one the ledger
  prices no trade in: the user adds it there first; the assistant never
  does. This is checked again here, against the list, as a second guard.

With an asset table made from the ledger's list, the flow already finds
such a trade cannot be recorded; it is told here in the words above, with
the word the user said for the asset, and money traded as an asset is said
to be an exchange of currencies, which the assistant does not record.

A trade that names a code two assets of the ledger share (a coin and a
stock) is not sent either: both are named, and none is picked.

Each trade is priced in the money its record names. The ledger checks each
trade on its own: those it takes wait there, each as a proposal of its
own, and those it turns down are told with its reason; it may take all,
some or none. A ledger that cannot be asked ends it with its failure; one
that does not answer in time may have taken them, and they are never sent
again. The user's words go with the call (``said``), as said.

Names defined here: ``propose``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from ledger_hand.core.assets import AssetTable, MoneyReading
from ledger_hand.core.ledger_records import Asset, Pricing, TradeFacts
from ledger_hand.core.ledger_table import SameCode, same_code_words, same_codes
from ledger_hand.core.trade import TimePrecision, TradeDraft, TradeRecord
from ledger_hand.core.validation import Violation
from ledger_hand.extraction.issues import Issue
from ledger_hand.flows.progress import Progress, Stage, TradeState, TradeStatus
from ledger_hand.flows.recorded import LeftOut, LeftOutTrade, Recorded, RecordEnding, Sent
from ledger_hand.flows.recording import finish, held_other_unit
from ledger_hand.ports import LedgerError, LedgerErrorKind, LedgerPort

type _Numbered = tuple[int, TradeRecord]


def propose(
    progress: Progress, ledger: LedgerPort, listed: Sequence[Asset] | None = None
) -> Recorded:
    """Send the settled trades of ``progress`` to ``ledger`` as one proposal, as far as can be.

    ``listed`` is the ledger's list of assets when the caller asked for it
    already this turn; it is used as it is, and the ledger is not asked again.
    """
    if progress.stage is Stage.REVIEWING:
        progress = finish(progress)
    if progress.stage is not Stage.DONE:
        raise ValueError(f"only settled trades are proposed: {progress.stage.value}")
    left_out, records = _flow_left_out(progress)
    if not records:
        return Recorded(ending=RecordEnding.NOTHING_TO_SEND, progress=progress, left_out=left_out)
    try:
        listed = ledger.list_assets() if listed is None else listed
    except LedgerError as error:
        return Recorded(ending=RecordEnding.LEDGER_FAILED, progress=progress, failure=error)
    shared = {same.code: same for same in same_codes(listed)}
    left_out = tuple(_same_code(trade, shared) for trade in left_out)
    assets = {asset.code: asset for asset in listed if asset.code not in shared}
    numbers, trades, not_sent = _sendable(records, assets, shared, progress.passage)
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
        result = ledger.propose_add(trades, progress.passage)
    except LedgerError as error:
        if error.kind is LedgerErrorKind.TIMED_OUT:
            # The ledger's rule 4: it may have taken them; never send them again.
            return Recorded(
                ending=RecordEnding.MAYBE_SENT,
                progress=progress,
                trades=trades,
                numbers=numbers,
                left_out=left_out,
                failure=error,
            )
        return Recorded(ending=RecordEnding.LEDGER_FAILED, progress=progress, failure=error)
    if len(result.checks) != len(trades):
        raise ValueError("the ledger answered a number of checks that is not the trades sent")
    if result.none_passed:
        ending = RecordEnding.LEDGER_REFUSED
    else:
        ending = RecordEnding.SENT if result.all_passed else RecordEnding.PARTLY_SENT
    return Recorded(
        ending=ending,
        progress=progress,
        trades=trades,
        numbers=numbers,
        left_out=left_out,
        checks=result.checks,
        sent=Sent(proposals=result.proposal_ids) if result.proposal_ids else None,
    )


def _flow_left_out(progress: Progress) -> tuple[tuple[LeftOutTrade, ...], tuple[_Numbered, ...]]:
    """The trades the flow left out, with why, and its records, each with its number."""
    left_out: list[LeftOutTrade] = []
    records: list[_Numbered] = []
    assets = progress.setting.assets
    for number, trade in enumerate(progress.trades, start=1):
        if trade.status is TradeStatus.RECORDED and trade.record is not None:
            records.append((number, trade.record))
        elif trade.status is TradeStatus.CANNOT_RECORD:
            left_out.append(_cannot_record(number, trade, assets, progress.issues))
        else:
            left_out.append(LeftOutTrade(number=number, why=LeftOut.SKIPPED))
    return tuple(left_out), tuple(records)


def _cannot_record(
    number: int, trade: TradeState, assets: AssetTable, issues: tuple[Issue, ...]
) -> LeftOutTrade:
    """A trade the flow found cannot be recorded, with why; the ledger's own reasons by name.

    With a table made from the ledger's list, money traded as an asset, an
    asset or a fee's asset the ledger lacks, and money the ledger prices
    nothing in are told by what the user said, as the second guard below
    would tell them. Any other reason is the flow's own words. A trade
    held back at the start, with no reason of the core's, is told by the
    unit its quantity was said in, first.
    """
    draft = trade.draft
    if trade.reason is None:
        held = held_other_unit(number - 1, draft, issues, assets)
        if held is not None:
            return LeftOutTrade(
                number=number,
                why=LeftOut.QUANTITY_IN_OTHER_UNIT,
                code=draft.coin,
                quantity=draft.quantity,
                unit=held.phrase,
            )
    if assets.from_ledger:
        named = _ledger_reason(number, draft, trade.reason, assets)
        if named is not None:
            return named
    reason = trade.reason.value if trade.reason is not None else None
    return LeftOutTrade(number=number, why=LeftOut.CANNOT_RECORD, reason=reason)


def _ledger_reason(
    number: int, draft: TradeDraft, reason: object, assets: AssetTable
) -> LeftOutTrade | None:
    coin = draft.coin
    if coin is not None and assets.money(coin).reading is not MoneyReading.NOT_MONEY:
        return LeftOutTrade(number=number, why=LeftOut.MONEY_TRADED, code=coin)
    if reason is Violation.ASSET_NOT_IN_LEDGER and coin is not None:
        return LeftOutTrade(number=number, why=LeftOut.NOT_IN_LEDGER, code=coin)
    if reason is Violation.FEE_ASSET_NOT_IN_LEDGER and draft.fee_coin is not None:
        return LeftOutTrade(number=number, why=LeftOut.NOT_IN_LEDGER, code=draft.fee_coin)
    if reason is Violation.QUOTE_CANNOT_PRICE and draft.quote is not None:
        code = assets.money(draft.quote).code or draft.quote
        return LeftOutTrade(number=number, why=LeftOut.QUOTE_CANNOT_PRICE, code=code)
    return None


def _same_code(trade: LeftOutTrade, shared: Mapping[str, SameCode]) -> LeftOutTrade:
    """A trade left out for an asset the ledger lacks, told instead by the two assets that
    share its code, when that is why the table did not have it."""
    if trade.why is not LeftOut.NOT_IN_LEDGER or trade.code is None or trade.code not in shared:
        return trade
    words = same_code_words(shared[trade.code])
    return LeftOutTrade(number=trade.number, why=LeftOut.SAME_CODE, code=trade.code, reason=words)


def _sendable(
    records: Sequence[_Numbered],
    assets: Mapping[str, Asset],
    shared: Mapping[str, SameCode],
    said: str,
) -> tuple[tuple[int, ...], tuple[TradeFacts, ...], tuple[LeftOutTrade, ...]]:
    """The records that can be sent, as trades, with their numbers; the rest, with why."""
    numbers: list[int] = []
    trades: list[TradeFacts] = []
    not_sent: list[LeftOutTrade] = []
    for number, record in records:
        named = next((code for code in _codes(record) if code in shared), None)
        if named is not None:
            words = same_code_words(shared[named])
            not_sent.append(
                LeftOutTrade(number=number, why=LeftOut.SAME_CODE, code=named, reason=words)
            )
            continue
        why = _why_not(number, record, assets)
        if why is not None:
            not_sent.append(why)
            continue
        numbers.append(number)
        trades.append(_facts(record, assets, said))
    return tuple(numbers), tuple(trades), tuple(not_sent)


def _codes(record: TradeRecord) -> tuple[str, ...]:
    return tuple(code for code in (record.coin, record.fee_coin, record.quote) if code)


def _why_not(number: int, record: TradeRecord, assets: Mapping[str, Asset]) -> LeftOutTrade | None:
    if record.occurred.precision is TimePrecision.DAY or not isinstance(
        record.occurred.value, datetime
    ):
        return LeftOutTrade(number=number, why=LeftOut.DAY_ONLY, code=record.coin)
    for code in (record.coin, record.fee_coin, record.quote):
        if code not in assets:
            return LeftOutTrade(number=number, why=LeftOut.NOT_IN_LEDGER, code=code)
    if assets[record.quote].pricing is not Pricing.CAN_PRICE:
        return LeftOutTrade(number=number, why=LeftOut.QUOTE_CANNOT_PRICE, code=record.quote)
    return None


def _facts(record: TradeRecord, assets: Mapping[str, Asset], said: str) -> TradeFacts:
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
        quote=assets[record.quote].code,
        fee=record.fee,
        fee_asset=assets[record.fee_coin].code,
        platform=record.platform if record.platform is not None else "",
        note=record.note if record.note is not None else "",
        raw_text=said,
        zone=record.occurred.time_zone,
        date_only=False,
        cost_rate=None,
    )
