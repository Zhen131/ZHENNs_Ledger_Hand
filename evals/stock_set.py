"""The sentences that record a share bought with dollars, their gold answers, and the judging.

The set, ``evals/sets/stocks.json``, holds sentences each said in a chat of
its own to the whole assistant, against the fake ledger's invented book (or,
where a sentence names ``usdt_only``, the same book with USD a money no
trade is priced in), at the set's fixed moment and zone. Each has a gold
answer, written before any run:

- ``send``: the trades that must reach the ledger as one proposal, in the
  order said: every figure as text, every asset and money by its ledger
  code, the moment in the set's zone, and the platform;
- ``ask``: nothing may be sent; the program must ask about the cell named
  (``fee``, ``pricing currency`` and so on);
- ``refuse``: nothing may be sent; the passage is stopped, or every trade
  is left out, for one of the reasons ``why`` names.

``judge`` compares what came of a sentence (``Outcome``) with its gold
answer, field by field and code by code, so "USD" and "USDT" are never the
same; it gives one of these (``Verdict``):

- ``RIGHT``: the trades sent are the gold ones, every field equal; or the
  question asked is the gold one and nothing was sent; or nothing was sent
  and the reason is one the gold allows;
- ``SILENTLY_WRONG``: a trade reached the ledger that is not one of the gold
  trades, field for field, or anything reached it where the gold sends
  nothing;
- ``NOT_DONE``: anything else: nothing was sent where the gold sends, only
  some of the gold trades were sent, another question was asked, or another
  reason was given. The program said why, so nothing is wrong unseen.

The pass lines (``passes``): no sentence ``SILENTLY_WRONG``; at least
``RIGHT_SHARE`` of all sentences ``RIGHT`` (the share the measures before
took; it was not measured).

Names defined here: ``STOCK_SET``, ``RIGHT_SHARE``, ``GoldTrade``,
``StockGold``, ``StockSentence``, ``StockSet``, ``load_stock_set``,
``Outcome``, ``Verdict``, ``judge``, ``passes`` and ``markdown``.
"""

from __future__ import annotations

import enum
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from ledger_hand.core.ledger_records import TradeFacts

STOCK_SET = Path(__file__).resolve().parent / "sets" / "stocks.json"
RIGHT_SHARE = Decimal("0.8")
SEND = "send"
ASK = "ask"
REFUSE = "refuse"
BOOKS = frozenset({"invented", "usdt_only"})
_EXPECTS = frozenset({SEND, ASK, REFUSE})


@dataclass(frozen=True)
class GoldTrade:
    """One trade the gold answer sends, every figure exact."""

    side: str
    asset: str
    quantity: Decimal
    price: Decimal
    total: Decimal
    quote: str
    fee: Decimal
    fee_asset: str
    occurred: datetime
    platform: str

    def matches(self, facts: TradeFacts) -> bool:
        """Whether the trade sent is this one, field for field."""
        return (
            facts.side.value == self.side
            and facts.asset == self.asset
            and facts.quantity == self.quantity
            and facts.price == self.price
            and facts.total == self.total
            and facts.quote == self.quote
            and facts.fee == self.fee
            and facts.fee_asset == self.fee_asset
            and facts.occurred == self.occurred
            and facts.platform == self.platform
        )


@dataclass(frozen=True)
class StockGold:
    expect: str
    trades: tuple[GoldTrade, ...] = ()
    ask: str | None = None
    why: frozenset[str] = frozenset()


@dataclass(frozen=True)
class StockSentence:
    id: str
    kind: str
    text: str
    gold: StockGold
    book: str = "invented"


@dataclass(frozen=True)
class StockSet:
    now: datetime
    zone: str
    sentences: tuple[StockSentence, ...]


def _trade(data: Mapping[str, str]) -> GoldTrade:
    occurred = datetime.fromisoformat(data["occurred"])
    if occurred.utcoffset() is None:
        raise ValueError("a gold moment carries its offset")
    return GoldTrade(
        side=data["side"],
        asset=data["asset"],
        quantity=Decimal(data["quantity"]),
        price=Decimal(data["price"]),
        total=Decimal(data["total"]),
        quote=data["quote"],
        fee=Decimal(data["fee"]),
        fee_asset=data["fee_asset"],
        occurred=occurred,
        platform=data["platform"],
    )


def _gold(data: Mapping[str, object]) -> StockGold:
    expect = str(data["expect"])
    if expect not in _EXPECTS:
        raise ValueError(f"unknown gold answer: {expect!r}")
    trades = data.get("trades", [])
    why = data.get("why", [])
    ask = data.get("ask")
    gold = StockGold(
        expect=expect,
        trades=tuple(_trade(one) for one in trades),  # type: ignore[attr-defined]
        ask=ask if isinstance(ask, str) else None,
        why=frozenset(str(one) for one in why),  # type: ignore[attr-defined]
    )
    if (expect == SEND) != bool(gold.trades):
        raise ValueError("only a send names trades, and it names one at least")
    if (expect == ASK) != (gold.ask is not None):
        raise ValueError("only an ask names the cell asked")
    if (expect == REFUSE) != bool(gold.why):
        raise ValueError("only a refusal names its reasons")
    return gold


