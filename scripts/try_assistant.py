"""Try the assistant by hand: say one or more things, see every step it takes.

    .venv/bin/python scripts/try_assistant.py "我现在手里有哪些币"
    .venv/bin/python scripts/try_assistant.py "我10月一共买了多少钱的币" "那9月呢"
    .venv/bin/python scripts/try_assistant.py "What do I hold?" "And which assets are there?"
    .venv/bin/python scripts/try_assistant.py "今天下午OKX 25U买了点ETH" "下午3点" "手续费0.01 USDT"
    .venv/bin/python scripts/try_assistant.py --save "Bought 0.02 BTC at 94900 at 9:40, fee 2 USDT."
    .venv/bin/python scripts/try_assistant.py --clock "What do I hold?"
    .venv/bin/python scripts/try_assistant.py --help

Each argument is one thing the user says, in order, in one chat. They are
sent to the model the settings name (by default ``qwen2.5:7b`` on this
machine's Ollama), with the fake ledger and its demo book behind the tools
(``ledger.demo_book``: the invented book with more assets, among them
shares with Chinese names, and buys in August 2026). For each thing said
it prints which way it went (the model chose the
tools, it was taken as the answer to the question waiting, or the program
took over after two wrong steps), after a line "read as: ..." when the
words were tidied first (number words and a time said in Chinese written
in digits, as the assistant reads them); for each step, what the model asked for
and with what, and what was handed back, or why the call was a wrong step,
or that it was not run because its step went to recording. A read tool's
call is followed by the table the program laid out of what the ledger
found: the header first (the days, the asset and the side it was looked up
with, and anything the model asked for that was not used), then one line a
row, every figure as the ledger gave it. When a trade is
recorded, it prints how many times the recording asked the model (counted
apart from the steps), the table of the trades sent, laid out from the
proposal itself, and one line from the program saying what reached the
ledger ("sent to the ledger: nothing" when nothing did); then who wrote
the last words ("words by: the model", or the program, and when the
model's words were withheld, why), the assistant's last words and how it
ended; just before the ending, when a question waits for its answer, what
it asks about ("asked about: time", the cell's name; "new-coin" when it
asks whether a word is a coin; "which-cell" when it asks which value is
wrong).
``LEDGER_HAND_ASSISTANT_STEPS``
says how many times the model may be asked in one turn (six by default).
When a question waits, the next argument is its answer.

"Now" is the invented book's fixed moment, 24 November 2026, 23:55 in
Budapest, since the demo book's trades are written against it; ``--clock`` takes the
machine's clock and zone instead. Which "now" is used is printed first.
``--save`` or ``--reject`` saves or rejects, once everything is said, every
proposal still pending in the fake ledger, as the person would on the
ledger's own page, and prints how many trades the book holds before and
after, the trades added, and each trade changed (before and after) or
deleted. The options come before the sentences.
``--help`` or ``-h``, given alone, prints this text and does nothing else.

The assistant runs on the local plug only: with the cloud plug set, the
script refuses before anything is sent. Nothing is written to disk.

Exit status: 0 everything said was done, or the user was told why not (the
model answered, a question waits, a proposal was sent, or nothing was sent
and the program said why), or this text was printed; 1 something said was
not: the model or the ledger failed, the step limit was reached, or the
program took over and still could not do it; 2 the script could not start:
nothing to say, an option given twice or both of ``--save`` and
``--reject``, a setting is wrong, the cloud plug is set, or the machine's
zone is not a zone name the program takes.
"""

from __future__ import annotations

import enum
import json
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import TextIO

import tzlocal

