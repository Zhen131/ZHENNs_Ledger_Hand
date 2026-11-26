"""The real ledger's plug: the ledger port, spoken through the ledger's assistant link.

``LinkLedger`` does all the ledger port promises against the ledger the
person keeps, through its eight tools (the ledger's
``assistant-link/README.md``, ``dev@a6ba639``; what they really hand back is
kept in ``tests/ledger/samples/``, 2026-11-25). It turns this program's
shapes into the ledger's arguments and the ledger's answers back into this
program's shapes. Every call goes through a started ``LedgerLink`` (or
anything that answers ``call`` the same way); it reads no environment
variable and no clock: the model's name and today's date are handed in.

What it turns, and how (68B2, part 13):

- Assets are named by the ledger's internal identifier. Whenever one is
  needed the ledger's list is asked for, and the code turned into it; a
  code two assets share is never picked from (``HAND_SAME_CODE``).
- Recording sends the day, the time to the minute and the time zone's
  name; a trade known only to its day sends the day alone, which the
  ledger takes (sample propose-add-date-only). A time with seconds that
  are not 0 is not sent; neither is a trade whose money differs from the
  asset's own (the ledger then needs a rate this program does not ask
  for), nor one with no time zone. Each is a
  failed check of this program's own (``HAND_...``), and the others go on.
  A fee of 0 is taken in the money traded. An empty platform or note is
  sent as ``null``. At most ``MOST_PER_CALL`` trades go in one call; when
  a later call fails after an earlier one was taken, the trades taken are
  handed back, and the rest are failed checks: one that timed out "may
  already have reached the ledger" (``HAND_MAY_HAVE_ARRIVED``), never sent
  again.
- A change sends the whole trade after it, with the write side's names.
  The time is left out unless it changed; the platform, the note and the
  rate are copied from the trade as last listed, unless they changed. A
  trade not listed in this session is not changed.
- Trades are listed page by page (fifty a page). When the ledger says it
  changed in between, the listing starts again from the first page, at
  most ``MOST_RESTARTS`` times; two runs are never mixed. At most
  ``MOST_TRADES_LISTED`` of the latest are kept, oldest first.
- The sums of all time run from ``ALL_TIME_START`` to today. The ledger's
  sums cannot be narrowed to one asset: for one asset, what its buys paid
  and its sells brought in is added up here, in exact decimals, from the
  money each listed trade moved (``cashSpentOrReceived``), one money apart
  from another, leaving out trades dated after today; one that the ledger
  could not work out leaves the sum not worked out, with its reason. Its
  profit or loss is the ledger's own row for that asset.
- Market prices are read from the holdings (``get_positions``), sold-out
  ones included, since an asset sold out still has one. Each is matched to
  its asset by the ledger's identifier and named by that asset's code; a
  code two assets share gives no market price, since neither is picked.
- Holdings that are sold out (quantity 0) are left out. No cash balance is
  ever handed back, and none is worked out from trades: a holding whose
  asset the ledger lists as cash ("currency") is left out too, whatever
  the ledger's holdings come to hold.
- What the user said and the model's name are measured before anything is
  sent, as the ledger measures them: words longer than
  ``SOURCE_TEXT_MOST`` or a name longer than ``MODEL_NAME_MOST`` send
  nothing; each trade is a failed check of this program's own
  (``HAND_SAID_TOO_LONG``, ``HAND_MODEL_NAME_TOO_LONG``), never cut short.
- Words the ledger kept that are not the user's (a trade recorded on the
  ledger's own page holds "Structured ledger entry: ...") are not words of
  the user's: such a trade holds none (``raw_text`` is ``None``).

How it fails (part 14), by two named tables that between them hold every
code of the ledger's README: ``CALL_FAILURES``, for a call the ledger
refuses whole, each to a ``LedgerErrorKind``; and ``TRADE_REFUSALS``, for
one trade of a proposal turned down, which is a failed check, never a
failure. A link that cannot be reached, or is gone, is ``UNREACHABLE``;
one that does not answer in time is ``TIMED_OUT``, and a proposal is then
never sent again. A status word this program does not know is a failure
of its own (``HAND_STATUS_UNKNOWN``), said in a plain sentence. The ledger's own
sentence is carried as it came, in the language of its page.

Names defined here: ``ToolCaller``, ``LinkLedger``, ``CALL_FAILURES``,
``TRADE_REFUSALS``, ``Refusal``, ``codes_on_no_table``, ``MOST_PER_CALL``, ``MOST_RESTARTS``,
``ALL_TIME_START``, ``WORDS_NOT_THE_USERS``, ``SOURCE_TEXT_MOST``, ``MODEL_NAME_MOST``.
"""

from __future__ import annotations

