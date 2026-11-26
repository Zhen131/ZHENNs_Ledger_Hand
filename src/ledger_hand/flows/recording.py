"""Recording a passage: from what was typed to records, one question and one answer at a time.

The steps, each handing back a new ``Progress``:

- ``start`` takes the passage, a model port, the current moment and the zone,
  and, if the caller hands one in, the book (a storage port). With a book,
  the passage is first looked up by its fingerprint: the earlier saves of it,
  or of one that differs only in spacing or the width of its characters, are
  kept as a reminder and hold nothing back; and the coins the user confirmed
  and saved before join the coin table. Without a book, nothing is looked
  up and nothing is opened. The passage is checked next and never sent when
  it is empty, too long or not valid text. The model judges it
  (``extraction.screening``): when it reports only things the ledger does
  not record, it is stopped, with the reason for each and the passage's own
  words where the model gave them, and nothing is extracted; when it
  reports nothing, there is no trade. Otherwise
  the trades are extracted, and what the passage reports beside them that is
  not recorded is set aside, to be shown as a caution. Each draft is checked
  (``core.validation``); a complete one is recorded at once.
  With ``hold_other_unit`` (the assistant's way; the Record page leaves
  it off), a trade whose quantity carries a unit that is not the asset
  traded ("25U" of ETH) is held back first, before any question, and
  nothing is asked about it (``held_other_unit``).
  With ``pick_assets`` (the assistant's way too), the name of an asset the
  ledger's own table does not find, and that cannot be written as a code,
  is first handed to the model to pick from the ledger's list
  (``extraction.asset_picking``), once for each name however many trades
  say it; an asset taken stands in the trade's cell, and a miss leaves the
  trade as it was. The calls are kept as ``Step.ASSET_PICK`` and each
  outcome in ``Progress.picks``. Left off, nothing is sent that was not.
- Then one trade is taken up at a time, in passage order, and one field of
  it at a time, in the order ``core.followup`` fixes. The question is put
  together and worded (``questions``); a trade that cannot be recorded is
  set aside with its reason, without a question.
- With ``unfinished`` (the assistant's way, when the ledger takes a trade
  with cells left empty), only which asset and buy or sell are asked,
  and a vague word for money ("美金", "刀") when the ledger has no trade
  of the asset or could not be asked (the product owner's rules, 81A
  section 2 items 1 and 2). Every other gap does not stop the trade: it
  is settled as ``TradeStatus.UNFINISHED`` with a card
  (``core.card_record``), its cells not said, or said wrong, left empty
  and marked. A vague word the ledger's last trade cannot settle (that
  day used both moneys, or another money) is left empty and marked. A
  quantity said in money ("25U" of ETH) is then taken as the total, not
  held back (``totals_from_units``). Without ``unfinished`` every gap is
  asked, as before.
- A trade paid in one money for an asset the ledger prices in another
  ("花了128欧元买了2股KO，一股69.5美元") is settled before it is checked
  (``paid_apart``): its money is the one paid, its price is worked out as
  the total over the quantity, and the price said in the asset's own money
  is kept apart (``Progress.said_prices``) and goes into its record or
  card. When that price was not said, it is asked by the program's own
  question, and its answer read by the program (``said_price_asking``);
  a quantity not said is asked even when the ledger takes cards.
- ``answer`` reads the answer (``extraction.answer_phrase``), puts it back
  into the trade (``filling``) and checks the trade again; then the next
  question follows. An answer that cannot be used gets the same question
  again, with the reason, and with the kind of the model's failure when
  the model could not be asked to read it. "skip" leaves the trade out;
  "cancel" drops the whole passage. Once every trade is settled, an answer
  is read as "done", "cancel" or "remove N".
- ``remove`` leaves out a recorded trade once every trade is settled (it
  counts as skipped), whether or not anything was asked about it, so that a
  wrong value seen in the records can be kept out. ``cancel`` drops the
  whole passage, and ``finish`` makes the records final.
- ``retuned`` hands back the passage with the model to be called as a new
  tuning says from its next step on, for settings changed while it is
  being recorded; nothing else about it changes.

When the model fails, or its replies cannot be read, while judging or
extracting, nothing is kept and the passage ends there; nothing is skipped
over. A failure while reading an answer or wording a question does not end
it: the answer is asked for again, or the program's own sentence is used.

The current moment and the zone are those of the passage throughout, and
the coins the user confirms are known for the rest of the run only; saving
keeps them with the trades that use them (``saving``). Nothing is written
anywhere here, and a book handed in is only read.

Names defined here: ``start``, ``answer``, ``remove``, ``cancel``,
``finish``, ``retuned``, ``tuning_from``, ``unbegun`` and
``held_other_unit``.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime

from ledger_hand.asking.prompts.bookkeeper import BOOKKEEPER_PROMPT
from ledger_hand.core.assets import BUILT_IN_ASSETS, AssetTable, MoneyReading, UnknownAssets
from ledger_hand.core.book import EarlierSave
from ledger_hand.core.card_record import card_record, money_doubt_other, money_doubt_two
from ledger_hand.core.coins import spoken_key
from ledger_hand.core.followup import (
    FOLLOW_UP_ORDER,
    AskCell,
    AskSaidPrice,
    CannotRecord,
    Cell,
    ConfirmCoin,
    Destination,
    FollowUp,
    follow_up_for,
    next_follow_up,
)
from ledger_hand.core.ledger_table import VAGUE_MONEY_CODES
from ledger_hand.core.marks import Field
from ledger_hand.core.time_wording import Refusal
from ledger_hand.core.timeparse import day_named
from ledger_hand.core.trade import Amount, OccurredTime, SaidPrice, TradeDraft, TradeRecord
from ledger_hand.core.validation import DraftProblems, Missing, check_draft
from ledger_hand.core.zones import is_zone_name
from ledger_hand.extraction.answer_phrase import (
    AnswerProblem,
    AnswerReading,
    AnswerSetting,
    Command,
    Commanded,
    Confirmed,
    Filled,
    NotRead,
    RemoveTrade,
    Review,
    TwoTimes,
    read_answer,
    read_review_answer,
)
from ledger_hand.extraction.asset_picking import (
    PICK_REPLY_TOKENS,
    AssetPick,
    pick_asset,
    should_pick,
)
from ledger_hand.extraction.extractor import Extracted, PassageRefused, extract
from ledger_hand.extraction.issues import Issue, IssueKind
from ledger_hand.extraction.prompting import PromptVersion
from ledger_hand.extraction.prompts.answer import ANSWER_PROMPT
from ledger_hand.extraction.prompts.asset_pick import ASSET_PICK_PROMPT, AssetPickPrompt
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.prompts.screen import SCREEN_PROMPT
from ledger_hand.extraction.reply_table import Field as ReplyField
from ledger_hand.extraction.screening import Decision, Screened, screen
from ledger_hand.extraction.unit_currency import currencies_in_unit
from ledger_hand.flows.coin_book import with_confirmed_coins
from ledger_hand.flows.filling import confirm, fill, fill_from_ledger, settle_clash
from ledger_hand.flows.fingerprint import passage_fingerprint
from ledger_hand.flows.guessing import guessed
from ledger_hand.flows.last_money import LastMoneyLookup, LastMoneyMiss
from ledger_hand.flows.paid_apart import AskPrice, Taken, paid_apart
from ledger_hand.flows.progress import (
    DEFAULT_TUNING,
    Asked,
    Call,
    Failure,
    MoneyClash,
    Progress,
    Question,
    Setting,
    Stage,
    Step,
    TradeState,
    TradeStatus,
    Tuning,
)
from ledger_hand.flows.questions import make_question
from ledger_hand.flows.said_price_asking import read_said_price, said_price_question
from ledger_hand.ports import ModelErrorKind, ModelParameters, ModelPort, ReplyRecord, StoragePort
from ledger_hand.settings import (
    DEFAULT_CONTEXT_TOKENS,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_TOP_P,
    ModelSettings,
)

_PROMPT_OF = {
    Step.SCREENING: SCREEN_PROMPT.name,
    Step.EXTRACTION: FIRST_PROMPT.name,
    Step.QUESTION: BOOKKEEPER_PROMPT.name,
    Step.ANSWER: ANSWER_PROMPT.name,
    Step.ASSET_PICK: ASSET_PICK_PROMPT.name,
}


def tuning_from(settings: ModelSettings) -> Tuning:
    """The tuning the settings name: the question's own temperature, the rest as for every call."""
    return Tuning(
        question_parameters=ModelParameters(
            temperature=settings.question_temperature,
            top_p=settings.top_p,
            max_reply_tokens=settings.max_reply_tokens,
            context_tokens=settings.context_tokens,
            timeout_seconds=settings.timeout_seconds,
        )
    )


