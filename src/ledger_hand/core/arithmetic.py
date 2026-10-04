"""Exact decimal arithmetic: the contexts every calculation in the core runs in.

Python's default decimal context keeps 28 significant digits and rounds a tie
to the even digit, and the ``+ - * /`` operators and ``abs()`` use that
context without saying so. A number in the ledger can be longer than 28
digits, and the ledger rounds a tie up. So the core never calculates through
the default context: it asks this module for a context and calls that
context's methods (``multiply``, ``divide``, ``subtract`` and so on).
Comparing two decimals needs no context; a comparison is always exact.

``working_context`` is for the program's own arithmetic. ``ledger_context``
reproduces the arithmetic of the ledger, for the places where a result has to
come out exactly as the ledger would compute it.

Every call returns a context of its own, so a caller can read its flags (did
the last division come out even?) without seeing anyone else's, and nothing
here is shared state.

This module only supplies the means to calculate. Which calculations a trade
needs is decided in ``validation``.

Names defined here: ``WORKING_PRECISION``, ``working_context``,
``ledger_context`` and ``round_half_up``.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Context, Decimal, DivisionByZero, InvalidOperation, Overflow

from ledger_hand.core.ledger_limits import ARITHMETIC_PRECISION

# Wide enough to be exact where it matters. Two numbers inside the ledger's
# digit limits multiply to at most 80 digits, and their product minus a third
# such number needs at most 99. A quotient of two such numbers keeps at least
# 92 digits after the point, far more than the 60 it takes for a second
# rounding, to a number of places the ledger can hold, to give the same answer
# as rounding the true quotient once.
WORKING_PRECISION = 150

# An impossible operation stops the calculation instead of handing on a
# not-a-number or an infinity for someone else to trip over.
_TRAPS = (InvalidOperation, DivisionByZero, Overflow)


def working_context() -> Context:
    """A fresh context for the program's own arithmetic: wide, and rounding half up."""
    return Context(prec=WORKING_PRECISION, rounding=ROUND_HALF_UP, traps=list(_TRAPS))


def ledger_context() -> Context:
    """A fresh context that calculates as the ledger does: 40 digits, rounding half up."""
    return Context(prec=ARITHMETIC_PRECISION, rounding=ROUND_HALF_UP, traps=list(_TRAPS))


def round_half_up(value: Decimal, places: int) -> Decimal:
    """``value`` with exactly ``places`` digits after the point, a tie rounded away from zero."""
    return value.quantize(Decimal((0, (1,), -places)), context=working_context())