import enum
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ledger_hand.core.ledger_limits import text_length
from ledger_hand.core.ledger_records import (
    MOST_TRADES_LISTED,
    Asset,
    AssetKind,
    AssetRealized,
    CurrencyTotals,
    Figure,
    LedgerTrade,
    MarketPrice,
    MoneyAmount,
    NotWorkedOut,
    PeriodRequest,
    PeriodSummary,
    Position,
    Pricing,
    TradeFacts,
    TradeFilter,
    TradeList,
)
from ledger_hand.core.ledger_table import same_code_words, same_codes
from ledger_hand.core.proposals import (
    TARGET_NOT_FOUND,
    CheckOutcome,
    ProposalResult,
    ProposalState,
    ProposalStatus,
    TradeCheck,
)
from ledger_hand.core.trade import Side
from ledger_hand.ledger.link_client import AnswerKind, ToolAnswer
from ledger_hand.ledger.link_failures import LedgerLinkError, LinkFailure
from ledger_hand.ports import LedgerError, LedgerErrorKind

# The ledger takes at most ten trades in one call to record ("TOO_MANY_TRADES").
MOST_PER_CALL = 10
# How many times a listing starts again when the ledger changed under it.
MOST_RESTARTS = 3
# The first day of "all time": the ledger checks only that a day is real,
# and this one was tried on 2026-11-25 (sample period-summary-all-time).
ALL_TIME_START = date(1970, 1, 1)
# The longest words of the user and model name the ledger takes with a
# proposal, in its own characters (its README, "sourceText" and "modelName").
SOURCE_TEXT_MOST = 16_384
MODEL_NAME_MOST = 128
# The start of the words the ledger keeps for a trade recorded on its own
# page: its own machine text, never what the user said (68C, note 7).
WORDS_NOT_THE_USERS = "Structured ledger entry:"

_COST_NOT_EXACT = "The ledger marks this cost as not exact: a fee was paid in another asset."
_NO_PROFIT_GIVEN = "The ledger gave no profit or loss for this sell."
_NOT_ADDED = "The ledger could not add this up."
_NOT_SPLIT = "The ledger does not split one asset's profit or loss into sells and transfers."
_TOO_MANY = (
    f"More than {MOST_TRADES_LISTED} trades of this asset fall in these days, so their "
    "money was not added up here."
)


class ToolCaller(Protocol):
    """Anything that calls one of the ledger's tools and hands back its answer as it came."""

    def call(self, name: str, arguments: Mapping[str, Any]) -> ToolAnswer:
        """The tool ``name`` with ``arguments``; a result or the ledger's error."""
        ...


# --- the two tables ------------------------------------------------------------

_U = LedgerErrorKind.UNREACHABLE
_O = LedgerErrorKind.OTHER

CALL_FAILURES: Mapping[str, LedgerErrorKind] = MappingProxyType(
    {
        # The page or the link: nothing to talk to (README, "From: bridge", "tool").
        "LEDGER_PAGE_NOT_CONNECTED": _U,
        "LEDGER_PAGE_DISCONNECTED": _U,
        "LEDGER_NOT_READY": _U,
        "LEDGER_PAGE_TIMEOUT": LedgerErrorKind.TIMED_OUT,
        "LEDGER_PAGE_REPLY_INVALID": _O,
        # The call itself.
        "INVALID_ARGUMENTS": _O,
        "UNKNOWN_TOOL": _O,
        "TOO_MANY_TRADES": _O,
        "UNEXPECTED_PROGRAM_ERROR": _O,
        # Reading.
        "INVALID_DATE": _O,
        "START_DATE_AFTER_END_DATE": _O,
        "ASSET_NOT_FOUND": LedgerErrorKind.UNKNOWN_ASSET,
        "ASSET_IS_CURRENCY": LedgerErrorKind.ASSET_IS_CURRENCY,
        "INVALID_PAGE_TOKEN": _O,
        "LEDGER_CHANGED_START_FROM_FIRST_PAGE": _O,
        "LEDGER_RECORDS_CONTRADICT": _O,
        # Proposals, as a whole call.
        "PROPOSAL_PROPOSER_INVALID": _O,
        "PROPOSAL_NOT_FOUND": LedgerErrorKind.RESULT_UNKNOWN,
    }
)


class Refusal(enum.Enum):
    """What one trade turned down by the ledger means for what is said next."""

    TARGET_GONE = "the trade to change or delete is no longer in the ledger"
    TRY_LATER = "the ledger could not take it now; it may take it later"
    TURNED_DOWN = "the ledger's check turned it down"


_G = Refusal.TARGET_GONE
_L = Refusal.TRY_LATER
_D = Refusal.TURNED_DOWN

