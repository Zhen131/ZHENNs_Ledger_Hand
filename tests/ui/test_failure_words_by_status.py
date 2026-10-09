"""Tests of the sentences said by status code, and of the wait a rate-limited server asks for.

A cloud service turns a call down as a server error with a status that says
why: 401 or 403 for a key it does not take, 400 for a request it does not
take. Each of those has a sentence of its own, looked up by kind and status;
every other status keeps the sentence of its kind. The sentence for 400
quotes the start of what the server answered, with the key hidden in every
form even if a snippet held it. A rate-limited call whose server said how
long to wait says that wait, in whole seconds rounded up. Every value is
invented.
"""

from __future__ import annotations

import json
import urllib.parse

import pytest

from ledger_hand.ports import ModelError, ModelErrorKind
from ledger_hand.settings import ModelSettings, Secret, Variable
from ledger_hand.ui.failure_words import (
    MODEL_FAILURES,
    MODEL_FAILURES_BY_STATUS,
    RATE_LIMITED_FOR,
    model_trouble,
)

KEY = 'sk-invented-"words\\status-0123456789'
SETTINGS = ModelSettings(
    base_url="https://api.example.com/v1", model="invented-cloud-model", api_key=Secret(KEY)
)
S = ModelErrorKind.SERVER_ERROR


def said_for(status: int | None, snippet: str | None = None) -> str:
    return model_trouble(ModelError(S, "invented", status=status, snippet=snippet), SETTINGS)


def test_the_statuses_with_a_sentence_of_their_own_are_these() -> None:
    assert set(MODEL_FAILURES_BY_STATUS) == {(S, 400), (S, 401), (S, 403)}


@pytest.mark.parametrize("status", [401, 403])
def test_a_key_refused_says_so_and_where_the_key_is_set(status: int) -> None:
    sentence = said_for(status)

    assert sentence.startswith(
        "The model server at https://api.example.com/v1 did not take the key"
    )
    assert f"(status {status})" in sentence
    assert f"Check {Variable.KEY.value} in the environment" in sentence
    assert "invented-cloud-model" in sentence
    assert sentence.endswith("start the program again.")


def test_a_request_refused_says_so_with_the_start_of_the_servers_answer() -> None:
    answer = '{"error": {"message": "Invalid schema for response_format \'reply\'"}}'

    sentence = said_for(400, answer)

    assert "turned the request down as it was sent (status 400)." in sentence
    assert f'Its answer began: "{answer}".' in sentence
    assert "Check the model's name on the Settings page." in sentence
    assert sentence.endswith("turns every call down this way.")


def test_a_request_refused_with_nothing_in_the_answer_leaves_the_quote_out() -> None:
    sentence = said_for(400, None)

    assert "Its answer began" not in sentence
    assert "(status 400). Check" in sentence


def test_the_three_sentences_differ_from_the_one_for_the_kind() -> None:
    general = said_for(500)

    assert general == MODEL_FAILURES[S].format(
        address="", model="", seconds="", status=" (status 500)"
    )
    for status in (400, 401, 403):
        assert said_for(status) != general


@pytest.mark.parametrize("status", [404, 405, 418, 422, 500, 503, None])
def test_every_other_status_keeps_the_sentence_of_its_kind(status: int | None) -> None:
    assert said_for(status).startswith("The model server reported an error of its own")


@pytest.mark.parametrize(
    "written",
    [KEY, json.dumps(KEY)[1:-1], urllib.parse.quote(KEY, safe="")],
    ids=["as sent", "json", "percent-encoded"],
)
@pytest.mark.parametrize("status", [400, 401, 403])
def test_no_sentence_by_status_holds_the_key_even_from_a_snippet_that_did(
    status: int, written: str
) -> None:
    # The plugs never let the key into a snippet; this one holds it anyway.
    sentence = said_for(status, f"Incorrect API key provided: {written}")

    assert KEY not in sentence
    assert written not in sentence


# --- the wait a rate-limited server asks for ----------------------------------------


@pytest.mark.parametrize(
    ("wait", "seconds"), [(2.0, "2"), (1.2, "2"), (30.0, "30"), (0.0, "1"), (61.0, "61")]
)
def test_rate_limited_with_a_wait_says_the_wait_in_whole_seconds(wait: float, seconds: str) -> None:
    error = ModelError(
        ModelErrorKind.RATE_LIMITED, "too often", status=429, retry_after_seconds=wait
    )

    sentence = model_trouble(error, SETTINGS)

    assert sentence == RATE_LIMITED_FOR.format(wait=seconds)
    assert f"asked to wait {seconds} seconds" in sentence
    assert "called too often" in sentence
    assert sentence.endswith("Wait that long, then try again.")


def test_rate_limited_without_a_wait_is_said_as_before() -> None:
    error = ModelError(ModelErrorKind.RATE_LIMITED, "too often", status=429)

    assert model_trouble(error, SETTINGS) == MODEL_FAILURES[ModelErrorKind.RATE_LIMITED]
