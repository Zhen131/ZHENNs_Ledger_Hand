"""Putting a follow-up question together: the facts, the notes beside it, and its wording.

``make_question`` takes the follow-up the core chose for one trade, the
trade's draft, the issues extraction raised and the shared setting, and
gives back the ``Question`` to show and the calls made to word it.

The program settles every fact: which trade (counting from 1, of how many),
the cells already known, the passage's own words for the field when
extraction left it empty for a reason (a number or a time it could not
read), and the notes shown beside the question:

- the passage's own words for the field, when there are some;
- when a price or a total is asked and the passage's words for it name
  something the asset table does not price trades in, that only trades
  priced in such money are recorded, and that the trade can be skipped;
  with the built-in table the note names USDT, as it always has;
- when the currency the trade was priced in is asked, the codes it may be
  answered with;
- with a table made from the ledger's list, when the asset is asked, that
  it is answered with its code as the ledger lists it, and that an asset
  the ledger lacks is added there first (``ADD_IN_LEDGER_FIRST``); the
  cells and the reasons are named as the ledger's table names them, and
  the asset by what it is (``core.asset_words``): a share, a coin, or an
  asset while it is not recognised;
- with a table made from the ledger's list, a price or a total is asked
  in the money the trade is priced in, named in the facts and in the
  program's sentence; it is always settled before (the currency is asked
  first), and a sentence of the model's that names other money is not used;
- for the cells one problem lies between, their values now, and how to say
  which one is wrong;
- for a coin to confirm, that the answer is yes or no; for the fee, that
  "none" means there was none;
- for a time the clocks showed twice, the two moments to choose from;
- and always, how to skip the trade or drop the whole passage.

Then the model words the question as a bookkeeper (``asking``), behind the
program's label; the program's own sentence stands in when the model's will
not do.

Names defined here: ``make_question``.
"""

from __future__ import annotations

from ledger_hand.asking.question_text import QuestionFacts, write_question
from ledger_hand.core.asset_words import cell_name, word_for
from ledger_hand.core.assets import AssetTable, MoneyReading
from ledger_hand.core.followup import AskCell, AskWhichCell, Cell, ConfirmCoin, value_of
from ledger_hand.core.numbers import write_number
from ledger_hand.core.timeparse import write_time
from ledger_hand.core.trade import OccurredTime, Side, TradeDraft
from ledger_hand.extraction.issues import Issue, IssueKind
from ledger_hand.extraction.reply_table import Field
from ledger_hand.extraction.unit_currency import currencies_in_unit
from ledger_hand.flows.progress import Asked, Call, Question, Setting, Step
from ledger_hand.ports import ModelPort

# The field of the model's table behind each cell, to find extraction's issues about it.
_FIELD_OF = {
    Cell.COIN: Field.COIN,
    Cell.QUANTITY: Field.QUANTITY,
    Cell.PRICE: Field.PRICE,
    Cell.TOTAL: Field.TOTAL,
    Cell.FEE: Field.FEE,
    Cell.FEE_COIN: Field.FEE_CURRENCY,
    Cell.OCCURRED: Field.TIME,
    Cell.PLATFORM: Field.PLATFORM,
    Cell.NOTE: Field.OPINION,
    Cell.QUOTE: Field.PRICE_CURRENCY,
}
# The issues whose phrase is the passage's own words for a field left empty.
_QUOTED_KINDS = frozenset(
    {IssueKind.NUMBER_UNSURE, IssueKind.NOT_A_NUMBER, IssueKind.TIME_REFUSED, IssueKind.TWO_TIMES}
)
# The cells shown as already known, in this order. The note is left out: it
# is the person's own view, and may be long.
_KNOWN = (
    Cell.SIDE,
    Cell.COIN,
    Cell.QUANTITY,
    Cell.PRICE,
    Cell.TOTAL,
    Cell.FEE,
    Cell.FEE_COIN,
    Cell.OCCURRED,
    Cell.PLATFORM,
)

SKIP_OR_CANCEL = "Say 'skip' to leave this trade out, or 'cancel' to drop the whole passage."
USDT_ONLY = "Only trades priced in USDT are recorded; the passage may price this one in a coin."
PRICEABLE_ONLY = (
    "Only trades priced in a currency the ledger prices trades in are recorded; "
    "the passage may price this one in something else."
)
ADD_IN_LEDGER_FIRST = (
    "Answer with the asset's code as the ledger lists it. If the ledger does not have "
    "this asset yet, please add it there first; meanwhile you may skip this trade."
)
TWICE = "The clocks showed that time twice that day: answer 1 or 2, or say the time again."


def make_question(
    position: int,
    trades: int,
    asked: Asked,
    draft: TradeDraft,
    issues: tuple[Issue, ...],
    setting: Setting,
    model: ModelPort,
    candidates: tuple[OccurredTime, ...] = (),
) -> tuple[Question, tuple[Call, ...]]:
    """The question about trade ``position`` of ``trades``, and the calls made to word it."""
    quoted = _quoted(asked, draft, issues, position)
    if not candidates and isinstance(asked, AskCell) and asked.cell is Cell.OCCURRED:
        candidates = _two_times(draft, issues, position)
    choices = tuple(
        f"{number}: {_shown_time(moment)}" for number, moment in enumerate(candidates, 1)
    )
    assets = setting.assets
    facts = QuestionFacts(
        trade=position + 1,
        trades=trades,
        asked=asked,
        known=_known(draft, ledger=assets.from_ledger),
        quoted=quoted,
        notes=_notes(asked, draft, quoted, setting, candidates),
        choices=choices,
        word=_word(asked, draft),
        money=_money(asked, draft, assets) if assets.from_ledger else None,
        asset=word_for(assets, draft.coin),
    )
    tuning = setting.tuning
    written = write_question(
        facts,
        model,
        assets.coins,
        parameters=tuning.question_parameters,
        money_words=_money_words(assets) if assets.from_ledger else frozenset(),
    )
    question = Question(
        trade=position,
        asked=asked,
        label=written.label,
        sentence=written.sentence,
        writer=written.writer,
        notes=facts.notes,
        choices=choices,
        candidates=candidates,
    )
    return question, tuple(Call(Step.QUESTION, record) for record in written.calls)