# --- start ------------------------------------------------------------------


def start(
    passage: str,
    model: ModelPort,
    *,
    now: datetime,
    zone: str,
    assets: AssetTable = BUILT_IN_ASSETS,
    tuning: Tuning = DEFAULT_TUNING,
    book: StoragePort | None = None,
    screen_prompt: PromptVersion = SCREEN_PROMPT,
    extract_prompt: PromptVersion = FIRST_PROMPT,
    hold_other_unit: bool = False,
    pick_assets: bool = False,
    pick_prompt: AssetPickPrompt = ASSET_PICK_PROMPT,
    last_money: LastMoneyLookup | None = None,
    unfinished: bool = False,
) -> Progress:
    """Judge ``passage``, extract its trades, check them, and ask the first question.

    ``assets`` is the asset table: which assets may be traded and which
    money they may be priced in. With ``book``, the earlier saves of the
    passage are looked up and, when the table lets an unseen asset be
    confirmed, the coins confirmed before join it; a failure of the book
    raises its ``StorageError`` before the model is asked anything.

    ``screen_prompt`` and ``extract_prompt`` are the prompt versions the
    passage is judged and extracted with; left out, they are the versions
    every caller used before, and the progress names the ones used.

    ``hold_other_unit`` holds back, before any question, every trade whose
    quantity was said in another unit (``held_other_unit``): it is set
    as one that cannot be recorded, with no reason of the core's, and
    nothing is asked about it. Only the assistant turns it on; the
    Record page keeps the number and only reminds, as before.

    ``pick_assets`` hands each name of an asset the ledger's own table
    does not find to the model, to pick from the ledger's list, before any
    question (``extraction.asset_picking``), with ``pick_prompt``. Only
    the assistant turns it on; with the built-in table it never asks.

    ``last_money`` looks up the money of an asset's last trade in the
    ledger, to guess what a vague word for money meant (``guessing``);
    only the assistant hands one in, and without it nothing is guessed.

    ``unfinished`` says the ledger takes a trade with cells left empty:
    only which asset and buy or sell (and a vague word for money the
    ledger cannot settle) are asked; every other gap becomes a card. Only
    the assistant turns it on, and only when the ledger offers it.
    """
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("the current moment must be a datetime that carries an offset")
    if not is_zone_name(zone):
        raise ValueError(f"not a time zone name: {zone!r}")
    seen_before: tuple[EarlierSave, ...] = ()
    if book is not None:
        seen_before = book.earlier_saves(passage_fingerprint(passage))
        if assets.unknown is UnknownAssets.CONFIRM_ON_THE_SPOT:
            assets = dataclasses.replace(
                assets, coins=with_confirmed_coins(assets.coins, book.confirmed_coins())
            )
    progress = Progress(
        Stage.REFUSED,
        passage,
        Setting(now, zone, assets, tuning, unfinished=unfinished),
        seen_before=seen_before,
    )
    screening = screen(passage, model, prompt=screen_prompt, asks_again=tuning.asks_again)
    progress = _with_calls(progress, Step.SCREENING, _calls_of(screening), screen_prompt.name)
    if isinstance(screening, PassageRefused):
        return dataclasses.replace(progress, refused=screening.problem)
    if not isinstance(screening, Screened):
        return _failed(progress, Step.SCREENING, screening)
    if screening.decision is Decision.STOP:
        return dataclasses.replace(progress, stage=Stage.STOPPED, stopped=screening.set_aside)
    if screening.decision is Decision.NO_TRADE:
        return dataclasses.replace(progress, stage=Stage.NO_TRADE)
    progress = dataclasses.replace(progress, set_aside=screening.set_aside)
    picking = pick_prompt if pick_assets else None
    return _extracted(
        progress, model, extract_prompt, hold=hold_other_unit, pick=picking, last=last_money
    )


