"""The live check: one real call to the model the settings name. Run only by hand.

Marked ``live_model``, so ordinary runs leave it out and the network guard
lets it through. ``scripts/check.sh live`` runs it, with the settings read
from the environment as the program reads them. It needs the model server
running and the model there; when the server cannot be reached it fails and
says "unreachable".

It asks the server who it is (its version and the model's fingerprint), then
hands the model an invented question with a small table and checks that the
reply is valid JSON that follows the table. It prints what it sent and got,
and how long the call took, so the run itself is the record.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest

from ledger_hand.llm.local import connect_local_model
from ledger_hand.llm.ollama_identity import ask_identity
from ledger_hand.ports import ModelError
from ledger_hand.settings import load_model_settings
from tests.live.schema_check import problems_with
from tests.live.small_table import QUESTION, SMALL_TABLE

pytestmark = pytest.mark.live_model


def or_fail[T](call: Callable[[], T]) -> T:
    """The call's result; a model failure fails the check with its kind and message."""
    try:
        return call()
    except ModelError as error:
        message = f"the live check could not talk to the model: {error}"
    # Failed outside the handler, so the report shows one message, not a chain of two.
    pytest.fail(message, pytrace=False)


def test_the_server_says_who_it_is() -> None:
    settings = load_model_settings()

    identity = or_fail(lambda: ask_identity(settings))

    print(f"\nserver:      {settings.base_url}")
    print(f"version:     {identity.server_version}")
    print(f"model:       {identity.model}")
    print(f"fingerprint: {identity.fingerprint}")
    assert identity.server_version
    assert identity.fingerprint


def test_the_model_replies_in_valid_json_that_follows_the_small_table() -> None:
    settings = load_model_settings()
    model = connect_local_model(settings)

    reply = or_fail(lambda: model.chat(QUESTION, reply_schema=SMALL_TABLE))

    print("\nsmall table:")
    print(json.dumps(SMALL_TABLE, indent=2))
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