def shown_value(value: Side | str | object) -> str:
    """A cell's value in words, the way the ledger would write it."""
    if isinstance(value, Side):
        return value.value
    if isinstance(value, OccurredTime):
        return _shown_time(value)
    if isinstance(value, str):
        return value
    return write_number(value)  # type: ignore[arg-type]


def _shown_time(moment: OccurredTime) -> str:
    return f"{write_time(moment)} ({moment.precision.value})"


def _known(draft: TradeDraft, *, ledger: bool) -> tuple[tuple[str, str], ...]:
    return tuple(
        (cell_name(cell, ledger=ledger), shown_value(value))
        for cell in _KNOWN
        if (value := value_of(draft, cell)) is not None
    )


def _word(asked: Asked, draft: TradeDraft) -> str | None:
    if not isinstance(asked, ConfirmCoin):
        return None
    word = value_of(draft, asked.cell)
    return word if isinstance(word, str) else None


def _quoted(
    asked: Asked, draft: TradeDraft, issues: tuple[Issue, ...], position: int
) -> str | None:
    """The passage's own words for the field asked, when extraction left it empty for a reason."""
    if not isinstance(asked, AskCell) or asked.cell not in _FIELD_OF:
        return None
    if value_of(draft, asked.cell) is not None:
        return None
    field = _FIELD_OF[asked.cell]
    for issue in issues:
        if issue.draft == position and issue.field is field and issue.kind in _QUOTED_KINDS:
            return issue.phrase
    return None


def _two_times(
    draft: TradeDraft, issues: tuple[Issue, ...], position: int
) -> tuple[OccurredTime, ...]:
    if draft.occurred is not None:
        return ()
    for issue in issues:
        if issue.draft == position and issue.kind is IssueKind.TWO_TIMES:
            return issue.candidates
    return ()


def _notes(
    asked: Asked,
    draft: TradeDraft,
    quoted: str | None,
    setting: Setting,
    candidates: tuple[OccurredTime, ...],
) -> tuple[str, ...]:
    notes: list[str] = []
    if quoted is not None:
        notes.append(f"The passage says: {quoted!r}.")
        if _prices_in_a_coin(asked, quoted, draft, setting):
            notes.append(USDT_ONLY if setting.assets.speaks_of_usdt_only() else PRICEABLE_ONLY)
    if isinstance(asked, AskWhichCell):
        ledger = setting.assets.from_ledger
        now = ", ".join(
            f"{cell_name(cell, ledger=ledger)} {_value_or_blank(draft, cell)}"
            for cell in asked.cells
        )
        notes.append(f"Now: {now}.")
        notes.append(
            "Answer with the one that is wrong and its right value (such as 'price <value>'), "
            "or say the passage did not say it (such as 'price not said')."
        )
    if isinstance(asked, ConfirmCoin):
        notes.append("Answer yes or no.")
    if isinstance(asked, AskCell) and asked.cell is Cell.FEE:
        notes.append("Answer 'none' if there was no fee.")
    if isinstance(asked, AskCell) and asked.cell is Cell.QUOTE:
        notes.append(f"Answer with one of: {', '.join(setting.assets.pricing_codes)}.")
    if setting.assets.from_ledger and isinstance(asked, AskCell) and asked.cell is Cell.COIN:
        notes.append(ADD_IN_LEDGER_FIRST)
    if candidates:
        notes.append(TWICE)
    notes.append(SKIP_OR_CANCEL)
    return tuple(notes)


def _money(asked: Asked, draft: TradeDraft, assets: AssetTable) -> str | None:
    """The code of the money a price or a total is asked in; empty when not settled yet."""
    if not isinstance(asked, AskCell) or asked.cell not in (Cell.PRICE, Cell.TOTAL):
        return None
    said = assets.money(draft.quote) if draft.quote is not None else None
    if said is not None and said.reading is MoneyReading.ONE and said.code is not None:
        return said.code
    if said is None or said.reading is MoneyReading.SEVERAL:
        return assets.sole_pricing_code or ""
    return ""


def _money_words(assets: AssetTable) -> frozenset[str]:
    """Every word for money of the table, in lookup form."""
    return frozenset(key for money in assets.moneys for key in money.spoken_keys())


def _value_or_blank(draft: TradeDraft, cell: Cell) -> str:
    value = value_of(draft, cell)
    return "(blank)" if value is None else shown_value(value)


def _prices_in_a_coin(asked: Asked, quoted: str, draft: TradeDraft, setting: Setting) -> bool:
    """Whether a price or total is asked and the passage's words for it name no pricing money.

    A word naming one money the table prices in, or several such, or a
    vague word for money ("刀"), does not count; anything else named (a
    coin, other money) does.
    """
    if not isinstance(asked, AskCell) or asked.cell not in (Cell.PRICE, Cell.TOTAL):
        return False
    allowed = tuple(word for word in (draft.coin, draft.fee_coin) if word is not None)
    assets = setting.assets
    named = currencies_in_unit(quoted, assets, allowed)
    pricing = (MoneyReading.ONE, MoneyReading.SEVERAL, MoneyReading.VAGUE)
    return any(assets.money(word.text).reading not in pricing for word in named)
