"""Changing or deleting one trade: the program finds it, and proposes the change to the ledger.

The model only says which trade (the user's words for the time, the asset
and the side), which part (a choice) and the new value (the user's words);
``edit_calls`` judged that. Everything after is the program's:

1. Find it. The period, asset and side become conditions the read tools'
   own way (``asking.find_conditions``): a period that cannot be read, or
   an asset the ledger does not have, ends here in the program's words.
   With no condition at all, the program does not look through every
   trade: it asks which one is meant. The ledger is asked every time, so
   the model need not have listed the trades first.
2. Count. None: the program says so, with what it looked for, and does not
   look again more widely. More than ``MOST_LISTED``: it lists the latest
   and asks the user to say more. Two or more: it lists them, numbered
   from 1 in time order, and asks which (``Picking``).
3. Read the new value (``new_values``), by the field, and put it into the
   trade. A value not taken, or one the trade already has, changes nothing,
   and the program says why. A new quantity, price or total that leaves
   the three out of step makes the program ask which of the other two
   follows (``Choosing``).
4. Propose. A change sends the whole trade, every other part as the ledger
   holds it and the words it was recorded from untouched; a deletion sends
   its identifier. Both carry the sentence that asked for them, word for
   word. The ledger checks it: passed, it waits there to be confirmed;
   turned down, the program gives the ledger's reason; a trade the ledger
   no longer has is said to be gone. A proposal the ledger did not answer
   in time is never sent again: the user is asked to look at the ledger.

While the program waits for an answer (``EditWaiting``), the user's next
words are read by the program (``answer``), not the model: a number, or
which amount follows, or "cancel". An answer it cannot read asks the same
question again. Once it can, the trade is looked up again by the same
conditions, and taken as the ledger holds it now: nothing listed before is
pieced back together, so a change saved in the meantime is not undone. A
trade gone by then is said to be gone.

So the trade changed or deleted is always either the only one found, or
the one whose number the user gave; never one the model named, and never
one picked by the program.

A period the model copied that is cut out of a longer time the user said
("9月" out of "9月13号") is not looked up at all: the program says the
same fixed sentence at once (``begun``), and proposes nothing.

When the model goes wrong twice in a row and its second try was a change
or a deletion, ``taken_over`` goes on from that call alone: a period it
gave that is not the user's words is said to the user, with what the
model wrote, what the user said and an example (``date_not_as_said_words``);
one cut out of a longer time they said, or a new value that is not their
words, is said in a fixed sentence; nothing is looked for. A call that can
be taken after all goes on as above.

A date the model only put this year to is taken as the user's date
(``edit_calls.this_year_read``); once it was looked for, whatever came of
it, the reply ends with a line saying it was read as this year
(``edit_words.this_year_line``, 2026-11-27).

This module reads no clock, no zone of the machine and no settings.

Names defined here: ``EditKind``, ``EditEnding``, ``EditRequest``,
``Picking``, ``Choosing``, ``EditWaiting``, ``EditSent``, ``Edited``,
``start``, ``begun``, ``answer`` and ``taken_over``.
"""

from __future__ import annotations

import dataclasses
import enum
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from ledger_hand.assistant import edit_words
from ledger_hand.assistant.edit_calls import (
    EditCall,
    date_not_copied,
    judge_edit_at,
    wrong_parts,
)
from ledger_hand.assistant.lookups import Conditions
from ledger_hand.assistant.new_values import (
    Fixes,
    NewValue,
    NotTaken,
    Unchanged,
    changed_trade,
    read_new_value,
    with_fix,
)
from ledger_hand.assistant.picking import (
    MOST_LISTED,
    NotPicked,
    is_cancel,
    read_follower,
    read_pick,
)
from ledger_hand.assistant.tools import ToolName
from ledger_hand.core.ledger_records import LedgerTrade, TradeFacts, TradeFilter
from ledger_hand.core.proposals import TARGET_NOT_FOUND, CheckOutcome, TradeCheck
from ledger_hand.core.trade import Amount
from ledger_hand.flows.asking import ProgramWords, find_conditions
from ledger_hand.ports import LedgerError, LedgerErrorKind, LedgerPort, ToolCall


