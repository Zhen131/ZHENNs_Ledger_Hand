"""The program's own sentence for each follow-up question.

``template_sentence`` gives one plain English question for what is asked. It
is used whenever the model's sentence will not do, so every question that
can be asked has one, and it says nothing beyond what is asked and why: the
facts around it (the words of the passage, the values already known, the
choices) are shown beside the question by the program.

With the ledger's own asset table, the sentences that would say "coin" call
the asset by what it is (``core.asset_words``): a share, a coin, or an
asset while it is not recognised; the fee's asset is the "fee asset". With
the built-in table every sentence stays as it was, word for word.

Names defined here: ``template_sentence``.
"""

from __future__ import annotations

from ledger_hand.core.asset_words import AssetWord, cell_name, problem_words
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
    Cell.QUOTE: "Which currency was this trade priced in?",
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


# The price and the total, asked with the money the trade is priced in named,
# or with none named while it is not known; for an asset table made from the
# ledger's list, which may price in more than USDT.
_ASK_IN = {
    Cell.PRICE: "What was the price of one unit{in_money}?",
    Cell.TOTAL: "What was the total paid or received{in_money}, without the fee?",
}


# The sentences that would say "coin", for the ledger's own table: asked with no
# kind of asset named, or with the trade's own (a share, a coin, an asset).
_LEDGER_ASK = {
    Cell.COIN: "Which asset was bought or sold in this trade?",
    Cell.FEE_COIN: "Which asset or currency was the fee paid in?",
}
_LEDGER_QUANTITY = {
    AssetWord.SHARE: "How many shares were bought or sold?",
    AssetWord.COIN: "How much of the coin was bought or sold?",
    AssetWord.ASSET: "How much of the asset was bought or sold?",
}
_LEDGER_BECAUSE = {
    Violation.COIN_NOT_A_SYMBOL: "The ledger lists no asset by that name; which asset was it?",
    Violation.FEE_COIN_NOT_A_SYMBOL: (
        "The ledger lists no asset by that name for the fee; "
        "which asset or currency was the fee paid in?"
    ),
}
_LEDGER_FEE_BELOW = (
    "A fee paid in the asset bought has to be smaller than the quantity; "
    "which of the two is wrong, and what is its right value?"
)


def template_sentence(
    asked: AskCell | ConfirmCoin | AskWhichCell,
    word: str | None,
    money: str | None = None,
    asset: AssetWord | None = None,
) -> str:
    """The program's question for ``asked``; ``word`` is the coin word a confirmation is about.

    ``money`` is the code of the money the trade is priced in, named when
    the price or the total is asked; empty when it is not known, so that no
    money is named. ``None`` keeps the built-in sentences, which name USDT.
    ``asset`` is what the ledger's own table calls the trade's asset (a
    share, a coin, an asset); ``None`` keeps the built-in sentences.
    """
    if asset is not None and not isinstance(asked, ConfirmCoin):
        ledger_s = _ledger_sentence(asked, asset)
        if ledger_s is not None:
            return ledger_s
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
        if money is not None and asked.cell in _ASK_IN:
            return _ASK_IN[asked.cell].format(in_money=f", in {money}" if money else "")
        return _ASK[asked.cell]
    return f"The {asked.cell.value} cannot be used ({asked.because.value}); what should it be?"


def _ledger_sentence(asked: AskCell | AskWhichCell, asset: AssetWord) -> str | None:
    """The ledger's table's own sentence where the built-in one says "coin"; else ``None``."""
    if isinstance(asked, AskWhichCell):
        return None if asked.cells == AMOUNT_CELLS else _LEDGER_FEE_BELOW
    if asked.because in _LEDGER_BECAUSE:
        return _LEDGER_BECAUSE[asked.because]
    if asked.because in _BECAUSE:
        return None
    if isinstance(asked.because, Missing):
        if asked.cell is Cell.QUANTITY:
            return _LEDGER_QUANTITY[asset]
        return _LEDGER_ASK.get(asked.cell)
    name = cell_name(asked.cell, ledger=True)
    because = problem_words(asked.because, ledger=True)
    return f"The {name} cannot be used ({because}); what should it be?"