def _extracted(
    progress: Progress,
    model: ModelPort,
    prompt: PromptVersion,
    *,
    hold: bool = False,
    pick: AssetPickPrompt | None = None,
    last: LastMoneyLookup | None = None,
) -> Progress:
    setting = progress.setting
    extraction = extract(
        progress.passage,
        model,
        now=setting.now,
        zone=setting.zone,
        assets=setting.assets,
        prompt=prompt,
        asks_again=setting.tuning.asks_again,
    )
    progress = _with_calls(progress, Step.EXTRACTION, _calls_of(extraction), prompt.name)
    if isinstance(extraction, PassageRefused):
        return dataclasses.replace(progress, stage=Stage.REFUSED, refused=extraction.problem)
    if not isinstance(extraction, Extracted):
        return _failed(progress, Step.EXTRACTION, extraction)
    if not extraction.drafts:
        return dataclasses.replace(progress, stage=Stage.NO_TRADE, issues=extraction.issues)
    drafts = extraction.drafts
    if pick is not None:
        drafts, picks = _picked(drafts, setting, model, pick)
        for found in picks:
            progress = _with_calls(progress, Step.ASSET_PICK, found.calls, found.prompt)
        progress = dataclasses.replace(progress, picks=picks)
    totals: list[tuple[int, str]] = []
    if hold and setting.unfinished:
        drafts, totals = _totals_from_units(drafts, extraction.issues, setting.assets)
    taken = {position for position, _ in totals}
    trades = tuple(
        TradeState(
            draft,
            _held_status(
                position,
                draft,
                extraction.issues,
                setting.assets,
                hold=hold and position not in taken,
            ),
        )
        for position, draft in enumerate(drafts)
    )
    progress = dataclasses.replace(
        progress,
        trades=trades,
        issues=extraction.issues,
        totals_from_units=tuple(totals),
        moneys_said=extraction.moneys_said,
    )
    return _next_question(progress, model, last)


