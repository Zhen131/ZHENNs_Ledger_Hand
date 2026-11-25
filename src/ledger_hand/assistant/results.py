"""What the program hands back to the model for one tool call, as JSON text.

Each function here turns one answer into the text of a ``ToolResult``: the
ledger's assets, holdings, trades or sums; where a proposal stands; or one
of the program's own answers, which carry a ``status`` word the model can
go by:

- ``not_connected``: the tool is on the list but its work is not built yet;
- ``no_proposal``: there is no proposal in this chat to ask about;
- ``wrong_step``: the call was not taken, and ``problem`` says why;
- ``ledger_error``: the ledger refused, with its code and its sentence;
- ``not_run``: the call was not run, because its step went to recording,
  or because the program answered the user itself in that step;
- ``answered_by_program``: the program told the user something itself
  (a time it cannot read, an asset the ledger does not have), and the
  ``message`` is what it said;
- for a call to record a trade, how the program's recording of what the
  user said ended (``recording_text``), in one word and with no figure:
  the program, not the model, tells the user the rest;
- for a call to change or delete a trade, how the program's change ended
  (``editing_text``), the same way; and for every other call of that step,
  that it was not run (``not_done_text``): one change or deletion at a time.

Amounts are written as exact decimal text, never as JSON numbers, so the
model reads the digits the ledger has. Money is always named beside an
amount. A figure that was not worked out is written as its reason.

Names defined here: ``assets_text``, ``positions_text``, ``trades_text``,
``summary_text``, ``lookup_text``, ``status_text``, ``not_connected_text``,
``no_proposal_text``, ``misstep_text``, ``period_misstep_text``,
``ledger_error_text``, ``not_run_text``, ``answered_by_program_text``, ``skipped_text``,
``recording_text``, ``editing_text`` and ``not_done_text``.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal

from ledger_hand.assistant.judging import Misstep
from ledger_hand.assistant.lookups import Conditions, Lookup
from ledger_hand.assistant.tools import ToolName
from ledger_hand.core.ledger_records import (
    MOST_TRADES_LISTED,
    Asset,
    CurrencyTotals,
    Figure,
    LedgerTrade,
    MoneyAmount,
    PeriodSummary,
    Position,
)
from ledger_hand.core.proposals import ProposalState
from ledger_hand.ports import LedgerError, LedgerErrorKind


def _text(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _number(value: Decimal) -> str:
    return format(value, "f")


def _figure(figure: Figure) -> dict[str, str]:
    if isinstance(figure, MoneyAmount):
        return {"amount": _number(figure.amount), "currency": figure.currency}
    return {"not_worked_out": figure.reason}


def assets_text(assets: Sequence[Asset]) -> str:
    """The ledger's assets."""
    return _text(
        {
            "assets": [
                {
                    "id": asset.id,
                    "code": asset.code,
                    "name": asset.name,
                    "kind": asset.kind.value,
                    "prices_trades": asset.pricing.value,
                }
                for asset in assets
            ]
        }
    )


def _position_entry(position: Position) -> dict[str, object]:
    # "bought_with" keeps its name for the model (68B2, part 11): it now holds
    # the asset's own money, which every figure of the holding is in.
    entry: dict[str, object] = {
        "asset": position.asset,
        "bought_with": position.currency,
        "quantity": _number(position.quantity),
        "cost": _figure(position.cost),
        "unrealized_profit": _figure(position.unrealized),
    }
    if position.cost_unreliable is not None:
        entry["cost_not_reliable"] = position.cost_unreliable
    return entry


def positions_text(positions: Sequence[Position]) -> str:
    """What is held, one holding for each asset, every figure in the asset's own money."""
    return _text({"positions": [_position_entry(position) for position in positions]})


