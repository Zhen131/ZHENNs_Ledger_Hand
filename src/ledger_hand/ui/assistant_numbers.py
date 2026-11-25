"""How the assistant page writes a number: every digit as given, with thousands marks.

Every figure the assistant page shows (a quantity, a price, a total, a fee,
a sum) is written by ``shown`` and nowhere else on that page. It writes the
exact decimal it is handed in full, with a comma between thousands and no
exponent, and never rounds, drops a place or works anything out:
``Decimal("94900")`` is "94,900" and ``Decimal("0.00012345")`` is
"0.00012345". ``read_back`` reads the shown text back into the decimal it
came from, so a test can check that showing a number never changes it.

The Record page writes numbers its own way (``preview``), as the ledger
does, and is not changed by this.

Names defined here: ``shown`` and ``read_back``.
"""

from __future__ import annotations

from decimal import Decimal

_THOUSANDS = ","


def shown(value: Decimal) -> str:
    """``value`` written out in full, every place kept, with commas between thousands."""
    if not isinstance(value, Decimal):
        raise TypeError(f"a figure is shown from a Decimal, not {type(value).__name__}")
    return format(value, ",f")


def read_back(text: str) -> Decimal:
    """The decimal ``shown`` wrote as ``text``."""
    return Decimal(text.replace(_THOUSANDS, ""))
