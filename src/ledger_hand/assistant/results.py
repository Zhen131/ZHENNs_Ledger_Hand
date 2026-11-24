"""What the program hands back to the model for one tool call, as JSON text.

Each function here turns one answer into the text of a ``ToolResult``: the
ledger's assets, holdings, trades or sums; where a proposal stands; or one
of the program's own answers, which carry a ``status`` word the model can
go by:

- ``not_connected``: the tool is on the list but its work is not built yet;
- ``no_proposal``: there is no proposal in this chat to ask about;
- ``wrong_step``: the call was not taken, and ``problem`` says why;
- ``ledger_error``: the ledger refused, with its code and its sentence;
- ``not_run``: the call was not run, because its step went to recording;
- for a call to record a trade, how the program's recording of what the
  user said ended (``recording_text``), in one word and with no figure:
  the program, not the model, tells the user the rest.

Amounts are written as exact decimal text, never as JSON numbers, so the
model reads the digits the ledger has. Money is always named beside an
amount. A figure that was not worked out is written as its reason.

Names defined here: ``assets_text``, ``positions_text``, ``trades_text``,
``summary_text``, ``status_text``, ``not_connected_text``,
``no_proposal_text``, ``misstep_text``, ``ledger_error_text``,
``not_run_text`` and ``recording_text``.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal

from ledger_hand.assistant.judging import Misstep
from ledger_hand.core.ledger_records import (
    Asset,
    Figure,
    LedgerTrade,
    MoneyAmount,
    PeriodSummary,
    Position,
)
from ledger_hand.core.proposals import ProposalStatus
from ledger_hand.ports import LedgerError


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


def positions_text(positions: Sequence[Position]) -> str:
    """What is held, one holding for each asset and the money it was bought with."""
    return _text(
        {
            "positions": [
                {
                    "asset": position.asset,
                    "bought_with": position.quote,
                    "quantity": _number(position.quantity),
                    "cost": _figure(position.cost),
                    "unrealized_profit": _figure(position.unrealized),
                }
                for position in positions
            ]
        }
    )


def trades_text(trades: Sequence[LedgerTrade]) -> str:
    """Trades of the ledger, each with its identifier."""
    listed = []
    for trade in trades:
        facts = trade.facts
        entry: dict[str, object] = {
            "id": trade.id,
            "time": facts.occurred.isoformat(),
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
        if trade.realized is not None:
            entry["realized_profit"] = _figure(trade.realized)
        listed.append(entry)
    return _text({"trades": listed})


def summary_text(summary: PeriodSummary) -> str:
    """The sums of a stretch of time, one set for each money."""
    return _text(
        {
            "trade_count": summary.trade_count,
            "by_currency": [
                {
                    "currency": totals.currency,
                    "spent_on_buys": _number(totals.spent),
                    "received_from_sells": _number(totals.received),
                    "realized_profit": _figure(totals.realized),
                }
                for totals in summary.by_currency
            ],
            "fees": [_figure(fee) for fee in summary.fees],
        }
    )


def status_text(proposal_id: str, status: ProposalStatus) -> str:
    """Where a proposal stands."""
    return _text({"proposal": proposal_id, "status": status.value})


def not_connected_text() -> str:
    """The answer to a tool whose work is not built yet."""
    return _text({"status": "not_connected", "message": "This feature is not connected yet."})


def no_proposal_text() -> str:
    """The answer to asking about a proposal when this chat has made none."""
    return _text({"status": "no_proposal", "message": "No proposal has been made in this chat."})


def misstep_text(misstep: Misstep) -> str:
    """The answer to a call that was not taken: what was wrong with it."""
    return _text({"status": "wrong_step", "kind": misstep.kind.value, "problem": misstep.detail})


def ledger_error_text(error: LedgerError) -> str:
    """The answer to a call the ledger refused."""
    return _text({"status": "ledger_error", "code": error.code, "message": error.message})


def not_run_text() -> str:
    """The answer to a call not run, because another call of its step went to recording."""
    return _text({"status": "not_run", "message": "Not run: this step went to recording."})


def recording_text(ending: str) -> str:
    """The answer to a call to record a trade: how the program's recording of it ended."""
    return _text(
        {
            "status": ending,
            "message": "The program recorded this itself and has told the user how it went.",
        }
    )