def _totals_from_units(
    drafts: tuple[TradeDraft, ...], issues: tuple[Issue, ...], assets: AssetTable
) -> tuple[tuple[TradeDraft, ...], list[tuple[int, str]]]:
    """The drafts with each quantity said in money ("25U" of ETH) taken as the total instead.

    This function reads a quantity held back for its unit as what was
    paid or got in all, when the unit is one money and no total was said:
    the quantity is left empty, the total is that number, and the money
    used is the unit's when none was said. A unit of no money, or of
    another money than the one said, stays held back. Example: "25U买了点
    ETH" gives a total of 25 in USDT and no quantity.

    Why: "数量带了别的单位 → 那个数当总花费" (81A section 5 item 9, the
    contract of 2026-11-25); the ledger then takes the quantity empty.
    """
    changed = list(drafts)
    taken: list[tuple[int, str]] = []
    for position, draft in enumerate(drafts):
        issue = held_other_unit(position, draft, issues, assets)
        if issue is None or issue.phrase is None or draft.quantity is None:
            continue
        if draft.total is not None:
            continue
        words = currencies_in_unit(issue.phrase, assets)
        if len(words) != 1:
            continue
        unit = words[0].text
        found = assets.money(unit)
        if found.reading not in (MoneyReading.ONE, MoneyReading.VAGUE):
            continue
        if draft.quote is not None and assets.money(draft.quote).code != found.code:
            continue
        said = f"{format(draft.quantity, 'f')}{issue.phrase}"
        changed[position] = dataclasses.replace(
            draft,
            quantity=None,
            total=draft.quantity,
            quote=draft.quote if draft.quote is not None else unit,
            derived=frozenset(),
        )
        taken.append((position, said))
    return tuple(changed), taken


def _picked(
    drafts: tuple[TradeDraft, ...], setting: Setting, model: ModelPort, prompt: AssetPickPrompt
) -> tuple[tuple[TradeDraft, ...], tuple[AssetPick, ...]]:
    """The drafts with each asset picked from the ledger's list in, and what came of each name.

    A name said in several trades is handed over once, and its outcome
    serves them all.
    """
    assets = setting.assets
    found: dict[str, AssetPick] = {}
    picked: list[TradeDraft] = []
    for draft in drafts:
        word = draft.coin
        if word is None or not should_pick(word, assets):
            picked.append(draft)
            continue
        key = spoken_key(word)
        if key not in found:
            found[key] = pick_asset(
                word, assets, model, prompt=prompt, parameters=_pick_parameters(setting)
            )
        code = found[key].code
        if code is None:
            picked.append(draft)
            continue
        words = (found[key].said or word).strip()
        picked.append(dataclasses.replace(draft, coin=code, picked=words))
    return tuple(picked), tuple(found.values())


def _pick_parameters(setting: Setting) -> ModelParameters:
    """How the model is called to pick an asset: at temperature 0, with a short reply.

    Why temperature 0, whatever the settings say for questions: the same
    words then pick the same asset each time, so a measure of it holds
    (decided on 2026-11-25). The rest follows the settings, as for a
    question, or the settings' defaults when none were handed in.
    """
    base = setting.tuning.question_parameters
    return ModelParameters(
        temperature=0.0,
        top_p=base.top_p if base is not None else DEFAULT_TOP_P,
        max_reply_tokens=PICK_REPLY_TOKENS,
        context_tokens=base.context_tokens if base is not None else DEFAULT_CONTEXT_TOKENS,
        timeout_seconds=base.timeout_seconds if base is not None else DEFAULT_TIMEOUT_SECONDS,
    )


def _held_status(
    position: int,
    draft: TradeDraft,
    issues: tuple[Issue, ...],
    assets: AssetTable,
    *,
    hold: bool,
) -> TradeStatus:
    if hold and held_other_unit(position, draft, issues, assets) is not None:
        return TradeStatus.CANNOT_RECORD
    return TradeStatus.OPEN


def held_other_unit(
    position: int, draft: TradeDraft, issues: tuple[Issue, ...], assets: AssetTable
) -> Issue | None:
    """The reminder that the quantity of trade ``position`` was said in another unit, if held.

    This function finds the reminder that the quantity carries a unit
    that is not the asset traded, about the draft at ``position``
    (counting from 0). It holds only when an asset was said ("25U" of
    ETH), or when none was and the unit is money ("25U" alone). With no
    asset said and a unit that is an asset ("0.1个BTC"), it does not
    hold: the asset is asked about, as before. ``None`` when it does
    not hold.

    Why: the assistant sent "25U买了点ETH" as 25 ETH, total 59700 USDT,
    while the user paid 25 USDT; the reminder was there but unsaid.
    Found on 2026-11-25 by the assistant's acceptance run.
    """
    for issue in issues:
        if issue.kind is not IssueKind.UNIT_NOT_THE_COIN or issue.draft != position:
            continue
        if draft.coin is not None or _is_money(issue.phrase, assets):
            return issue
    return None


def _is_money(unit: str | None, assets: AssetTable) -> bool:
    """Whether ``unit`` names a money of ``assets`` ("U", "USDT", "美元")."""
    if unit is None:
        return False
    return any(
        assets.money(word.text).reading is not MoneyReading.NOT_MONEY
        for word in currencies_in_unit(unit, assets)
    )


def _failed(progress: Progress, step: Step, result: object) -> Progress:
    """The passage ends here: the model failed, or none of its replies could be read."""
    error = getattr(result, "error", None)
    problems = tuple(problem.value for problem in getattr(result, "problems", ()))
    return dataclasses.replace(progress, stage=Stage.FAILED, failure=Failure(step, error, problems))


def _calls_of(result: object) -> tuple[ReplyRecord, ...]:
    calls: tuple[ReplyRecord, ...] = getattr(result, "calls", ())
    return calls


