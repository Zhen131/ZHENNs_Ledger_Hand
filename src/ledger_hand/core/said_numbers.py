"""A figure the program worked out, put back to the number the user said, when it only rounds.

When the user says quantity, price and total but the model copies only two,
the program works out the third (``validation``), and the figure it comes
to may differ from the one said in its last places: 150 said, 150.00078
worked out from 0.94 and 159.575; 0.2314547 said, 0.23145469 worked out
from 100 and 432.05. The number said stands among the passage's numbers
that no cell used (the reminder ``NUMBERS_LEFT_OVER``).

``said_instead`` takes the three figures of one trade, which of them was
worked out, those numbers left over and how close counts, and gives back
the number said to put in place of the one worked out, or ``None``. A
number said counts when both hold:

- the figure worked out, rounded half up to as many places as the number
  said has, is that number;
- they are apart by at most ``gap`` as a part of the number said
  (``settings.LEDGER_HAND_SAID_NUMBER_GAP``, one ten-thousandth unless set).

Exactly one number must count; with two or none, nothing changes. Put in
place, the three figures must still agree, here and as the ledger works it
out (``validation.amounts_agree``), and the number must fit the ledger's
digits; otherwise nothing changes. The figure keeps its mark "worked out by
the program", with a reason that says both (``SaidInstead.reason``).

Only a figure worked out is ever changed, never one the model copied; the
time, the fee and the money are not looked at. (Decided on 2026-11-26 by
the session that hands out the work; the gap has no source behind it.)

Names defined here: ``SaidInstead`` and ``said_instead``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from ledger_hand.core.arithmetic import round_half_up, working_context
from ledger_hand.core.ledger_limits import fits_digit_limits
from ledger_hand.core.trade import Amount
from ledger_hand.core.validation import amounts_agree


@dataclass(frozen=True, kw_only=True)
class SaidInstead:
    """The number said, put in place of the figure worked out for ``amount``.

    ``worked`` is the figure the program came to, ``said`` the number put in
    its place and ``written`` that number as the passage writes it.
    Example: total, 150.00078 worked out, 150 said.
    """

    amount: Amount
    worked: Decimal
    said: Decimal
    written: str

    @property
    def reason(self) -> str:
        """The mark's reason: what was worked out, what was said, which is kept."""
        return (
            f"worked out as {format(self.worked, 'f')}, but you said {self.written}; "
            "your figure is kept"
        )


def _places(value: Decimal) -> int:
    exponent = value.as_tuple().exponent
    return max(0, -exponent) if isinstance(exponent, int) else 0


def _close(worked: Decimal, said: Decimal, gap: Decimal) -> bool:
    """Whether ``worked`` rounds to ``said`` at its places and is within ``gap`` of it."""
    if said <= 0 or not said.is_finite():
        return False
    if round_half_up(worked, _places(said)) != said:
        return False
    context = working_context()
    apart = context.subtract(worked, said).copy_abs()
    return apart <= context.multiply(said, gap)


def said_instead(
    *,
    derived: Amount,
    quantity: Decimal,
    price: Decimal,
    total: Decimal,
    left_over: Sequence[tuple[str, Decimal]],
    gap: Decimal,
) -> SaidInstead | None:
    """The number said to keep in place of the ``derived`` figure, or ``None``.

    ``left_over`` holds the passage's numbers no cell used, each as written
    and as read. Example: total worked out 150.00078, left over ("150", 150),
    gap 0.0001: 150 is kept.
    """
    if gap <= 0:
        raise ValueError(f"how close counts must be above 0, not {gap}")
    figures = {Amount.QUANTITY: quantity, Amount.PRICE: price, Amount.TOTAL: total}
    worked = figures[derived]
    found = [(written, said) for written, said in left_over if _close(worked, said, gap)]
    if len(found) != 1:
        return None
    ((written, said),) = found
    figures[derived] = said
    if not fits_digit_limits(said):
        return None
    if not amounts_agree(figures[Amount.QUANTITY], figures[Amount.PRICE], figures[Amount.TOTAL]):
        return None
    return SaidInstead(amount=derived, worked=worked, said=said, written=written)
