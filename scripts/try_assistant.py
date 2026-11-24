"""Try the assistant by hand: say one or more things, see every step it takes.

    .venv/bin/python scripts/try_assistant.py "我现在手里有哪些币"
    .venv/bin/python scripts/try_assistant.py "What do I hold?" "And which assets are there?"
    .venv/bin/python scripts/try_assistant.py --clock "What do I hold?"
    .venv/bin/python scripts/try_assistant.py --help

Each argument is one thing the user says, in order, in one chat. They are
sent to the model the settings name (by default ``qwen2.5:7b`` on this
machine's Ollama), with the fake ledger and its invented book behind the
tools. For each step it prints what the model asked for and with what, and
what was handed back, or why the call was a wrong step (a copied argument
that is not the user's words among them); then the assistant's last words
and why the turn ended. ``LEDGER_HAND_ASSISTANT_STEPS`` says how many times
the model may be asked in one turn (six by default).

"Now" is the invented book's fixed moment, 24 November 2026, 23:55 in
Budapest, since its trades are written against it; ``--clock`` takes the
machine's clock and zone instead. Which "now" is used is printed first.
``--help`` or ``-h``, given alone, prints this text and does nothing else.

The assistant runs on the local plug only: with the cloud plug set, the
script refuses before anything is sent. Nothing is written to disk.

Exit status: 0 every turn ended with the model's answer, or this text was
printed; 1 a turn did not (stopped, or a failure); 2 the script could not
start: nothing to say, a setting is wrong, the cloud plug is set, or the
machine's zone is not a zone name the program takes.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import TextIO

import tzlocal

from ledger_hand.assistant.outcome import Chat, Ending, RefusedCall, TurnResult
from ledger_hand.core.zones import is_zone_name
from ledger_hand.flows.assisting import take_turn
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.llm.connect import connect_model
from ledger_hand.ports import LedgerPort, ModelPort
from ledger_hand.settings import (
    Plug,
    SettingsError,
    Variable,
    load_assistant_steps,
    load_model_settings,
)

_ASKING_FOR_HELP = frozenset({"--help", "-h"})
_CLOCK = "--clock"


def main(
    arguments: Sequence[str],
    *,
    out: TextIO = sys.stdout,
    model: ModelPort | None = None,
    ledger: LedgerPort | None = None,
    max_steps: int | None = None,
) -> int:
    """Run the script; the keyword arguments stand in for the outside world in tests."""
    if len(arguments) == 1 and arguments[0] in _ASKING_FOR_HELP:
        print((__doc__ or "usage: scripts/try_assistant.py sentence...").strip(), file=out)
        return 0
    on_the_clock = bool(arguments) and arguments[0] == _CLOCK
    sentences = list(arguments[1:] if on_the_clock else arguments)
    if not sentences:
        print("nothing to say: give one or more sentences", file=out)
        return 2
    moment = _moment(out) if on_the_clock else (INVENTED_NOW, INVENTED_ZONE, "the invented book's")
    if moment is None:
        return 2
    now, zone, whose = moment
    if model is None or max_steps is None:
        built = _model_and_steps(out)
        if built is None:
            return 2
        model, max_steps = model or built[0], max_steps or built[1]
    ledger = ledger or FakeLedger()
    print(f"now:    {now.isoformat()} in {zone} ({whose} moment)", file=out)
    print(f"model:  {getattr(model, 'name', None) or _model_name()}", file=out)
    print(f"ledger: {type(ledger).__name__}; at most {max_steps} steps a turn", file=out)
    chat = Chat()
    every_turn_answered = True
    for said in sentences:
        result = take_turn(
            chat, said, model=model, ledger=ledger, now=now, zone=zone, max_steps=max_steps
        )
        show_turn(said, result, out)
        every_turn_answered = every_turn_answered and result.ending is Ending.ANSWERED
        chat = result.chat
    return 0 if every_turn_answered else 1


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


def _model_and_steps(out: TextIO) -> tuple[ModelPort, int] | None:
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
    return connect_model(settings), steps


def _model_name() -> str:
    """The model the settings name, or a word saying it is not known."""
    try:
        return load_model_settings().model
    except SettingsError:
        return "unknown"


def show_turn(said: str, result: TurnResult, out: TextIO) -> None:
    """Print one turn: what was said, each step, the last words and why it ended."""
    print(f"\nyou said: {said}", file=out)
    for number, step in enumerate(result.steps, start=1):
        if not step.calls:
            print(f"step {number}: the model answered", file=out)
            continue
        print(f"step {number}: the model asked for {len(step.calls)} tool(s)", file=out)
        for handled in step.calls:
            arguments = json.dumps(dict(handled.call.arguments), ensure_ascii=False)
            print(f"  {handled.call.name} {arguments}", file=out)
            if isinstance(handled, RefusedCall):
                print(
                    f"    wrong step ({handled.misstep.kind.value}): {handled.misstep.detail}",
                    file=out,
                )
            else:
                print(f"    handed back: {handled.result}", file=out)
    if result.failure is not None:
        print(f"failure: {type(result.failure).__name__}: {result.failure}", file=out)
    print(f"assistant: {result.reply or '-'}", file=out)
    print(f"ending: {result.ending.value}", file=out)


if __name__ == "__main__":
    # Words the terminal cannot show are still shown, escaped.
    sys.stdout.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
    sys.exit(main(sys.argv[1:]))