def _trade_entry(trade: LedgerTrade) -> dict[str, object]:
    facts = trade.facts
    entry: dict[str, object] = {
        "id": trade.id,
        "time": facts.day.isoformat() if facts.date_only else facts.occurred.isoformat(),
        "side": facts.side.value,
        "asset": facts.asset,
        "quantity": _number(facts.quantity),
        "price": _number(facts.price),
        "total": _number(facts.total),
        "priced_in": facts.quote,
        "fee": _number(facts.fee),
        "fee_in": facts.fee_asset,
        "platform": facts.platform,
        "note": facts.note,
    }
    if facts.date_only:
        entry["date_only"] = True
    if trade.realized is not None:
        entry["realized_profit"] = _figure(trade.realized)
    if trade.realized_unreliable is not None:
        entry["realized_profit_not_reliable"] = trade.realized_unreliable
    if trade.dated_after_today:
        entry["dated_after_today"] = True
    return entry


def trades_text(trades: Sequence[LedgerTrade]) -> str:
    """Trades of the ledger, each with its identifier."""
    return _text({"trades": [_trade_entry(trade) for trade in trades]})


def _sum(figure: Figure) -> object:
    """A sum of one group: its digits alone, as before, or why it was not worked out."""
    if isinstance(figure, MoneyAmount):
        return _number(figure.amount)
    return {"not_worked_out": figure.reason}


def _group_entry(totals: CurrencyTotals, *, several: bool) -> dict[str, object]:
    entry: dict[str, object] = {
        "currency": totals.currency,
        "spent_on_buys": _sum(totals.spent),
        "received_from_sells": _sum(totals.received),
        "realized_profit": _figure(totals.realized),
    }
    # With one group the summary's own count and fees say it all; with two
    # or more, each group says its own (68B2, part 7).
    if several:
        entry["buy_count"] = totals.buy_count
        entry["sell_count"] = totals.sell_count
        entry["fees"] = [_figure(fee) for fee in totals.fees]
    transfers = totals.realized_from_transfers
    if not (isinstance(transfers, MoneyAmount) and transfers.amount == 0):
        entry["realized_from_sells"] = _figure(totals.realized_from_sells)
        entry["cost_taken_out_by_transfers"] = _figure(transfers)
    unreliable = [row for row in totals.by_asset if row.unreliable is not None]
    if unreliable:
        entry["realized_not_reliable"] = [
            {"asset": row.asset, "realized_profit": _figure(row.realized), "why": row.unreliable}
            for row in unreliable
        ]
    return entry


def _summary_data(summary: PeriodSummary) -> dict[str, object]:
    several = len(summary.by_currency) > 1
    return {
        "trade_count": summary.trade_count,
        "by_currency": [_group_entry(totals, several=several) for totals in summary.by_currency],
        "fees": [_figure(fee) for fee in summary.fees],
    }


def summary_text(summary: PeriodSummary) -> str:
    """The sums of a stretch of time, one set for each money."""
    return _text(_summary_data(summary))


def _conditions_data(conditions: Conditions) -> dict[str, object]:
    period = conditions.period
    data: dict[str, object] = {
        "from": period.first_day.isoformat() if period else "all time",
        "to": period.last_day.isoformat() if period else "all time",
        "asset": conditions.asset or "all assets",
        "side": conditions.side.value if conditions.side else "buys and sells",
    }
    if conditions.not_narrowed:
        data["not_narrowed"] = list(conditions.not_narrowed)
    return data


def lookup_text(lookup: Lookup) -> str:
    """What a read tool found, as the model is handed it: the trades shown, never more.

    A list of trades or a summary comes with the conditions it was looked
    up with; a list of trades with the count of all of them and of those
    shown. The holdings and the assets are as ``positions_text`` and
    ``assets_text`` write them.
    """
    if lookup.tool is ToolName.GET_POSITIONS:
        return positions_text(lookup.positions)
    if lookup.tool is ToolName.LIST_ASSETS:
        return assets_text(lookup.assets)
    data: dict[str, object] = {}
    if lookup.conditions is not None:
        data["conditions"] = _conditions_data(lookup.conditions)
    if lookup.summary is not None:
        data.update(_summary_data(lookup.summary))
    else:
        data["trade_count"] = lookup.trade_count
        data["shown"] = len(lookup.trades)
        if lookup.cut:
            data["only_the_latest_taken"] = MOST_TRADES_LISTED
        data["trades"] = [_trade_entry(trade) for trade in lookup.trades]
    return _text(data)


