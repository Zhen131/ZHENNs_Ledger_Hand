"""The requests the default settings send to the local model, captured for the baseline test.

With no model setting at all, the program talks to the local Ollama. This
module sends the three kinds of call the program makes through it (an
extraction call with its reply table, an assistant call that hands the
model tools after earlier calls, one of them left without results, and a
call that shows the vision model a picture), each through the real wiring of
the plug, and captures every request as it would leave the machine: its
method, its address, its headers and its body. The moment and the zone are
fixed, because the assistant's system prompt holds the current time. The
fake server answers each request with 400, which is never tried again, so
each call sends exactly one request.

``tests/llm/golden/local-requests.json`` holds what this module captured on
the code before the cloud services were added; the baseline test compares
against it. ``capture`` is also what wrote that file.

Names defined here: ``GOLDEN``, ``NOW``, ``ZONE``, ``capture``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx

from ledger_hand.assistant.prompting import system_message
from ledger_hand.assistant.tools import tool_specs
from ledger_hand.extraction.extractor import extract
from ledger_hand.flows.assisting import DEFAULT_PROMPT
from ledger_hand.llm.connect import connect_model, connect_vision_model
from ledger_hand.ports import (
    Message,
    ModelError,
    Picture,
    PictureKind,
    Role,
    ToolCall,
    ToolCallTurn,
    ToolResult,
)
from ledger_hand.settings import load_model_settings
from ledger_hand.ui.setting_text import plug_in_use
from tests.llm.fake_server import mock_transport

GOLDEN = Path(__file__).parent / "golden" / "local-requests.json"
NOW = datetime(2026, 11, 27, 9, 30, tzinfo=UTC)
ZONE = "Europe/Budapest"
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


def _history() -> list[Message | ToolCallTurn | ToolResult]:
    """Earlier steps: a call with its result, then two calls left without results."""
    return [
        Message(Role.USER, "我现在持有哪些币？"),
        ToolCallTurn(text="", calls=(ToolCall(name="get_positions", arguments={}),)),
        ToolResult(name="get_positions", content='{"positions": [{"asset": "BTC"}]}'),
        Message(Role.ASSISTANT, "你持有 BTC。"),
        Message(Role.USER, "看看我上个月的 BTC 买入"),
        ToolCallTurn(
            text="我查一下。",
            calls=(
                ToolCall(
                    name="list_trades",
                    arguments={"period": "上个月", "asset": "BTC", "side": "buy"},
                ),
                ToolCall(name="list_assets", arguments={}),
            ),
        ),
        Message(Role.USER, "算了，再说一遍持仓"),
    ]


def capture() -> dict[str, object]:
    """Every request the three calls send, and the settings page's line on the plug."""
    seen: list[dict[str, object]] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers.items()),
                "body": request.content.decode("utf-8"),
            }
        )
        return httpx.Response(400, content=b'{"error": "invented refusal"}')

    settings = load_model_settings({})
    transport = mock_transport(answer)
    model = connect_model(settings, transport=transport, sleep=lambda _: None)
    extract("昨天买了 0.5 个 BTC，单价 60000 美元", model, now=NOW, zone=ZONE)
    items = [system_message(DEFAULT_PROMPT, NOW, ZONE), *_history()]
    try:
        model.chat_with_tools(items, tool_specs())
    except ModelError as error:  # the refusal is expected; only the request counts
        assert error.status == 400
    vision = connect_vision_model(settings, transport=transport, sleep=lambda _: None)
    try:
        vision.chat_with_pictures(
            [Message(Role.USER, "read this order")], [Picture(_PNG, PictureKind.PNG)]
        )
    except ModelError as error:
        assert error.status == 400
    return {"plug_line": plug_in_use(settings), "requests": seen}
