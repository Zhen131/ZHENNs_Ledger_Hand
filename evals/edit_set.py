"""The sentences that change or delete a trade, their gold answers, and how one is judged.

The set, ``evals/sets/edits.json``, holds sentences said each in a chat of
its own against the fake ledger's invented book, at the set's fixed moment
and zone. Each has a gold answer, written before any run:

- ``send``: a proposal must reach the ledger: a ``change`` or a ``delete``
  (``kind``) of the trade with the identifier ``trade``; for a change, the
  ``field`` and its new ``value`` as text. ``pick`` is there when more than
  one trade matches: the program must ask which, and the ruler answers
  with ``pick.answer``; the trade it names is ``trade``. ``choose`` is there
  when the change leaves quantity, price and total out of step: the
  program must ask which follows, and the ruler answers with that amount's
  name; ``amounts`` are then the quantity, price and total the proposal
  must hold.
- ``not_found``: the program must say no trade matches, and propose nothing.
- ``refuse``: the program must change nothing and say why itself.

``judge_edit`` compares what came of a sentence (``Outcome``) with its gold
answer and gives one of these (``Verdict``):

- ``RIGHT``: done as the gold says: the proposal sent is the gold one, the
  whole trade proposed being the ledger's trade with the gold value (and
  amounts) put in; or the program said what the gold says it should;
- ``SILENTLY_WRONG``: a proposal reached the ledger that is not the gold
  one, or one was sent where the program should first have asked which
  trade, or which amount follows, or where nothing should have been sent;
- ``NOT_DONE``: nothing was sent and the gold sends something, or the
  program asked where the gold does not ask, or said something else.

The pass lines (``passes``): no sentence ``SILENTLY_WRONG``; E1, E2 and E3
``RIGHT``; at least ``RIGHT_SHARE`` of all sentences ``RIGHT``. A sentence
and the ruler's answers after it count as one.

Names defined here: ``EDIT_SET``, ``RIGHT_SHARE``, ``FIRST_THREE``,
``EditGold``, ``EditSentence``, ``EditSet``, ``load_edit_set``, ``Outcome``,
``Verdict``, ``expected_trade``, ``judge_edit``, ``passes`` and
``markdown``.
"""

from __future__ import annotations

import dataclasses
import enum
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from ledger_hand.core.ledger_records import TradeFacts
from ledger_hand.core.trade import Side
from ledger_hand.ledger.invented_book import INVENTED_TRADES

EDIT_SET = Path(__file__).resolve().parent / "sets" / "edits.json"
RIGHT_SHARE = Decimal("0.8")
FIRST_THREE = ("E1", "E2", "E3")
SEND = "send"
NOT_FOUND = "not_found"
REFUSE = "refuse"
_EXPECTS = frozenset({SEND, NOT_FOUND, REFUSE})
_NUMBER_FIELDS = frozenset({"quantity", "price", "total", "fee"})


@dataclass(frozen=True)
class EditGold:
    """The gold answer of one sentence."""

    expect: str
    kind: str | None = None
    trade: str | None = None
    field: str | None = None
    value: str | None = None
    pick: str | None = None
    choose: str | None = None
    amounts: tuple[str, str, str] | None = None


@dataclass(frozen=True)
class EditSentence:
    id: str
    text: str
    gold: EditGold


@dataclass(frozen=True)
class EditSet:
    now: datetime
    zone: str
    sentences: tuple[EditSentence, ...]


def _gold(data: Mapping[str, object]) -> EditGold:
    expect = str(data["expect"])
    if expect not in _EXPECTS:
        raise ValueError(f"unknown gold answer: {expect!r}")
    pick = data.get("pick")
    amounts = data.get("amounts")
    gold = EditGold(
        expect=expect,
        kind=_text(data.get("kind")),
        trade=_text(data.get("trade")),
        field=_text(data.get("field")),
        value=_text(data.get("value")),
        pick=_text(pick.get("answer")) if isinstance(pick, Mapping) else None,
        choose=_text(data.get("choose")),
        amounts=(
            (str(amounts["quantity"]), str(amounts["price"]), str(amounts["total"]))
            if isinstance(amounts, Mapping)
            else None
        ),
    )
    if isinstance(pick, Mapping) and pick.get("trade") != gold.trade:
        raise ValueError("the trade picked is the trade sent")
    if expect == SEND and (gold.kind not in ("change", "delete") or gold.trade is None):
        raise ValueError("a send names its kind and its trade")
    if gold.kind == "change" and (gold.field is None or gold.value is None):
        raise ValueError("a change names its field and its value")
    if (gold.choose is None) != (gold.amounts is None):
        raise ValueError("a choice comes with the amounts it leads to")
    return gold


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def load_edit_set(path: Path = EDIT_SET) -> EditSet:
    """The set in ``path``; raises ``ValueError`` for a sentence or a gold answer out of shape."""
    data = json.loads(path.read_text(encoding="utf-8"))
    sentences = tuple(
        EditSentence(id=item["id"], text=item["text"], gold=_gold(item["gold"]))
        for item in data["sentences"]
    )
    ids = [sentence.id for sentence in sentences]
    if len(set(ids)) != len(ids):
        raise ValueError("every sentence has an identifier of its own")
    return EditSet(now=datetime.fromisoformat(data["now"]), zone=data["zone"], sentences=sentences)


