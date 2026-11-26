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
go into every trade (``raw_text``): the progress's own ``raw_text`` when
the passage was tidied from them on the assistant's way, the passage
itself otherwise.

A trade is left out, and the others still sent, when:

- the user said to skip it, or the flow found it cannot be recorded;
- the flow held it back at the start, its quantity said in a unit that is
  not the asset traded ("25U" of ETH); it is told by that unit and the
  number as read, before any other reason it may also have;
- the money it is priced in, or its fee was taken in, is a money the
  ledger does not have at all ("欧元" with no euro): it is told so, by
  that money's code, never as an asset the ledger lacks;
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

A trade known only to its day is sent with its day alone (``date_only``):
no time of day is made up for it, and the ledger takes it so.

Once the trades to send are known, and only then, the ledger is asked
once for its market prices. Each trade's price is compared with its
asset's (``core/price_check.py``), far at ``gap`` times apart
(``settings.LEDGER_HAND_PRICE_GAP_TIMES``), and the marks on its cells
are worked out (``core/marks.py``, ``core/card_record.py``): they come
back with the proposal (``Recorded.marked``), for the user to see. A
ledger that cannot be asked for its market prices leaves every price not
compared, and the trades are sent all the same. A card whose price or
money used is empty is not compared.

Each trade goes as a card (``core/trade_card.py``). When the flow was
told the ledger takes cards (``Setting.unfinished``), every card is sent
that way (``propose_cards``), with its marks after the guard
(``marks.sent_marks``): a cell sent empty keeps only a suspicious mark,
and no time of day is marked when none is sent. A trade the flow settled
with cells left empty or marked (``TradeStatus.UNFINISHED``) is sent
with those cells empty (``null``), never 0. Otherwise every trade is
whole and is sent as before (``propose_add``), its marks kept here.

