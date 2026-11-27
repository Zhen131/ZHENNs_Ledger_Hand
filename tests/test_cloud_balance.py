"""Tests of the script that prints DeepSeek's balance: one line for each money, and nothing else.

The balance endpoint is a fake transport; the key is invented. The script
prints the code and the total of each money, sends the key in the header
only, never prints it, and says a failure by its kind or status alone.
``--help`` reads no key.
"""

from __future__ import annotations

import io
import json

import httpx
import pytest

from ledger_hand.settings import Variable
from scripts import cloud_balance
from tests.llm.fake_server import mock_transport

KEY = "sk-invented-balance-0123456789abcdef"
ENVIRON = {Variable.DEEPSEEK_KEY.value: KEY}
BALANCE = {
    "is_available": True,
    "balance_infos": [
        {
            "currency": "CNY",
            "total_balance": "100.11",
            "granted_balance": "0.00",
            "topped_up_balance": "100.11",
        },
        {
            "currency": "USD",
            "total_balance": "0.00",
            "granted_balance": "0.00",
            "topped_up_balance": "0.00",
        },
    ],
}


def run(answer: httpx.Response, seen: list[httpx.Request] | None = None) -> tuple[int, str]:
    def reply(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return answer

    out = io.StringIO()
    status = cloud_balance.main([], out=out, environ=ENVIRON, transport=mock_transport(reply))
    return status, out.getvalue()


def test_each_money_is_one_line_of_its_code_and_its_total() -> None:
    seen: list[httpx.Request] = []

    status, printed = run(httpx.Response(200, content=json.dumps(BALANCE).encode()), seen)

    assert status == 0
    assert printed == "CNY 100.11\nUSD 0.00\n"
    (request,) = seen
    assert (request.method, str(request.url)) == ("GET", "https://api.deepseek.com/user/balance")
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert KEY not in printed


@pytest.mark.parametrize("status", [401, 402, 500])
def test_a_refusal_is_said_by_its_status_alone(status: int) -> None:
    body = json.dumps({"error": {"message": f"Authentication Fails, key ****{KEY[-4:]}"}})

    code, printed = run(httpx.Response(status, content=body.encode()))

    assert code == 1
    assert printed == f"the balance could not be read: status {status}\n"
    assert KEY[-4:] not in printed


@pytest.mark.parametrize(
    "body",
    [b"not json", b'{"balance_infos": [{"currency": "CNY"}]}', b'{"balance_infos": "x"}'],
)
def test_an_answer_in_another_shape_prints_no_part_of_it(body: bytes) -> None:
    code, printed = run(httpx.Response(200, content=body))

    assert code == 1
    assert printed == "the balance could not be read: an answer in another shape\n"


def test_without_the_key_nothing_is_sent() -> None:
    out = io.StringIO()

    status = cloud_balance.main([], out=out, environ={}, transport=mock_transport(_never))

    assert status == 2
    assert out.getvalue() == "DEEPSEEK_API_KEY is not set\n"


def test_help_reads_no_key_and_sends_nothing() -> None:
    out = io.StringIO()

    status = cloud_balance.main(["--help"], out=out, environ=None, transport=mock_transport(_never))

    assert status == 0
    assert "DEEPSEEK_API_KEY" in out.getvalue()


def _never(request: httpx.Request) -> httpx.Response:
    raise AssertionError("nothing is to be sent")
