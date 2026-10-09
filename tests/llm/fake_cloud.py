"""Pieces for the cloud plug's tests: settings, normal answers and the errors services send.

Everything here is invented. The address is ``example.com``, which belongs to
no service, and the key is made up; the requests never leave the process,
because the plug is always handed the fake transport of ``fake_server``.
The bodies follow the shape of an OpenAI-style chat endpoint.

Names defined here: ``KEY``, ``ADDRESS``, ``MODEL``, ``CLOUD_SETTINGS``,
``completion``, ``error_body``.
"""

from __future__ import annotations

from ledger_hand.settings import ModelSettings, Secret

KEY = "sk-invented-cloud-0123456789abcdef"
ADDRESS = "https://api.example.com/v1"
MODEL = "invented-cloud-model"
# A cloud service with a key, no retries and no wait, so a test sees one try.
CLOUD_SETTINGS = ModelSettings(
    base_url=ADDRESS, model=MODEL, api_key=Secret(KEY), retries=0, retry_wait_seconds=0.0
)


def completion(
    content: object = '{"fruit": "apple"}', *, finish: object = "stop", **fields: object
) -> dict[str, object]:
    """The body of a normal answer, with ``fields`` changed at the top level."""
    body: dict[str, object] = {
        "id": "chatcmpl-invented-1",
        "object": "chat.completion",
        "created": 1791000000,
        "model": MODEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish,
            }
        ],
        "usage": {"prompt_tokens": 812, "completion_tokens": 9, "total_tokens": 821},
    }
    body.update(fields)
    return body


def error_body(
    message: str, *, kind: str | None = None, code: str | None = None
) -> dict[str, object]:
    """The body of an error, as such services send it."""
    return {"error": {"message": message, "type": kind, "param": None, "code": code}}