from ledger_hand.assistant.lookups import lookup_lines
from ledger_hand.assistant.outcome import (
    Chat,
    Ending,
    NotRunCall,
    RefusedCall,
    Step,
    TurnResult,
)
from ledger_hand.assistant.results import not_done_text
from ledger_hand.core.followup import AskCell, ConfirmCoin
from ledger_hand.core.ledger_records import TradeFacts, TradeFilter
from ledger_hand.core.proposals import ProposalStatus
from ledger_hand.core.zones import is_zone_name
from ledger_hand.flows.conversation import AssistantChat, Route, Said, say
from ledger_hand.flows.progress import DEFAULT_TUNING, Asked, Tuning
from ledger_hand.flows.recording import tuning_from
from ledger_hand.ledger.demo_book import demo_ledger
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.llm.connect import connect_model
from ledger_hand.ports import ModelPort
from ledger_hand.settings import (
    Plug,
    SettingsError,
    Variable,
    load_assistant_steps,
    load_model_settings,
)

_ASKING_FOR_HELP = frozenset({"--help", "-h"})
_CLOCK = "--clock"


class Afterwards(enum.Enum):
    """What is done, once everything is said, with the proposals still pending."""

    SAVE = "--save"
    REJECT = "--reject"


_OPTIONS = frozenset({_CLOCK, *(option.value for option in Afterwards)})


def main(
    arguments: Sequence[str],
    *,
    out: TextIO = sys.stdout,
    model: ModelPort | None = None,
    ledger: FakeLedger | None = None,
    max_steps: int | None = None,
) -> int:
    """Run the script; the keyword arguments stand in for the outside world in tests."""
    if len(arguments) == 1 and arguments[0] in _ASKING_FOR_HELP:
        print((__doc__ or "usage: scripts/try_assistant.py sentence...").strip(), file=out)
        return 0
    parsed = _options(arguments, out)
    if parsed is None:
        return 2
    on_the_clock, afterwards, sentences = parsed
    moment = _moment(out) if on_the_clock else (INVENTED_NOW, INVENTED_ZONE, "the invented book's")
    if moment is None:
        return 2
    now, zone, whose = moment
    tuning = DEFAULT_TUNING
    if model is None or max_steps is None:
        built = _model_and_steps(out)
        if built is None:
            return 2
        model, max_steps, tuning = model or built[0], max_steps or built[1], built[2]
    ledger = ledger or demo_ledger()
    print(f"now:    {now.isoformat()} in {zone} ({whose} moment)", file=out)
    print(f"model:  {getattr(model, 'name', None) or _model_name()}", file=out)
    print(f"ledger: {type(ledger).__name__}; at most {max_steps} steps a turn", file=out)
    state = AssistantChat()
    all_well = True
    for words in sentences:
        said = say(
            state,
            words,
            model=model,
            ledger=ledger,
            now=now,
            zone=zone,
            max_steps=max_steps,
            tuning=tuning,
        )
        show_said(words, said, out)
        all_well = all_well and said.well_ended
        state = said.state
    if afterwards is not None:
        _then(afterwards, state.chat, ledger, out)
    return 0 if all_well else 1


def _options(
    arguments: Sequence[str], out: TextIO
) -> tuple[bool, Afterwards | None, list[str]] | None:
    """The options at the front, then the sentences; ``None`` when they cannot be taken."""
    given: list[str] = []
    for argument in arguments:
        if argument not in _OPTIONS:
            break
        given.append(argument)
    sentences = list(arguments[len(given) :])
    afterwards = [option for option in Afterwards if option.value in given]
    if len(set(given)) != len(given) or len(afterwards) > 1:
        print(
            f"give each option once, and only one of {Afterwards.SAVE.value} and "
            f"{Afterwards.REJECT.value}",
            file=out,
        )
        return None
    if not sentences:
        print("nothing to say: give one or more sentences", file=out)
        return None
    return _CLOCK in given, (afterwards[0] if afterwards else None), sentences


def _moment(out: TextIO) -> tuple[datetime, str, str] | None:
    """The machine's clock and zone, if the program takes the zone's name as it stands."""
    try:
        name = tzlocal.get_localzone_name()
    except (LookupError, OSError, ValueError):
        name = None
    if name is None or not is_zone_name(name):
        print("cannot tell the machine's time zone by a name the program takes", file=out)
        return None
    return datetime.now(timezone.utc), name, "the machine's"