TRADE_REFUSALS: Mapping[str, Refusal] = MappingProxyType(
    {
        "INVALID_ARGUMENTS": _D,
        "ASSET_NOT_FOUND": _D,
        "PROPOSAL_PROPOSER_INVALID": _D,
        "PROPOSAL_LIST_FULL": _L,
        "PROPOSAL_ID_UNAVAILABLE": _L,
        TARGET_NOT_FOUND: _G,
        "PROPOSAL_TARGET_ALREADY_PENDING": _L,
        "PROPOSAL_TARGET_CHANGED": _D,
        "PROPOSAL_NO_CHANGE": _D,
        "PROPOSAL_NOT_PENDING": _D,
        "PROPOSAL_TIME_INVALID": _D,
        "PROPOSAL_TIME_ZONE_MISSING": _D,
        "PROPOSAL_TIME_ZONE_WITHOUT_TIME": _D,
        "PROPOSAL_TIME_ZONE_UNKNOWN": _D,
        "PROPOSAL_TIME_NONEXISTENT": _D,
        "PROPOSAL_TIME_AMBIGUOUS": _D,
        "INVALID_DECIMAL": _D,
        "VALUE_MUST_BE_POSITIVE": _D,
        "FEE_MUST_BE_NON_NEGATIVE": _D,
        "ASSET_FEE_MUST_BE_LESS_THAN_QUANTITY": _D,
        "TOTAL_VALUE_MISMATCH": _D,
        "INSUFFICIENT_HOLDINGS": _D,
        "CURRENCY_MISMATCH": _D,
        "FEE_CURRENCY_MISMATCH": _D,
        "FUTURE_FACT": _D,
        "TRADE_UPDATE_BREAKS_LEDGER_TIMELINE": _D,
        "TRADE_REMOVAL_BREAKS_LEDGER_TIMELINE": _D,
        "TRADE_ID_GENERATION_EXHAUSTED": _L,
        "TRADE_DEPENDENCY_FAILURE": _L,
    }
)

_README_CODE = re.compile(r"^\| `([A-Z_]+)` \|", re.MULTILINE)


def codes_on_no_table(readme: str) -> list[str]:
    """The codes of the error table in the ledger's README that neither table holds.

    ``readme`` is the text of ``assistant-link/README.md``; the table is the
    one under its heading "Error codes". The ledger tier runs this against
    the ledger itself, so a code the ledger adds cannot go unsorted.
    """
    _, found, table = readme.partition("## Error codes")
    if not found:
        return ["(the README has no heading 'Error codes')"]
    codes = _README_CODE.findall(table)
    if not codes:
        return ["(the README's error table holds no code)"]
    return [code for code in codes if code not in CALL_FAILURES and code not in TRADE_REFUSALS]


# Link failures that mean the answer may still come, or may have been taken.
_LINK_TIMED_OUT = frozenset({LinkFailure.TIMED_OUT})
_LINK_ODD = frozenset({LinkFailure.REPLY_NOT_JSON, LinkFailure.REPLY_UNEXPECTED})
_RESTART = frozenset({"LEDGER_CHANGED_START_FROM_FIRST_PAGE", "INVALID_PAGE_TOKEN"})

_KINDS = {"crypto": AssetKind.CRYPTO, "stock": AssetKind.STOCK, "currency": AssetKind.CASH}