def _with_calls(
    progress: Progress, step: Step, records: tuple[ReplyRecord, ...], prompt: str | None = None
) -> Progress:
    """``progress`` with the calls made for ``step``, and the step's prompt when it called.

    ``prompt`` names the version used, when the caller chose it; otherwise
    the step's one version is named.
    """
    if not records:
        return progress
    calls = (*progress.calls, *(Call(step, record) for record in records))
    prompts = progress.prompts
    if all(used != step for used, _ in prompts):
        prompts = (*prompts, (step, prompt if prompt is not None else _PROMPT_OF[step]))
    return dataclasses.replace(progress, calls=calls, prompts=prompts)


def unbegun(passage: str, *, now: datetime, zone: str, tuning: Tuning = DEFAULT_TUNING) -> Progress:
    """The passage as it stands before anything was done with it: nothing judged, nothing asked.

    It is for a caller that ends before the flow begins, such as the
    assistant when the ledger cannot give its list of assets; the built-in
    asset table stands in its setting, and nothing ever reads it.
    """
    return Progress(Stage.REFUSED, passage, Setting(now, zone, BUILT_IN_ASSETS, tuning))


# --- one trade at a time ----------------------------------------------------


def _next_question(
    progress: Progress, model: ModelPort, last: LastMoneyLookup | None = None
) -> Progress:
    """Settle the open trades in order until one needs a question, or none is left.

    Before a trade is checked, a vague word for its money is guessed from
    the ledger where it may be (``guessing``), so that no question is
    asked about a money the ledger's last trade settles.
    """
    trades = list(progress.trades)
    assets = progress.setting.assets
    for position, trade in enumerate(trades):
        if trade.status is not TradeStatus.OPEN:
            continue
        draft, progress = guessed(progress, position, trade.draft, last)
        draft, said, asked, progress = _paid_apart(progress, position, draft, last)
        checked = check_draft(draft, assets, progress.setting.now)
        if asked is None and said is None:
            asked = _worked_across(progress, position, draft, checked)
        if asked is not None:
            trades[position] = TradeState(draft, TradeStatus.OPEN)
            progress = dataclasses.replace(progress, trades=tuple(trades))
            return _asking(progress, position, asked, model)
        if isinstance(checked, TradeRecord):
            if said is not None:
                checked = dataclasses.replace(checked, said_price=said)
            trades[position] = TradeState(draft, TradeStatus.RECORDED, checked)
            continue
        follow_up = next_follow_up(draft, checked)
        trades[position] = TradeState(draft, TradeStatus.OPEN)
        if isinstance(follow_up, CannotRecord):
            trades[position] = TradeState(
                draft, TradeStatus.CANNOT_RECORD, reason=follow_up.because
            )
            continue
        if progress.setting.unfinished:
            carded = _carded(progress, position, draft, checked, said)
            if isinstance(carded, TradeState):
                trades[position] = carded
                continue
            follow_up = carded
        progress = dataclasses.replace(progress, trades=tuple(trades))
        return _asking(progress, position, follow_up, model)
    return dataclasses.replace(progress, stage=Stage.REVIEWING, trades=tuple(trades), question=None)


def _carded(
    progress: Progress,
    position: int,
    draft: TradeDraft,
    checked: DraftProblems,
    said: SaidPrice | None,
) -> TradeState | Asked:
    """The trade settled as a card, once the ledger takes cards; or what is still asked."""
    asked, doubts = _still_asked(progress, position, draft, checked)
    if asked is not None:
        return asked
    card = card_record(
        draft,
        checked,
        progress.setting.assets,
        progress.setting.now,
        money_doubts=doubts,
        taken_as_total=dict(progress.totals_from_units).get(position),
        after_today=_after_today(progress, position),
    )
    if said is not None:
        card = dataclasses.replace(card, said_price=said)
    return TradeState(draft, TradeStatus.UNFINISHED, card=card)


def _paid_apart(
    progress: Progress, position: int, draft: TradeDraft, last: LastMoneyLookup | None
) -> tuple[TradeDraft, SaidPrice | None, Asked | None, Progress]:
    """The draft of a trade paid in another money, settled; the price said apart; what to ask.

    A trade that does not go that way comes back as it was. One that would,
    with no price said in its asset's own money, asks for it; one that
    does, with no quantity, asks the quantity, even when the ledger takes
    cards: the rate cannot be worked out without it (``paid_apart``).
    """
    apart, progress = paid_apart(progress, position, draft, last)
    if isinstance(apart, AskPrice):
        return draft, None, apart.asked, progress
    if not isinstance(apart, Taken):
        return draft, None, None, progress
    if apart.draft.quantity is None:
        asked = AskCell(Cell.QUANTITY, Missing.ONE_MORE_OF_QUANTITY_PRICE_TOTAL)
        return apart.draft, apart.said, asked, progress
    return apart.draft, apart.said, None, progress


# The cell asked for in place of an amount that would be worked out across two moneys.
_AMOUNT_CELL = {Amount.QUANTITY: Cell.QUANTITY, Amount.PRICE: Cell.PRICE, Amount.TOTAL: Cell.TOTAL}

# The issues that say a trade's price or total named another money than the trade's own.
_ACROSS = frozenset({IssueKind.UNIT_NOT_THE_PRICE_CURRENCY, IssueKind.MONEY_NOT_CLEAR})


