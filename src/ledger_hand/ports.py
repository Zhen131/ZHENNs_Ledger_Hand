"""The three ports: what the program may ask of a language model, of storage and of the ledger.

The rest of the program only ever talks to a ``ModelPort``. Behind it sits a
plug: the local model server today, perhaps a cloud service later, or a
scripted stand-in in the tests. One call sends a list of messages, optionally
a JSON schema the reply has to follow, and the sampling parameters; it gets
back the reply's text and a short record of the call. Every failure, whatever
the plug, is one ``ModelError`` carrying one of six kinds.

A second kind of call shows the model pictures: the same messages, with one
or more pictures (``Picture``: the bytes of a PNG or JPEG file and which of
the two it is) attached to the last message, which must be the user's. It
takes no reply schema: what is asked of a picture is its text as it stands.
A plug that cannot send pictures refuses such a call before sending
anything, as the caller's mistake rather than as a model failure.

A third kind of call hands the model a list of tools it may ask for
(``ToolSpec``: a name, what it does, and the JSON schema of what it takes).
Its reply is either text or one or more tool calls (``ToolReply``,
``ToolCall``). The conversation it is sent may hold, besides plain messages,
the model's own earlier tool calls (``ToolCallTurn``) and what the program
handed back for each (``ToolResult``); only this call takes them. A tool
call is untrusted input like any reply: whether its tool is on the list and
its arguments follow the tool's schema is for the caller to judge.

Saved trades are kept behind a ``StoragePort``: a SQLite file today, or an
in-memory stand-in in the tests. It saves the trades recorded from one
passage together, with the coins the user confirmed for them; says whether a
passage with the same fingerprint was saved before; lists the saved trades,
all of them or those not exported yet; marks trades as exported; and lists
the confirmed coins. Every failure, whatever the plug, is one
``StorageError`` carrying one of eight kinds. The shapes it takes and gives
carry moments, so they are declared in ``core.book`` and only named here.

The ledger itself, the one the person keeps their trades in, is reached
through a ``LedgerPort``: list its assets and trades, sum a stretch of time
up, say what is held and at what market price, say how much of each cash
money it holds (a ledger with no tool for that says so with its own code,
``NO_CASH_TOOL``), list the exchange rates it keeps between two moneys (one
with no tool for that says ``NO_RATE_TOOL``), and propose to record,
change or delete trades. A
proposal writes nothing: it waits in the ledger for the person to save or
reject it there, one proposal for each trade. A ledger that takes a trade
with cells left empty (``takes_unfinished``) is sent cards
(``propose_cards``, ``core.trade_card``), each with its marks; it says
for each card it took whether it can be saved as it is, which cells are
empty, and what its checks found in the cells given. Every failure is one
``LedgerError`` carrying one of seven kinds, a fixed code and a sentence; a
trade that fails the ledger's check is not a failure, but part of the
proposal's answer. Its shapes are declared in ``core.ledger_records`` and
``core.proposals``.

This module only declares shapes. It sends nothing, stores nothing, reads no
settings and holds no prompt. Whether the text of a reply is valid JSON that
follows the schema is for the caller to check: a model reply is untrusted
input. Which plug is used, and with which defaults, is decided where the plug
is built from the settings.

Names defined here: ``Role``, ``Message``, ``JsonSchema``,
``PictureKind``, ``Picture``, ``picture_kind``, ``ModelParameters``,
``FinishReason``, ``ReplyRecord``, ``ModelReply``, ``ModelErrorKind``,
``ModelError``, ``ToolSpec``, ``ToolCall``, ``ToolCallTurn``, ``ToolResult``,
``ChatItem``, ``ToolReply``, ``ModelPort``, ``StorageErrorKind``,
``StorageError``, ``StoragePort``, ``LedgerErrorKind``, ``LedgerError`` and
``LedgerPort``.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from ledger_hand.core.book import (
    ConfirmedCoin,
    EarlierSave,
    ExportMark,
    ListedTrade,
    Listing,
    PassageSave,
)
from ledger_hand.core.ledger_rate import RateList, RateRequest
from ledger_hand.core.ledger_records import (
    Asset,
    CashBalances,
    MarketPrice,
    PeriodRequest,
    PeriodSummary,
    Position,
    TradeFacts,
    TradeFilter,
    TradeList,
)
from ledger_hand.core.proposals import ProposalResult, ProposalState
from ledger_hand.core.stored import StoredTrade
from ledger_hand.core.trade_card import TradeCard


class Role(enum.Enum):
    """Who speaks in a message; the values are the names model servers use."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class Message:
    """One message of a conversation."""

    role: Role
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, Role):
            raise TypeError(f"a message role is a Role, not {type(self.role).__name__}")
        if not isinstance(self.content, str):
            raise TypeError(f"a message's content is text, not {type(self.content).__name__}")


