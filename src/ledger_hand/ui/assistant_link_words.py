"""What the assistant page says about reaching the ledger page: one plain sentence for each case.

The assistant page can reach the person's own ledger page through the
ledger's assistant link (``ledger.link_keeper``). Everything the page says
about that link is written here, in plain English, never a raw error:

- ``STATE_WORDS``: one sentence for each ``LinkState``, with what to do;
- ``START_FAILURES``: one sentence for each way the link can fail to start
  (``LinkFailure``), with what to do; the ledger's own words follow it when
  there are any (``start_failed``);
- ``NO_LINK_WORDS``: why there is no link to start at all (``LinkNotSet``);
- ``THREE_STEPS``: how the person connects the ledger page;
- ``not_connected``: what is said in the chat when something is typed
  while the ledger page is not connected: nothing is sent and the model is
  not asked;
- ``SWITCHED``: what is said when the tab switches ledger and its chat is
  cleared.

The token is never part of any sentence here. A test walks every table
against its enumeration, so a new kind cannot go without one.

Names defined here: ``STATE_WORDS``, ``START_FAILURES``, ``NO_LINK_WORDS``,
``THREE_STEPS``, ``SWITCHED``, ``start_failed``, ``no_link`` and
``not_connected``.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from ledger_hand.ledger.link_failures import LedgerLinkError, LinkFailure
from ledger_hand.ledger.link_keeper import LinkState
from ledger_hand.settings import LEDGER_DIRECTORY_VARIABLE, LEDGER_LINK_PORT_VARIABLE
from ledger_hand.wiring import LinkNotSet, NoLink

STATE_WORDS: Mapping[LinkState, str] = MappingProxyType(
    {
        LinkState.NOT_STARTED: "Not started. Press Start to start the assistant link.",
        LinkState.STOPPED: (
            "Stopped. Stopping it in one browser tab stops it in every tab of this program; "
            "press Start to start it again, with a new token."
        ),
        LinkState.WAITING: (
            "Started, waiting for your ledger page to connect. Follow the three steps below."
        ),
        LinkState.CONNECTED: "Connected to your ledger page.",
        LinkState.DISCONNECTED: (
            "Your ledger page disconnected (it was disconnected there, closed, or reloaded). "
            "Connect it again with the three steps below."
        ),
        LinkState.GONE: (
            "The assistant link stopped by itself. Press Stop, then Start, to start it again."
        ),
    }
)

START_FAILURES: Mapping[LinkFailure, str] = MappingProxyType(
    {
        LinkFailure.NODE_MISSING: (
            "Node.js was not found, so the assistant link did not start. Install Node.js 24 "
            "or later, then start this program again."
        ),
        LinkFailure.NODE_TOO_OLD: (
            "Node.js is older than the ledger needs, so the assistant link did not start. "
            "Install Node.js 24 or later, then start this program again."
        ),
        LinkFailure.LEDGER_FOLDER_WRONG: (
            f"The folder {LEDGER_DIRECTORY_VARIABLE} names is not the ledger's, or its "
            "programs are not installed, so the assistant link did not start. Name the "
            "ledger's folder, and run npm install in it once."
        ),
        LinkFailure.PACKAGES_MISSING: (
            "The ledger's folder lacks packages its assistant link needs, so the link did not "
            "start. Run npm install in the ledger's folder once, then press Start again."
        ),
        LinkFailure.PORT_IN_USE: (
            "The assistant link's port is already used by another program (perhaps another "
            "copy of this one), so the link did not start. Stop that program, or choose "
            f"another port with {LEDGER_LINK_PORT_VARIABLE} and start this program again."
        ),
        LinkFailure.CANNOT_START: (
            "The assistant link did not start. Check the ledger's folder and Node.js, then "
            "press Start again."
        ),
        LinkFailure.HANDSHAKE_REFUSED: (
            "The assistant link refused this program's name or version, so it did not start. "
            "The ledger may be of another version than this program expects."
        ),
        LinkFailure.CALL_REFUSED: "The assistant link refused this program's first call.",
        LinkFailure.TIMED_OUT: (
            "The assistant link did not answer in time while starting. Press Start again."
        ),
        LinkFailure.LINK_GONE: (
            "The assistant link stopped while it was starting. Press Start again."
        ),
        LinkFailure.REPLY_NOT_JSON: (
            "The assistant link answered something this program cannot read while starting."
        ),
        LinkFailure.REPLY_UNEXPECTED: (
            "The assistant link answered in a shape this program does not know while starting."
        ),
        LinkFailure.NOT_STARTED: "The assistant link is not running. Press Start.",
    }
)

NO_LINK_WORDS: Mapping[LinkNotSet, str] = MappingProxyType(
    {
        LinkNotSet.NO_FOLDER: (
            f"To reach your ledger page, set {LEDGER_DIRECTORY_VARIABLE} to the ledger's "
            "folder (its dev version, with its programs installed) and start this program "
            "again. Until then only the demo ledger can be used."
        ),
        LinkNotSet.SETTING_REFUSED: (
            "A setting of the assistant link was refused: {detail}. Correct it and start this "
            "program again. Until then only the demo ledger can be used."
        ),
    }
)

THREE_STEPS = (
    "1. Open the ledger page at http://127.0.0.1:{page_port} and open your ledger.",
    '2. Press "Connect assistant" on the ledger page.',
    '3. Enter port {port} and paste the token (press "Show token" here to see it).',
)

SWITCHED = (
    "Switched to {ledger}. This chat was cleared: the two ledgers' trades and proposals are "
    "numbered apart, so a chat that mixed them could act on the wrong one."
)


def start_failed(error: LedgerLinkError) -> str:
    """The sentence for a start that failed, with what was seen after it."""
    said = START_FAILURES[error.failure]
    return f"{said} ({error.detail})" if error.detail else said


def no_link(missing: NoLink) -> str:
    """Why there is no link to start, and what to set."""
    return NO_LINK_WORDS[missing.reason].format(detail=missing.detail)


def not_connected(state: LinkState | None, port: int | None, page_port: int | None) -> str:
    """What is said when something is typed while the ledger page is not connected."""
    head = "Your ledger page is not connected yet, so nothing was sent and the model was not asked."
    if state is LinkState.GONE:
        return f"{head} {STATE_WORDS[state]}"
    if state is None or port is None or page_port is None:
        return f"{head} Press Start at the top of this page first, then connect your ledger page."
    steps = " ".join(step.format(port=port, page_port=page_port) for step in THREE_STEPS)
    return f"{head} {STATE_WORDS[state]} {steps}"
