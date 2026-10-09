"""The live check of the cloud plug sends nothing when the address is not on this machine.

That check carries an invented key, and is meant only for the local Ollama's
OpenAI-style endpoint. Here it is called, with the network guard on, while
the settings name a cloud address: it must skip, saying why, before it
builds or sends anything. Were it to send, the guard would stop the test
with an error of its own. The address is invented.
"""

from __future__ import annotations

import os

import pytest

from ledger_hand.settings import ENV_PREFIX, Variable
from tests.live.test_live_cloud_plug import (
    test_the_cloud_plug_gets_a_valid_reply_from_the_local_openai_style_endpoint as live_check,
)


@pytest.mark.parametrize(
    "address", ["https://api.example.com/v1", "http://192.0.2.7:8080", "http://127.0.0.2:11434"]
)
def test_the_live_check_skips_without_sending_when_the_address_is_elsewhere(
    monkeypatch: pytest.MonkeyPatch, address: str
) -> None:
    for name in list(os.environ):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name)
    monkeypatch.setenv(Variable.URL.value, address)

    with pytest.raises(pytest.skip.Exception, match="is not on this machine"):
        live_check()
