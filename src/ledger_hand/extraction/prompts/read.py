"""The prompt that reads a screenshot out as text. Zero-shot.

The technique is zero-shot: instructions only, not one example. The model is
shown a screenshot of an exchange's order and writes out, as plain text,
what the screen shows about the order: each value with the label the screen
gives it, copied as it stands, in the language it is written in, every
number as written, with the unit or coin beside it. It never translates,
calculates, converts or completes anything, never adds what the screen does
not show, and leaves out what is not part of the order. The text it writes
is then extracted as a typed passage is; the labels are kept so that the
extraction can tell a price from a total.

A version is never changed once it has been used with a real model; a
change of wording is a new version in a new file.

This version is named ``read-1``; the state of a recorded passage names it
for the step it was used in.

Names defined here: ``READ_PROMPT``.
"""

from __future__ import annotations

from ledger_hand.extraction.picture_prompt import PicturePromptVersion

_INSTRUCTIONS = """\
You read a screenshot of a crypto exchange's app or website for a person \
who records their own trades. You write out, as plain text, what the \
screenshot shows about the order or orders on it, and nothing else.

Write one line for each value the order shows: the label the screen gives \
it, a colon, and the value. Copy both exactly as they appear on the screen, \
character for character, in the language they are written in, Chinese or \
English; never translate them. Copy every number as it is written: never \
calculate, convert or round it, and never add or drop a digit, a zero, a \
sign, a decimal point or a thousands separator. Copy the unit, coin or \
currency written next to a number together with it. Read every value of \
the order that the screen shows, such as the side (buy or sell), the pair \
or the coin, the amount, the price it was filled at, the total, the fee, \
the time and the status, so that each number keeps the label that says \
what it is.

Write only what the screenshot shows. Never add a value it does not show, \
such as the name of the exchange when the screen does not write it. Leave \
out what is not part of the order: the phone's clock, battery and signal at \
the top of the screen, balances, advertisements, menus and buttons. When \
the screenshot shows more than one order, read each one, with an empty line \
between them. Add no comment, judgement or explanation of your own.
"""

_ASK = "Read out the order on this screenshot."

READ_PROMPT = PicturePromptVersion(name="read-1", instructions=_INSTRUCTIONS, ask=_ASK)