def _model_and_steps(out: TextIO) -> tuple[ModelPort, int, Tuning] | None:
    try:
        settings = load_model_settings()
        steps = load_assistant_steps()
    except SettingsError as error:
        print(f"setting refused: {error}", file=out)
        return None
    if settings.plug is Plug.CLOUD:
        print(
            f"the assistant runs on the local plug only; set {Variable.PLUG.value} "
            f"to {Plug.LOCAL.value}",
            file=out,
        )
        return None
    return connect_model(settings), steps, tuning_from(settings)


def _model_name() -> str:
    """The model the settings name, or a word saying it is not known."""
    try:
        return load_model_settings().model
    except SettingsError:
        return "unknown"


def show_said(words: str, said: Said, out: TextIO) -> None:
    """Print one thing said: the way it went, each step, the recording, the last words."""
    print(f"\nyou said: {words}", file=out)
    if said.read_as is not None and said.read_as.changed:
        print(f"read as: {said.read_as.text}", file=out)
    print(f"route: {said.route.value}", file=out)
    turn = said.turn
    for number, step in enumerate(turn.steps if turn is not None else (), start=1):
        _show_step(number, step, out)
    recorded = said.recorded
    if recorded is not None:
        asked = len(recorded.progress.calls)
        print(
            f"recording: {asked} call(s) to the model for this passage so far, "
            "apart from the steps",
            file=out,
        )
        for number, trade in zip(recorded.numbers, recorded.trades, strict=True):
            print(f"  trade {number}: {trade_line(trade)}", file=out)
    failure = turn.failure if turn is not None else None
    if recorded is not None and recorded.failure is not None:
        failure = recorded.failure
    if failure is not None:
        print(f"failure: {type(failure).__name__}: {failure}", file=out)
    if said.edited is not None and said.edited.failure is not None:
        failure = said.edited.failure
        print(f"failure: {type(failure).__name__}: {failure}", file=out)
    _show_end(said, out)


def _show_end(said: Said, out: TextIO) -> None:
    """Print what reached the ledger, who wrote the last words, them, the ending, what is asked."""
    turn, recorded = said.turn, said.recorded
    sent = said.sent
    to_ledger = f"{sent.proposal}, {sent.trades} trade(s)" if sent is not None else "nothing"
    edit_sent = said.edit_sent
    if edit_sent is not None:
        to_ledger = f"{edit_sent.proposal}, {edit_sent.kind.value} of {edit_sent.trade}"
    print(f"sent to the ledger: {to_ledger}", file=out)
    by_the_model = recorded is None and said.edited is None and turn is not None
    print(f"words by: {_words_by(turn) if by_the_model else 'the program'}", file=out)
    print(f"assistant: {said.reply or '-'}", file=out)
    question = recorded.question if recorded is not None else None
    if question is not None:
        print(f"asked about: {asked_about(question.asked)}", file=out)
    print(f"ending: {_ending(said)}", file=out)


def asked_about(asked: Asked) -> str:
    """What a question asks about, in one word: a cell's name, ``new-coin`` or ``which-cell``."""
    if isinstance(asked, AskCell):
        return asked.cell.value
    if isinstance(asked, ConfirmCoin):
        return "new-coin"
    return "which-cell"


def show_turn(said: str, result: TurnResult, out: TextIO) -> None:
    """Print one turn of the model alone: what was said, each step, the last words, the end."""
    print(f"\nyou said: {said}", file=out)
    for number, step in enumerate(result.steps, start=1):
        _show_step(number, step, out)
    if result.failure is not None:
        print(f"failure: {type(result.failure).__name__}: {result.failure}", file=out)
    print(f"words by: {_words_by(result)}", file=out)
    print(f"assistant: {result.reply or '-'}", file=out)
    print(f"ending: {result.ending.value}", file=out)


