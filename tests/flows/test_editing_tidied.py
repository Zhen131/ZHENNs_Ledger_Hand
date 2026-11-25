"""Tests of a new value said in number words: tidied first, the model's digits are the user's.

What the user says is tidied before the model sees it, so a new value said
in Chinese number words is in digits by then, and the model's copy of it in
digits is a copy of the user's words. Every sentence and figure is invented.
"""

from __future__ import annotations

from decimal import Decimal

from tests.flows.test_editing import proposed, talk, update


def test_a_new_value_said_in_number_words_is_known_once_tidied_and_proposed() -> None:
    (said, answered), _, ledger = talk(
        "把9月25号那笔ADA的数量改成六百四十一",
        "total",
        steps=[update(period="9月25号", asset="ADA", field="quantity", new_value="641")],
    )

    assert said.read_as is not None
    assert said.read_as.text == "把9月25号那笔ADA的数量改成641"
    assert said.edit_sent is None
    assert answered.edit_sent is not None
    assert answered.edit_sent.trade == "t-03"
    assert answered.edited is not None and answered.edited.after is not None
    assert answered.edited.after.quantity == Decimal("641")
    assert proposed(ledger) == ["propose_update"]