def _worked_across(
    progress: Progress, position: int, draft: TradeDraft, checked: TradeRecord | DraftProblems
) -> AskCell | None:
    """The amount to ask for instead of working it out, when it would be across two moneys.

    This function looks at a trade whose price or total named another
    money than the trade's own (extraction said so: a unit of another
    money, or a vague word beside another money), with only two of
    quantity, price and total said. The third is then not worked out from
    figures in two moneys: it is asked, even when the ledger takes cards.
    Example: "用欧元买了2股KO，一股69.5美元" asks the total, never 139.

    Why: "任何时候不许跨两种钱去算第三样" (87B, part 4, item 4,
    2026-11-25). A trade paid in another money that goes the way of
    ``paid_apart`` never gets here: its price is not said in the money paid.
    """
    if isinstance(checked, TradeRecord):
        blank = checked.derived
    else:
        stated = [amount for amount in Amount if draft.stated(amount) is not None]
        blank = next(iter(set(Amount) - set(stated))) if len(stated) == 2 else None
    if blank is None:
        return None
    across = any(
        issue.draft == position
        and issue.kind in _ACROSS
        and (
            issue.kind is IssueKind.UNIT_NOT_THE_PRICE_CURRENCY
            or issue.field is ReplyField.PRICE_CURRENCY
        )
        for issue in progress.issues
    )
    if not across:
        return None
    return AskCell(_AMOUNT_CELL[blank], Missing.ONE_MORE_OF_QUANTITY_PRICE_TOTAL)


# Where a problem still leads to a question once the ledger takes cards: which
# asset, and buy or sell; the ledger never takes either empty (81A section 2
# item 1). A vague word for money is decided apart (``_vague_verdict``).
_STILL_ASKED = frozenset({Destination.ASK_SIDE, Destination.ASK_COIN, Destination.CONFIRM_COIN})

# The cell a vague word for money stands in, by the problem the check noted.
_VAGUE_CELLS = {
    Missing.QUOTE: (Field.QUOTE_ASSET_ID, ReplyField.PRICE_CURRENCY),
    Missing.FEE_COIN: (Field.FEE_ASSET_ID, ReplyField.FEE_CURRENCY),
}


def _still_asked(
    progress: Progress, position: int, draft: TradeDraft, problems: DraftProblems
) -> tuple[Asked | None, dict[Field, str]]:
    """The question still asked about a trade once the ledger takes cards, or none.

    When none is, the reasons each vague word for money is doubted come
    back, by the card's cell, for the card. Example: "30刀" for ETH whose
    latest day used both USDT and the US dollar: no question, and the
    money used doubted.
    """
    found = set(problems.missing) | set(problems.violations)
    doubts: dict[Field, str] = {}
    for problem, destination in FOLLOW_UP_ORDER:
        if problem not in found:
            continue
        if destination in _STILL_ASKED:
            return _asked(follow_up_for(problem, draft)), doubts
        if problem in _VAGUE_CELLS:
            field, reply_field = _VAGUE_CELLS[problem]
            word = draft.quote if problem is Missing.QUOTE else draft.fee_coin
            verdict = _vague_verdict(progress, position, draft, word, reply_field)
            if verdict is _ASK:
                return _asked(follow_up_for(problem, draft)), doubts
            if isinstance(verdict, str):
                doubts[field] = verdict
    return None, doubts


def _asked(follow_up: FollowUp) -> Asked:
    """``follow_up`` as a question; a problem the table sends to no question is a mistake."""
    if isinstance(follow_up, CannotRecord):
        raise AssertionError(f"{follow_up.because} leads to no question")
    return follow_up


def _after_today(progress: Progress, position: int) -> str | None:
    """The day of a time said for the trade at ``position`` that reading refused for lying
    after today ("2026-11-25"), or its words when no day is named; ``None`` for none."""
    setting = progress.setting
    for issue in progress.issues:
        if (
            issue.kind is IssueKind.TIME_REFUSED
            and issue.draft == position
            and issue.cause is Refusal.IN_THE_FUTURE
            and issue.phrase is not None
        ):
            day = day_named(issue.phrase, setting.now, setting.zone)
            return day.isoformat() if day is not None else f'"{issue.phrase}"'
    return None


class _Ask:
    """The word for money is asked about, as before."""


_ASK = _Ask()


def _vague_verdict(
    progress: Progress,
    position: int,
    draft: TradeDraft,
    word: str | None,
    reply_field: ReplyField,
) -> _Ask | str | None:
    """Whether a vague word for money is asked about, doubted (why), or not vague at all.

    It is asked about, as before, when the ledger has no trade of the
    asset, or could not be asked (then "no trade" cannot be ruled out),
    and in every case these rules do not name (81A section 2 item 2; the
    contract's review, must-fix 5). It is doubted when the asset's latest
    day used both USDT and the US dollar, or its last trade used another
    money (the contract's table B, 2026-11-25).
    """
    assets = progress.setting.assets
    if word is None or assets.money(word).reading is not MoneyReading.VAGUE:
        return None
    not_clear = any(
        issue.kind is IssueKind.MONEY_NOT_CLEAR
        and issue.draft == position
        and issue.field is reply_field
        for issue in progress.issues
    )
    coin = assets.find(draft.coin) if draft.coin is not None else None
    if not_clear or coin is None:
        return _ASK
    last = dict(progress.last_moneys).get(coin.symbol)
    if last is None:
        return _ASK
    if last.miss is LastMoneyMiss.TWO_MONEYS:
        return money_doubt_two(word, coin.symbol)
    found = last.found
    if found is not None and found.money not in VAGUE_MONEY_CODES:
        return money_doubt_other(word, found)
    return _ASK


