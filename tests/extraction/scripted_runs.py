"""Scripted runs for the extraction tests: the invented "now", the zone, and replies.

Names defined here: ``ZONE``, ``NOW``, ``row``, ``table`` and ``run``.
"""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from ledger_hand.extraction.extractor import Extraction, extract
from ledger_hand.extraction.reply_table import Field
from tests.fakes.scripted_model import ScriptedModel, Step

ZONE = "Europe/Budapest"
# An invented evening, so that "今天下午" and "9:40" lie in the past.
NOW = datetime(2026, 10, 5, 22, 0, tzinfo=ZoneInfo(ZONE))


def row(**cells: str) -> dict[str, str]:
    """A full row of the table: every field, empty unless given."""
    unknown = set(cells) - {field.value for field in Field}
    assert not unknown, unknown
    return {field.value: cells.get(field.value, "") for field in Field}


def table(*rows: object) -> str:
    """The text of a reply holding these rows."""
    return json.dumps({"trades": list(rows)}, ensure_ascii=False)


def run(passage: str, *steps: Step, **options: object) -> tuple[Extraction, ScriptedModel]:
    """Extract from ``passage`` with a scripted model that plays ``steps``."""
    model = ScriptedModel(steps)
    settings: dict[str, object] = {"now": NOW, "zone": ZONE, **options}
    return extract(passage, model, **settings), model  # type: ignore[arg-type]
