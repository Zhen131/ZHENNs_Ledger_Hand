"""Try extraction by hand: type a passage, see the drafts and the issues it gives.

    .venv/bin/python scripts/try_extraction.py "9:40 bought 0.02 BTC at 94,900, fee 2 USDT"
    echo "昨天卖了 2 ETH，价格 3,420" | .venv/bin/python scripts/try_extraction.py

The passage is the arguments, joined by spaces, or else everything on
standard input. It is sent to the model the settings name (see "Model
settings" in the README; by default ``qwen2.5:7b`` on this machine's
Ollama), and what comes back is printed: each draft, field by field, the
issues, and one line for each call to the model saying how long it took and
how many tokens it read and wrote.

The current moment is read from the machine's clock and the time zone is the
machine's own, read with ``tzlocal``. Both are read here, outside the
package, and handed in. A zone name the program does not take as it stands
stops the script; it is never replaced by another zone.

Nothing is written to disk, and the passage is not kept anywhere.

Exit status: 0 the passage was read (even when it holds no trade); 1 it was
not: the passage was refused, every reply missed the table, or the model
failed; 2 the script could not start: a setting is wrong or the machine's
zone is not a zone name the program takes.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import TextIO

import tzlocal

from ledger_hand.core.numbers import write_number
from ledger_hand.core.timeparse import write_time
from ledger_hand.core.trade import OccurredTime, TradeDraft
from ledger_hand.core.zones import is_zone_name
from ledger_hand.extraction.extractor import (
    Extracted,
    Extraction,
    ModelFailed,
    PassageRefused,
    ReplyUnreadable,
    extract,
)
from ledger_hand.extraction.issues import Issue
from ledger_hand.llm.connect import connect_model
from ledger_hand.ports import ModelPort, ReplyRecord
from ledger_hand.settings import SettingsError, load_model_settings

_NOTHING = "-"


def main(
    arguments: Sequence[str],
    *,
    read_input: Callable[[], str] = sys.stdin.read,
    out: TextIO = sys.stdout,
    model: ModelPort | None = None,
    now: datetime | None = None,
    zone: str | None = None,
) -> int:
    """Run the script; the keyword arguments stand in for the outside world in tests."""
    passage = " ".join(arguments) if arguments else read_input()
    if zone is None:
        zone = _machine_zone()
        if zone is None:
            print("cannot tell the machine's time zone by a name the program takes", file=out)
            return 2
    if model is None:
        model = _model(out)
        if model is None:
            return 2
    result = extract(passage, model, now=now or datetime.now(timezone.utc), zone=zone)
    show_result(result, passage, zone, out)
    return 0 if isinstance(result, Extracted) else 1


def _machine_zone() -> str | None:
    """The machine's zone name as tzlocal reads it, if the program takes it as it stands."""
    try:
        name = tzlocal.get_localzone_name()
    except (LookupError, OSError, ValueError):
        return None
    return name if is_zone_name(name) else None


def _model(out: TextIO) -> ModelPort | None:
    try:
        return connect_model(load_model_settings())
    except SettingsError as error:
        print(f"setting refused: {error}", file=out)
        return None


def show_result(result: Extraction, passage: str, zone: str, out: TextIO) -> None:
    """Print what extraction gave for ``passage``: the drafts, the issues and the calls."""
    print(f"passage: {passage!r}", file=out)
    print(f"zone:    {zone}", file=out)
    if isinstance(result, PassageRefused):
        print(f"not sent: {result.problem.value}", file=out)
        return
    if isinstance(result, ModelFailed):
        print(f"model failed: {result.error}", file=out)
    elif isinstance(result, ReplyUnreadable):
        problems = "; ".join(problem.value for problem in result.problems)
        print(f"no reply could be read: {problems}", file=out)
    else:
        _show_drafts(result, out)
    _show_calls(result.calls, out)


def _show_drafts(result: Extracted, out: TextIO) -> None:
    if not result.drafts:
        print("no trade", file=out)
    for position, draft in enumerate(result.drafts):
        print(f"trade {position + 1}", file=out)
        for label, value in _fields(draft):
            print(f"  {label:<15} {value}", file=out)
    print("issues" if result.issues else "issues: none", file=out)
    for issue in result.issues:
        print(f"  {_issue_line(issue)}", file=out)


def _fields(draft: TradeDraft) -> list[tuple[str, str]]:
    def number(value: object) -> str:
        return _NOTHING if value is None else write_number(value)  # type: ignore[arg-type]

    return [
        ("side", _NOTHING if draft.side is None else draft.side.value),
        ("coin", draft.coin or _NOTHING),
        ("quantity", number(draft.quantity)),
        ("price", number(draft.price)),
        ("total", number(draft.total)),
        ("price currency", draft.quote or _NOTHING),
        ("fee", number(draft.fee)),
        ("fee currency", draft.fee_coin or _NOTHING),
        ("time", _NOTHING if draft.occurred is None else _time(draft.occurred)),
        ("platform", draft.platform or _NOTHING),
        ("opinion", draft.note or _NOTHING),
    ]


def _time(occurred: OccurredTime) -> str:
    return f"{write_time(occurred)} ({occurred.precision.value})"


def _issue_line(issue: Issue) -> str:
    where = "passage" if issue.draft is None else f"trade {issue.draft + 1}"
    if issue.field is not None:
        where += f", {issue.field.value}"
    line = f"{where}: {issue.kind.value}"
    if issue.cause is not None:
        line += f" ({issue.cause.value})"
    if issue.phrase is not None:
        line += f" [{issue.phrase!r}]"
    if issue.candidates:
        line += ": " + " or ".join(_time(candidate) for candidate in issue.candidates)
    if issue.numbers:
        line += ": " + ", ".join(issue.numbers)
    if issue.same_as is not None:
        line += f": the same as trade {issue.same_as + 1}"
    return line


def _show_calls(calls: tuple[ReplyRecord, ...], out: TextIO) -> None:
    for number, call in enumerate(calls, start=1):
        print(
            f"call {number}: {call.model}, {call.elapsed_seconds:.2f} s, "
            f"{call.prompt_tokens} tokens read, {call.reply_tokens} written, {call.finish.value}",
            file=out,
        )


if __name__ == "__main__":
    # A passage with characters the terminal cannot show is still shown, escaped.
    sys.stdout.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
    sys.exit(main(sys.argv[1:]))