@dataclass(frozen=True)
class Outcome:
    """What came of one sentence, with the ruler's answers after it.

    ``asked_pick`` and ``asked_choose`` say whether the program asked which
    trade, and which amount follows; ``sent_kind``, ``sent_trade`` and
    ``after`` what reached the ledger, if anything did; ``ending`` the last
    ending of the change, or ``None`` when the program never took one on.
    """

    asked_pick: bool = False
    asked_choose: bool = False
    sent_kind: str | None = None
    sent_trade: str | None = None
    after: TradeFacts | None = None
    ending: str | None = None


class Verdict(enum.Enum):
    RIGHT = "right"
    SILENTLY_WRONG = "silently wrong"
    NOT_DONE = "not done"


def _value(field: str, text: str) -> object:
    if field in _NUMBER_FIELDS:
        return Decimal(text)
    if field == "time":
        return datetime.fromisoformat(text)
    if field == "side":
        return Side(text)
    return text


_FACT_NAMES = {"quote_currency": "quote", "fee_currency": "fee_asset", "time": "occurred"}


def expected_trade(gold: EditGold) -> TradeFacts | None:
    """The whole trade the gold change proposes; ``None`` for a deletion or no send."""
    if gold.expect != SEND or gold.kind != "change":
        return None
    assert gold.trade is not None and gold.field is not None and gold.value is not None
    trade = dict(INVENTED_TRADES)[gold.trade]
    name = _FACT_NAMES.get(gold.field, gold.field)
    changed = dataclasses.replace(trade, **{name: _value(gold.field, gold.value)})  # type: ignore[arg-type]
    if gold.amounts is not None:
        quantity, price, total = (Decimal(amount) for amount in gold.amounts)
        changed = dataclasses.replace(changed, quantity=quantity, price=price, total=total)
    return changed


def judge_edit(gold: EditGold, outcome: Outcome) -> Verdict:
    """How one sentence went against its gold answer."""
    sent = outcome.sent_kind is not None
    if gold.expect != SEND:
        if sent:
            return Verdict.SILENTLY_WRONG
        wanted = "not_found" if gold.expect == NOT_FOUND else "told"
        return Verdict.RIGHT if outcome.ending == wanted else Verdict.NOT_DONE
    if not sent:
        return Verdict.NOT_DONE
    if (gold.pick is not None and not outcome.asked_pick) or (
        gold.choose is not None and not outcome.asked_choose
    ):
        return Verdict.SILENTLY_WRONG
    if outcome.sent_kind != gold.kind or outcome.sent_trade != gold.trade:
        return Verdict.SILENTLY_WRONG
    if gold.kind == "change" and outcome.after != expected_trade(gold):
        return Verdict.SILENTLY_WRONG
    return Verdict.RIGHT


def passes(verdicts: Mapping[str, Verdict]) -> dict[str, bool]:
    """The three pass lines."""
    right = sum(verdict is Verdict.RIGHT for verdict in verdicts.values())
    return {
        "nothing silently wrong": all(
            verdict is not Verdict.SILENTLY_WRONG for verdict in verdicts.values()
        ),
        "E1 to E3 right": all(verdicts.get(name) is Verdict.RIGHT for name in FIRST_THREE),
        "at least 80% right": Decimal(right) >= RIGHT_SHARE * len(verdicts),
    }


def _gold_words(gold: EditGold) -> str:
    if gold.expect != SEND:
        return "say nothing matches" if gold.expect == NOT_FOUND else "change nothing, say why"
    what = (
        f"delete {gold.trade}"
        if gold.kind == "delete"
        else (f"change {gold.trade} {gold.field} to {gold.value}")
    )
    if gold.pick is not None:
        what = f"ask which; '{gold.pick}': {what}"
    if gold.choose is not None:
        what += f"; ask which follows; '{gold.choose}'"
    return what


def markdown(
    rows: Sequence[tuple[EditSentence, Outcome, Verdict, str]], head: Mapping[str, object]
) -> str:
    """The result as a Markdown section body: the pass lines, then one row a sentence."""
    verdicts = {sentence.id: verdict for sentence, _, verdict, _ in rows}
    right = sum(verdict is Verdict.RIGHT for verdict in verdicts.values())
    lines = [
        f"Model `{head['model']}`, prompt `{head['prompt']}`: done right on {right} of "
        f"{len(rows)} sentences.",
        "",
    ]
    for line, passed in passes(verdicts).items():
        lines.append(f"- {line}: {'passed' if passed else 'NOT passed'}")
    lines += ["", "| Sentence | Gold | What came of it | Verdict |", "| --- | --- | --- | --- |"]
    for sentence, _, verdict, came in rows:
        lines.append(f"| {sentence.id} | {_gold_words(sentence.gold)} | {came} | {verdict.value} |")
    return "\n".join(lines)
