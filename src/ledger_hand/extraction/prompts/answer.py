"""The prompt that copies one piece out of an answer the rules could not read. Zero-shot.

The technique is zero-shot: instructions only, not one example. The model is
told what was asked (one field of a trade, or yes or no) and given the
user's answer, and it copies out of the answer the one piece that gives it,
character for character, or nothing when the answer does not give it. It
never calculates, converts, translates, corrects or completes anything: the
program checks that the piece really is a piece of the answer, and then
reads it with the same rules it reads a whole answer with.

A version is never changed once it has been measured; a change of wording is
a new version in a new file.

This version is named ``answer-1``; the state of a recorded passage names it
for the step it was used in.

Names defined here: ``ANSWER_PROMPT``.
"""

from __future__ import annotations

from ledger_hand.extraction.answer_table import AnswerPromptVersion, Wanted
from ledger_hand.extraction.prompting import PROBLEM_MARK

_INSTRUCTIONS = """\
A person is completing the record of one of their own crypto trades. They \
were asked about one field of it and typed an answer, in Chinese, English or \
both. You copy out of the answer the one piece that gives that field. You \
never calculate, convert, translate, correct, complete or guess anything.

The piece is the value itself: a number with the unit or currency word \
written right next to it, the words for a day and a time, the name of a \
coin, or the one word that says buy, sell, yes or no. Leave out the words \
around it that only lead up to it, such as "it was" or "I think". Keep a \
word right next to the value that makes it approximate, such as "about", so \
that the program can tell it is not exact.

You are told the field and given the answer. Reply with one JSON object: \
{"phrase": "..."}. The phrase is one unbroken piece of the answer, copied \
character for character in the language it is written in. Reply \
{"phrase": ""} only when the answer does not give the field at all.
"""

_FIELDS = {
    Wanted.SIDE: "whether the coin was bought or sold: the word that says so",
    Wanted.COIN: "the coin that was bought or sold, as the answer calls it",
    Wanted.QUANTITY: (
        "how much of the coin: the number, with the unit written right after it if there is one"
    ),
    Wanted.PRICE: (
        "the price of one coin: the number, with the currency sign or word written right "
        "next to it if there is one"
    ),
    Wanted.TOTAL: (
        "the whole amount paid or received, without the fee: the number, with the currency "
        "sign or word written right next to it if there is one"
    ),
    Wanted.FEE: (
        "the fee: the number, with the currency word written right after it if there is "
        "one, or the words that say there was no fee"
    ),
    Wanted.FEE_COIN: "the coin or currency the fee was paid in, as the answer calls it",
    Wanted.TIME: "when the trade happened: only the words that say the day and the time",
    Wanted.YES_OR_NO: "whether the answer says yes or no: the word that says it",
}

_ASK_AGAIN = (
    f"Your last answer could not be used: {PROBLEM_MARK}. Answer again with only "
    'the JSON object {"phrase": "..."}, following the rules above.'
)

ANSWER_PROMPT = AnswerPromptVersion(
    name="answer-1",
    instructions=_INSTRUCTIONS,
    fields=_FIELDS,
    ask_again=_ASK_AGAIN,
)
