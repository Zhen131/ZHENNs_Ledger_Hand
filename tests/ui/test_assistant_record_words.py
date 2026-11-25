"""Tests of what the pages say about the assistant's record: one sentence for every problem."""

from __future__ import annotations

import pytest

from ledger_hand.flows.assistant_record import NotKept, RecordProblem, RecordRead, Unreadable
from ledger_hand.ui import assistant_record_words as words


def test_every_problem_has_a_sentence() -> None:
    assert set(words.PROBLEMS) == set(RecordProblem)


@pytest.mark.parametrize(
    "problem", [p for p in RecordProblem if p is not RecordProblem.NO_DATA_FOLDER]
)
def test_a_reply_not_kept_says_it_was_still_done_and_where_to_look(
    problem: RecordProblem,
) -> None:
    said = words.not_kept_words(NotKept(problem, "invented detail"))

    assert said.startswith("This was done, but it was not kept in the assistant's record: ")
    assert words.PROBLEMS[problem] in said
    assert "(invented detail)" in said
    assert "Settings page" in said


def test_no_data_folder_is_said_as_no_record_this_time() -> None:
    assert words.not_kept_words(NotKept(RecordProblem.NO_DATA_FOLDER)) == words.NO_RECORD
    assert words.NO_RECORD.startswith("No record this time")


def test_the_count_says_none_one_many_or_why_it_cannot_be_read() -> None:
    one = {"format_version": 1}
    assert words.count_words(RecordRead(())).startswith("Entries: none yet.")
    assert words.count_words(RecordRead((one,))).startswith("Entries: 1 entry.")
    assert words.count_words(RecordRead((one,) * 1000)).startswith("Entries: 1,000 entries.")
    unreadable = Unreadable(RecordProblem.LINE_NOT_READ, "line 2")
    assert words.count_words(unreadable) == (
        f"Entries: cannot be read: {words.PROBLEMS[RecordProblem.LINE_NOT_READ]} (line 2)."
    )
