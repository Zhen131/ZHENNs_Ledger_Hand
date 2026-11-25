"""Link client: starts the ledger's assistant link and talks to it, nothing more.

The assistant link (``assistant-link/main.ts`` in the ledger's folder) is a
small Node.js program. This program starts it as a child process and speaks
JSON-RPC 2.0 with it, one JSON object per line, over the child's standard
input and output (the Model Context Protocol's way, written by hand with the
standard library: no package is added for it). The link passes every tool
call to the ledger page the person connected, and passes the page's answer
back.

``LedgerLink`` does five things: ``start`` (check Node.js and the folder,
start the link, wait for its one machine-readable line, shake hands with the
name ``Ledger Hand`` and the version handed in), ``tools`` (the tool list as
the link gives it), ``call`` (one tool, its arguments as a dictionary; the
answer is the ledger's ``structuredContent`` as it came, a result or the
ledger's ``{code, category, message, field?}`` error, marked by
``AnswerKind``), ``page_state`` (whether a ledger page is connected, from
the link's lines on its standard error, which carry no ledger data) and
``close``. It translates nothing into the ledger port's shapes; that is
for the plug built on it.

Every failure is a ``LedgerLinkError`` with a ``LinkFailure``; none hangs:
each wait has a limit (``LinkSetup.start_seconds``, ``answer_seconds``),
kept with the waiting tools of ``subprocess`` and ``queue``. The token lives
only in memory: it goes to the link in its environment and to whoever asks
``token_to_show``; it is in no error, no ``repr`` and no file.

Everything it needs comes in through ``LinkSetup``: the folder, both ports,
the version, the environment the link is started with. It reads no
environment variable and no clock itself.

Names defined here: ``LinkSetup``, ``LedgerLink``, ``ToolAnswer``,
``AnswerKind``, ``PageState``, ``CLIENT_NAME``, ``PROTOCOL_VERSION``,
``MINIMUM_NODE_MAJOR``, ``TOKEN_VARIABLE``.
"""

from __future__ import annotations

import enum
import json
import queue
import re
import subprocess
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import IO, Any

from ledger_hand.ledger.link_failures import LedgerLinkError, LinkFailure, LinkToken

# The name the ledger shows and writes into its change history as
# "Assistant, self-reported: ...".
CLIENT_NAME = "Ledger Hand"
# The protocol version the link was tried with on 2026-11-25 (68B, part two, 2).
PROTOCOL_VERSION = "2025-06-18"
# The ledger's package.json asks for Node.js 24 or later ("engines").
MINIMUM_NODE_MAJOR = 24
TOKEN_VARIABLE = "LEDGER_LINK_TOKEN"
# The link's exit status for bad options, a bad token or a port it cannot open.
_EXIT_CANNOT_START = 2
_TOKEN_LINE = re.compile(r"ledger-link token=\S+ port=(\d+)")
_NODE_VERSION = re.compile(r"v(\d+)\.\d+\.\d+")
_LINE_PREFIX = "assistant-link: "
_ERROR_PREFIX = _LINE_PREFIX + "ERROR: "
_PORT_TAKEN = "already in use"
# JSON-RPC's code for "invalid params"; the link answers it to a refused name.
_INVALID_PARAMS = -32602
_END = object()


class AnswerKind(enum.Enum):
    """What a tool call came back as."""

    RESULT = "result"
    ERROR = "error"


@dataclass(frozen=True)
class ToolAnswer:
    """One tool's answer: the ledger's ``structuredContent`` as it came, and which kind it is."""

    kind: AnswerKind
    content: Mapping[str, Any]


class PageState(enum.Enum):
    """Whether a ledger page is connected to the link, as its lines on standard error say."""

    NOT_CONNECTED = "no ledger page has connected yet"
    CONNECTED = "a ledger page is connected"
    DISCONNECTED = "the ledger page disconnected"


@dataclass(frozen=True)
class LinkSetup:
    """What the link is started with. ``environment`` is copied for the link, token added."""

    ledger_directory: Path
    token: LinkToken
    hand_version: str
    port: int = 47651
    page_port: int = 3000
    environment: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    node: str = "node"
    start_seconds: float = 30.0
    # Above the 45 seconds the link waits for the page, so the link's own
    # LEDGER_PAGE_TIMEOUT comes back before this program gives up.
    answer_seconds: float = 60.0
    # How long a link that is leaving is waited for before it is stopped.
    close_seconds: float = 5.0