def _state_entry(state: ProposalState) -> dict[str, object]:
    entry: dict[str, object] = {"proposal": state.proposal_id, "status": state.status.value}
    if state.reason is not None:
        entry["void_reason"] = state.reason
    if state.message is not None:
        entry["message"] = state.message
    return entry


def status_text(states: Sequence[ProposalState]) -> str:
    """Where the proposals of the last thing sent stand: one, as before, or each of several.

    Several proposals (a call to record more than one trade) are said one
    by one under ``proposals``; ``status`` is theirs when they agree and
    ``mixed`` when not, and ``proposal`` is the first.
    """
    if not states:
        raise ValueError("there is at least one proposal to say")
    data = _state_entry(states[0])
    if len(states) > 1:
        statuses = {state.status for state in states}
        data["status"] = states[0].status.value if len(statuses) == 1 else "mixed"
        data.pop("void_reason", None)
        data.pop("message", None)
        data["proposals"] = [_state_entry(state) for state in states]
    return _text(data)


def not_connected_text() -> str:
    """The answer to a tool whose work is not built yet."""
    return _text({"status": "not_connected", "message": "This feature is not connected yet."})


def no_proposal_text() -> str:
    """The answer to asking about a proposal when this chat has made none."""
    return _text({"status": "no_proposal", "message": "No proposal has been made in this chat."})


def misstep_text(misstep: Misstep) -> str:
    """The answer to a call that was not taken: what was wrong with it."""
    return _text({"status": "wrong_step", "kind": misstep.kind.value, "problem": misstep.detail})


def period_misstep_text(misstep: Misstep, said: str) -> str:
    """The answer to a period that is not the user's words: what is wrong, and their words.

    ``said`` is what the user just said, as they said it; nothing the program
    worked out (a date, a range) is added.
    """
    return _text(
        {
            "status": "wrong_step",
            "kind": misstep.kind.value,
            "problem": misstep.detail,
            "user_said": said,
            "how": (
                "Copy the time from user_said exactly as it is written there, in the "
                "language the user wrote it in: English words stay English, Chinese words "
                "stay Chinese. Do not translate it and do not turn it into a date."
            ),
        }
    )


# What two failures mean, which their codes alone do not say (the ledger's
# assistant-link/README.md, rules 4 and 5).
_MEANINGS = {
    LedgerErrorKind.TIMED_OUT: (
        "The ledger did not answer in time. A proposal may still have reached it: do not "
        "send it again; ask the user to look at the ledger's pending list first."
    ),
    LedgerErrorKind.RESULT_UNKNOWN: (
        "The ledger page may have been reloaded, so the result of this proposal can no "
        "longer be looked up. This does not mean it was not saved; ask the user to look "
        "at the ledger."
    ),
}


def ledger_error_text(error: LedgerError) -> str:
    """The answer to a call the ledger refused."""
    data = {"status": "ledger_error", "code": error.code, "message": error.message}
    meaning = _MEANINGS.get(error.kind)
    if meaning is not None:
        data["what_it_means"] = meaning
    return _text(data)


def not_run_text() -> str:
    """The answer to a call not run, because another call of its step went to recording."""
    return _text({"status": "not_run", "message": "Not run: this step went to recording."})


def answered_by_program_text(words: str) -> str:
    """The answer to a call after which the program told the user something itself."""
    return _text({"status": "answered_by_program", "message": words})


def skipped_text() -> str:
    """The answer to a call not run, because the program answered the user in its step."""
    return _text({"status": "not_run", "message": "Not run: the program answered the user."})


def recording_text(ending: str) -> str:
    """The answer to a call to record a trade: how the program's recording of it ended."""
    return _text(
        {
            "status": ending,
            "message": "The program took this over and has told the user where it stands.",
        }
    )


def editing_text(ending: str) -> str:
    """The answer to a call to change or delete a trade: how the program's change ended."""
    return _text(
        {
            "status": ending,
            "message": "The program took this over and has told the user where it stands.",
        }
    )


def not_done_text() -> str:
    """The answer to a call not run, because another call of its step changes or deletes."""
    return _text(
        {
            "status": "not_run",
            "message": "Not run: one change or deletion at a time; the program told the user.",
        }
    )