def _asking_said_price(
    progress: Progress, position: int, asked: AskSaidPrice, again: str | None = None
) -> Progress:
    """Ask the price of one unit in the asset's own money: the program's question, no model."""
    question = said_price_question(position, len(progress.trades), asked, again)
    return dataclasses.replace(progress, stage=Stage.ASKING, question=question, note=None)


def _said_price_answered(
    progress: Progress,
    question: Question,
    asked: AskSaidPrice,
    text: str,
    model: ModelPort,
    last: LastMoneyLookup | None,
) -> Progress:
    """The answer to the price asked in the asset's own money, read by the program."""
    read = read_said_price(text, asked, progress.setting.assets)
    if read.command is Command.CANCEL:
        return cancel(progress)
    if read.command is Command.SKIP:
        return _settle(progress, question.trade, TradeStatus.SKIPPED, model, last)
    if read.price is None:
        return _asking_said_price(progress, question.trade, asked, again=read.not_used)
    said = SaidPrice(amount=read.price, money=asked.money, paid=asked.paid)
    prices = tuple(pair for pair in progress.said_prices if pair[0] != question.trade)
    progress = dataclasses.replace(progress, said_prices=(*prices, (question.trade, said)))
    return _next_question(progress, model, last)


def _asking(
    progress: Progress,
    position: int,
    asked: Asked,
    model: ModelPort,
    candidates: tuple[OccurredTime, ...] = (),
) -> Progress:
    if isinstance(asked, AskSaidPrice):
        return _asking_said_price(progress, position, asked)
    question, calls = make_question(
        position,
        len(progress.trades),
        asked,
        progress.trades[position].draft,
        progress.issues,
        progress.setting,
        model,
        candidates,
    )
    progress = _with_calls(progress, Step.QUESTION, tuple(call.record for call in calls))
    return dataclasses.replace(progress, stage=Stage.ASKING, question=question, note=None)


# --- answers ----------------------------------------------------------------


def answer(
    progress: Progress,
    text: str,
    model: ModelPort,
    *,
    last_money: LastMoneyLookup | None = None,
) -> Progress:
    """Read ``text`` as the answer to the waiting question, or as a command once all is settled.

    ``last_money`` is as for ``start``: the caller hands the same one in
    each time.
    """
    if progress.stage is Stage.REVIEWING:
        return _reviewed(progress, text)
    question = progress.question
    if progress.stage is not Stage.ASKING or question is None:
        raise ValueError(f"nothing is being asked: {progress.stage.value}")
    if isinstance(question.asked, AskSaidPrice):
        return _said_price_answered(progress, question, question.asked, text, model, last_money)
    trade = progress.trades[question.trade]
    setting = progress.setting
    reading = read_answer(
        text,
        question.asked,
        model,
        AnswerSetting(
            now=setting.now,
            zone=setting.zone,
            assets=setting.assets,
            coin=trade.draft.coin,
            fee_coin=trade.draft.fee_coin,
            candidates=question.candidates,
        ),
        asks_again=setting.tuning.asks_again,
    )
    progress = _with_calls(progress, Step.ANSWER, reading.calls)
    return _answered(progress, question, reading, model, last_money)


def _answered(
    progress: Progress,
    question: Question,
    reading: AnswerReading,
    model: ModelPort,
    last: LastMoneyLookup | None = None,
) -> Progress:
    outcome = reading.outcome
    if isinstance(outcome, Commanded):
        progress = dataclasses.replace(progress, clash=None)
        if outcome.command is Command.CANCEL:
            return cancel(progress)
        return _settle(progress, question.trade, TradeStatus.SKIPPED, model, last)
    if isinstance(outcome, NotRead):
        return _asked_again(progress, question, outcome)
    if isinstance(outcome, TwoTimes):
        return _asking(
            progress, question.trade, question.asked, model, (outcome.earlier, outcome.later)
        )
    trades = list(progress.trades)
    draft = trades[question.trade].draft
    assets = progress.setting.assets
    clash = progress.clash
    if isinstance(outcome, Confirmed) and isinstance(question.asked, ConfirmCoin):
        draft, assets = confirm(draft, assets, question.asked, outcome.confirmation)
    elif isinstance(outcome, Filled) and clash is not None and isinstance(outcome.value, str):
        draft = settle_clash(draft, clash, outcome.value, assets)
        clash = None
    elif isinstance(outcome, Filled) and assets.from_ledger:
        filled = fill_from_ledger(draft, outcome, assets, question.trade)
        if isinstance(filled, MoneyClash):
            progress = dataclasses.replace(progress, clash=filled)
            return _asking_which_money(progress, filled, model)
        draft = filled
    elif isinstance(outcome, Filled):
        draft = fill(draft, outcome)
    trades[question.trade] = TradeState(draft, TradeStatus.OPEN)
    setting = dataclasses.replace(progress.setting, assets=assets)
    progress = dataclasses.replace(progress, trades=tuple(trades), setting=setting, clash=clash)
    return _next_question(progress, model, last)


