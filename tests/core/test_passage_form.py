"""Tests of the form a passage is compared in: only spacing and character width are let go."""

from __future__ import annotations

import pytest

from ledger_hand.core.passage_form import comparison_form

PASSAGE = "昨天买了 0.5 ETH，价格 3420"


@pytest.mark.parametrize(
    "same",
    [
        PASSAGE,
        f"  {PASSAGE}\n",
        "昨天买了   0.5\tETH，价格  3420",
        "昨天买了　0.5 ETH，价格 3420",
        "昨天买了 ０.５ ＥＴＨ，价格 ３４２０",
        "昨天买了 0.5 ETH,价格 3420",
        "\t昨天买了\n\n0.5  ＥＴＨ，价格　　3420 ",
    ],
)
def test_spacing_and_width_alone_give_the_same_form(same: str) -> None:
    assert comparison_form(same) == comparison_form(PASSAGE)


@pytest.mark.parametrize(
    "other",
    [
        "昨天买了 0.5 eth，价格 3420",
        "昨天买了0.5 ETH，价格 3420",
        "昨天买了 0.5 ETH。价格 3420",
        "昨天买了 0.6 ETH，价格 3420",
        "昨天买了 0.5 ETH，价格 3420！",
        "昨天买了 0.5 ETH，价格 3420²",
        "今天买了 0.5 ETH，价格 3420",
    ],
)
def test_any_other_difference_gives_another_form(other: str) -> None:
    assert comparison_form(other) != comparison_form(PASSAGE)


def test_only_full_and_half_width_characters_are_folded() -> None:
    assert comparison_form("ｱｲ ① ² ﬁ") == "アイ ① ² ﬁ"
    assert comparison_form("￠１００") == "¢100"


def test_the_form_is_plain_text_with_single_spaces_and_nothing_around_it() -> None:
    assert comparison_form("　 a \t\n b　") == "a b"
    assert comparison_form("") == ""
    assert comparison_form(" 　\t") == ""


def test_text_that_is_not_valid_unicode_is_kept_as_it_is() -> None:
    assert comparison_form("a\ud800 b") == "a\ud800 b"