class EditKind(enum.Enum):
    CHANGE = "change"
    DELETE = "delete"


class EditEnding(enum.Enum):
    """How a change or a deletion ended this time."""

    SENT = "sent"
    """A proposal waits in the ledger to be confirmed."""
    PICKING = "picking"
    """More than one trade matches; the program asked which, and waits."""
    CHOOSING = "choosing"
    """A new amount leaves the three out of step; the program asked which follows, and waits."""
    NOT_FOUND = "not_found"
    """No trade matches what was looked for."""
    NO_CONDITIONS = "no_conditions"
    """Nothing said which trade; the program asked the user to say it."""
    TOO_MANY = "too_many"
    """More trades match than are listed; the program asked the user to say more."""
    TOLD = "told"
    """Nothing was proposed, and the program said why: words it cannot read, an asset the
    ledger lacks, a value not taken or already there, a trade gone."""
    LEDGER_REFUSED = "ledger_refused"
    """The ledger's check turned the proposal down; nothing waits there."""
    CANCELLED = "cancelled"
    """The user dropped it."""
    LEDGER_FAILED = "ledger_failed"
    """The ledger could not be asked."""
    MAYBE_SENT = "maybe_sent"
    """The ledger did not answer the proposal in time: it may have reached it. It is not
    sent again; the user is asked to look at the ledger's pending list."""


@dataclass(frozen=True, kw_only=True)
class EditRequest:
    """What is to be done: delete, or change ``field`` to ``value``, read from ``words``.

    ``said`` is the user's sentence that asked for it, word for word: the
    proposal carries it to the ledger, even when a later answer (a number,
    which amount follows) settles which trade. On the assistant's way it is
    the sentence as said, before it was tidied (``raw_text``).
    """

    kind: EditKind
    said: str
    field: str | None = None
    words: str | None = None
    value: NewValue | None = None


@dataclass(frozen=True, kw_only=True)
class Picking:
    """Waiting for which of the listed trades: the conditions, and their identifiers in order."""

    request: EditRequest
    conditions: Conditions
    trades: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class Choosing:
    """Waiting for which amount follows: the trade, how it was found, the amounts offered."""

    request: EditRequest
    conditions: Conditions
    trade: str
    offered: tuple[Amount, ...]


type EditWaiting = Picking | Choosing


@dataclass(frozen=True, kw_only=True)
class EditSent:
    """What reached the ledger: the proposal, whether a change or a deletion, of which trade."""

    proposal: str
    kind: EditKind
    trade: str


@dataclass(frozen=True, kw_only=True)
class Edited:
    """How a change or a deletion ended this time, and what it rests on.

    ``reply`` is the program's words to the user; ``waiting`` what the next
    words will answer, if anything; ``before`` the trade as the ledger
    held it and ``after`` the trade proposed (``None`` for a deletion);
    ``listed`` the trades shown; ``checks`` the ledger's checks when it
    turned the proposal down.
    """

    ending: EditEnding
    reply: str
    waiting: EditWaiting | None = None
    sent: EditSent | None = None
    before: LedgerTrade | None = None
    after: TradeFacts | None = None
    listed: tuple[LedgerTrade, ...] = ()
    checks: tuple[TradeCheck, ...] = ()
    failure: LedgerError | None = None


@dataclass(frozen=True)
class _Around:
    ledger: LedgerPort
    now: datetime
    zone: str


