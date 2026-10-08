"""Shared pieces of the flow tests: the invented "now", the zone, and the replies to script.

Names defined here: ``ZONE``, ``NOW``, ``screened``, ``copied``, ``worded``,
``begin``, ``walk`` and ``row``/``table`` (from the extraction tests).
"""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from ledger_hand.flows.progress import Progress
from ledger_hand.flows.recording import answer, start
from tests.extraction.scripted_runs import row, table
from tests.fakes.routed_model import RoutedModel

__all__ = ["NOW", "ZONE", "begin", "copied", "row", "screened", "table", "walk", "worded"]

ZONE = "Europe/Budapest"
# An invented evening, so that "今天下午" and "昨天" lie in the past.
NOW = datetime(2026, 10, 7, 21, 0, tzinfo=ZoneInfo(ZONE))


def screened(*reports: tuple[str, str]) -> str:
    """A reply of the judging step listing ``reports`` as (kind, evidence)."""
    items = [{"kind": kind, "evidence": evidence} for kind, evidence in reports]
    return json.dumps({"reports": items}, ensure_ascii=False)


def copied(phrase: str) -> str:
    """A reply of the answer-reading step copying ``phrase``."""
    return json.dumps({"phrase": phrase}, ensure_ascii=False)


def worded(question: str) -> str:
    """A reply of the question-wording step."""
    return json.dumps({"question": question}, ensure_ascii=False)


def begin(passage: str, model: RoutedModel) -> Progress:
    return start(passage, model, now=NOW, zone=ZONE)


def walk(progress: Progress, model: RoutedModel, *answers: str) -> list[Progress]:
    """Every progress after each of ``answers``, the first being ``progress`` itself."""
    seen = [progress]
    for given in answers:
        seen.append(answer(seen[-1], given, model))
    return seen