class LinkLedger:
    """The ledger the person keeps, reached through its assistant link."""

    def __init__(self, link: ToolCaller, *, model_name: str, today: Callable[[], date]) -> None:
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("the model's name is text that is not blank")
        self._link = link
        self._model = model_name
        self._today = today
        # The trades as last listed, as the ledger wrote them, by their identifier.
        self._rows: dict[str, Mapping[str, Any]] = {}

    def __repr__(self) -> str:
        return f"LinkLedger(model={self._model!r})"

    # --- reading ----------------------------------------------------------------

    def list_assets(self) -> tuple[Asset, ...]:
        return tuple(_asset(row) for row in self._raw_assets())

    def list_trades(self, trade_filter: TradeFilter) -> TradeList:
        arguments: dict[str, Any] = _days(trade_filter.first_day, trade_filter.last_day)
        if trade_filter.asset is not None:
            arguments["assetId"] = self._id_of(trade_filter.asset, self._raw_assets())
        if trade_filter.side is not None:
            arguments["side"] = trade_filter.side.value
        rows, cut = self._listed(arguments)
        return TradeList(trades=tuple(_trade(row) for row in rows), cut=cut)

    def period_summary(self, request: PeriodRequest) -> PeriodSummary:
        first = request.first_day or ALL_TIME_START
        last = request.last_day or self._today()
        answer = self._answer(
            "get_period_summary", {"startDate": first.isoformat(), "endDate": last.isoformat()}
        )
        groups = _list(answer, "currencyGroups")
        if request.asset is None:
            return PeriodSummary(request=request, by_currency=tuple(map(_totals, groups)))
        return self._one_asset(request, first, last, groups)

    def positions(self) -> tuple[Position, ...]:
        answer = self._answer("get_positions", {})
        cash = {str(row.get("assetId")) for row in self._raw_assets() if _is_cash(row)}
        return tuple(
            _position(row)
            for row in _list(answer, "positions")
            if _decimal(row["quantity"]) and str(row.get("assetId")) not in cash
        )

    def market_prices(self) -> tuple[MarketPrice, ...]:
        answer = self._answer("get_positions", {})
        assets = self._raw_assets()
        shared = {same.code for same in same_codes([_asset(row) for row in assets])}
        codes = {str(row.get("assetId")): str(row.get("assetCode")) for row in assets}
        found = (_market_price(row, codes, shared) for row in _list(answer, "positions"))
        return tuple(market for market in found if market is not None)

    # --- proposing --------------------------------------------------------------

    def propose_add(self, trades: tuple[TradeFacts, ...], said: str) -> ProposalResult:
        if not trades:
            raise ValueError("a proposal to record holds at least one trade")
        too_long = self._too_long(said)
        if too_long is not None:
            return ProposalResult(checks=tuple(too_long for _ in trades))
        assets = self._raw_assets()
        checks: list[TradeCheck | None] = []
        sendable: list[tuple[int, dict[str, Any]]] = []
        for index, facts in enumerate(trades):
            written = _written(facts, assets, row=None)
            if isinstance(written, TradeCheck):
                checks.append(written)
            else:
                checks.append(None)
                sendable.append((index, written))
        for start in range(0, len(sendable), MOST_PER_CALL):
            batch = sendable[start : start + MOST_PER_CALL]
            try:
                results = self._added(batch, said)
            except LedgerError as error:
                if start == 0:
                    raise
                # An earlier call left proposals waiting: they are handed back,
                # and the rest said as the failure leaves them (68B3, addition 1).
                for index, _ in sendable[start:]:
                    checks[index] = _after_earlier(error)
                break
            for (index, _), result in zip(batch, results, strict=True):
                checks[index] = _check(result)
        return ProposalResult(checks=tuple(check for check in checks if check is not None))

    def _added(self, batch: Sequence[tuple[int, dict[str, Any]]], said: str) -> list[Any]:
        """The ledger's result for each trade of one call to record ``batch``."""
        arguments = {"trades": [one for _, one in batch], **self._who(said)}
        results = _list(self._answer("propose_trade_add", arguments), "results")
        if len(results) != len(batch):
            raise LedgerError(
                _O,
                "HAND_ANSWER_UNEXPECTED",
                "The ledger answered for another number of trades.",
            )
        return results

    def propose_update(self, trade_id: str, facts: TradeFacts, said: str) -> ProposalResult:
        too_long = self._too_long(said)
        if too_long is not None:
            return ProposalResult(checks=(too_long,))
        row = self._rows.get(trade_id)
        if row is None:
            return ProposalResult(
                checks=(
                    _refused(
                        "HAND_TRADE_NOT_LISTED",
                        "This trade was not listed in this session, so it was not changed.",
                    ),
                )
            )
        written = _written(facts, self._raw_assets(), row=row)
        if isinstance(written, TradeCheck):
            return ProposalResult(checks=(written,))
        arguments = {"tradeId": trade_id, "trade": written, **self._who(said)}
        return self._one(self._answer("propose_trade_update", arguments))

    def propose_delete(self, trade_id: str, said: str) -> ProposalResult:
        too_long = self._too_long(said)
        if too_long is not None:
            return ProposalResult(checks=(too_long,))
        arguments = {"tradeId": trade_id, **self._who(said)}
        return self._one(self._answer("propose_trade_delete", arguments))

    def proposal_status(self, proposal_id: str) -> ProposalState:
        answer = self._answer("get_proposal_status", {"proposalId": proposal_id})
        word = answer.get("status")
        try:
            status = ProposalStatus(word)
        except ValueError:
            raise LedgerError(
                _O,
                "HAND_STATUS_UNKNOWN",
                f"The ledger answered a status this program does not know ({word!r}), so "
                "where this proposal stands cannot be said here: please look at the ledger.",
            ) from None
        saved = status is ProposalStatus.SAVED
        void = status is ProposalStatus.VOID
        return ProposalState(
            proposal_id=proposal_id,
            status=status,
            trade_id=_text(answer.get("tradeId")) if saved else None,
            reason=_text(answer.get("reason")) if void else None,
            message=_text(answer.get("message")) if void else None,
        )

    # --- inside -----------------------------------------------------------------

    def _too_long(self, said: str) -> TradeCheck | None:
        """A failed check when ``said`` or the model's name is longer than the ledger takes."""
        if text_length(said) > SOURCE_TEXT_MOST:
            return _refused(
                "HAND_SAID_TOO_LONG",
                f"What you said is longer than the {SOURCE_TEXT_MOST} characters the ledger "
                "keeps with a proposal, so nothing was sent. Please say it in shorter words.",
            )
        if text_length(self._model) > MODEL_NAME_MOST:
            return _refused(
                "HAND_MODEL_NAME_TOO_LONG",
                f"The model's name is longer than the {MODEL_NAME_MOST} characters the ledger "
                "takes, so nothing was sent.",
            )
        return None

    def _who(self, said: str) -> dict[str, Any]:
        return {"sourceText": said if said.strip() else None, "modelName": self._model}

    def _answer(self, name: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """The ledger's result for one call, or its refusal as a ``LedgerError``."""
        try:
            answer = self._link.call(name, arguments)
        except LedgerLinkError as error:
            raise _link_failure(error) from error
        content = answer.content
        if answer.kind is AnswerKind.ERROR:
            code = str(content.get("code", "UNEXPECTED_PROGRAM_ERROR"))
            message = _text(content.get("message")) or "The ledger gave no reason."
            raise LedgerError(CALL_FAILURES.get(code, _O), code, message)
        return content

    def _raw_assets(self) -> list[Mapping[str, Any]]:
        return _list(self._answer("list_assets", {}), "assets")

    def _id_of(self, code: str, assets: Sequence[Mapping[str, Any]]) -> str:
        found = _found(code, assets)
        if isinstance(found, str):
            return found
        raise LedgerError(found[0], found[1], found[2])

    def _listed(self, arguments: Mapping[str, Any]) -> tuple[list[Mapping[str, Any]], bool]:
        """Every page, oldest first, the latest ``MOST_TRADES_LISTED`` and whether more were."""
        for _ in range(MOST_RESTARTS + 1):
            rows: list[Mapping[str, Any]] = []
            token: str | None = None
            try:
                while True:
                    asked = dict(arguments)
                    if token is not None:
                        asked["pageToken"] = token
                    page = self._answer("list_trades", asked)
                    rows.extend(_list(page, "trades"))
                    token = _text(page.get("nextPageToken"))
                    if token is None or len(rows) > MOST_TRADES_LISTED:
                        break
            except LedgerError as error:
                if error.code in _RESTART:
                    continue
                raise
            cut = len(rows) > MOST_TRADES_LISTED
            kept = list(reversed(rows[:MOST_TRADES_LISTED]))
            for row in kept:
                self._rows[str(row["tradeId"])] = row
            return kept, cut
        raise LedgerError(
            _O,
            "LEDGER_CHANGED_START_FROM_FIRST_PAGE",
            f"The ledger kept changing while its trades were listed ({MOST_RESTARTS} tries).",
        )

    def _one_asset(
        self,
        request: PeriodRequest,
        first: date,
        last: date,
        groups: Sequence[Mapping[str, Any]],
    ) -> PeriodSummary:
        """The sums of one asset: its trades' money added here; its profit, the ledger's row."""
        assert request.asset is not None
        arguments = {
            "startDate": first.isoformat(),
            "endDate": last.isoformat(),
            "assetId": self._id_of(request.asset, self._raw_assets()),
        }
        rows, cut = self._listed(arguments)
        sums: dict[str, _AssetGroup] = {}
        for row in rows:
            if row.get("isDatedAfterToday") is True:
                continue
            group = sums.setdefault(str(row["tradeCurrencyCode"]), _AssetGroup())
            group.add(row, cut=cut)
        for group_row in groups:
            code = str(group_row["currencyCode"])
            for by_asset in _list(group_row, "realizedProfitAndLossByAsset"):
                if by_asset.get("assetCode") == request.asset:
                    sums.setdefault(code, _AssetGroup()).realized = by_asset
        return PeriodSummary(
            request=request,
            by_currency=tuple(sums[code].totals(code, request.asset) for code in sorted(sums)),
        )

    def _one(self, answer: Mapping[str, Any]) -> ProposalResult:
        results = _list(answer, "results")
        return ProposalResult(checks=tuple(_check(result) for result in results))


# --- turning the ledger's answers into this program's shapes --------------------


def _list(answer: Mapping[str, Any], name: str) -> list[Mapping[str, Any]]:
    found = answer.get(name)
    if not isinstance(found, list) or not all(isinstance(one, Mapping) for one in found):
        raise LedgerError(_O, "HAND_ANSWER_UNEXPECTED", f"The ledger's answer has no list {name}.")
    return found


def _is_cash(row: Mapping[str, Any]) -> bool:
    return _KINDS.get(str(row.get("assetKind"))) is AssetKind.CASH


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        raise LedgerError(
            _O, "HAND_ANSWER_UNEXPECTED", f"The ledger gave {value!r} where a number was due."
        ) from None


def _reasons(value: object, fallback: str) -> str:
    if isinstance(value, list):
        said = [one for one in value if isinstance(one, str) and one.strip()]
        if said:
            return "; ".join(said)
    if isinstance(value, str) and value.strip():
        return value
    return fallback


def _money(code: str, value: object, reasons: object, fallback: str = _NOT_ADDED) -> Figure:
    if value is None:
        return NotWorkedOut(reason=_reasons(reasons, fallback))
    return MoneyAmount(currency=code, amount=_decimal(value))


def _asset(row: Mapping[str, Any]) -> Asset:
    return Asset(
        id=str(row["assetId"]),
        code=str(row["assetCode"]),
        name=str(row["assetName"]),
        kind=_KINDS.get(str(row["assetKind"]), AssetKind.CRYPTO),
        pricing=Pricing.CAN_PRICE
        if row.get("canBeTradeCurrency") is True
        else Pricing.CANNOT_PRICE,
        price_currency=_text(row.get("priceCurrencyCode")),
    )


def _moment(row: Mapping[str, Any]) -> tuple[datetime, bool, str | None]:
    """When a listed trade happened, whether only its day is known, and its zone's name."""
    written = str(row["occurredAt"])
    zone = _text(row.get("occurredTimeZone"))
    if row.get("timePrecision") == "day" or len(written) == len("2026-11-14"):
        day = date.fromisoformat(written[:10])
        start = datetime(day.year, day.month, day.day)
        tz = _zone(zone)
        midnight = (
            start.replace(tzinfo=tz) if tz is not None else start.replace(tzinfo=timezone.utc)
        )
        # The offset the zone has at the start of that day, held fixed.
        offset = midnight.utcoffset()
        assert offset is not None
        return start.replace(tzinfo=timezone(offset)), True, zone
    return datetime.fromisoformat(written), False, zone


def _zone(name: str | None) -> ZoneInfo | None:
    if name is None:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def _words(row: Mapping[str, Any]) -> str | None:
    """The user's words a trade was recorded from; none for the ledger's own machine text."""
    words = _text(row.get("rawText"))
    if words is None or words.startswith(WORDS_NOT_THE_USERS):
        return None
    return words


def _trade(row: Mapping[str, Any]) -> LedgerTrade:
    occurred, date_only, zone = _moment(row)
    side = Side(str(row["side"]))
    rate = row.get("costRate")
    facts = TradeFacts(
        occurred=occurred,
        side=side,
        asset=str(row["assetCode"]),
        quantity=_decimal(row["quantity"]),
        price=_decimal(row["price"]),
        total=_decimal(row["tradeAmount"]),
        quote=str(row["tradeCurrencyCode"]),
        fee=_decimal(row["fee"]),
        fee_asset=str(row["feeAssetCode"]),
        platform=_text(row.get("platform")) or "",
        note=_text(row.get("note")) or "",
        raw_text=_words(row),
        zone=zone,
        date_only=date_only,
        cost_rate=_decimal(rate) if rate is not None else None,
    )
    realized: Figure | None = None
    unreliable: str | None = None
    if side is Side.SELL:
        value = row.get("realizedProfitAndLoss")
        reason = _text(row.get("realizedProfitAndLossUnreliableReason"))
        if value is None:
            realized = NotWorkedOut(reason=reason or _NO_PROFIT_GIVEN)
        else:
            code = _text(row.get("realizedProfitAndLossCurrencyCode")) or facts.quote
            realized = MoneyAmount(currency=code, amount=_decimal(value))
            if row.get("realizedProfitAndLossIsReliable") is False:
                unreliable = reason or "The ledger marks this figure as not exact."
    return LedgerTrade(
        id=str(row["tradeId"]),
        facts=facts,
        realized=realized,
        realized_unreliable=unreliable,
        dated_after_today=row.get("isDatedAfterToday") is True,
    )


def _fees(rows: Iterable[Mapping[str, Any]]) -> tuple[MoneyAmount, ...]:
    added: dict[str, Decimal] = {}
    for row in rows:
        code = str(row["feeAssetCode"])
        added[code] = added.get(code, Decimal(0)) + _decimal(row["amount"])
    return tuple(MoneyAmount(currency=code, amount=added[code]) for code in sorted(added))


def _totals(group: Mapping[str, Any]) -> CurrencyTotals:
    code = str(group["currencyCode"])
    missing = group.get("realizedProfitAndLossMissingReasons")
    return CurrencyTotals(
        currency=code,
        buy_count=int(group["buyCount"]),
        sell_count=int(group["sellCount"]),
        spent=_money(code, group.get("buyTotalSpent"), group.get("buyTotalSpentMissingReasons")),
        received=_money(
            code, group.get("sellTotalReceived"), group.get("sellTotalReceivedMissingReasons")
        ),
        fees=_fees(_list(group, "feesPaid")),
        realized=_money(code, group.get("realizedProfitAndLoss"), missing),
        realized_from_sells=_money(code, group.get("realizedProfitAndLossFromSells"), missing),
        realized_from_transfers=_money(
            code, group.get("realizedProfitAndLossFromAssetTransfers"), missing
        ),
        by_asset=tuple(
            AssetRealized(
                asset=str(row["assetCode"]),
                realized=MoneyAmount(currency=code, amount=_decimal(row["realizedProfitAndLoss"])),
                unreliable=None
                if row.get("isReliable") is not False
                else _text(row.get("unreliableReason")) or "The ledger marks this as not exact.",
            )
            for row in _list(group, "realizedProfitAndLossByAsset")
        ),
    )


class _AssetGroup:
    """One money's trades of one asset, added up here: the ledger's sums cannot be narrowed."""

    def __init__(self) -> None:
        self.buys = 0
        self.sells = 0
        self.spent: Decimal | str = Decimal(0)
        self.received: Decimal | str = Decimal(0)
        self.fees: list[Mapping[str, Any]] = []
        self.realized: Mapping[str, Any] | None = None

    def add(self, row: Mapping[str, Any], *, cut: bool) -> None:
        moved = row.get("cashSpentOrReceived")
        why = _text(row.get("cashSpentOrReceivedMissingReason")) or _NOT_ADDED
        if cut:
            why = _TOO_MANY
        buy = row.get("side") == "buy"
        if buy:
            self.buys += 1
        else:
            self.sells += 1
        current = self.spent if buy else self.received
        if isinstance(current, Decimal):
            current = why if moved is None or cut else current + _decimal(moved)
        if buy:
            self.spent = current
        else:
            self.received = current
        self.fees.append({"feeAssetCode": row["feeAssetCode"], "amount": row["fee"]})

    def totals(self, code: str, asset: str) -> CurrencyTotals:
        def figure(value: Decimal | str) -> Figure:
            if isinstance(value, Decimal):
                return MoneyAmount(currency=code, amount=value)
            return NotWorkedOut(reason=value)

        zero = MoneyAmount(currency=code, amount=Decimal(0))
        rows: tuple[AssetRealized, ...] = ()
        realized: Figure = zero
        from_sells: Figure = zero
        transfers: Figure = zero
        if self.realized is not None:
            realized = MoneyAmount(
                currency=code, amount=_decimal(self.realized["realizedProfitAndLoss"])
            )
            from_sells = NotWorkedOut(reason=_NOT_SPLIT)
            transfers = NotWorkedOut(reason=_NOT_SPLIT)
            unreliable = None
            if self.realized.get("isReliable") is False:
                unreliable = _text(self.realized.get("unreliableReason")) or "Not exact."
            rows = (AssetRealized(asset=asset, realized=realized, unreliable=unreliable),)
        return CurrencyTotals(
            currency=code,
            buy_count=self.buys,
            sell_count=self.sells,
            spent=figure(self.spent),
            received=figure(self.received),
            fees=_fees(self.fees),
            realized=realized,
            realized_from_sells=from_sells,
            realized_from_transfers=transfers,
            by_asset=rows,
        )


def _position(row: Mapping[str, Any]) -> Position:
    code = str(row["valueCurrencyCode"])
    return Position(
        asset=str(row["assetCode"]),
        currency=code,
        quantity=_decimal(row["quantity"]),
        cost=MoneyAmount(currency=code, amount=_decimal(row["remainingCost"])),
        cost_unreliable=None if row.get("costIsReliable") is not False else _COST_NOT_EXACT,
        unrealized=_money(
            code,
            row.get("unrealizedProfitAndLoss"),
            row.get("unrealizedProfitAndLossMissingReasons"),
            "The ledger gave no profit or loss on paper.",
        ),
    )


def _market_price(
    row: Mapping[str, Any], codes: Mapping[str, str], shared: set[str]
) -> MarketPrice | None:
    """The market price of one holding's asset, by its identifier; ``None`` when it has none.

    A code two assets share gives none: neither is picked (85B, 2026-11-25).
    """
    price = row.get("marketPrice")
    if not isinstance(price, Mapping):
        return None
    code = codes.get(str(row.get("assetId")))
    money = _text(price.get("priceCurrencyCode"))
    if code is None or code in shared or money is None:
        return None
    return MarketPrice(
        asset=code,
        price=MoneyAmount(currency=money, amount=_decimal(price.get("price"))),
        day=_price_day(price.get("priceDate")),
    )


def _price_day(value: object) -> date | None:
    """The day of a market price, written as a day or a moment; ``None`` when unreadable."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _check(result: Mapping[str, Any]) -> TradeCheck:
    if result.get("ok") is True:
        return TradeCheck(outcome=CheckOutcome.PASSED, proposal_id=str(result["proposalId"]))
    error = result.get("error")
    error = error if isinstance(error, Mapping) else {}
    code = _text(error.get("code")) or "UNEXPECTED_PROGRAM_ERROR"
    message = _text(error.get("message")) or "The ledger gave no reason."
    return _refused(code, message)


def _after_earlier(error: LedgerError) -> TradeCheck:
    """A trade of a later call that failed, when an earlier call's trades are waiting."""
    if error.kind is LedgerErrorKind.TIMED_OUT:
        return _refused(
            "HAND_MAY_HAVE_ARRIVED",
            "The ledger did not answer in time for this trade, so it may already have "
            "reached the ledger: please look at the ledger's pending list. It was not "
            "sent again.",
        )
    return _refused(error.code, f"It was not sent: {error.message}")


def _refused(code: str, message: str) -> TradeCheck:
    return TradeCheck(outcome=CheckOutcome.FAILED, code=code, message=message)


def _link_failure(error: LedgerLinkError) -> LedgerError:
    if error.failure in _LINK_TIMED_OUT:
        kind = LedgerErrorKind.TIMED_OUT
    elif error.failure in _LINK_ODD:
        kind = _O
    else:
        kind = _U
    return LedgerError(kind, f"LINK_{error.failure.name}", str(error))


def _days(first: date | None, last: date | None) -> dict[str, Any]:
    days: dict[str, Any] = {}
    if first is not None:
        days["startDate"] = first.isoformat()
    if last is not None:
        days["endDate"] = last.isoformat()
    return days


# --- turning this program's trade into the ledger's write side -------------------


def _found(
    code: str, assets: Sequence[Mapping[str, Any]]
) -> str | tuple[LedgerErrorKind, str, str]:
    """The identifier of the asset ``code``; or the failure: none has it, or two share it."""
    matching = [row for row in assets if row.get("assetCode") == code]
    if len(matching) == 1:
        return str(matching[0]["assetId"])
    if not matching:
        return (
            LedgerErrorKind.UNKNOWN_ASSET,
            "ASSET_NOT_FOUND",
            f"The ledger has no asset {code}.",
        )
    (shared,) = (same for same in same_codes([_asset(row) for row in assets]) if same.code == code)
    return (_O, "HAND_SAME_CODE", same_code_words(shared))


def _written(
    facts: TradeFacts, assets: Sequence[Mapping[str, Any]], *, row: Mapping[str, Any] | None
) -> dict[str, Any] | TradeCheck:
    """``facts`` with the write side's names, or this program's own reason not to send it.

    ``row`` is the trade as last listed, for a change: its identifiers, its
    time, platform, note and rate are kept where ``facts`` did not change them.
    """
    ids: dict[str, str] = {}
    # Each identifier to write, the code it stands for, and where a listed trade keeps both.
    for name, code, listed_code, listed_id in (
        ("assetId", facts.asset, "assetCode", "assetId"),
        ("quoteAssetId", facts.quote, "tradeCurrencyCode", "tradeCurrencyAssetId"),
        (
            "feeAssetId",
            facts.quote if facts.fee == 0 else facts.fee_asset,
            "feeAssetCode",
            "feeAssetId",
        ),
    ):
        if row is not None and row.get(listed_code) == code:
            ids[name] = str(row[listed_id])
            continue
        found = _found(code, assets)
        if not isinstance(found, str):
            return _refused(found[1], found[2])
        ids[name] = found
    own = next((asset for asset in assets if str(asset.get("assetId")) == ids["assetId"]), None)
    own_money = _text(own.get("priceCurrencyAssetId")) if own is not None else None
    rate = facts.cost_rate
    if row is not None and _same_rate(row, rate):
        rate_text = row.get("costRate")
    else:
        rate_text = format(rate, "f") if rate is not None else None
    if own_money is not None and own_money != ids["quoteAssetId"] and rate_text is None:
        return _refused(
            "HAND_NEEDS_COST_RATE",
            f"{facts.asset} is priced in another money than {facts.quote}; the ledger needs the "
            "rate between the two, which this program does not ask for yet, so it was not sent.",
        )
    written: dict[str, Any] = {
        "type": facts.side.value,
        "assetId": ids["assetId"],
        "quantity": format(facts.quantity, "f"),
        "price": format(facts.price, "f"),
        "totalValue": format(facts.total, "f"),
        "quoteAssetId": ids["quoteAssetId"],
        "fee": format(facts.fee, "f"),
        "feeAssetId": ids["feeAssetId"],
        "costRate": rate_text,
        "platform": _kept_text(facts.platform, row, "platform"),
        "note": _kept_text(facts.note, row, "note"),
    }
    if row is not None and _same_time(facts, row):
        return written
    time = _time(facts)
    if isinstance(time, TradeCheck):
        return time
    written.update(time)
    return written


def _same_rate(row: Mapping[str, Any], rate: Decimal | None) -> bool:
    listed = row.get("costRate")
    if listed is None:
        return rate is None
    return rate is not None and _decimal(listed) == rate


def _kept_text(now: str, row: Mapping[str, Any] | None, name: str) -> str | None:
    """The platform or note to write: the listed one unless it changed; empty is ``null``."""
    if row is not None and now == (_text(row.get(name)) or ""):
        return row.get(name) if isinstance(row.get(name), str) else None
    return now if now.strip() else None


def _same_time(facts: TradeFacts, row: Mapping[str, Any]) -> bool:
    occurred, date_only, zone = _moment(row)
    return (facts.occurred, facts.date_only, facts.zone) == (occurred, date_only, zone)


def _time(facts: TradeFacts) -> dict[str, Any] | TradeCheck:
    """The day, the time to the minute and the zone's name, or the day alone for a trade
    known only to its day; or why they cannot be sent."""
    if facts.date_only:
        # The day alone: the ledger takes no time or zone without a time said.
        return {"occurredDate": facts.occurred.date().isoformat()}
    moment = facts.occurred
    if moment.second or moment.microsecond:
        return _refused(
            "HAND_TIME_HAS_SECONDS",
            "The ledger takes a time to the minute; this one has seconds, so it was not sent.",
        )
    if facts.zone is None or _zone(facts.zone) is None:
        return _refused(
            "HAND_NO_TIME_ZONE",
            "The time has no time zone the ledger knows, so it was not sent.",
        )
    local = moment.astimezone(ZoneInfo(facts.zone))
    if local.utcoffset() != moment.utcoffset():
        return _refused(
            "HAND_NO_TIME_ZONE",
            f"The time's offset is not that of {facts.zone} then, so it was not sent.",
        )
    return {
        "occurredDate": local.date().isoformat(),
        "occurredTime": local.strftime("%H:%M"),
        "occurredTimeZone": facts.zone,
    }