def start(
    call: EditCall,
    ledger: LedgerPort,
    user_said: Sequence[str],
    *,
    now: datetime,
    zone: str,
    raw_text: str | None = None,
) -> Edited:
    """Find the trade ``call`` names and propose its change or deletion, or say why not.

    ``user_said`` holds the words the call is checked against, tidied on the
    assistant's way; ``raw_text`` is the last of them as the user said it,
    when tidying changed it, and goes to the ledger in its place.
    """
    try:
        return _started(call, _Around(ledger, now, zone), user_said, raw_text)
    except LedgerError as error:
        return _failed(error)


def _started(
    call: EditCall, around: _Around, user_said: Sequence[str], raw_text: str | None = None
) -> Edited:
    said = raw_text if raw_text is not None else user_said[-1]
    conditions = find_conditions(
        call.period,
        call.asset,
        call.side,
        around.ledger,
        user_said,
        now=around.now,
        zone=around.zone,
    )
    if isinstance(conditions, ProgramWords):
        return Edited(ending=EditEnding.TOLD, reply=conditions.words)
    if conditions.period is None and conditions.asset is None and conditions.side is None:
        return Edited(ending=EditEnding.NO_CONDITIONS, reply=edit_words.NO_CONDITIONS)
    request = EditRequest(kind=EditKind.DELETE, said=said)
    if call.tool is ToolName.PROPOSE_TRADE_UPDATE:
        assert call.field is not None and call.new_value is not None
        value = read_new_value(
            call.field,
            call.new_value,
            around.ledger.list_assets(),
            now=around.now,
            zone=around.zone,
        )
        if isinstance(value, NotTaken):
            return Edited(ending=EditEnding.TOLD, reply=value.words)
        request = EditRequest(
            kind=EditKind.CHANGE,
            said=said,
            field=call.field,
            words=call.new_value,
            value=value,
        )
    try:
        trades = _found(conditions, around.ledger)
    except LedgerError as error:
        if error.kind is LedgerErrorKind.ASSET_IS_CURRENCY:
            return Edited(ending=EditEnding.TOLD, reply=error.message)
        raise
    edited = _looked(trades, request, conditions, around)
    if call.this_year is None:
        return edited
    # The user's date was looked for read as this year: said once it was (2026-11-27).
    line = edit_words.this_year_line(call.this_year)
    return dataclasses.replace(edited, reply=f"{edited.reply}\n{line}")


def _looked(
    trades: tuple[LedgerTrade, ...], request: EditRequest, conditions: Conditions, around: _Around
) -> Edited:
    """What comes of the trades found by ``conditions``: none, too many, a pick, or the one."""
    if not trades:
        return Edited(ending=EditEnding.NOT_FOUND, reply=edit_words.not_found_words(conditions))
    if len(trades) > MOST_LISTED:
        latest = trades[-MOST_LISTED:]
        reply = edit_words.too_many_words(conditions, len(trades), latest)
        return Edited(ending=EditEnding.TOO_MANY, reply=reply, listed=latest)
    if len(trades) > 1:
        return _picking(request, conditions, trades)
    return _onto(trades[0], request, conditions, around)


def _found(conditions: Conditions, ledger: LedgerPort) -> tuple[LedgerTrade, ...]:
    period = conditions.period
    return ledger.list_trades(
        TradeFilter(
            first_day=period.first_day if period is not None else None,
            last_day=period.last_day if period is not None else None,
            asset=conditions.asset,
            side=conditions.side,
        )
    ).trades


def _picking(
    request: EditRequest, conditions: Conditions, trades: Sequence[LedgerTrade], why: str = ""
) -> Edited:
    waiting = Picking(
        request=request, conditions=conditions, trades=tuple(trade.id for trade in trades)
    )
    return Edited(
        ending=EditEnding.PICKING,
        reply=edit_words.picking_words(conditions, trades, why),
        waiting=waiting,
        listed=tuple(trades),
    )


