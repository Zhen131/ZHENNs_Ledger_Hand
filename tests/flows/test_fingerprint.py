"""Tests of a passage's fingerprint: the same for spacing and width alone, another otherwise."""

from __future__ import annotations

import hashlib

import pytest

from ledger_hand.flows.fingerprint import passage_fingerprint

PASSAGE = "昨天买了 0.5 ETH，价格 3420"


def test_the_fingerprint_is_the_sha256_of_the_comparison_form() -> None:
    digest = hashlib.sha256("昨天买了 0.5 ETH,价格 3420".encode()).hexdigest()

    assert passage_fingerprint(PASSAGE) == f"sha256:{digest}"
    assert len(passage_fingerprint(PASSAGE)) == 71


@pytest.mark.parametrize(
    "same", [f" {PASSAGE} ", "昨天买了  0.5　ETH，价格 3420", "昨天买了 ０.５ ＥＴＨ，价格 3420"]
)
def test_spacing_and_width_alone_keep_the_fingerprint(same: str) -> None:
    assert passage_fingerprint(same) == passage_fingerprint(PASSAGE)


@pytest.mark.parametrize("other", ["昨天买了 0.5 eth，价格 3420", "昨天买了0.5 ETH，价格 3420", ""])
def test_any_other_difference_changes_the_fingerprint(other: str) -> None:
    assert passage_fingerprint(other) != passage_fingerprint(PASSAGE)


def test_text_that_is_not_valid_unicode_still_has_one() -> None:
    assert passage_fingerprint("a\ud800").startswith("sha256:")
