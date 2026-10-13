"""The voice set: ten passages in the owner's own voice, with invented numbers.

Besides the debug, the final and the writings set there is a fourth, small
set (``sets/voice.json``, read as the ``voice`` set): ten passages written
the way the owner of the ledger writes a trade down, every amount, quantity,
price, date and clock time in them invented. Voice here means the owner's
own way of writing, not speech: the passages are typed text, like every
other set's.

Its sentences and gold answers keep the same shape and rules as the other
sets (``gold``), and a run of it is scored the same way, but apart: it is
never merged into the debug set, so the scores of the debug and the final
set stay comparable with every earlier run.

Names defined here: ``VOICE_SET``.
"""

from __future__ import annotations

from evals.gold import SETS_DIR

VOICE_SET = SETS_DIR / "voice.json"
