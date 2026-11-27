"""Pieces for the tests of the deepseek plug: settings, and answers shaped as DeepSeek's.

Everything here is invented. The key is made up, and the requests never
leave the process: the plug is always handed a fake transport. The bodies
follow the shape DeepSeek's chat endpoint answered with on 2026-11-27.

Names defined here: ``KEY``, ``GENERAL_KEY``, ``deepseek_settings``,
``tool_completion``, ``sent_body``.
"""

from __future__ import annotations

import dataclasses
import json

import httpx

from ledger_hand.settings import ModelSettings, Plug, Secret, effective_settings
from tests.llm.fake_cloud import completion

KEY = "sk-invented-deepseek-0123456789abcdef"
GENERAL_KEY = "sk-invented-general-0123456789abcdef"


def deepseek_settings(**changed: object) -> ModelSettings:
    """The effective settings of the deepseek plug with the invented key; no retries, no wait."""
    read = ModelSettings(
        plug=Plug.DEEPSEEK, deepseek_key=Secret(KEY), retries=0, retry_wait_seconds=0.0
    )
    return effective_settings(dataclasses.replace(read, **changed))  # type: ignore[arg-type]


def tool_completion(*calls: tuple[str, str], content: object = "") -> dict[str, object]:
    """An answer that calls the tools named, each with its arguments as JSON text."""
    body = completion(content, finish="tool_calls", model="deepseek-v4-pro")
    message = body["choices"][0]["message"]  # type: ignore[index]
    message["tool_calls"] = [
        {
            "index": number,
            "id": f"call_from_the_service_{number}",
            "type": "function",
            "function": {"name": name, "arguments": arguments},
        }
        for number, (name, arguments) in enumerate(calls)
    ]
    return body


def sent_body(request: httpx.Request) -> dict[str, object]:
    loaded = json.loads(request.content.decode("utf-8"))
    assert isinstance(loaded, dict)
    return loaded