class LedgerLink:
    """The ledger's assistant link, run as a child process of this program."""

    def __init__(self, setup: LinkSetup) -> None:
        self._setup = setup
        self._process: subprocess.Popen[str] | None = None
        self._replies: queue.Queue[object] = queue.Queue()
        self._starting: queue.Queue[object] = queue.Queue()
        self._lock = threading.Lock()
        self._page = PageState.NOT_CONNECTED
        self._last_error = ""
        self._next_id = 0

    def __repr__(self) -> str:
        running = self._process is not None and self._process.poll() is None
        return f"LedgerLink(port={self._setup.port}, running={running})"

    def __enter__(self) -> LedgerLink:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @property
    def port(self) -> int:
        """The port of 127.0.0.1 the link listens on, for the person to enter on the page."""
        return self._setup.port

    @property
    def page_port(self) -> int:
        """The port the ledger page is opened on; the link takes pages from there only."""
        return self._setup.page_port

    def token_to_show(self) -> str:
        """The token, for the interface to show the person beside the port; nowhere else."""
        return self._setup.token.reveal()

    def start(self) -> None:
        """Start the link and shake hands; a ``LedgerLinkError`` when that cannot be done."""
        self._check_folder()
        self._check_node()
        self._process = self._spawn()
        self._wait_until_listening()
        try:
            reply = self._request("initialize", self._hello())
        except LedgerLinkError:
            # A link left running would hold its port, and the next try would
            # find it taken (68D, finding 1).
            self.close()
            raise
        if "error" in reply:
            self.close()
            failure = (
                LinkFailure.HANDSHAKE_REFUSED
                if _error_code(reply) == _INVALID_PARAMS
                else LinkFailure.CANNOT_START
            )
            raise self._error(failure, _error_message(reply))
        self._write({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def tools(self) -> list[dict[str, Any]]:
        """The tools the link lists, each as it came (name, description, input schema)."""
        result = self._result(self._request("tools/list", {}))
        listed = result.get("tools")
        if not isinstance(listed, list) or not all(isinstance(t, dict) for t in listed):
            raise self._error(LinkFailure.REPLY_UNEXPECTED, "tools/list without a list of tools")
        return listed

    def call(self, name: str, arguments: Mapping[str, Any]) -> ToolAnswer:
        """Call the tool ``name`` with ``arguments``; the ledger's answer as it came."""
        reply = self._request("tools/call", {"name": name, "arguments": dict(arguments)})
        result = self._result(reply)
        content = result.get("structuredContent")
        if not isinstance(content, dict):
            raise self._error(LinkFailure.REPLY_UNEXPECTED, f"{name}: no structuredContent")
        kind = AnswerKind.ERROR if result.get("isError") is True else AnswerKind.RESULT
        return ToolAnswer(kind=kind, content=content)

    def page_state(self) -> PageState:
        """Whether a ledger page is connected now."""
        with self._lock:
            return self._page

    def close(self) -> None:
        """Close the link's input, so that it leaves; stop it when it does not. Safe to repeat."""
        process = self._process
        if process is None:
            return
        self._process = None
        try:
            if process.stdin is not None:
                process.stdin.close()
        except OSError:
            pass
        try:
            process.wait(timeout=self._setup.close_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    # --- before starting ------------------------------------------------------

    def _check_folder(self) -> None:
        folder = self._setup.ledger_directory
        if not (folder / "assistant-link" / "main.ts").is_file():
            raise self._error(LinkFailure.LEDGER_FOLDER_WRONG, "no assistant-link/main.ts in it")
        if not (folder / "node_modules" / "tsx").is_dir():
            raise self._error(LinkFailure.LEDGER_FOLDER_WRONG, "its programs are not installed")

    def _check_node(self) -> None:
        try:
            answered = subprocess.run(
                [self._setup.node, "--version"],
                capture_output=True,
                text=True,
                timeout=self._setup.start_seconds,
                env=dict(self._setup.environment),
                check=False,
            )
        except (FileNotFoundError, PermissionError, NotADirectoryError) as error:
            raise self._error(LinkFailure.NODE_MISSING) from error
        except subprocess.TimeoutExpired as error:
            raise self._error(LinkFailure.TIMED_OUT, "asking Node.js its version") from error
        found = _NODE_VERSION.fullmatch(answered.stdout.strip())
        if found is None:
            raise self._error(LinkFailure.NODE_MISSING, "it did not say its version")
        if int(found.group(1)) < MINIMUM_NODE_MAJOR:
            raise self._error(
                LinkFailure.NODE_TOO_OLD,
                f"found {found.group(0)}, the ledger needs {MINIMUM_NODE_MAJOR} or later",
            )

    def _spawn(self) -> subprocess.Popen[str]:
        setup = self._setup
        environment = {**setup.environment, TOKEN_VARIABLE: setup.token.reveal()}
        command = [
            setup.node,
            "--import",
            "tsx",
            "assistant-link/main.ts",
            f"--port={setup.port}",
            f"--page-port={setup.page_port}",
        ]
        try:
            process = subprocess.Popen(
                command,
                cwd=setup.ledger_directory,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except OSError as error:
            raise self._error(LinkFailure.NODE_MISSING) from error
        _reader(process.stdout, self._replies.put, self._replies)
        _reader(process.stderr, self._heard, self._starting)
        return process

    def _wait_until_listening(self) -> None:
        try:
            heard = self._starting.get(timeout=self._setup.start_seconds)
        except queue.Empty:
            self.close()
            raise self._error(LinkFailure.TIMED_OUT, "waiting for the link to listen") from None
        if heard is _END:
            raise self._exit_error()
        if heard != self._setup.port:
            self.close()
            raise self._error(LinkFailure.CANNOT_START, f"it listens on port {heard}")

    def _exit_error(self) -> LedgerLinkError:
        process, self._process = self._process, None
        try:
            status = process.wait(timeout=self._setup.close_seconds) if process else None
        except subprocess.TimeoutExpired:
            # A link that said why it stops but does not leave is stopped (68D, finding 2).
            assert process is not None
            process.kill()
            process.wait()
            return self._error(LinkFailure.TIMED_OUT, "waiting for the link to leave")
        with self._lock:
            said = self._last_error
        if status == _EXIT_CANNOT_START and _PORT_TAKEN in said:
            return self._error(LinkFailure.PORT_IN_USE, said)
        return self._error(LinkFailure.CANNOT_START, f"exit status {status}. {said}".strip())

    def _heard(self, line: str) -> None:
        """Take one line of the link's standard error; the token line is read, never kept."""
        text = line.rstrip("\n")
        listening = _TOKEN_LINE.fullmatch(text)
        if listening is not None:
            self._starting.put(int(listening.group(1)))
            return
        with self._lock:
            if text == _LINE_PREFIX + "page connected":
                self._page = PageState.CONNECTED
            elif text == _LINE_PREFIX + "page disconnected":
                self._page = PageState.DISCONNECTED
            elif text.startswith(_ERROR_PREFIX):
                self._last_error = self._setup.token.hide_in(text.removeprefix(_ERROR_PREFIX))

    # --- talking ----------------------------------------------------------------

    def _hello(self) -> dict[str, Any]:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": CLIENT_NAME, "version": self._setup.hand_version},
        }

    def _request(self, method: str, params: Mapping[str, Any]) -> dict[str, Any]:
        self._next_id += 1
        asked = self._next_id
        self._write({"jsonrpc": "2.0", "id": asked, "method": method, "params": dict(params)})
        return self._reply(asked)

    def _write(self, message: Mapping[str, Any]) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise self._error(LinkFailure.NOT_STARTED)
        try:
            process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            process.stdin.flush()
        except (OSError, ValueError) as error:
            raise self._error(LinkFailure.LINK_GONE) from error

    def _reply(self, asked: int) -> dict[str, Any]:
        while True:
            try:
                line = self._replies.get(timeout=self._setup.answer_seconds)
            except queue.Empty:
                raise self._error(LinkFailure.TIMED_OUT, "waiting for an answer") from None
            if line is _END:
                raise self._error(LinkFailure.LINK_GONE)
            try:
                message = json.loads(str(line))
            except json.JSONDecodeError:
                raise self._error(LinkFailure.REPLY_NOT_JSON) from None
            if not isinstance(message, dict):
                raise self._error(LinkFailure.REPLY_NOT_JSON, "not a JSON object")
            if message.get("id") == asked:
                return message

    def _result(self, reply: Mapping[str, Any]) -> dict[str, Any]:
        if "error" in reply:
            raise self._error(LinkFailure.CALL_REFUSED, _error_message(reply))
        result = reply.get("result")
        if not isinstance(result, dict):
            raise self._error(LinkFailure.REPLY_UNEXPECTED, "an answer without a result")
        return result

    def _error(self, failure: LinkFailure, detail: str = "") -> LedgerLinkError:
        return LedgerLinkError(failure, self._setup.token.hide_in(detail))


def _reader(
    stream: IO[str] | None, take: Callable[[str], object], ended: queue.Queue[object]
) -> None:
    """Read ``stream`` line by line on a thread of its own; ``_END`` into ``ended`` at its end."""

    def read() -> None:
        if stream is not None:
            for line in stream:
                take(line)
        ended.put(_END)

    threading.Thread(target=read, daemon=True).start()


def _error_code(reply: Mapping[str, Any]) -> object:
    error = reply.get("error")
    return error.get("code") if isinstance(error, dict) else None


def _error_message(reply: Mapping[str, Any]) -> str:
    error = reply.get("error")
    message = error.get("message") if isinstance(error, dict) else None
    return message if isinstance(message, str) else ""