def load_stock_set(path: Path = STOCK_SET) -> StockSet:
    """The set in ``path``; raises ``ValueError`` for a sentence or a gold answer out of shape."""
    data = json.loads(path.read_text(encoding="utf-8"))
    sentences = tuple(
        StockSentence(
            id=item["id"],
            kind=item["kind"],
            text=item["text"],
            gold=_gold(item["gold"]),
            book=item.get("book", "invented"),
        )
        for item in data["sentences"]
    )
    ids = [sentence.id for sentence in sentences]
    if len(set(ids)) != len(ids):
        raise ValueError("every sentence has an identifier of its own")
    if any(sentence.book not in BOOKS for sentence in sentences):
        raise ValueError(f"a book is one of {sorted(BOOKS)}")
    return StockSet(now=datetime.fromisoformat(data["now"]), zone=data["zone"], sentences=sentences)


@dataclass(frozen=True)
class Outcome:
    """What came of one sentence.

    ``sent`` are the trades that reached the ledger; ``asked`` the cell of
    the question left waiting, if one is; ``reasons`` why nothing (or not
    everything) was sent: the ending, and each trade left out.
    """

    sent: tuple[TradeFacts, ...] = ()
    asked: str | None = None
    reasons: frozenset[str] = frozenset()


class Verdict(enum.Enum):
    RIGHT = "right"
    SILENTLY_WRONG = "silently wrong"
    NOT_DONE = "not done"


def judge(gold: StockGold, outcome: Outcome) -> Verdict:
    """How one sentence went against its gold answer."""
    if gold.expect != SEND:
        if outcome.sent:
            return Verdict.SILENTLY_WRONG
        if gold.expect == ASK:
            return Verdict.RIGHT if outcome.asked == gold.ask else Verdict.NOT_DONE
        return (
            Verdict.RIGHT if outcome.reasons and outcome.reasons <= gold.why else Verdict.NOT_DONE
        )
    left = list(gold.trades)
    for facts in outcome.sent:
        match = next((one for one in left if one.matches(facts)), None)
        if match is None:
            return Verdict.SILENTLY_WRONG
        left.remove(match)
    if left:
        return Verdict.NOT_DONE
    sent_order = [one.asset for one in outcome.sent]
    return Verdict.RIGHT if sent_order == [one.asset for one in gold.trades] else Verdict.NOT_DONE


def passes(verdicts: Mapping[str, Verdict]) -> dict[str, bool]:
    """The two pass lines."""
    right = sum(verdict is Verdict.RIGHT for verdict in verdicts.values())
    return {
        "nothing silently wrong": all(
            verdict is not Verdict.SILENTLY_WRONG for verdict in verdicts.values()
        ),
        "at least 80% right": Decimal(right) >= RIGHT_SHARE * len(verdicts),
    }


def _gold_words(gold: StockGold) -> str:
    if gold.expect == ASK:
        return f"ask the {gold.ask}"
    if gold.expect == REFUSE:
        return "send nothing: " + " or ".join(sorted(gold.why))
    return "send " + "; ".join(
        f"{one.side} {one.quantity} {one.asset} at {one.price} {one.quote}, fee {one.fee} "
        f"{one.fee_asset}"
        for one in gold.trades
    )


def markdown(
    rows: Sequence[tuple[StockSentence, Outcome, Verdict, str]], head: Mapping[str, object]
) -> str:
    """The result as a Markdown section body: the pass lines, then one row a sentence."""
    verdicts = {sentence.id: verdict for sentence, _, verdict, _ in rows}
    right = sum(verdict is Verdict.RIGHT for verdict in verdicts.values())
    wrong = sum(verdict is Verdict.SILENTLY_WRONG for verdict in verdicts.values())
    lines = [
        f"Model `{head['model']}`, tools prompt `{head['prompt']}`: done right on {right} of "
        f"{len(rows)} sentences; silently wrong {wrong}.",
        "",
    ]
    for line, passed in passes(verdicts).items():
        lines.append(f"- {line}: {'passed' if passed else 'NOT passed'}")
    lines += [
        "",
        "| Sentence | Kind | Gold | What came of it | Verdict |",
        "| --- | --- | --- | --- | --- |",
    ]
    for sentence, _, verdict, came in rows:
        lines.append(
            f"| {sentence.id} | {sentence.kind} | {_gold_words(sentence.gold)} | {came} | "
            f"{verdict.value} |"
        )
    return "\n".join(lines)