A trade paid in one money for an asset the ledger prices in another (its
record holds the price said in the asset's own money, ``said_price``) is
sent with its rate between the two moneys (``costRate``): the quantity
times the price said over the total paid, worked out by
``core/cost_rate.py``. Every other trade is sent with no rate, as before.
Its rate is compared with the rate of the latest trade in the ledger paid
in the same money for an asset priced in the same money: the asset's own
trades as listed when its money was looked up, and otherwise those of one
more call for trades with no condition, asked once for the whole proposal;
far at ``rate_gap`` in a hundred (``settings.LEDGER_HAND_RATE_GAP_PERCENT``),
not compared when there is no such trade. The price said is compared with
the ledger's market price of the asset, in that same money. Either one far
marks the rate suspicious, and the trade is sent all the same; what came of
it goes back with the proposal (``MarkedTrade.rate``), for the words said.

A trade whose fee is taken in a money other than the one it was paid in
(paid in USD, fee in EUR) has its fee's money marked suspicious: nothing
else changes (2026-11-26).

Each trade is priced in the money its record names. The ledger checks each
trade on its own: those it takes wait there, each as a proposal of its
own, and those it turns down are told with its reason; it may take all,
some or none. A ledger that cannot be asked ends it with its failure; one
that does not answer in time may have taken them, and they are never sent
again. The user's words go with the call (``said``), as said.

Names defined here: ``propose``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from ledger_hand.core.asset_words import problem_words
from ledger_hand.core.assets import AssetTable, MoneyReading
from ledger_hand.core.card_record import CardRecord, card_marks
from ledger_hand.core.cost_rate import (
    RateNote,
    RateReference,
    far_from_reference,
    rate_of,
    reference_in,
    with_rate_marks,
)
from ledger_hand.core.ledger_records import (
    Asset,
    AssetKind,
    LedgerTrade,
    MarketPrice,
    Pricing,
    TradeFacts,
    TradeFilter,
)
from ledger_hand.core.ledger_table import SameCode, same_code_words, same_codes
from ledger_hand.core.marks import (
    fee_money_mark,
    fields_sent,
    marks_for,
    sent_marks,
    with_mark,
)
from ledger_hand.core.price_check import PriceCheck, check_price, no_price, not_asked
from ledger_hand.core.trade import TradeDraft, TradeRecord
from ledger_hand.core.trade_card import TradeCard, card_of
from ledger_hand.core.validation import Violation, amounts_agree
from ledger_hand.extraction.issues import Issue
from ledger_hand.flows.progress import Progress, Stage, TradeState, TradeStatus
from ledger_hand.flows.recorded import (
    LeftOut,
    LeftOutTrade,
    MarkedTrade,
    Recorded,
    RecordEnding,
    Sent,
)
from ledger_hand.flows.recording import finish, held_other_unit
from ledger_hand.ports import LedgerError, LedgerErrorKind, LedgerPort
from ledger_hand.settings import DEFAULT_PRICE_GAP_TIMES, DEFAULT_RATE_GAP_PERCENT

type _Sendable = TradeRecord | CardRecord
type _Numbered = tuple[int, _Sendable]


def propose(
    progress: Progress,
    ledger: LedgerPort,
    listed: Sequence[Asset] | None = None,
    *,
    gap: Decimal = DEFAULT_PRICE_GAP_TIMES,
    rate_gap: Decimal = DEFAULT_RATE_GAP_PERCENT,
) -> Recorded:
    """Send the settled trades of ``progress`` to ``ledger`` as one proposal, as far as can be.

    ``listed`` is the ledger's list of assets when the caller asked for it
    already this turn; it is used as it is, and the ledger is not asked again.
    ``gap`` is how many times apart a price and the market price are far;
    ``rate_gap`` how far apart, in a hundred, a rate and the last one are.
    """
    if progress.stage is Stage.REVIEWING:
        progress = finish(progress)
    if progress.stage is not Stage.DONE:
        raise ValueError(f"only settled trades are proposed: {progress.stage.value}")
    left_out, records = _flow_left_out(progress)
    if not records:
        left_out = _told_by_same_code(left_out, ledger, listed)
        return Recorded(ending=RecordEnding.NOTHING_TO_SEND, progress=progress, left_out=left_out)
    try:
        listed = ledger.list_assets() if listed is None else listed
    except LedgerError as error:
        return Recorded(ending=RecordEnding.LEDGER_FAILED, progress=progress, failure=error)
    shared = {same.code: same for same in same_codes(listed)}
    left_out = tuple(_same_code(trade, shared) for trade in left_out)
    assets = {asset.code: asset for asset in listed if asset.code not in shared}
    said = progress.raw_text if progress.raw_text is not None else progress.passage
    numbers, trades, not_sent = _sendable(records, assets, shared, said)
    left_out = tuple(sorted((*left_out, *not_sent), key=lambda trade: trade.number))
    if not trades:
        return Recorded(ending=RecordEnding.NOTHING_TO_SEND, progress=progress, left_out=left_out)
    rates = _rates(numbers, dict(records), progress, ledger, rate_gap)
    trades = tuple(
        dataclasses.replace(card, cost_rate=rates[number].rate) if number in rates else card
        for number, card in zip(numbers, trades, strict=True)
    )
    marked = _marked(numbers, dict(records), ledger, assets, gap, rates)
    trades = tuple(
        dataclasses.replace(card, marks=sent_marks(one.marks, fields_sent(card)))
        for card, one in zip(trades, marked, strict=True)
    )
    return _sent(progress, ledger, numbers, trades, left_out, marked)


def _rates(
    numbers: tuple[int, ...],
    records: Mapping[int, _Sendable],
    progress: Progress,
    ledger: LedgerPort,
    rate_gap: Decimal,
) -> dict[int, RateNote]:
    """Each trade paid in another money, by its number: its rate, compared with the last one.

    The price said is not compared with the market price here (``_marked``
    does).
    """
    rated: dict[int, RateNote] = {}
    every: list[tuple[LedgerTrade, ...] | None] = []
    share = rate_gap / 100
    for number in numbers:
        record = records[number]
        said = record.said_price
        if said is None or record.quantity is None or record.total is None:
            continue
        rate = rate_of(record.quantity, said.amount, record.total)
        reference = _reference(record, progress, ledger, every)
        far = reference is not None and far_from_reference(rate, reference.rate, share)
        dropped = said.dropped
        disagrees = dropped is not None and not amounts_agree(
            record.quantity, dropped, record.total
        )
        kind = progress.setting.assets.kind_of(record.coin)
        note = RateNote(
            rate=rate,
            said=said,
            quantity=record.quantity,
            total=record.total,
            each="a share" if kind == AssetKind.STOCK.value else f"per {record.coin}",
            reference=reference,
            reference_far=far,
            dropped_disagrees=disagrees,
        )
        rated[number] = note
    return rated


def _reference(
    record: _Sendable,
    progress: Progress,
    ledger: LedgerPort,
    every: list[tuple[LedgerTrade, ...] | None],
) -> RateReference | None:
    """The trade the rate of ``record`` is compared with, or ``None`` when there is none.

    The asset's own trades as listed when its money was looked up come
    first; then, asked once for the whole proposal and kept in ``every``,
    the ledger's trades with no condition, the asset's own first. A ledger
    that cannot be asked gives none.
    """
    said = record.said_price
    assert said is not None
    setting = progress.setting
    priced = dict(setting.assets.priced_in)
    own = dict(progress.last_moneys).get(record.coin)
    if own is not None:
        found = reference_in(own.listed, said.paid, said.money, priced, setting.now)
        if found is not None:
            return found
    if not every:
        try:
            every.append(ledger.list_trades(TradeFilter()).trades)
        except LedgerError:
            every.append(None)
    listed = every[0]
    if listed is None:
        return None
    mine = tuple(trade for trade in listed if trade.facts.asset == record.coin)
    found = reference_in(mine, said.paid, said.money, priced, setting.now)
    if found is not None:
        return found
    return reference_in(listed, said.paid, said.money, priced, setting.now)


def _marked(
    numbers: tuple[int, ...],
    records: Mapping[int, _Sendable],
    ledger: LedgerPort,
    assets: Mapping[str, Asset],
    gap: Decimal,
    rates: Mapping[int, RateNote],
) -> tuple[MarkedTrade, ...]:
    """Each trade to send, its price compared with the market price and its cells marked.

    The ledger is asked for its market prices once. When it cannot be asked,
    no price is compared and the trades are still sent (decided on 2026-11-25).
    """
    markets: tuple[MarketPrice, ...] = ()
    failure: str | None = None
    try:
        markets = ledger.market_prices()
    except LedgerError as error:
        failure = error.message
    marked: list[MarkedTrade] = []
    for number in numbers:
        record = records[number]
        check = _price_check(record, markets, failure, gap)
        asset = assets.get(record.coin)
        name = asset.name if asset is not None else None
        if isinstance(record, CardRecord):
            marks = card_marks(record, check, asset_name=name)
        else:
            marks = marks_for(record, check, asset_name=name)
        fee_money = _fee_money_apart(record, assets)
        if fee_money is not None:
            marks = with_mark(marks, fee_money_mark(fee_money, record.quote or ""))
        note = rates.get(number)
        if note is not None:
            note = dataclasses.replace(
                note, market=_said_check(note, record, markets, failure, gap)
            )
            marks = with_rate_marks(marks, note, record.coin)
        marked.append(MarkedTrade(marks=marks, price=check, rate=note))
    return tuple(marked)


def _fee_money_apart(record: _Sendable, assets: Mapping[str, Asset]) -> str | None:
    """The fee's money when it is a money other than the one the trade was paid in, or ``None``.

    A fee taken in the asset traded, or a fee or trade whose money is empty,
    is not one. Example: paid in USD, fee in EUR: "EUR".
    """
    fee, paid = record.fee_coin, record.quote
    if fee is None or paid is None or fee == paid or fee == record.coin:
        return None
    asset = assets.get(fee)
    if asset is None or not (asset.kind is AssetKind.CASH or asset.pricing is Pricing.CAN_PRICE):
        return None
    return fee


def _said_check(
    note: RateNote,
    record: _Sendable,
    markets: Sequence[MarketPrice],
    failure: str | None,
    gap: Decimal,
) -> PriceCheck | None:
    """The price said in the asset's own money against its market price, in that money;
    ``None`` when the ledger could not be asked for its market prices."""
    if failure is not None:
        return None
    own = [market for market in markets if market.asset == record.coin]
    return check_price(note.said.amount, note.said.money, own, gap)


def _price_check(
    record: _Sendable, markets: Sequence[MarketPrice], failure: str | None, gap: Decimal
) -> PriceCheck:
    """One trade's price against its asset's market price; a card with no price, none."""
    if record.price is None:
        return no_price(record.quote)
    if failure is not None:
        return not_asked(record.price, record.quote, failure)
    own = [market for market in markets if market.asset == record.coin]
    return check_price(record.price, record.quote, own, gap)


def _sent(
    progress: Progress,
    ledger: LedgerPort,
    numbers: tuple[int, ...],
    trades: tuple[TradeCard, ...],
    left_out: tuple[LeftOutTrade, ...],
    marked: tuple[MarkedTrade, ...],
) -> Recorded:
    try:
        said = progress.raw_text if progress.raw_text is not None else progress.passage
        if progress.setting.unfinished:
            result = ledger.propose_cards(trades, said)
        else:
            whole = tuple(card.facts for card in trades if card.facts is not None)
            if len(whole) != len(trades):
                raise ValueError("a trade with an empty cell goes only to a ledger that takes it")
            result = ledger.propose_add(whole, said)
    except LedgerError as error:
        if error.kind is LedgerErrorKind.TIMED_OUT:
            # The ledger's rule 4: it may have taken them; never send them again.
            return Recorded(
                ending=RecordEnding.MAYBE_SENT,
                progress=progress,
                trades=trades,
                numbers=numbers,
                marked=marked,
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
        marked=marked,
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
        elif trade.status is TradeStatus.UNFINISHED and trade.card is not None:
            records.append((number, trade.card))
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
    reason = (
        problem_words(trade.reason, ledger=assets.from_ledger) if trade.reason is not None else None
    )
    return LeftOutTrade(number=number, why=LeftOut.CANNOT_RECORD, reason=reason)


def _ledger_reason(
    number: int, draft: TradeDraft, reason: object, assets: AssetTable
) -> LeftOutTrade | None:
    coin = draft.coin
    if coin is not None and assets.money(coin).reading is not MoneyReading.NOT_MONEY:
        return LeftOutTrade(number=number, why=LeftOut.MONEY_TRADED, code=coin)
    lacked = _money_lacked(draft, reason, assets)
    if lacked is not None:
        return LeftOutTrade(number=number, why=lacked[0], code=lacked[1])
    if reason is Violation.ASSET_NOT_IN_LEDGER and coin is not None:
        return LeftOutTrade(number=number, why=LeftOut.NOT_IN_LEDGER, code=coin)
    if reason is Violation.FEE_ASSET_NOT_IN_LEDGER and draft.fee_coin is not None:
        return LeftOutTrade(number=number, why=LeftOut.NOT_IN_LEDGER, code=draft.fee_coin)
    if reason is Violation.QUOTE_CANNOT_PRICE and draft.quote is not None:
        code = assets.money(draft.quote).code or draft.quote
        return LeftOutTrade(number=number, why=LeftOut.QUOTE_CANNOT_PRICE, code=code)
    return None


def _money_lacked(
    draft: TradeDraft, reason: object, assets: AssetTable
) -> tuple[LeftOut, str] | None:
    """Why, and in which money, a trade priced or charged in money the ledger lacks is left out.

    Example: "价格2200欧元" with no euro in the ledger is told as the
    ledger having no currency EUR yet, never as an asset it lacks.
    """
    if reason is Violation.QUOTE_CANNOT_PRICE and draft.quote is not None:
        code = assets.missing_money(draft.quote)
        if code is not None:
            return LeftOut.MONEY_NOT_IN_LEDGER, code
    if reason is Violation.FEE_ASSET_NOT_IN_LEDGER and draft.fee_coin is not None:
        code = assets.missing_money(draft.fee_coin)
        if code is not None:
            return LeftOut.FEE_MONEY_NOT_IN_LEDGER, code
    return None


def _told_by_same_code(
    left_out: tuple[LeftOutTrade, ...], ledger: LedgerPort, listed: Sequence[Asset] | None
) -> tuple[LeftOutTrade, ...]:
    """When nothing is sent: each trade the ledger seemed to lack, told by the two assets
    sharing its code when that is why. The ledger is asked for its list only then, and a
    ledger that cannot be asked leaves the words as they were."""
    if not any(trade.why is LeftOut.NOT_IN_LEDGER for trade in left_out):
        return left_out
    if listed is None:
        try:
            listed = ledger.list_assets()
        except LedgerError:
            return left_out
    shared = {same.code: same for same in same_codes(listed)}
    return tuple(_same_code(trade, shared) for trade in left_out)


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
) -> tuple[tuple[int, ...], tuple[TradeCard, ...], tuple[LeftOutTrade, ...]]:
    """The records that can be sent, as cards, with their numbers; the rest, with why."""
    numbers: list[int] = []
    trades: list[TradeCard] = []
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
        if isinstance(record, CardRecord):
            trades.append(_card(record, assets, said))
        else:
            trades.append(card_of(_facts(record, assets, said)))
    return tuple(numbers), tuple(trades), tuple(not_sent)


def _codes(record: _Sendable) -> tuple[str, ...]:
    return tuple(code for code in (record.coin, record.fee_coin, record.quote) if code)


def _why_not(number: int, record: _Sendable, assets: Mapping[str, Asset]) -> LeftOutTrade | None:
    for code in (record.coin, record.fee_coin, record.quote):
        if code is not None and code not in assets:
            return LeftOutTrade(number=number, why=LeftOut.NOT_IN_LEDGER, code=code)
    quote = record.quote
    if quote is not None and assets[quote].pricing is not Pricing.CAN_PRICE:
        return LeftOutTrade(number=number, why=LeftOut.QUOTE_CANNOT_PRICE, code=quote)
    return None


def _card(record: CardRecord, assets: Mapping[str, Asset], said: str) -> TradeCard:
    """A trade settled with cells left empty, as the ledger takes it: each empty cell ``None``.

    A day alone holds the start of that day, as for a record; no day
    holds no time and no zone.
    """
    occurred = record.occurred
    moment: datetime | None = None
    date_only = False
    zone: str | None = None
    if occurred is not None:
        zone = occurred.time_zone
        value = occurred.value
        date_only = not isinstance(value, datetime)
        moment = value if isinstance(value, datetime) else _start_of(value, zone)
    return TradeCard(
        occurred=moment,
        side=record.side,
        asset=assets[record.coin].code,
        quantity=record.quantity,
        price=record.price,
        total=record.total,
        quote=assets[record.quote].code if record.quote is not None else None,
        fee=record.fee,
        fee_asset=assets[record.fee_coin].code if record.fee_coin is not None else None,
        platform=record.platform if record.platform is not None else "",
        note=record.note if record.note is not None else "",
        raw_text=said,
        zone=zone,
        date_only=date_only,
        cost_rate=None,
    )


def _facts(record: TradeRecord, assets: Mapping[str, Asset], said: str) -> TradeFacts:
    """The record as the ledger takes it: every figure as the flow gave it.

    A trade known only to its day holds the start of that day, with that
    day's offset in its zone, and says so (``date_only``).
    """
    moment = record.occurred.value
    date_only = not isinstance(moment, datetime)
    if date_only:
        moment = _start_of(moment, record.occurred.time_zone)
    assert isinstance(moment, datetime)
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
        date_only=date_only,
        cost_rate=None,
    )


def _start_of(day: date, zone: str) -> datetime:
    """The start of ``day`` in ``zone``, held with that moment's fixed offset."""
    start = datetime.combine(day, time(0), tzinfo=ZoneInfo(zone))
    offset = start.utcoffset()
    assert offset is not None
    return start.replace(tzinfo=timezone(offset))