def _show_step(number: int, step: Step, out: TextIO) -> None:
    if not step.calls:
        print(f"step {number}: the model answered", file=out)
        return
    print(f"step {number}: the model asked for {len(step.calls)} tool(s)", file=out)
    for handled in step.calls:
        arguments = json.dumps(dict(handled.call.arguments), ensure_ascii=False)
        print(f"  {handled.call.name} {arguments}", file=out)
        if isinstance(handled, RefusedCall):
            print(
                f"    wrong step ({handled.misstep.kind.value}): {handled.misstep.detail}",
                file=out,
            )
        elif isinstance(handled, NotRunCall):
            if handled.result == not_done_text():
                print("    not run: one change or deletion at a time", file=out)
            else:
                print("    not run: its step went to recording", file=out)
        else:
            if handled.dropped:
                print(f"    dropped, unread: {', '.join(handled.dropped)}", file=out)
            print(f"    handed back: {handled.result}", file=out)
            if handled.lookup is not None:
                print("    table:", file=out)
                for line in lookup_lines(handled.lookup):
                    print(f"      {line}", file=out)


def _words_by(result: TurnResult) -> str:
    """Who wrote the last words of a turn: the model, or the program, and why."""
    if result.ending is not Ending.ANSWERED:
        return "the program"
    if result.withheld is not None:
        return f"the program (the model's words were withheld: {result.withheld.reason})"
    return "the model"


def _ending(said: Said) -> str:
    turn, recorded = said.turn, said.recorded
    if said.edited is not None:
        if said.route is Route.TAKEOVER and turn is not None:
            return f"{turn.ending.value}, taken over: {said.edited.ending.value}"
        return said.edited.ending.value
    if said.route is Route.TAKEOVER and turn is not None and recorded is not None:
        return f"{turn.ending.value}, taken over: {recorded.ending.value}"
    if recorded is not None:
        return recorded.ending.value
    return turn.ending.value if turn is not None else "-"


def trade_line(trade: TradeFacts) -> str:
    """One trade on one line, every figure as the proposal holds it, written out in full."""
    quantity, price, total, fee = (
        format(value, "f") for value in (trade.quantity, trade.price, trade.total, trade.fee)
    )
    return (
        f"{trade.occurred.isoformat()} {trade.side.value} {quantity} {trade.asset} "
        f"at {price} {trade.quote}, total {total} {trade.quote}, "
        f"fee {fee} {trade.fee_asset}, platform {trade.platform or '-'}, "
        f"note {trade.note or '-'}"
    )


def _then(afterwards: Afterwards, chat: Chat, ledger: FakeLedger, out: TextIO) -> None:
    """Save or reject every proposal still pending, and show the book before and after."""
    before = ledger.list_trades(TradeFilter()).trades
    print(f"\nthen: {afterwards.value}", file=out)
    for proposal in (one for sent in chat.proposals for one in sent):
        status = ledger.proposal_status(proposal).status
        if status is not ProposalStatus.PENDING:
            print(f"{proposal}: {status.value}, left as it is", file=out)
            continue
        if afterwards is Afterwards.SAVE:
            ledger.save(proposal)
        else:
            ledger.reject(proposal)
        print(f"{proposal}: pending -> {ledger.proposal_status(proposal).status.value}", file=out)
    after = ledger.list_trades(TradeFilter()).trades
    print(f"trades in the fake ledger: {len(before)} before, {len(after)} after", file=out)
    known = {trade.id for trade in before}
    added = [trade for trade in after if trade.id not in known]
    for trade in added:
        print(f"  added {trade.id}: {trade_line(trade.facts)}", file=out)
    if not added:
        print("  added: none", file=out)
    now = {trade.id: trade.facts for trade in after}
    for trade in before:
        if trade.id not in now:
            print(f"  deleted {trade.id}: {trade_line(trade.facts)}", file=out)
        elif now[trade.id] != trade.facts:
            print(f"  changed {trade.id}, before: {trade_line(trade.facts)}", file=out)
            print(f"  changed {trade.id}, after:  {trade_line(now[trade.id])}", file=out)


if __name__ == "__main__":
    # Words the terminal cannot show are still shown, escaped.
    sys.stdout.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
    sys.exit(main(sys.argv[1:]))