def _onto(
    trade: LedgerTrade, request: EditRequest, conditions: Conditions, around: _Around
) -> Edited:
    """The change or the deletion of the one trade found, proposed, or why not."""
    if request.kind is EditKind.DELETE:
        return _proposed(trade, None, request, conditions, around.ledger)
    assert request.field is not None and request.value is not None
    changed = changed_trade(request.field, request.value, trade.facts, around.ledger.list_assets())
    if isinstance(changed, NotTaken):
        return Edited(ending=EditEnding.TOLD, reply=changed.words, before=trade)
    if isinstance(changed, Unchanged):
        return Edited(ending=EditEnding.TOLD, reply=edit_words.NOTHING_TO_CHANGE, before=trade)
    if isinstance(changed, Fixes):
        return _choosing(trade, changed, request, conditions)
    return _proposed(trade, changed, request, conditions, around.ledger)


def _choosing(
    trade: LedgerTrade, fixes: Fixes, request: EditRequest, conditions: Conditions, why: str = ""
) -> Edited:
    waiting = Choosing(
        request=request,
        conditions=conditions,
        trade=trade.id,
        offered=tuple(fix.follows for fix in fixes.fixes),
    )
    return Edited(
        ending=EditEnding.CHOOSING,
        reply=edit_words.choosing_words(trade, fixes, why),
        waiting=waiting,
        before=trade,
    )


def _proposed(
    trade: LedgerTrade,
    after: TradeFacts | None,
    request: EditRequest,
    conditions: Conditions,
    ledger: LedgerPort,
) -> Edited:
    """Send the change (``after``) or the deletion (no ``after``) of ``trade`` to the ledger.

    A trade the ledger no longer has, by its failure or by its check's code,
    is said to be gone. A proposal the ledger did not answer in time is not
    sent again (``MAYBE_SENT``).
    """
    try:
        if after is None:
            result = ledger.propose_delete(trade.id, request.said)
        else:
            result = ledger.propose_update(trade.id, after, request.said)
    except LedgerError as error:
        if error.kind is LedgerErrorKind.NOT_FOUND:
            return Edited(ending=EditEnding.TOLD, reply=edit_words.GONE, before=trade)
        if error.kind is LedgerErrorKind.TIMED_OUT:
            return Edited(
                ending=EditEnding.MAYBE_SENT,
                reply=edit_words.MAYBE_SENT,
                before=trade,
                after=after,
                failure=error,
            )
        raise
    failed = [check for check in result.checks if check.outcome is CheckOutcome.FAILED]
    if any(check.code == TARGET_NOT_FOUND for check in failed):
        return Edited(ending=EditEnding.TOLD, reply=edit_words.GONE, before=trade)
    if failed or not result.proposal_ids:
        message = failed[0].message if failed else "it was not kept."
        return Edited(
            ending=EditEnding.LEDGER_REFUSED,
            reply=edit_words.refused_words(message or ""),
            before=trade,
            after=after,
            checks=result.checks,
        )
    kind = EditKind.DELETE if after is None else EditKind.CHANGE
    proposal = result.proposal_ids[0]
    return Edited(
        ending=EditEnding.SENT,
        reply=edit_words.sent_words(proposal, conditions, trade, after),
        sent=EditSent(proposal=proposal, kind=kind, trade=trade.id),
        before=trade,
        after=after,
    )


def answer(
    waiting: EditWaiting, said: str, ledger: LedgerPort, *, now: datetime, zone: str
) -> Edited:
    """The user's ``said`` read as the answer to what ``waiting`` asked."""
    if is_cancel(said):
        return Edited(ending=EditEnding.CANCELLED, reply=edit_words.CANCELLED)
    around = _Around(ledger, now, zone)
    try:
        if isinstance(waiting, Picking):
            return _picked(waiting, said, around)
        return _chosen(waiting, said, around)
    except LedgerError as error:
        return _failed(error)


def _again(conditions: Conditions, trade_id: str, ledger: LedgerPort) -> LedgerTrade | None:
    """The trade ``trade_id``, looked up again by the same conditions, as it stands now."""
    return next((trade for trade in _found(conditions, ledger) if trade.id == trade_id), None)


