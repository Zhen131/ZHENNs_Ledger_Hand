"""The program's own sentence for each follow-up question.

``template_sentence`` gives one plain English question for what is asked. It
is used whenever the model's sentence will not do, so every question that
can be asked has one, and it says nothing beyond what is asked and why: the
facts around it (the words of the passage, the values already known, the
choices) are shown beside the question by the program.

Names defined here: ``template_sentence``.
"""

from __future__ import annotations

from ledger_hand.core.followup import AMOUNT_CELLS, AskCell, AskWhichCell, Cell, ConfirmCoin
from ledger_hand.core.validation import Missing, Violation

# What to ask for a cell when it is missing or a value has to be given again.
_ASK = {
    Cell.SIDE: "Was this trade a buy or a sell?",
    Cell.COIN: "Which coin was bought or sold in this trade?",
    Cell.QUANTITY: "How much of the coin was bought or sold?",
    Cell.PRICE: "What was the price of one coin, in USDT?",
    Cell.TOTAL: "What was the total paid or received, in USDT, without the fee?",
    Cell.FEE: "What was the fee for this trade?",
    Cell.FEE_COIN: "Which coin or currency was the fee paid in?",
    Cell.OCCURRED: "When did this trade happen?",
    Cell.PLATFORM: "What shorter name should be kept for the platform (or 'none')?",
    Cell.NOTE: "What shorter note should be kept (or 'none')?",
}

# A few problems that are worth saying in the question itself.
_BECAUSE = {
    Violation.IN_THE_FUTURE: "That time lies in the future; when did this trade happen?",
    Violation.OFFSET_HAS_SECONDS: (
        "That time cannot be written for the ledger; when did this trade happen?"
    ),
    Violation.COIN_NOT_A_SYMBOL: (
        "That coin cannot be written as a ledger symbol; which coin was it?"
    ),
    Violation.FEE_COIN_NOT_A_SYMBOL: (
        "That fee coin cannot be written as a ledger symbol; which coin was the fee paid in?"
    ),
    Violation.PLATFORM_TOO_LONG: (
        "The platform's name is longer than the ledger allows; "
        "what shorter name should be kept (or 'none')?"
    ),
    Violation.NOTE_TOO_LONG: (
        "The note is longer than the ledger allows; what shorter note should be kept (or 'none')?"
    ),
}


def template_sentence(asked: AskCell | ConfirmCoin | AskWhichCell, word: str | None) -> str:
    """The program's question for ``asked``; ``word`` is the coin word a confirmation is about."""
    if isinstance(asked, ConfirmCoin):
        if asked.cell is Cell.COIN:
            return f'Is "{word}" the symbol of a coin?'
        return f'Is "{word}", which the fee was paid in, the symbol of a coin?'
    if isinstance(asked, AskWhichCell):
        if asked.cells == AMOUNT_CELLS:
            return (
                "Quantity times price does not match the total; "
                "which of the three is wrong, and what is its right value?"
            )
        return (
            "A fee paid in the bought coin has to be smaller than the quantity; "
            "which of the two is wrong, and what is its right value?"
        )
    if asked.because in _BECAUSE:
        return _BECAUSE[asked.because]
    if isinstance(asked.because, Missing):
        return _ASK[asked.cell]
    return f"The {asked.cell.value} cannot be used ({asked.because.value}); what should it be?"
