"""Tests of the assistant matching a name of an asset itself: by its table and by the answers.

A scripted model stands in for every call, and a fake ledger for the
ledger. What is checked, one test a case: a name of the table the ledger
has is sent, marked as taken from the table and said so; one the ledger
lacks is told, asked nothing and not sent; a name with two codes is
matched only when the ledger has exactly one; an answer to "which asset"
is kept, used the next time, for the same kind of ledger only, and only
while the ledger has the code; general words and words not said are never
kept; a later answer wins; an answer wins over the table; a broken file is
used as far as it can be and never written; each switch on its own; a
screenshot's text; and the Record page's way, which never matches. Every
file is in a temporary folder, and every sentence and figure is invented.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import pytest

from ledger_hand.core.ledger_records import Asset, AssetKind, Pricing
from ledger_hand.core.ledger_table import table_of
from ledger_hand.core.marks import Field, MarkKind
from ledger_hand.extraction.picture_reading import PictureRead
from ledger_hand.flows import conversation, recording
from ledger_hand.flows.asset_names import NamesFile, remember
from ledger_hand.flows.conversation import (
    AssistantChat,
    Said,
    ScreenshotText,
    say,
    say_from_reading,
)
from ledger_hand.flows.recorded import LeftOut, RecordEnding
from ledger_hand.flows.standing import LedgerKind
from ledger_hand.ledger.demo_book import DEMO_ASSETS, demo_ledger
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_ASSETS, INVENTED_NOW, INVENTED_ZONE
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import Step as ScriptStep
from tests.flows.scripted_flow import copied, screened, table
from tests.flows.test_conversation_asset_pick import RECORD, row_of, said_as

# The day of the invented book's moment: the day an answer is kept with.
TODAY = INVENTED_NOW.date().isoformat()


def stock(code: str, name: str) -> Asset:
    return Asset(
        id=f"asset-{code.lower()}",
        code=code,
        name=name,
        kind=AssetKind.STOCK,
        pricing=Pricing.CANNOT_PRICE,
    )


def ledger_with(*stocks: Asset) -> FakeLedger:
    """A ledger of the US dollar, USDT and ``stocks`` alone, with no trade."""
    return FakeLedger(assets=(*INVENTED_ASSETS[:2], *stocks), trades=())


def model_for(words: str, coin: str, answers: Sequence[ScriptStep] = ()) -> RoutedModel:
    return RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", words.split("，")[0]))],
        extraction=[table(row_of(coin))],
        answers=answers,
    )


def talk(
    coin: str,
    *answers: str,
    ledger: FakeLedger | None = None,
    names: NamesFile | None = None,
    name_table: bool | None = True,
    said: str | None = None,
) -> tuple[list[Said], RoutedModel]:
    """``said`` (the sentence for ``coin`` by default) in a new chat, then each answer; the
    table on unless ``name_table`` says otherwise (``None``: the default, off)."""
    words = said if said is not None else said_as(coin)
    model = model_for(words, coin, [copied(answer) for answer in answers])
    ledger = ledger if ledger is not None else demo_ledger()
    state = AssistantChat()
    seen = []
    for one in (words, *answers):
        done = say(
            state,
            one,
            model=model,
            ledger=ledger,
            now=INVENTED_NOW,
            zone=INVENTED_ZONE,
            max_steps=6,
            name_table=name_table,
            names=names,
        )
        seen.append(done)
        state = done.state
    return seen, model


def calls(model: RoutedModel) -> int:
    return sum(
        len(one.calls)
        for one in (model.screen, model.extraction, model.questions, model.answers, model.tools)
    )


def asset_mark(said: Said) -> str:
    """The reason of the asset cell's mark of the one trade sent; it must be assumed."""
    assert said.recorded is not None
    (marked,) = said.recorded.marked
    (mark,) = [one for one in marked.marks.marks if one.field is Field.ASSET_ID]
    assert mark.kind is MarkKind.INFERRED and mark.reason is not None
    return mark.reason


def kept(place: Path, kind: str = "demo") -> list[dict[str, str]]:
    if not place.exists():
        return []
    entries: list[dict[str, str]] = json.loads(place.read_text(encoding="utf-8"))[kind]
    return entries


# --- 1. the table has it, and the ledger has it ------------------------------------------