def _picked(waiting: Picking, said: str, around: _Around) -> Edited:
    pick = read_pick(said, len(waiting.trades))
    if isinstance(pick, NotPicked):
        found = _found(waiting.conditions, around.ledger)
        listed = [trade for trade in found if trade.id in waiting.trades]
        if len(listed) != len(waiting.trades):
            return Edited(ending=EditEnding.TOLD, reply=edit_words.GONE)
        return _picking(waiting.request, waiting.conditions, listed, pick.why)
    trade = _again(waiting.conditions, waiting.trades[pick.number - 1], around.ledger)
    if trade is None:
        return Edited(ending=EditEnding.TOLD, reply=edit_words.GONE)
    return _onto(trade, waiting.request, waiting.conditions, around)


def _chosen(waiting: Choosing, said: str, around: _Around) -> Edited:
    trade = _again(waiting.conditions, waiting.trade, around.ledger)
    if trade is None:
        return Edited(ending=EditEnding.TOLD, reply=edit_words.GONE)
    request = waiting.request
    assert request.field is not None and request.value is not None
    changed = changed_trade(request.field, request.value, trade.facts, around.ledger.list_assets())
    if not isinstance(changed, Fixes):
        # The trade changed under the question; it is taken as it stands now.
        return _onto(trade, request, waiting.conditions, around)
    follows = read_follower(said, waiting.offered)
    fix = next((one for one in changed.fixes if one.follows is follows), None)
    if follows is None or fix is None:
        why = f"I could not tell which you mean from {said.strip()!r}."
        return _choosing(trade, changed, request, waiting.conditions, why)
    return _proposed(trade, with_fix(trade.facts, fix), request, waiting.conditions, around.ledger)


def _failed(error: LedgerError) -> Edited:
    return Edited(
        ending=EditEnding.LEDGER_FAILED, reply=edit_words.failed_words(error.message), failure=error
    )


def begun(
    call: ToolCall,
    ledger: LedgerPort,
    user_said: Sequence[str],
    *,
    now: datetime,
    zone: str,
    raw_text: str | None = None,
) -> Edited:
    """A call taken by the turn, gone on with; a period cut out of a longer time says the
    fixed words and looks nothing up."""
    verdict = judge_edit_at(call, user_said, now=now, zone=zone)
    if not isinstance(verdict, EditCall):
        return Edited(ending=EditEnding.TOLD, reply=edit_words.PERIOD_AGAIN)
    return start(verdict, ledger, user_said, now=now, zone=zone, raw_text=raw_text)


def taken_over(
    call: ToolCall,
    ledger: LedgerPort,
    user_said: Sequence[str],
    *,
    now: datetime,
    zone: str,
    raw_text: str | None = None,
) -> Edited | None:
    """After two wrong steps, the last a change or a deletion: go on from that call alone.

    ``None`` when nothing in the call can be gone on with: the turn's own
    words stand.
    """
    verdict = judge_edit_at(call, user_said, now=now, zone=zone)
    if isinstance(verdict, EditCall):
        return start(verdict, ledger, user_said, now=now, zone=zone, raw_text=raw_text)
    parts = wrong_parts(call, user_said, now=now, zone=zone)
    if parts.period_wrong:
        written = date_not_copied(call, user_said, now=now, zone=zone)
        if written is None:
            return Edited(ending=EditEnding.TOLD, reply=edit_words.PERIOD_AGAIN)
        said = raw_text if raw_text is not None else user_said[-1]
        words = edit_words.date_not_as_said_words(written, user_said, said, now=now, zone=zone)
        return Edited(ending=EditEnding.TOLD, reply=words)
    if parts.field_taken and parts.new_value_wrong:
        return Edited(ending=EditEnding.TOLD, reply=edit_words.VALUE_AGAIN)
    return None