type JsonSchema = Mapping[str, object]
"""A JSON schema, as plain JSON values, that a reply's text has to follow."""


class PictureKind(enum.Enum):
    """The kinds of picture a model may be shown; the values are their media types."""

    PNG = "image/png"
    JPEG = "image/jpeg"


# The bytes every file of each kind starts with.
_SIGNATURES = {
    PictureKind.PNG: b"\x89PNG\r\n\x1a\n",
    PictureKind.JPEG: b"\xff\xd8\xff",
}


def picture_kind(data: bytes) -> PictureKind | None:
    """The kind of picture ``data`` starts as, by its first bytes; ``None`` when neither."""
    if not isinstance(data, bytes):
        raise TypeError(f"a picture is bytes, not {type(data).__name__}")
    for kind, signature in _SIGNATURES.items():
        if data.startswith(signature):
            return kind
    return None


@dataclass(frozen=True)
class Picture:
    """A picture to show the model: the bytes of the file, and which kind they are.

    The bytes must start the way a file of that kind does; only the start is
    checked, not whether the rest is a whole picture: the model server reads
    the rest.
    """

    data: bytes
    kind: PictureKind

    def __post_init__(self) -> None:
        if not isinstance(self.data, bytes):
            raise TypeError(f"a picture is bytes, not {type(self.data).__name__}")
        if not isinstance(self.kind, PictureKind):
            raise TypeError(f"a picture's kind is a PictureKind, not {type(self.kind).__name__}")
        if not self.data:
            raise ValueError("a picture cannot be empty")
        if picture_kind(self.data) is not self.kind:
            raise ValueError(f"the bytes do not start as a file of {self.kind.value} does")

    def __repr__(self) -> str:
        return f"Picture({self.kind.name}, {len(self.data)} bytes)"


@dataclass(frozen=True, kw_only=True)
class ModelParameters:
    """How the model samples its reply, and how long the caller waits for it.

    ``temperature`` is how adventurous the model is (0 is the same answer to
    the same text). ``top_p`` keeps only the likeliest words whose chances add
    up to it (1 keeps them all). ``max_reply_tokens`` caps the length of the
    reply and ``context_tokens`` the length the model reads at once, both in
    tokens, the pieces of words a model counts in. ``timeout_seconds`` is how
    long the caller waits for the whole reply; it is not sent to the model.
    """

    temperature: float
    top_p: float
    max_reply_tokens: int
    context_tokens: int
    timeout_seconds: float

    def __post_init__(self) -> None:
        _require_number("temperature", self.temperature)
        _require_number("top_p", self.top_p)
        _require_number("timeout_seconds", self.timeout_seconds)
        _require_whole_number("max_reply_tokens", self.max_reply_tokens)
        _require_whole_number("context_tokens", self.context_tokens)
        if self.temperature < 0:
            raise ValueError("temperature must be 0 or more")
        if not 0 < self.top_p <= 1:
            raise ValueError("top_p must be more than 0 and at most 1")
        if self.max_reply_tokens < 1 or self.context_tokens < 1:
            raise ValueError("max_reply_tokens and context_tokens must be 1 or more")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be more than 0")


