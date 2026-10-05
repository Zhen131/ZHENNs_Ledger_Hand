"""Tests of reading the wording of a time phrase, before any calendar is looked at.

How those parts become dates and moments is tested with ``timeparse``; here
the point is which texts are read at all, and what their words say.
"""

from __future__ import annotations

from datetime import time, timedelta

import pytest

from ledger_hand.core.time_wording import (
    MAX_PHRASE_LENGTH,
    Clock,
    DayOfMonth,
    DaysBack,
    MonthDay,
    OnADay,
    Phrase,
    Refusal,
    RightNow,
    SpanBack,
    TimeCaution,
    Weekday,
    WeekReckoning,
    read_phrase,
)

NO_HALF = (TimeCaution.NO_HALF_OF_DAY,)
ONLY_A_HALF = (TimeCaution.ONLY_A_HALF_OF_DAY,)


@pytest.mark.parametrize(
    ("text", "phrase"),
    [
        ("刚才", RightNow()),
        ("3 小时前", SpanBack(timedelta(hours=3))),
        ("half an hour ago", SpanBack(timedelta(minutes=30))),
        ("三天前", OnADay(DaysBack(3))),
        ("上周五", OnADay(Weekday(4, WeekReckoning.LAST_WEEK))),
        ("上个周五", OnADay(Weekday(4, WeekReckoning.LAST))),
        ("last Friday", OnADay(Weekday(4, WeekReckoning.LAST))),
        ("周日", OnADay(Weekday(6, WeekReckoning.LATEST))),
        ("去年10月2号", OnADay(MonthDay(10, 2, years_back=1))),
        ("2026-10-02", OnADay(MonthDay(10, 2, year=2026))),
        ("Oct 2", OnADay(MonthDay(10, 2))),
        ("上个月15号", OnADay(DayOfMonth(15, months_back=1))),
        ("9点40", OnADay(DaysBack(0), Clock(9, 40), cautions=NO_HALF)),
        ("晚上9点40", OnADay(DaysBack(0), Clock(21, 40))),
        ("15:05:30", OnADay(DaysBack(0), Clock(15, 5, 30))),
        ("this afternoon", OnADay(DaysBack(0), not_before=time(12), cautions=ONLY_A_HALF)),
        ("昨天晚上9点40", OnADay(DaysBack(1), Clock(21, 40))),
    ],
)
def test_what_the_words_say(text: str, phrase: Phrase) -> None:
    assert read_phrase(text) == phrase


# --- the plain form ----------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "plain"),
    [
        ("ＹＥＳＴＥＲＤＡＹ", "yesterday"),
        ("昨天\N{IDEOGRAPHIC SPACE}晚上９点", "昨天晚上9点"),
        ("yesterday\N{NO-BREAK SPACE}at\N{NO-BREAK SPACE}9pm", "yesterday at 9pm"),
        ("11 o\N{RIGHT SINGLE QUOTATION MARK}clock", "11 o'clock"),
        ("3\tdays   ago", "3 days ago"),
        ("昨 天 晚 上 9 点 40", "昨天晚上9点40"),
    ],
)
def test_text_is_read_in_its_plain_form(text: str, plain: str) -> None:
    assert read_phrase(text) == read_phrase(plain)
    assert not isinstance(read_phrase(text), Refusal)


@pytest.mark.parametrize(
    "text",
    [
        "\N{MATHEMATICAL BOLD SMALL Y}esterday",
        "yesterday\N{ZERO WIDTH SPACE}",
        "yester\N{SOFT HYPHEN}day",
        "\N{KELVIN SIGN}",
        "3 \N{LATIN SMALL LETTER DOTLESS I}",
        "\N{ARABIC-INDIC DIGIT NINE}:40",
        "9\N{RATIO}40",
        "昨天\N{EM SPACE}晚上9点",
        "昨天\n晚上9点",
    ],
)
def test_a_character_outside_the_known_words_is_not_folded_into_one(text: str) -> None:
    assert read_phrase(text) is Refusal.UNKNOWN_WORDING


def test_a_text_at_the_length_limit_is_read_and_one_longer_is_not() -> None:
    padded = "昨天".ljust(MAX_PHRASE_LENGTH)

    assert read_phrase(padded) == OnADay(DaysBack(1))
    assert read_phrase(padded + " ") is Refusal.UNKNOWN_WORDING


# --- every part must be known ---------------------------------------------------

KNOWN_PHRASES = [
    "昨天晚上 9 点 40",
    "上周五下午三点",
    "yesterday at 9:40pm",
    "last Friday 3pm",
    "2026 年 10 月 2 日 15:05:30",
    "3 days ago at 9pm",
    "on Oct 2, 3pm",
    "20 分钟前",
]

STRANGERS = ["的", "#", "\N{ZERO WIDTH SPACE}", "左右", "?"]


@pytest.mark.parametrize("stranger", STRANGERS)
@pytest.mark.parametrize("text", KNOWN_PHRASES)
def test_an_unknown_piece_anywhere_makes_the_whole_text_unknown(text: str, stranger: str) -> None:
    assert not isinstance(read_phrase(text), Refusal)
    for place in range(len(text) + 1):
        changed = text[:place] + stranger + text[place:]
        assert read_phrase(changed) is Refusal.UNKNOWN_WORDING, changed


@pytest.mark.parametrize("text", KNOWN_PHRASES)
def test_a_known_phrase_said_twice_is_not_read(text: str) -> None:
    assert read_phrase(f"{text} {text}") is Refusal.UNKNOWN_WORDING


# --- halves of the day never move an hour into another part of the day ---------

# Where on a 24-hour clock each half of the day may land.
HALF_WORDS = {
    "凌晨": range(7),
    "早上": range(1, 12),
    "上午": range(1, 12),
    "中午": range(11, 15),
    "下午": range(13, 24),
    "傍晚": range(16, 21),
    "晚上": range(17, 24),
    "in the morning": range(1, 12),
    "in the afternoon": range(13, 24),
    "in the evening": range(17, 24),
    "at night": range(17, 24),
}


@pytest.mark.parametrize("hour", range(26))
@pytest.mark.parametrize(("word", "span"), HALF_WORDS.items())
def test_a_half_of_the_day_puts_the_hour_inside_it_or_is_ambiguous(
    word: str, span: range, hour: int
) -> None:
    text = f"{word}{hour}点" if not word.isascii() else f"at {hour} {word}"

    phrase = read_phrase(text)

    if isinstance(phrase, OnADay):
        assert phrase.clock is not None
        assert phrase.clock.hour in span
        assert phrase.cautions == ()
    else:
        # Past 23 there is no such hour, or it is midnight again (24 点).
        assert phrase is Refusal.AMBIGUOUS or hour > 23


@pytest.mark.parametrize("hour", range(26))
@pytest.mark.parametrize(("suffix", "span"), [("am", range(1, 12)), ("pm", range(12, 24))])
def test_am_and_pm_put_the_hour_in_their_half(suffix: str, span: range, hour: int) -> None:
    phrase = read_phrase(f"{hour}{suffix}")

    if isinstance(phrase, OnADay):
        assert phrase.clock is not None
        assert phrase.clock.hour in span
    elif hour == 12:
        assert phrase is Refusal.AMBIGUOUS
    else:
        assert phrase is Refusal.UNKNOWN_WORDING
