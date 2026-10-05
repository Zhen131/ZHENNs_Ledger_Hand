"""The ledger's limits, in one place, and the ledger's way of measuring against them.

Entries leave this program as a file for the Local-First Trading Ledger, and
the ledger refuses a file that breaks any limit below. Every value here is
copied from the ledger's own validation code; when the ledger changes one,
this is the only file that has to follow.

Three things must be measured exactly as the ledger measures them, so the
yardsticks live here as well: the length of a text, the digits of a number as
the ledger would see it written out, and what counts as surrounding
whitespace.

This module judges nothing about a trade: ``validation`` applies the limits
and ``coins`` uses the symbol rule.

Names defined here: the constants below, ``text_length``, ``trim``,
``is_symbol``, ``decimal_places``, ``significant_digits`` and
``fits_digit_limits``.
"""

from __future__ import annotations

import re
from decimal import Decimal

# The only currency the ledger prices trades in. A coin may not use it as its
# own symbol.
QUOTE_CURRENCY = "USDT"

# A coin symbol: capital letters and digits only.
SYMBOL_MAX_LENGTH = 32
SYMBOL_PATTERN = re.compile(rf"[A-Z0-9]{{1,{SYMBOL_MAX_LENGTH}}}")

# A coin's full name, and the name of its market on an exchange.
COIN_NAME_MAX_LENGTH = 128
MARKET_PAIR_MAX_LENGTH = 32

# A number, written out in full: digits after the point, and digits in all.
MAX_DECIMAL_PLACES = 18
MAX_SIGNIFICANT_DIGITS = 40

# How far quantity times price may be from the stated total.
TOTAL_TOLERANCE = Decimal("0.01")

# The ledger rounds each product and each difference to this many significant
# digits, half up, before it compares them.
ARITHMETIC_PRECISION = 40

# Free text on a trade.
PLATFORM_MAX_LENGTH = 128
NOTE_MAX_LENGTH = 4_096
RAW_TEXT_MAX_LENGTH = 16_384

# The identifier of a trade or of a coin in a file, and the name and version
# of the program that wrote the file. Both may not have surrounding
# whitespace either.
ID_MAX_LENGTH = 128
APP_VERSION_MAX_LENGTH = 128

# How much one file may hold: coins, trades, and its text in bytes of UTF-8,
# the way the ledger counts a file before it reads it. In the ledger these are
# DEFAULT_LEDGER_RESOURCE_LIMITS (assets, trades, fileBytes) in
# src/core/validation/resourcePolicy.ts.
MAX_COINS_PER_FILE = 500
MAX_TRADES_PER_FILE = 250_000
MAX_FILE_BYTES = 128 * 1024 * 1024

# What the ledger's runtime strips from the ends of a text: its white-space
# and line-terminator characters. Python's own notion differs at the edges.
_WHITESPACE = "".join(
    map(
        chr,
        (0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20, 0xA0, 0x1680)
        + tuple(range(0x2000, 0x200B))
        + (0x2028, 0x2029, 0x202F, 0x205F, 0x3000, 0xFEFF),
    )
)


def text_length(text: str) -> int:
    """Length as the ledger counts it: UTF-16 code units, so one emoji counts as two."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def trim(text: str) -> str:
    """``text`` without the surrounding whitespace the ledger would object to."""
    return text.strip(_WHITESPACE)


def is_symbol(text: str) -> bool:
    """Whether ``text`` can be a coin symbol in the ledger."""
    return SYMBOL_PATTERN.fullmatch(text) is not None and text != QUOTE_CURRENCY


def decimal_places(value: Decimal) -> int:
    """Digits after the point when ``value`` is written out without an exponent."""
    return len(_written_out(value)[1])


def significant_digits(value: Decimal) -> int:
    """Significant digits as the ledger counts them: trailing zeros count, leading ones do not."""
    whole, fraction = _written_out(value)
    return len((whole + fraction).lstrip("0")) or 1


def fits_digit_limits(value: Decimal) -> bool:
    """Whether the ledger would accept ``value`` as written, as far as its digits go."""
    return (
        decimal_places(value) <= MAX_DECIMAL_PLACES
        and significant_digits(value) <= MAX_SIGNIFICANT_DIGITS
    )


def _written_out(value: Decimal) -> tuple[str, str]:
    """The digits before and after the point, without sign or exponent."""
    whole, _, fraction = format(value.copy_abs(), "f").partition(".")
    return whole, fraction