def test_a_name_of_the_table_the_ledger_has_is_sent_marked_and_said() -> None:
    (said,), model = talk("微软的股票")
    (off,), off_model = talk("微软的股票", name_table=False)

    assert said.recorded is not None and said.recorded.ending is RecordEnding.SENT
    assert [trade.asset for trade in said.recorded.trades] == ["MSFT"]
    reason = asset_mark(said)
    assert all(part in reason for part in ("微软的股票", "MSFT", "Microsoft", "table"))
    line = (
        'Took "微软的股票" as MSFT (Microsoft) from the program\'s table of common company '
        "names. Please check it before you confirm."
    )
    assert line in said.reply.splitlines()
    assert said.reply.count(line) == 1
    assert off.recorded is not None and off.recorded.ending is RecordEnding.ASKING
    assert calls(model) <= calls(off_model)
    assert model.picks.calls == []


# --- 2. the table has it, and the ledger does not ----------------------------------------


def test_a_name_whose_code_the_ledger_lacks_is_told_and_nothing_is_asked_or_sent() -> None:
    (said,), model = talk("特斯拉")

    assert said.recorded is not None
    assert said.recorded.ending is RecordEnding.NOTHING_TO_SEND
    assert said.sent is None
    (left,) = said.recorded.left_out
    assert (left.why, left.codes, left.reason) == (LeftOut.NAME_NOT_IN_LEDGER, ("TSLA",), "特斯拉")
    assert "TSLA" in said.reply and "特斯拉" in said.reply
    assert "add it in the ledger first" in said.reply
    assert model.questions.calls == []


# --- 3. one name, two codes --------------------------------------------------------------


def test_one_code_of_two_in_the_ledger_is_matched() -> None:
    (said,), _ = talk("谷歌", ledger=ledger_with(stock("GOOGL", "Alphabet A")))

    assert said.recorded is not None and said.recorded.ending is RecordEnding.SENT
    assert [trade.asset for trade in said.recorded.trades] == ["GOOGL"]


def test_both_codes_in_the_ledger_are_asked_about_and_the_answer_is_kept(
    tmp_path: Path,
) -> None:
    place = tmp_path / "asset-names.json"
    ledger = ledger_with(stock("GOOGL", "Alphabet A"), stock("GOOG", "Alphabet C"))

    (first, last), _ = talk("谷歌", "GOOGL", ledger=ledger, names=NamesFile(place, LedgerKind.DEMO))

    assert first.recorded is not None and first.recorded.ending is RecordEnding.ASKING
    assert '"谷歌" may be GOOGL or GOOG in your ledger' in first.reply
    assert last.recorded is not None and last.recorded.ending is RecordEnding.SENT
    assert [trade.asset for trade in last.recorded.trades] == ["GOOGL"]
    assert kept(place) == [{"name": "谷歌", "code": "GOOGL", "day": TODAY}]


def test_neither_code_in_the_ledger_is_told_by_both_and_nothing_is_sent() -> None:
    (said,), _ = talk("谷歌", ledger=ledger_with(stock("KO", "Coca-Cola")))

    assert said.recorded is not None and said.sent is None
    (left,) = said.recorded.left_out
    assert (left.why, left.codes) == (LeftOut.NAME_NOT_IN_LEDGER, ("GOOGL", "GOOG"))
    assert "GOOGL or GOOG" in said.reply


# --- 4. asked, answered, kept, matched the next time -------------------------------------


def test_a_name_answered_with_a_code_is_kept_and_matched_in_a_new_chat(tmp_path: Path) -> None:
    names = NamesFile(tmp_path / "asset-names.json", LedgerKind.DEMO)
    names.place.write_text("", encoding="utf-8")
    names.place.unlink()

    (first, last), _ = talk("小可", "KO", names=names)
    (again,), model = talk("小可", names=names)

    assert first.recorded is not None and first.recorded.ending is RecordEnding.ASKING
    assert last.recorded is not None and last.recorded.ending is RecordEnding.SENT
    assert [trade.asset for trade in last.recorded.trades] == ["KO"]
    assert kept(names.place) == [{"name": "小可", "code": "KO", "day": TODAY}]
    assert again.recorded is not None and again.recorded.ending is RecordEnding.SENT
    assert [trade.asset for trade in again.recorded.trades] == ["KO"]
    assert f"from your answer on {TODAY}" in asset_mark(again)
    assert f'Took "小可" as KO (Coca-Cola) from your answer on {TODAY}.' in again.reply
    assert model.questions.calls == []