def _require_number(name: str, value: object) -> None:
    """Refuse anything but a finite int or float; a bool is not a number here."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{name} must be a number, not {type(value).__name__}")
    # Infinity minus itself, and NaN minus anything, are NaN, which is not 0.
    if value - value != 0:
        raise ValueError(f"{name} must be a finite number")


def _require_whole_number(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a whole number, not {type(value).__name__}")


class FinishReason(enum.Enum):
    """Why the model stopped writing."""

    STOPPED = "stopped"
    """The model ended the reply itself."""
    LENGTH_LIMIT = "length_limit"
    """The reply reached ``max_reply_tokens`` and was cut off; its text is incomplete."""
    NOT_REPORTED = "not_reported"
    """The server gave no reason, or one this program does not know."""


@dataclass(frozen=True, kw_only=True)
class ReplyRecord:
    """A short record of one call.

    ``model`` is the model that answered, as the server names it.
    ``elapsed_seconds`` is measured by the caller's side, from sending to
    having the whole reply. The two token counts are what the model read and
    wrote, and are ``None`` when the server does not say.
    ``service_fingerprint`` is what a cloud service says identifies the
    model behind the name, when it says (OpenAI-style ``system_fingerprint``);
    a local model server never does, and it is ``None``.
    """

    model: str
    elapsed_seconds: float
    prompt_tokens: int | None
    reply_tokens: int | None
    finish: FinishReason
    service_fingerprint: str | None = None


@dataclass(frozen=True, kw_only=True)
class ModelReply:
    """The text the model wrote, and the record of the call."""

    text: str
    record: ReplyRecord


class ModelErrorKind(enum.Enum):
    """The six kinds of failure. Every plug sorts every failure into one of them."""

    UNREACHABLE = "unreachable"
    """Nothing answered at the address: the server is not running, refused the
    connection, or the address cannot be resolved."""
    TIMED_OUT = "timed_out"
    """No complete reply within the time allowed."""
    MODEL_NOT_FOUND = "model_not_found"
    """The server answered that it does not have the model asked for."""
    RATE_LIMITED = "rate_limited"
    """The server refused because it was called too often."""
    SERVER_ERROR = "server_error"
    """The server reported an internal error, or failed in a way that fits no
    other kind; then the error carries the raw status and the start of the reply."""
    MALFORMED_REPLY = "malformed_reply"
    """An answer came back but not in the agreed shape: not JSON, a field
    missing, empty text, too long, or not valid text."""


class ModelError(Exception):
    """A call to the model failed; ``kind`` says how.

    ``message`` says what happened in words. ``status`` is the HTTP status
    when the server answered with one, and ``snippet`` the start of what it
    sent, made printable, when that helps to see what went wrong. None of
    these ever holds a key. ``retry_after_seconds`` is how long the server
    asked to wait before the next call, when it said (a rate-limited call
    may); it is a finite number, 0 or more.
    """

    def __init__(
        self,
        kind: ModelErrorKind,
        message: str,
        *,
        status: int | None = None,
        snippet: str | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        if retry_after_seconds is not None:
            _require_number("retry_after_seconds", retry_after_seconds)
            if retry_after_seconds < 0:
                raise ValueError("retry_after_seconds must be 0 or more")
        super().__init__(kind, message)
        self.kind = kind
        self.message = message
        self.status = status
        self.snippet = snippet
        self.retry_after_seconds = retry_after_seconds

    def __str__(self) -> str:
        text = f"{self.kind.value}: {self.message}"
        if self.status is not None:
            text += f" (status {self.status})"
        if self.snippet is not None:
            text += f"; the reply began {self.snippet!r}"
        if self.retry_after_seconds is not None:
            text += f"; the server asked to wait {self.retry_after_seconds:g} seconds"
        return text

    def __repr__(self) -> str:
        shown = f"ModelError({self.kind.name}, {self.message!r}, status={self.status!r}"
        if self.retry_after_seconds is not None:
            shown += f", retry_after_seconds={self.retry_after_seconds!r}"
        return shown + ")"


@dataclass(frozen=True, kw_only=True)
class ToolSpec:
    """A tool the model may ask for: its name, what it does, and the schema of its arguments."""

    name: str
    description: str
    parameters: JsonSchema

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("a tool's name is text that is not empty")
        if not isinstance(self.description, str):
            raise TypeError("a tool's description is text")
        if not isinstance(self.parameters, Mapping):
            raise TypeError("a tool's parameters are a JSON schema, a mapping")


@dataclass(frozen=True, kw_only=True)
class ToolCall:
    """One tool the model asked for, by name, and the arguments it gave, as plain JSON values.

    Neither has been checked against the list of tools: that is the caller's job.
    """

    name: str
    arguments: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(f"a tool call's name is text, not {type(self.name).__name__}")
        if not isinstance(self.arguments, Mapping) or not all(
            isinstance(key, str) for key in self.arguments
        ):
            raise TypeError("a tool call's arguments are a mapping with text keys")


@dataclass(frozen=True, kw_only=True)
class ToolCallTurn:
    """The model's turn in which it asked for tools: any text it wrote, and its calls."""

    text: str
    calls: tuple[ToolCall, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError("a tool-call turn's text is text")
        if not isinstance(self.calls, tuple) or not self.calls:
            raise ValueError("a tool-call turn holds a tuple of at least one call")
        if not all(isinstance(call, ToolCall) for call in self.calls):
            raise TypeError("a tool-call turn's calls are ToolCall values")


@dataclass(frozen=True, kw_only=True)
class ToolResult:
    """What the program handed back for one tool call: the tool's name and the text of it."""

    name: str
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not isinstance(self.content, str):
            raise TypeError("a tool result's name and content are text")


type ChatItem = Message | ToolCallTurn | ToolResult
"""One item of a conversation that may use tools."""


@dataclass(frozen=True, kw_only=True)
class ToolReply:
    """The model's answer when it was handed tools: text, tool calls, or both, and the record.

    With no call, the text is not blank.
    """

    text: str
    calls: tuple[ToolCall, ...]
    record: ReplyRecord

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not isinstance(self.calls, tuple):
            raise TypeError("a tool reply holds text and a tuple of calls")
        if not all(isinstance(call, ToolCall) for call in self.calls):
            raise TypeError("a tool reply's calls are ToolCall values")
        if not self.calls and not self.text.strip():
            raise ValueError("a tool reply with no call has text that is not blank")


class ModelPort(Protocol):
    """Anything the program can ask for a reply."""

    def chat(
        self,
        messages: Sequence[Message],
        *,
        reply_schema: JsonSchema | None = None,
        parameters: ModelParameters | None = None,
    ) -> ModelReply:
        """Send ``messages`` and return the reply, or raise ``ModelError``.

        With ``reply_schema`` the model is asked to write JSON that follows
        it. Without ``parameters`` the plug uses the defaults it was built with.
        """
        ...

    def chat_with_pictures(
        self,
        messages: Sequence[Message],
        pictures: Sequence[Picture],
        *,
        parameters: ModelParameters | None = None,
    ) -> ModelReply:
        """Send ``messages`` with ``pictures`` on the last, and return the reply, or raise.

        The last message must be the user's, and there must be at least one
        picture; a call in another shape is the caller's mistake, refused
        with ``TypeError`` or ``ValueError`` before anything is sent. The
        reply is read as ``chat`` reads it, and fails as ``chat`` fails, with
        ``ModelError``. Without ``parameters`` the plug uses its defaults.
        """
        ...

    def chat_with_tools(
        self,
        items: Sequence[ChatItem],
        tools: Sequence[ToolSpec],
        *,
        parameters: ModelParameters | None = None,
    ) -> ToolReply:
        """Send ``items`` with ``tools`` the model may ask for; return its text or its calls.

        ``items`` may hold the model's earlier tool calls and the results
        handed back for them. A reply that comes back in a shape that cannot
        be read (a tool's name that is not text, arguments that are not a
        JSON object) is ``MALFORMED_REPLY``, as for ``chat``. A plug that
        cannot send tools refuses the call before sending anything, as the
        caller's mistake (``ValueError``). Without ``parameters`` the plug
        uses its defaults.
        """
        ...


class StorageErrorKind(enum.Enum):
    """The eight kinds of storage failure. Every plug sorts every failure into one of them."""

    NEWER_VERSION = "newer_version"
    """The book was written by a newer version of this program. Nothing is written to
    it, unless SQLite first rolled back a write to it that had been cut off part
    way; the message then says so."""
    NOT_A_DATABASE = "not_a_database"
    """The file is not a database at all. Nothing is written to it, unless SQLite
    first rolled back a write to it that had been cut off part way; the message
    then says so."""
    NOT_THIS_PROGRAMS = "not_this_programs"
    """The file is a database, but not this program's book, or its tables are not
    the ones its version has. Nothing is written to it, unless SQLite first rolled
    back a write to it that had been cut off part way; the message then says so."""
    DAMAGED = "damaged"
    """The book is damaged: cut short, or holding what cannot be read back."""
    LOCKED = "locked"
    """Someone else is using the book and it stayed busy for longer than the wait allowed."""
    INACCESSIBLE = "inaccessible"
    """The book or its folder cannot be made, read or written: no permission, a
    folder that is read-only or not a folder, a full disk, or an input or output error."""
    CONFLICT = "conflict"
    """What was asked does not fit what the book holds: an identifier already
    saved, or a trade to mark that is not there or was exported already."""
    UNEXPECTED = "unexpected"
    """A failure that fits no other kind; the message says what the store reported."""


class StorageError(Exception):
    """A storage operation failed; ``kind`` says how and ``message`` says it in words.

    Nothing is changed by an operation that fails: a save, or a marking, is
    whole or not at all.
    """

    def __init__(self, kind: StorageErrorKind, message: str) -> None:
        super().__init__(kind, message)
        self.kind = kind
        self.message = message

    def __str__(self) -> str:
        return f"{self.kind.value}: {self.message}"

    def __repr__(self) -> str:
        return f"StorageError({self.kind.name}, {self.message!r})"


class StoragePort(Protocol):
    """Where saved trades are kept. Every method raises ``StorageError`` when it fails.

    Moments come back in UTC; they are the same instants that were handed in.
    """

    def save(self, passage: PassageSave) -> tuple[StoredTrade, ...]:
        """Save the trades of ``passage`` and its confirmed coins, all together or not at all.

        Gives back the trades as saved. A coin already in the book keeps the
        moment it was first confirmed. An identifier already in the book is
        a ``CONFLICT``, and nothing is saved.
        """
        ...

    def earlier_saves(self, fingerprint: str) -> tuple[EarlierSave, ...]:
        """Every earlier save of a passage with ``fingerprint``, oldest first; none if never."""
        ...

    def trades(self, listing: Listing) -> tuple[ListedTrade, ...]:
        """The saved trades ``listing`` asks for, in the order they were saved."""
        ...

    def mark_exported(self, mark: ExportMark) -> None:
        """Mark every trade ``mark`` names as exported at its moment, all of them or none.

        A trade that is not in the book, or was exported already, is a
        ``CONFLICT``, and nothing is marked.
        """
        ...

    def confirmed_coins(self) -> tuple[ConfirmedCoin, ...]:
        """Every coin the user confirmed and saved a trade with, in the order of their symbols."""
        ...


class LedgerErrorKind(enum.Enum):
    """The kinds of ledger failure. Every plug sorts every failure into one of them."""

    UNREACHABLE = "unreachable"
    """The ledger could not be reached: no page connected, no ledger open, or the page
    gone before it answered."""
    UNKNOWN_ASSET = "unknown_asset"
    """The ledger does not know an asset it was asked about."""
    ASSET_IS_CURRENCY = "asset_is_currency"
    """Trades were asked for by a money (cash), which the ledger does not list trades by."""
    NOT_FOUND = "not_found"
    """The trade or the proposal asked about is not in the ledger."""
    TIMED_OUT = "timed_out"
    """The ledger did not answer in time. A proposal may still have reached it: it is
    never sent again, and the person is asked to look at the ledger's pending list."""
    RESULT_UNKNOWN = "result_unknown"
    """The ledger no longer knows the proposal asked about (its page was reloaded, which
    forgets every proposal). This says nothing of whether it was saved."""
    OTHER = "other"
    """A failure that fits no other kind; the message says what the ledger reported."""


class LedgerError(Exception):
    """A call to the ledger failed; ``kind`` says how, ``code`` is the ledger's fixed
    code for it, and ``message`` says it in one plain sentence.

    A trade that fails the ledger's check when it is proposed is not a
    failure: the proposal's answer says so for each trade.
    """

    def __init__(self, kind: LedgerErrorKind, code: str, message: str) -> None:
        super().__init__(kind, code, message)
        self.kind = kind
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"{self.kind.value} ({self.code}): {self.message}"

    def __repr__(self) -> str:
        return f"LedgerError({self.kind.name}, {self.code!r}, {self.message!r})"


class LedgerPort(Protocol):
    """The person's ledger. Every method raises ``LedgerError`` when it fails.

    Nothing here writes to the ledger: a proposal waits there until the
    person saves or rejects it on the ledger's own page. Every proposal
    carries ``said``, what the user said this time, word for word: for a
    change or a deletion that is what was said now, not what the trade was
    recorded from.
    """

    def list_assets(self) -> tuple[Asset, ...]:
        """Every asset the ledger knows."""
        ...

    def list_trades(self, trade_filter: TradeFilter) -> TradeList:
        """The trades ``trade_filter`` asks for, oldest first: at most ``MOST_TRADES_LISTED``,
        the latest, and whether older ones were left out. An asset the ledger does not
        know is ``UNKNOWN_ASSET``; a money is ``ASSET_IS_CURRENCY``."""
        ...

    def period_summary(self, request: PeriodRequest) -> PeriodSummary:
        """The sums of the stretch of days ``request`` names."""
        ...

    def positions(self) -> tuple[Position, ...]:
        """What is held now, one holding for each asset; none that is sold out."""
        ...

    def market_prices(self) -> tuple[MarketPrice, ...]:
        """The ledger's market price of each asset that has one, sold-out assets included.

        Only read. An asset with a market price in two moneys has one for
        each; a code two assets share has none, since neither is picked.
        """
        ...

    def cash_balances(self) -> CashBalances:
        """How much of each cash money the ledger holds today, one row a money, as it says.

        Only read. A ledger with no tool for it (an older one) raises
        ``LedgerError`` with the code ``NO_CASH_TOOL`` (kind ``OTHER``),
        so that "this ledger cannot" is told apart from "it could not be
        asked this time". Nothing is ever worked out from the trades.
        """
        ...

    def exchange_rates(self, request: RateRequest) -> RateList:
        """The exchange rates the ledger keeps between the two moneys ``request`` names.

        Only read; each row as the ledger stored it, newest first, never
        turned round or worked out. A ledger with no tool for it (an older
        one) raises ``LedgerError`` with the code ``NO_RATE_TOOL`` (kind
        ``OTHER``). The program asks it itself; the model is never handed it.
        """
        ...

    def propose_add(self, trades: tuple[TradeFacts, ...], said: str) -> ProposalResult:
        """Propose to record ``trades``; the answer holds the check of each, in order."""
        ...

    def takes_unfinished(self) -> bool:
        """Whether the ledger takes a trade with cells left empty, and marks on its cells.

        Only read, once: what the ledger's tools say they take, not a call
        about the person's trades. ``False`` for a ledger that never
        said so, which is then sent every trade whole, as before.
        """
        ...

    def propose_cards(self, cards: tuple[TradeCard, ...], said: str) -> ProposalResult:
        """Propose to record ``cards``, cells left empty allowed, each with its marks.

        The answer holds the check of each, in order; each card taken says
        whether it can be saved as it is (``TradeCheck.ready``), its empty
        cells and what the ledger found in the cells given. A card whose
        every cell is given is checked as by ``propose_add``. Only for a
        ledger that ``takes_unfinished``.
        """
        ...

    def propose_update(self, trade_id: str, facts: TradeFacts, said: str) -> ProposalResult:
        """Propose that the trade ``trade_id`` becomes ``facts``. A trade not in the ledger
        is a failed check (or ``NOT_FOUND``)."""
        ...

    def propose_delete(self, trade_id: str, said: str) -> ProposalResult:
        """Propose to delete the trade ``trade_id``. A trade not in the ledger is a failed
        check (or ``NOT_FOUND``)."""
        ...

    def proposal_status(self, proposal_id: str) -> ProposalState:
        """Where the proposal ``proposal_id`` stands. One the ledger never kept is
        ``NOT_FOUND``; one it forgot is ``RESULT_UNKNOWN``."""
        ...
