"""The shape of a version of the prompt that reads a screenshot.

A version of the reading prompt has a name, the instructions the model is
given as the system message, and the words of the user's message the
picture is attached to. It asks for no table: what is wanted is the text
of the order as the screen shows it, and the model writes it as plain text.
The versions themselves are in ``prompts`` (``read`` for ``read-1``); this
module only states their shape, so that a version and the step that reads a
picture can both import it without importing each other.

Names defined here: ``PicturePromptVersion``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PicturePromptVersion:
    """One version of the prompt that reads a screenshot.

    ``instructions`` is the system message, and ``ask`` the user's message
    the picture goes with; neither may be blank.
    """

    name: str
    instructions: str
    ask: str

    def __post_init__(self) -> None:
        for field in ("name", "instructions", "ask"):
            text = getattr(self, field)
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"a reading prompt's {field} must be text that is not blank")