def test_answers_on_one_kind_of_ledger_are_never_used_on_the_other(tmp_path: Path) -> None:
    place = tmp_path / "asset-names.json"
    remember(NamesFile(place, LedgerKind.DEMO), "小可", "KO", date(2026, 11, 20))
    remember(NamesFile(place, LedgerKind.PAGE), "大可", "KO", date(2026, 11, 20))

    (on_page,), _ = talk("小可", names=NamesFile(place, LedgerKind.PAGE))
    (on_demo,), _ = talk("大可", names=NamesFile(place, LedgerKind.DEMO))

    assert on_page.recorded is not None and on_page.recorded.ending is RecordEnding.ASKING
    assert on_demo.recorded is not None and on_demo.recorded.ending is RecordEnding.ASKING


# --- 5. a code remembered that the ledger no longer has ----------------------------------


def test_an_answer_whose_code_the_ledger_no_longer_has_is_as_if_never_given(
    tmp_path: Path,
) -> None:
    names = NamesFile(tmp_path / "asset-names.json", LedgerKind.DEMO)
    remember(names, "小可", "KO", date(2026, 11, 20))

    (said,), _ = talk("小可", names=names, ledger=ledger_with(stock("PEP", "PepsiCo")))

    assert said.recorded is not None and said.recorded.ending is RecordEnding.ASKING
    assert said.recorded.question is not None


# --- 6. general words, and words not said ------------------------------------------------


@pytest.mark.parametrize("coin", ["股票", "这只", "美股", "期权", "可"])
def test_a_general_word_answered_with_a_code_is_recorded_and_never_kept(
    tmp_path: Path, coin: str
) -> None:
    names = NamesFile(tmp_path / "asset-names.json", LedgerKind.DEMO)

    (first, last), _ = talk(coin, "KO", names=names)

    assert first.recorded is not None and first.recorded.ending is RecordEnding.ASKING
    assert last.recorded is not None and last.recorded.ending is RecordEnding.SENT
    assert kept(names.place) == []


@pytest.mark.parametrize("coin", ["coin", "ETF"])
def test_a_general_word_that_can_be_a_code_is_told_as_not_in_the_ledger_and_never_kept(
    tmp_path: Path, coin: str
) -> None:
    names = NamesFile(tmp_path / "asset-names.json", LedgerKind.DEMO)

    (said,), _ = talk(coin, names=names)

    assert said.recorded is not None and said.recorded.ending is RecordEnding.NOTHING_TO_SEND
    assert said.recorded.progress.names == ()
    assert kept(names.place) == []


def test_words_the_user_never_said_are_never_kept(tmp_path: Path) -> None:
    names = NamesFile(tmp_path / "asset-names.json", LedgerKind.DEMO)

    (_, last), _ = talk("大可", "KO", names=names, said=said_as("小可"))

    assert last.recorded is not None and last.recorded.ending is RecordEnding.SENT
    assert kept(names.place) == []


# --- 7. a later answer wins --------------------------------------------------------------


def test_a_later_answer_takes_the_place_of_the_earlier(tmp_path: Path) -> None:
    names = NamesFile(tmp_path / "asset-names.json", LedgerKind.DEMO)
    talk("小可", "KO", names=names)

    talk("小可", "PEP", names=names, ledger=ledger_with(stock("PEP", "PepsiCo")))
    (said,), _ = talk("小可", names=names)

    assert [entry["code"] for entry in kept(names.place)] == ["PEP"]
    assert said.recorded is not None
    assert [trade.asset for trade in said.recorded.trades] == ["PEP"]


# --- 8. the user's answer wins over the table --------------------------------------------


def test_an_answer_wins_over_the_table(tmp_path: Path) -> None:
    names = NamesFile(tmp_path / "asset-names.json", LedgerKind.DEMO)
    remember(names, "微软", "INTC", date(2026, 11, 20))

    (said,), _ = talk("微软", names=names)

    assert said.recorded is not None
    assert [trade.asset for trade in said.recorded.trades] == ["INTC"]
    assert "from your answer on 2026-11-20" in asset_mark(said)


# --- 9. a file changed by hand, or broken ------------------------------------------------