def _asking_which_money(progress: Progress, clash: MoneyClash, model: ModelPort) -> Progress:
    """Ask which money a trade (or its fee) was in, when an answer named another one.

    The question is the one for a blank pricing currency, or a blank fee
    currency, with a note that says both: what the trade had, and what the
    answer said. Example: "Before, this trade was in USDT; now you said
    2400 美元."
    """
    if clash.cell is Cell.FEE:
        asked = AskCell(Cell.FEE_COIN, Missing.FEE_COIN)
        what = "its fee was taken"
    else:
        asked = AskCell(Cell.QUOTE, Missing.QUOTE)
        what = "this trade was priced"
    guess = " (a guess from the ledger's last trade)" if clash.guessed else ""
    note = (
        f"Before, {what} in {clash.before}{guess}; now you said "
        f"{format(clash.value, 'f')} {clash.said}. Which is it?"
    )
    progress = _asking(progress, clash.trade, asked, model)
    question = progress.question
    if question is None:
        return progress
    return dataclasses.replace(
        progress, question=dataclasses.replace(question, notes=(note, *question.notes))
    )


# The reasons an answer was not used whose words say "coin", for the ledger's own table.
_LEDGER_ANSWER_WORDS = {
    AnswerProblem.UNIT_NOT_THE_COIN: "the quantity names an asset other than the trade's",
}


def _reason(outcome: NotRead, *, ledger: bool = False) -> str:
    reason = outcome.problem.value
    if ledger:
        reason = _LEDGER_ANSWER_WORDS.get(outcome.problem, reason)
    if outcome.cause is not None:
        reason += f" ({outcome.cause.value})"
    return reason


def _asked_again(progress: Progress, question: Question, outcome: NotRead) -> Progress:
    ledger = progress.setting.assets.from_ledger
    again = dataclasses.replace(
        question, again=_reason(outcome, ledger=ledger), model_failure=_model_failure(outcome)
    )
    return dataclasses.replace(progress, question=again)


def _model_failure(outcome: NotRead) -> ModelErrorKind | None:
    """The kind of the model's failure, when that is why the answer could not be read."""
    if outcome.problem is AnswerProblem.MODEL_FAILED and isinstance(outcome.cause, ModelErrorKind):
        return outcome.cause
    return None


def _settle(
    progress: Progress,
    position: int,
    status: TradeStatus,
    model: ModelPort,
    last: LastMoneyLookup | None = None,
) -> Progress:
    trades = list(progress.trades)
    trades[position] = TradeState(trades[position].draft, status)
    return _next_question(dataclasses.replace(progress, trades=tuple(trades)), model, last)


# --- once every trade is settled --------------------------------------------


def _reviewed(progress: Progress, text: str) -> Progress:
    said = read_review_answer(text)
    if said is Review.DONE:
        return finish(progress)
    if said is Review.CANCEL:
        return cancel(progress)
    if isinstance(said, RemoveTrade):
        return remove(progress, said.number)
    return dataclasses.replace(progress, note=_reason(said))


def remove(progress: Progress, number: int) -> Progress:
    """Leave out the recorded trade shown as ``number`` (counting from 1); it counts as skipped."""
    if progress.stage is not Stage.REVIEWING:
        raise ValueError(f"a trade can be removed only once all is settled: {progress.stage.value}")
    position = number - 1
    if not 0 <= position < len(progress.trades) or (
        progress.trades[position].status is not TradeStatus.RECORDED
    ):
        return dataclasses.replace(progress, note=f"there is no recorded trade {number}")
    trades = list(progress.trades)
    trades[position] = TradeState(trades[position].draft, TradeStatus.SKIPPED)
    return dataclasses.replace(progress, trades=tuple(trades), note=None)


def cancel(progress: Progress) -> Progress:
    """Drop the whole passage: nothing is kept."""
    if not progress.can_cancel:
        raise ValueError(f"the passage cannot be dropped now: {progress.stage.value}")
    return dataclasses.replace(progress, stage=Stage.CANCELLED, question=None, note=None)


def finish(progress: Progress) -> Progress:
    """Make the records final."""
    if progress.stage is not Stage.REVIEWING:
        raise ValueError(f"the records are final only once all is settled: {progress.stage.value}")
    return dataclasses.replace(progress, stage=Stage.DONE, note=None)


def retuned(progress: Progress, tuning: Tuning) -> Progress:
    """``progress`` with the model called as ``tuning`` says from its next step on."""
    if progress.setting.tuning == tuning:
        return progress
    setting = dataclasses.replace(progress.setting, tuning=tuning)
    return dataclasses.replace(progress, setting=setting)
