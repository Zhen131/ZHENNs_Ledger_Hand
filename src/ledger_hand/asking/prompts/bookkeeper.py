"""The prompt that words a follow-up question: the model plays a meticulous bookkeeper.

The technique is a persona: the instructions open by giving the model a
role, a meticulous bookkeeper who asks for exactly what is missing, one
thing at a time, and never guesses on anyone's behalf. It is given only
the facts the program settled (which trade, what to ask and why, the cells
already known, the words of the passage about it, the notes and the choices)
and writes one English question. It may not bring in a number, a coin, a
date or a time that is not among them; the program checks that, and uses
its own sentence instead when the model's will not do.

A version is never changed once it has been used for a measurement; a change
of wording is a new version in a new file.

This version is named ``bookkeeper-1``; the state of a recorded passage names it
for the step it was used in.

Names defined here: ``BookkeeperPrompt`` and ``BOOKKEEPER_PROMPT``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BookkeeperPrompt:
    """One version of the prompt: its name and its instructions."""

    name: str
    instructions: str


_INSTRUCTIONS = """\
You are a meticulous bookkeeper who keeps the crypto trading ledger of one \
person. When something is missing from a record, or cannot be right, you ask \
for exactly that one thing, one question at a time, and you never guess or \
fill in anything on the person's behalf.

You are given the facts that are already settled about one trade, and the one \
thing to ask. Write exactly one short, polite question in English that asks \
for that one thing. Use only the facts you are given: never bring in a \
number, a coin, a date or a time that is not among them. Words quoted from \
the person's passage may be repeated exactly as given. Do not explain, greet \
or add a second sentence.

Reply with one JSON object: {"question": "..."}.
"""

BOOKKEEPER_PROMPT = BookkeeperPrompt(name="bookkeeper-1", instructions=_INSTRUCTIONS)
