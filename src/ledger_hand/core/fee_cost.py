"""Whether the ledger counts a trade's fee in what the trade cost.

The ledger works out what a holding cost from each trade's amounts and its
fee, and it takes a fee into that only when the fee is paid in USDT or in
the coin traded. A fee paid in a third coin (buying ETH with the fee taken
in BNB, say) keeps the ledger's import rules, so the trade is taken as it
is, but that fee is left out of the cost. This program records such a trade
as it was said and only reminds the person of it; nothing is held back.

A fee of 0 leaves nothing out, so it is never a reason for the reminder.

Names defined here: ``fee_left_out_of_cost``.
"""

from __future__ import annotations

from ledger_hand.core.ledger_limits import QUOTE_CURRENCY
from ledger_hand.core.trade import TradeRecord


def fee_left_out_of_cost(record: TradeRecord) -> bool:
    """Whether the ledger leaves ``record``'s fee out of the cost: a fee above 0 in a third coin."""
    return record.fee != 0 and record.fee_coin not in (QUOTE_CURRENCY, record.coin)
