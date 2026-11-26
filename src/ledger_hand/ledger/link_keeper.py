"""Link keeper: the one assistant link of this program, started and stopped on request.

The assistant page lets the person reach their own ledger page through the
ledger's assistant link (``link_client.LedgerLink``). Its port is fixed, so
one program may run only one link: every browser tab of the page shares
the one ``LinkKeeper`` the interface keeps for the whole process.

- ``start`` builds a fresh link (a new token each time) and starts it;
  a link that cannot start is handed back as its ``LedgerLinkError``, and
  nothing is left running. Starting while one runs does nothing.
- ``stop`` closes it; every tab then sees ``LinkState.STOPPED``.
- ``state`` says where it stands (``LinkState``): not started, stopped,
  waiting for the ledger page, connected, the page disconnected, or the
  link gone by itself. It is read from the link's own lines on its
  standard error, which carry no ledger data.
- ``plug`` gives the ledger port over the running link for one model's
  name (the name the ledger writes into its change history), one plug for
  each name until the next start, so a trade listed in one turn can be
  changed in the next. Over a link that is not running, every call fails
  as the ledger not being reached.
- ``port`` and ``token_to_show`` give what the person enters on the
  ledger page; the token nowhere else.

Start and stop hold a lock, so two tabs pressing Start together start one
link. This module reads no setting and no clock: the way a link and a plug
are built is handed in.

Names defined here: ``LinkState``, ``LinkKeeper``.
"""

from __future__ import annotations

import enum
import threading
from collections.abc import Callable, Mapping
from typing import Any

from ledger_hand.ledger.link_client import LedgerLink, PageState, ToolAnswer
from ledger_hand.ledger.link_failures import LedgerLinkError, LinkFailure
from ledger_hand.ledger.link_ledger import ToolCaller
from ledger_hand.ports import LedgerPort


class LinkState(enum.Enum):
    """Where the one assistant link stands."""

    NOT_STARTED = "not started"
    STOPPED = "stopped"
    WAITING = "waiting for your ledger page to connect"
    CONNECTED = "connected to your ledger page"
    DISCONNECTED = "your ledger page disconnected"
    GONE = "the assistant link stopped by itself"


class _Current:
    """Whatever link runs now, for a plug that outlives one link: every call goes to it."""

    def __init__(self, keeper: LinkKeeper) -> None:
        self._keeper = keeper

    def call(self, name: str, arguments: Mapping[str, Any]) -> ToolAnswer:
        link = self._keeper.running_link()
        if link is None:
            raise LedgerLinkError(LinkFailure.NOT_STARTED)
        return link.call(name, arguments)

    def tools(self) -> list[dict[str, Any]]:
        """The tools the running link lists, so the plug can tell what the ledger takes."""
        link = self._keeper.running_link()
        if link is None:
            raise LedgerLinkError(LinkFailure.NOT_STARTED)
        return link.tools()


class LinkKeeper:
    """The program's one assistant link, and the plugs over it."""

    def __init__(
        self,
        make_link: Callable[[], LedgerLink],
        make_plug: Callable[[ToolCaller, str], LedgerPort],
    ) -> None:
        self._make_link = make_link
        self._make_plug = make_plug
        self._lock = threading.Lock()
        self._link: LedgerLink | None = None
        self._stopped = False
        self._plugs: dict[str, LedgerPort] = {}

    def __repr__(self) -> str:
        return f"LinkKeeper(state={self.state().name})"

    def start(self) -> LedgerLinkError | None:
        """Start a fresh link, unless one runs; its failure when it cannot start."""
        with self._lock:
            if self._link is not None and self._link.running():
                return None
            if self._link is not None:
                self._link.close()
                self._link = None
            link = self._make_link()
            try:
                link.start()
            except LedgerLinkError as error:
                link.close()
                return error
            self._link = link
            self._stopped = False
            self._plugs = {}
            return None

    def stop(self) -> None:
        """Close the link, if one was started; safe to repeat."""
        with self._lock:
            link, self._link = self._link, None
            if link is not None:
                link.close()
                self._stopped = True
            self._plugs = {}

    def state(self) -> LinkState:
        """Where the link stands now."""
        link = self._link
        if link is None:
            return LinkState.STOPPED if self._stopped else LinkState.NOT_STARTED
        if not link.running():
            return LinkState.GONE
        page = link.page_state()
        if page is PageState.CONNECTED:
            return LinkState.CONNECTED
        if page is PageState.DISCONNECTED:
            return LinkState.DISCONNECTED
        return LinkState.WAITING

    def running_link(self) -> LedgerLink | None:
        """The link, while it runs."""
        link = self._link
        return link if link is not None and link.running() else None

    def plug(self, model_name: str) -> LedgerPort:
        """The ledger port over whatever link runs, for ``model_name``; the same one each time."""
        with self._lock:
            kept = self._plugs.get(model_name)
            if kept is None:
                kept = self._make_plug(_Current(self), model_name)
                self._plugs[model_name] = kept
            return kept

    @property
    def port(self) -> int | None:
        """The port the person enters on the ledger page, while a link runs."""
        link = self.running_link()
        return link.port if link is not None else None

    @property
    def page_port(self) -> int | None:
        """The port the ledger page must be opened on, while a link runs."""
        link = self.running_link()
        return link.page_port if link is not None else None

    def token_to_show(self) -> str | None:
        """The token, for the interface to show the person beside the port; nowhere else."""
        link = self.running_link()
        return link.token_to_show() if link is not None else None