def test_an_entry_written_by_hand_for_a_general_word_does_not_count(tmp_path: Path) -> None:
    place = tmp_path / "asset-names.json"
    place.write_text(
        json.dumps(
            {
                "version": 1,
                "demo": [
                    {"name": "股票", "code": "MSFT", "day": "2026-11-01"},
                    {"name": "小可", "code": "KO", "day": "2026-11-01"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    names = NamesFile(place, LedgerKind.DEMO)

    (general,), _ = talk("股票", names=names)
    (other,), _ = talk("小可", names=names)

    assert general.recorded is not None and general.recorded.ending is RecordEnding.ASKING
    assert other.recorded is not None
    assert [trade.asset for trade in other.recorded.trades] == ["KO"]


@pytest.mark.parametrize("text", ["{ not json", json.dumps({"version": 9, "demo": [], "page": []})])
def test_a_broken_file_is_taken_as_empty_said_nothing_of_and_left_as_it_is(
    tmp_path: Path, text: str
) -> None:
    place = tmp_path / "asset-names.json"
    place.write_text(text, encoding="utf-8")
    before = place.read_bytes()
    names = NamesFile(place, LedgerKind.DEMO)

    (table_said,), _ = talk("微软", names=names)
    (first, last), _ = talk("小可", "KO", names=names)

    assert table_said.recorded is not None
    assert [trade.asset for trade in table_said.recorded.trades] == ["MSFT"]
    assert "file" not in first.reply.casefold()
    assert last.recorded is not None and last.recorded.ending is RecordEnding.SENT
    assert place.read_bytes() == before


# --- 10. each switch on its own ----------------------------------------------------------


def test_the_table_off_asks_about_the_name_and_the_answer_is_kept(tmp_path: Path) -> None:
    names = NamesFile(tmp_path / "asset-names.json", LedgerKind.DEMO)

    (first, last), _ = talk("微软", "MSFT", names=names, name_table=False)

    assert first.recorded is not None and first.recorded.ending is RecordEnding.ASKING
    assert last.recorded is not None
    assert [trade.asset for trade in last.recorded.trades] == ["MSFT"]
    assert kept(names.place) == [{"name": "微软", "code": "MSFT", "day": TODAY}]


def test_with_no_file_the_table_still_matches_and_an_answer_is_never_kept(
    tmp_path: Path,
) -> None:
    (table_said,), _ = talk("微软")
    (_, last), _ = talk("小可", "KO")
    (again,), _ = talk("小可")

    assert table_said.recorded is not None
    assert [trade.asset for trade in table_said.recorded.trades] == ["MSFT"]
    assert last.recorded is not None and last.recorded.ending is RecordEnding.SENT
    assert again.recorded is not None and again.recorded.ending is RecordEnding.ASKING
    assert list(tmp_path.iterdir()) == []


def test_the_table_is_off_by_default_and_the_default_is_read_when_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (off,), _ = talk("微软", name_table=None)
    monkeypatch.setattr(conversation, "ASSISTANT_NAME_TABLE", True)
    (on,), _ = talk("微软", name_table=None)

    assert off.recorded is not None and off.recorded.ending is RecordEnding.ASKING
    assert on.recorded is not None
    assert [trade.asset for trade in on.recorded.trades] == ["MSFT"]
    assert conversation.ASSISTANT_PICKS_ASSETS is False


# --- 12. a screenshot's text -------------------------------------------------------------


def test_a_screenshots_text_is_matched_by_the_table_as_well() -> None:
    text = said_as("微软")
    model = RoutedModel(
        screen=[screened(("spot_trade", text.split("，")[0]))],
        extraction=[table(row_of("微软"))],
    )
    shot = ScreenshotText(
        reading=PictureRead(text=text, version="read-1", calls=()),
        text=text,
    )

    said = say_from_reading(
        AssistantChat(),
        shot,
        model=model,
        ledger=demo_ledger(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        name_table=True,
    )

    assert said.recorded is not None
    assert [trade.asset for trade in said.recorded.trades] == ["MSFT"]


# --- 13. the Record page's way -----------------------------------------------------------


def test_the_record_pages_way_never_matches_a_name() -> None:
    words = said_as("微软")
    model = model_for(words, "微软")
    assets = table_of(DEMO_ASSETS)
    assert assets is not None

    progress = recording.start(words, model, now=INVENTED_NOW, zone=INVENTED_ZONE, assets=assets)

    assert progress.names == ()
    assert progress.question is not None
    assert progress.trades[0].draft.coin == "微软"


# --- 14. the ways that must not be matched -----------------------------------------------


@pytest.mark.parametrize(
    "coin",
    [
        "可口可乐装瓶公司",
        "雪碧的股票",
        "微软的期权",
        "微软A股",
        "英伟达两倍做多ETF",
        "微软和英特尔",
        "可乐",
    ],
)
def test_a_way_of_saying_that_must_not_be_matched_goes_as_before(tmp_path: Path, coin: str) -> None:
    names = NamesFile(tmp_path / "asset-names.json", LedgerKind.DEMO)

    (said,), _ = talk(coin, names=names)
    (off,), _ = talk(coin, name_table=False)

    assert said.recorded is not None and said.recorded.progress.names == ()
    assert said.reply == off.reply
