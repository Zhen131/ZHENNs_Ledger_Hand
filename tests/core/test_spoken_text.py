"""Tests of tidying what is said: what is handed back, and what is never touched.

Words with no Chinese character are handed back as they were; so are words
tidied already. Each change says what it was, and laid on the words said
the changes give the words tidied. Every figure is invented.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from evals.gold import DEBUG_SET, FINAL_SET, Split, load_set
from evals.voice import VOICE_SET
from evals.writings import WRITINGS_SET
from ledger_hand.core.spoken_text import SPOKEN_ZONES, Change, ChangeKind, tidy_spoken
from ledger_hand.core.zones import is_zone_name

ZONE = "Europe/Budapest"
DEMO = Path(__file__).resolve().parents[1] / "live" / "demo_sentences.json"
_CHINESE = re.compile("[一-鿿〇]")


def _english_sentences() -> list[str]:
    said = [
        sentence.text
        for path, split in (
            (DEBUG_SET, Split.DEBUG),
            (FINAL_SET, Split.FINAL),
            (VOICE_SET, Split.VOICE),
            (WRITINGS_SET, Split.WRITINGS),
        )
        for sentence in load_set(path, split)
    ]
    said += [one["said"] for one in json.loads(DEMO.read_text(encoding="utf-8"))["sentences"]]
    return [text for text in said if _CHINESE.search(text) is None]


ENGLISH = _english_sentences()


def test_there_are_english_sentences_to_try() -> None:
    assert len(ENGLISH) >= 10


@pytest.mark.parametrize("said", ENGLISH)
def test_words_with_no_chinese_character_are_handed_back_as_they_were(said: str) -> None:
    tidied = tidy_spoken(said, ZONE)

    assert tidied.text == said
    assert tidied.changes == ()
    assert not tidied.changed


def test_seconds_in_english_are_kept() -> None:
    said = "Bought 0.02 BTC at 9:40:15 on 20 November 2026"

    assert tidy_spoken(said, ZONE).text == said


def test_a_name_that_is_not_a_zone_is_a_mistake_of_the_caller() -> None:
    with pytest.raises(ValueError, match="not a time zone name"):
        tidy_spoken("二六年十月", "Budapest")


def test_every_spoken_zone_names_a_zone() -> None:
    assert all(is_zone_name(zone) for zone in SPOKEN_ZONES.values())


def test_each_change_says_what_it_was_where_it_was() -> None:
    said = "在匈牙利时间的二六年十一月二十号下午两点十二分三十秒花了三十五 USDT"

    tidied = tidy_spoken(said, ZONE)

    assert tidied.said == said
    assert tidied.text == "在2026年11月20号下午2点12分花了35 USDT"
    assert [change.kind for change in tidied.changes] == [
        ChangeKind.ZONE,
        ChangeKind.YEAR,
        ChangeKind.DATE,
        ChangeKind.DATE,
        ChangeKind.CLOCK,
        ChangeKind.CLOCK,
        ChangeKind.SECOND,
        ChangeKind.NUMBER,
    ]
    for change in tidied.changes:
        assert said[change.start : change.end] == change.said
    assert tidied.changes[0] == Change(ChangeKind.ZONE, "匈牙利时间的", "", 1, 7)


def test_the_changes_laid_on_the_words_said_give_the_words_tidied() -> None:
    said = "二六年的九月零七号的下午的十五点三十八分，卖了七百四十七点二七个ADA，手续费0.七五"
    tidied = tidy_spoken(said, ZONE)

    text, position = "", 0
    for change in tidied.changes:
        assert change.start >= position
        text += said[position : change.start] + change.written
        position = change.end

    assert text + said[position:] == tidied.text
    assert tidied.changed


def test_tidying_twice_changes_nothing_more() -> None:
    said = "二六年十一月二十号下午十四点十二分三十一秒买了零点零零五个BTC，布达佩斯时间"
    once = tidy_spoken(said, ZONE).text

    assert tidy_spoken(once, ZONE).text == once
    assert tidy_spoken(once, ZONE).changes == ()


def test_a_time_said_with_a_zone_at_the_start_loses_the_mark_after_it_too() -> None:
    assert tidy_spoken("匈牙利时间，十四点十二分买的", ZONE).text == "14点12分买的"


def test_a_time_said_with_the_same_zone_another_way_is_tidied_the_same() -> None:
    assert tidy_spoken("北京时间二六年十月三号下午三点", "Asia/Shanghai").text == (
        "2026年10月3号下午3点"
    )


def test_a_clock_with_shi_alone_is_not_taken_for_a_time() -> None:
    assert tidy_spoken("一时半会儿卖不掉", ZONE).text == "一时半会儿卖不掉"


def test_a_lone_day_or_month_is_left_as_it_was() -> None:
    assert tidy_spoken("一号钱包里有十二月买的币", ZONE).text == "一号钱包里有十二月买的币"
