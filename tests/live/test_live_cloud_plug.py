"""The live check of the cloud plug, against the local Ollama's OpenAI-style endpoint. By hand only.

Marked ``live_model``, so ordinary runs leave it out and the network guard
lets it through. ``scripts/check.sh live`` runs it. Ollama answers the same
OpenAI-style chat endpoint the cloud plug speaks, under ``/v1`` of its own
address, so the cloud plug's request (its path, its fields, the reply table
in ``response_format``) can be tried against a real server without leaving
this machine and without a real key. The address is the one the settings
name with ``/v1`` after it: by default Ollama on this machine. The key is
an invented one, which Ollama does not check; no cloud service is called.

It builds the plug the way the program does (the plug setting switched to
cloud, through ``connect_model``), with no retries, so the server is asked
exactly once. It hands the model the same invented question and small table
as the live check of the local plug, and checks that the reply is valid JSON
that follows the table. It prints what it sent and got, so the run itself is
the record.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from ledger_hand.llm.cloud_request import CHAT_PATH
from ledger_hand.llm.connect import connect_model
from ledger_hand.ports import ModelError
from ledger_hand.settings import Plug, Secret, load_model_settings
from tests.live.schema_check import problems_with
from tests.live.small_table import QUESTION, SMALL_TABLE

pytestmark = pytest.mark.live_model

# Plainly invented: the local server takes any key, and none is ever real here.
INVENTED_KEY = "sk-invented-live-cloud-plug-not-a-real-key"
# Where Ollama answers the OpenAI-style endpoints, under its own address.
OPENAI_STYLE_PATH = "/v1"


def test_the_cloud_plug_gets_a_valid_reply_from_the_local_openai_style_endpoint() -> None:
    local = load_model_settings()
    settings = dataclasses.replace(
        local,
        plug=Plug.CLOUD,
        base_url=local.base_url + OPENAI_STYLE_PATH,
        api_key=Secret(INVENTED_KEY),
        retries=0,
    )
    model = connect_model(settings)

    print(f"\naddress:     {settings.base_url}{CHAT_PATH}")
    try:
        reply = model.chat(QUESTION, reply_schema=SMALL_TABLE)
    except ModelError as error:
        message = f"the cloud plug could not get a reply from the local endpoint: {error}"
    else:
        message = ""
    if message:
        pytest.fail(message, pytrace=False)

    print(f"reply:       {reply.text}")
    print(f"model:       {reply.record.model}")
    print(f"took:        {reply.record.elapsed_seconds:.2f} s")
    print(f"tokens:      {reply.record.prompt_tokens} read, {reply.record.reply_tokens} written")
    print(f"finish:      {reply.record.finish.value}")
    try:
        data = json.loads(reply.text)
    except ValueError:
        pytest.fail(f"the reply is not valid JSON: {reply.text!r}", pytrace=False)
    problems = problems_with(data, SMALL_TABLE)
    assert problems == [], f"the reply does not follow the small table: {problems}"
