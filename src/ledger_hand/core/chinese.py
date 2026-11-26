"""Whether words hold a Chinese character: the one rule the program has for it.

Tidying what the user said (``spoken_text``) leaves words with no Chinese
character in them as they were, and the assistant extracts a trade from
words with a Chinese character in them with the version of the prompt
whose examples are written the way the owner speaks
(``extraction.prompt_language``). Both ask the same pattern, kept here
once so that the two cannot drift apart.

Names defined here: ``CHINESE_CHARACTER`` and ``holds_chinese``.
"""

from __future__ import annotations

import re

# One character of the main block of Chinese characters, or the round zero "〇".
CHINESE_CHARACTER = re.compile("[一-鿿〇]")


def holds_chinese(text: str) -> bool:
    """Whether ``text`` holds at least one Chinese character."""
    return CHINESE_CHARACTER.search(text) is not None
