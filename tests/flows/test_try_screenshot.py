"""Tests of ``scripts/try_screenshot.py``, with stand-ins for the two models.

``--help`` alone prints the script's description and reads nothing. A file
that cannot be read, or is neither PNG nor JPEG, and settings that choose
the cloud plug, stop the script with status 2 before any model is asked. A
picture read is printed in order: the text read, the note, the passage they
are joined into, the drafts, one line for each call, the reading's last.
The status is 0 when the picture was read and its passage extracted, and 1
when it was not read or its passage was not extracted. Nothing is left on
disk but the file the test made. The file holds only the first bytes of a
PNG or JPEG file and invented words: it is no picture.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

from ledger_hand.ports import (
    FinishReason,
    ModelError,
    ModelErrorKind,
    ModelReply,
    PictureKind,
    ReplyRecord,
)
from scripts import try_screenshot
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import ScriptedModel
from tests.flows.scripted_flow import NOW, ZONE, row, table

PNG_BYTES = b"\x89PNG\r\n\x1a\n invented words, not a picture"
JPEG_BYTES = b"\xff\xd8\xff\xe0 invented words, not a picture"
READ = "方向: 买入\n成交数量: 0.5 ETH\n成交均价: 3,420 USDT\n时间: 昨天"
NOTE = "手续费 0.2 USDT"
ROWS = table(
    row(side="buy", coin="ETH", quantity="0.5 ETH", price="3,420 USDT", fee="0.2 USDT", time="昨天")
)
READING = ReplyRecord(
    model="invented-vl:8b",
    elapsed_seconds=12.5,
    prompt_tokens=1300,
    reply_tokens=70,
    finish=FinishReason.STOPPED,
)


class Untouched:
    """Stands for what must not be read; records every time it is."""

    def __init__(self) -> None:
        self.reads: list[str] = []

    def zone(self) -> None:
        self.reads.append("machine's zone")

    def settings(self) -> None:
        self.reads.append("settings")

    def plug(self, *_: object, **__: object) -> None:
        self.reads.append("a plug")


@pytest.fixture
def untouched(monkeypatch: pytest.MonkeyPatch) -> Untouched:
    seen = Untouched()
    monkeypatch.setattr(try_screenshot, "_machine_zone", seen.zone)
    monkeypatch.setattr(try_screenshot, "load_model_settings", seen.settings)
    monkeypatch.setattr(try_screenshot, "connect_vision_model", seen.plug)
    monkeypatch.setattr(try_screenshot, "connect_model", seen.plug)
    return seen


def picture_file(folder: Path, data: bytes = PNG_BYTES, name: str = "shot.png") -> Path:
    path = folder / name
    path.write_bytes(data)
    return path


def run(arguments: list[str], vision: ScriptedModel, model: RoutedModel) -> tuple[int, list[str]]:
    out = io.StringIO()
    status = try_screenshot.main(
        arguments, out=out, vision_model=vision, model=model, now=NOW, zone=ZONE
    )
    return status, out.getvalue().splitlines()


def extraction() -> RoutedModel:
    """The model that extracts; the script extracts as try_extraction.py does, without judging."""
    return RoutedModel(extraction=[ROWS])


# --- what stops the script before any model is asked ---------------------------------


@pytest.mark.parametrize("asking", ["--help", "-h"])
def test_help_alone_prints_the_description_and_reads_nothing(
    asking: str, untouched: Untouched
) -> None:
    out = io.StringIO()

    status = try_screenshot.main([asking], out=out)

    assert status == 0
    assert untouched.reads == []
    shown = out.getvalue()
    for expected in ("scripts/try_screenshot.py", "--note", "Exit status", "PNG or JPEG"):
        assert expected in shown, expected


@pytest.mark.parametrize(
    "arguments",
    [[], ["a.png", "b.png"], ["--note"], ["a.png", "--note", "x", "--note", "y"], ["-h", "a.png"]],
)
def test_arguments_not_of_the_form_stop_the_script(
    arguments: list[str], untouched: Untouched
) -> None:
    out = io.StringIO()

    assert try_screenshot.main(arguments, out=out) == 2
    assert out.getvalue().startswith("usage: scripts/try_screenshot.py")
    assert untouched.reads == []


@pytest.mark.parametrize(
    "data", [b"GIF89a invented", b"plain text", b""], ids=["gif", "text", "empty"]
)
def test_a_file_that_is_neither_png_nor_jpeg_stops_the_script(
    data: bytes, tmp_path: Path, untouched: Untouched
) -> None:
    vision, model = ScriptedModel([READ]), extraction()

    status, lines = run([str(picture_file(tmp_path, data))], vision, model)

    assert status == 2
    assert lines == ["not a picture this script reads: the file is neither PNG nor JPEG"]
    assert vision.calls == [] and model.extraction.calls == []


@pytest.mark.parametrize("missing", ["missing.png", ""], ids=["no such file", "a folder"])
def test_a_file_that_cannot_be_read_stops_the_script(
    missing: str, tmp_path: Path, untouched: Untouched
) -> None:
    vision, model = ScriptedModel([READ]), extraction()

    status, lines = run([str(tmp_path / missing)], vision, model)

    assert status == 2
    assert lines[0].startswith("cannot read the picture: ")
    assert vision.calls == [] and model.extraction.calls == []


def test_settings_that_choose_the_cloud_plug_stop_the_script_before_anything_is_sent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in list(os.environ):
        if name.startswith("LEDGER_HAND_MODEL_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("LEDGER_HAND_MODEL_PLUG", "cloud")
    monkeypatch.setenv("LEDGER_HAND_MODEL_URL", "https://api.example.com/v1")
    monkeypatch.setenv("LEDGER_HAND_MODEL_KEY", "sk-invented-0123456789")
    built: list[str] = []
    monkeypatch.setattr(try_screenshot, "connect_model", lambda *_, **__: built.append("plug"))
    out = io.StringIO()

    status = try_screenshot.main([str(picture_file(tmp_path))], out=out, now=NOW, zone=ZONE)

    assert status == 2
    assert out.getvalue().startswith("setting refused: LEDGER_HAND_MODEL_PLUG is cloud")
    assert built == []


def test_a_machine_zone_the_program_does_not_take_stops_the_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(try_screenshot, "_machine_zone", lambda: None)
    vision, model = ScriptedModel([READ]), extraction()
    out = io.StringIO()

    status = try_screenshot.main(
        [str(picture_file(tmp_path))], out=out, vision_model=vision, model=model, now=NOW
    )

    assert status == 2
    assert vision.calls == []


# --- a picture read ---------------------------------------------------------------


def test_the_text_read_the_note_the_passage_the_drafts_and_the_calls_in_order(
    tmp_path: Path,
) -> None:
    vision = ScriptedModel([ModelReply(text=READ, record=READING)])

    status, lines = run([str(picture_file(tmp_path)), "--note", NOTE], vision, extraction())

    assert status == 0
    assert lines[:6] == [
        "text read (read-1):",
        "  方向: 买入",
        "  成交数量: 0.5 ETH",
        "  成交均价: 3,420 USDT",
        "  时间: 昨天",
        f"note: {NOTE!r}",
    ]
    assert lines[6] == f"passage: {READ + chr(10) * 2 + NOTE!r}"
    assert lines[7] == f"zone:    {ZONE}"
    assert lines[8] == "trade 1"
    assert lines[-2].startswith("call 1: scripted, ")
    assert lines[-1] == (
        "reading call: invented-vl:8b, 12.50 s, 1300 tokens read, 70 written, stopped"
    )
    fee = next(line for line in lines if line.startswith("  fee "))
    assert fee.split() == ["fee", "0.2"]


def test_the_picture_is_shown_to_the_vision_model_as_it_is_in_the_file(tmp_path: Path) -> None:
    vision = ScriptedModel([READ])

    run(
        [f"--note={NOTE}", str(picture_file(tmp_path, JPEG_BYTES, "shot.jpg"))],
        vision,
        extraction(),
    )

    (call,) = vision.calls
    (picture,) = call.pictures
    assert picture.data == JPEG_BYTES
    assert picture.kind is PictureKind.JPEG


def test_without_a_note_the_passage_is_the_text_read(tmp_path: Path) -> None:
    status, lines = run([str(picture_file(tmp_path))], ScriptedModel([READ]), extraction())

    assert status == 0
    assert "note: none" in lines
    assert f"passage: {READ!r}" in lines


def test_a_passage_with_no_trade_still_ends_with_status_0(tmp_path: Path) -> None:
    model = RoutedModel(extraction=[table()])

    status, lines = run([str(picture_file(tmp_path))], ScriptedModel([READ]), model)

    assert status == 0
    assert "no trade" in lines


def test_a_model_failure_while_reading_ends_with_status_1(tmp_path: Path) -> None:
    error = ModelError(
        ModelErrorKind.MALFORMED_REPLY, "the model server's answer has an empty reply"
    )
    model = extraction()

    status, lines = run([str(picture_file(tmp_path))], ScriptedModel([error]), model)

    assert status == 1
    assert lines == [f"picture not read: the model failed: {error}"]
    assert model.extraction.calls == []


def test_a_reading_cut_off_ends_with_status_1_and_its_call(tmp_path: Path) -> None:
    cut = ReplyRecord(
        model="invented-vl:8b",
        elapsed_seconds=40.0,
        prompt_tokens=1300,
        reply_tokens=1024,
        finish=FinishReason.LENGTH_LIMIT,
    )
    vision = ScriptedModel([ModelReply(text="方向: 买", record=cut)])

    status, lines = run([str(picture_file(tmp_path))], vision, extraction())

    assert status == 1
    assert lines == [
        "picture not read: the reading reached the longest reply and was cut off",
        "reading call: invented-vl:8b, 40.00 s, 1300 tokens read, 1024 written, length_limit",
    ]


def test_a_model_failure_while_extracting_ends_with_status_1(tmp_path: Path) -> None:
    model = RoutedModel(extraction=[ModelError(ModelErrorKind.TIMED_OUT, "slow")])

    status, lines = run([str(picture_file(tmp_path))], ScriptedModel([READ]), model)

    assert status == 1
    assert any(line.startswith("model failed: timed_out") for line in lines)


def test_nothing_is_left_on_disk_but_the_file_made_for_the_test(tmp_path: Path) -> None:
    path = picture_file(tmp_path)
    before = sorted(os.listdir(tmp_path))

    run([str(path), "--note", NOTE], ScriptedModel([READ]), extraction())

    assert sorted(os.listdir(tmp_path)) == before == ["shot.png"]
    assert path.read_bytes() == PNG_BYTES
