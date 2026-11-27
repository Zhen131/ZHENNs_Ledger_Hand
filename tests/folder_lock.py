"""A folder that cannot be written into, on Windows, for the tests that need one.

On macOS and Linux those tests take the write bit off the folder with chmod,
and these functions do nothing there. Windows ignores that bit on a folder,
so on Windows they add, and later take away, an access rule that refuses
adding a file or a folder inside it and removing one from it: what a folder
without the write bit refuses. The rule is set with icacls, which comes with
Windows. The folder itself can still be read and listed, and the files
already in it keep their own rights, as on macOS and Linux.

Names defined here: ``refuse_writing_on_windows``, ``allow_writing_on_windows``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Windows' name for everyone, whatever the system's language.
_EVERYONE = "*S-1-1-0"
# Add a file, add a folder, remove anything inside.
_REFUSED = "(WD,AD,DC)"
# Remove a file or folder inside, set on what is in it.
_REFUSED_INSIDE = "(OI)(CI)(IO)(DE)"


def refuse_writing_on_windows(folder: Path) -> None:
    """On Windows, refuse adding to or removing from ``folder``; elsewhere do nothing."""
    if sys.platform == "win32":
        subprocess.run(
            [
                "icacls",
                str(folder),
                "/deny",
                f"{_EVERYONE}:{_REFUSED}",
                "/deny",
                f"{_EVERYONE}:{_REFUSED_INSIDE}",
            ],
            check=True,
            capture_output=True,
        )


def allow_writing_on_windows(folder: Path) -> None:
    """On Windows, take the rule ``refuse_writing_on_windows`` added away; elsewhere do nothing."""
    if sys.platform == "win32":
        subprocess.run(
            ["icacls", str(folder), "/remove:d", _EVERYONE], check=True, capture_output=True
        )
