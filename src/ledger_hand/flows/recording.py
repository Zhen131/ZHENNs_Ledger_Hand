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
from ledger_hand.core.coins import spoken_key
from ledger_hand.core.followup import CannotRecord, ConfirmCoin, next_follow_up
from ledger_hand.core.trade import OccurredTime, TradeDraft, TradeRecord
from ledger_hand.core.validation import check_draft
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
from ledger_hand.extraction.screening import Decision, Screened, screen
from ledger_hand.extraction.unit_currency import currencies_in_unit
from ledger_hand.flows.coin_book import with_confirmed_coins
from ledger_hand.flows.filling import confirm, fill
from ledger_hand.flows.fingerprint import passage_fingerprint
from ledger_hand.flows.progress import (
    DEFAULT_TUNING,
    Asked,
    Call,
    Failure,
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
        Stage.REFUSED, passage, Setting(now, zone, assets, tuning), seen_before=seen_before
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
    return _extracted(progress, model, extract_prompt, hold=hold_other_unit, pick=picking)


def _extracted(
    progress: Progress,
    model: ModelPort,
    prompt: PromptVersion,
    *,
    hold: bool = False,
    pick: AssetPickPrompt | None = None,
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
    trades = tuple(
        TradeState(
            draft, _held_status(position, draft, extraction.issues, setting.assets, hold=hold)
        )
        for position, draft in enumerate(drafts)
    )
    progress = dataclasses.replace(progress, trades=trades, issues=extraction.issues)
    return _next_question(progress, model)


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
        picked.append(draft if code is None else dataclasses.replace(draft, coin=code))
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


def _next_question(progress: Progress, model: ModelPort) -> Progress:
    """Settle the open trades in order until one needs a question, or none is left."""
    trades = list(progress.trades)
    assets = progress.setting.assets
    for position, trade in enumerate(trades):
        if trade.status is not TradeStatus.OPEN:
            continue
        checked = check_draft(trade.draft, assets, progress.setting.now)
        if isinstance(checked, TradeRecord):
            trades[position] = TradeState(trade.draft, TradeStatus.RECORDED, checked)
            continue
        follow_up = next_follow_up(trade.draft, checked)
        if isinstance(follow_up, CannotRecord):
            trades[position] = TradeState(
                trade.draft, TradeStatus.CANNOT_RECORD, reason=follow_up.because
            )
            continue
        progress = dataclasses.replace(progress, trades=tuple(trades))
        return _asking(progress, position, follow_up, model)
    return dataclasses.replace(progress, stage=Stage.REVIEWING, trades=tuple(trades), question=None)


def _asking(
    progress: Progress,
    position: int,
    asked: Asked,
    model: ModelPort,
    candidates: tuple[OccurredTime, ...] = (),
) -> Progress:
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


def answer(progress: Progress, text: str, model: ModelPort) -> Progress:
    """Read ``text`` as the answer to the waiting question, or as a command once all is settled."""
    if progress.stage is Stage.REVIEWING:
        return _reviewed(progress, text)
    question = progress.question
    if progress.stage is not Stage.ASKING or question is None:
        raise ValueError(f"nothing is being asked: {progress.stage.value}")
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
    return _answered(progress, question, reading, model)


def _answered(
    progress: Progress, question: Question, reading: AnswerReading, model: ModelPort
) -> Progress:
    outcome = reading.outcome
    if isinstance(outcome, Commanded):
        if outcome.command is Command.CANCEL:
            return cancel(progress)
        return _settle(progress, question.trade, TradeStatus.SKIPPED, model)
    if isinstance(outcome, NotRead):
        return _asked_again(progress, question, outcome)
    if isinstance(outcome, TwoTimes):
        return _asking(
            progress, question.trade, question.asked, model, (outcome.earlier, outcome.later)
        )
    trades = list(progress.trades)
    draft = trades[question.trade].draft
    assets = progress.setting.assets
    if isinstance(outcome, Confirmed) and isinstance(question.asked, ConfirmCoin):
        draft, assets = confirm(draft, assets, question.asked, outcome.confirmation)
    elif isinstance(outcome, Filled):
        draft = fill(draft, outcome)
    trades[question.trade] = TradeState(draft, TradeStatus.OPEN)
    setting = dataclasses.replace(progress.setting, assets=assets)
    progress = dataclasses.replace(progress, trades=tuple(trades), setting=setting)
    return _next_question(progress, model)


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


def _settle(progress: Progress, position: int, status: TradeStatus, model: ModelPort) -> Progress:
    trades = list(progress.trades)
    trades[position] = TradeState(trades[position].draft, status)
    return _next_question(dataclasses.replace(progress, trades=tuple(trades)), model)


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
