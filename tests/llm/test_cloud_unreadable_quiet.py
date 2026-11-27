"""Tests of a reply the cloud plugs cannot read: what the service wrote stays out of the error.

A service answers with status 200 and a body the program cannot read. With
the cloud or the deepseek plug, the error says what kind of failure it was
and its status, but nothing of what the service wrote: not in its text, not
in what the try-out script prints. The same class handed the local plug's
settings keeps the beginning of the reply, as the local plug always has.
Every value is invented; nothing leaves the process.
"""

from __future__ import annotations

import dataclasses
import io

import httpx
import pytest

from ledger_hand.llm.cloud import CloudModel
from ledger_hand.ports import Message, ModelError, ModelErrorKind, Role, ToolSpec
from ledger_hand.settings import ModelSettings, Plug
from scripts import try_assistant
from tests.ledger.test_cards_to_the_ledger import taking
from tests.llm.fake_cloud import CLOUD_SETTINGS
from tests.llm.fake_deepseek import deepseek_settings
from tests.llm.fake_server import mock_transport

MARKER = "INVENTED-MARKER-7Q3"
HELLO = [Message(Role.USER, "Greet the invented baker.")]
TOOL = ToolSpec(
    name="invented_tool",
    description="An invented tool.",
    parameters={"type": "object", "properties": {}},
)

CLOUD_PLUGS: dict[str, ModelSettings] = {
    "cloud": dataclasses.replace(CLOUD_SETTINGS, plug=Plug.CLOUD),
    "deepseek": deepseek_settings(),
}


def unreadable(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text=f"<html>{MARKER} this is not the answer</html>")


def model(settings: ModelSettings) -> CloudModel:
    return CloudModel(settings, transport=mock_transport(unreadable))


def every_text_of(error: ModelError) -> str:
    return " ".join((str(error), repr(error), error.message, error.snippet or ""))


@pytest.mark.parametrize("plug", list(CLOUD_PLUGS))
def test_a_chat_reply_not_read_leaves_nothing_of_it_in_the_error(plug: str) -> None:
    with pytest.raises(ModelError) as caught:
        model(CLOUD_PLUGS[plug]).chat(HELLO)

    assert caught.value.kind is ModelErrorKind.MALFORMED_REPLY
    assert caught.value.status == 200
    assert caught.value.snippet is None
    assert MARKER not in every_text_of(caught.value)


@pytest.mark.parametrize("plug", list(CLOUD_PLUGS))
def test_a_tool_reply_not_read_leaves_nothing_of_it_in_the_error(plug: str) -> None:
    with pytest.raises(ModelError) as caught:
        model(CLOUD_PLUGS[plug]).chat_with_tools(HELLO, [TOOL])

    assert caught.value.kind is ModelErrorKind.MALFORMED_REPLY
    assert caught.value.snippet is None
    assert MARKER not in every_text_of(caught.value)


@pytest.mark.parametrize("plug", list(CLOUD_PLUGS))
def test_the_try_out_script_prints_nothing_of_it(plug: str) -> None:
    out = io.StringIO()

    status = try_assistant.main(
        ["2026年11月20号14点在OKX买了0.1个ETH"],
        out=out,
        model=model(CLOUD_PLUGS[plug]),
        ledger=taking(),
        max_steps=6,
    )

    printed = out.getvalue()
    assert status == 1
    assert "failure: ModelError" in printed
    assert MARKER not in printed


def test_the_same_class_with_the_local_plug_still_keeps_the_beginning() -> None:
    with pytest.raises(ModelError) as caught:
        model(CLOUD_SETTINGS).chat(HELLO)

    assert CLOUD_SETTINGS.plug is Plug.LOCAL
    assert caught.value.kind is ModelErrorKind.MALFORMED_REPLY
    assert MARKER in (caught.value.snippet or "")
