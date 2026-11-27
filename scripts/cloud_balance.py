"""Print the money left on the DeepSeek account: one line for each money, such as "CNY 99.80".

    .venv/bin/python scripts/cloud_balance.py
    .venv/bin/python scripts/cloud_balance.py --help

It reads the key from ``DEEPSEEK_API_KEY``, asks DeepSeek's balance
endpoint (``GET https://api.deepseek.com/user/balance``) once, and prints,
for each money the account holds, its code and its total balance as
DeepSeek writes them, and nothing else. Run it before and after a run that
calls DeepSeek: the difference is what the run cost. DeepSeek writes the
balance to the cent (two decimals, measured 2026-11-27), so a few calls may
cost less than it shows; the tokens each call used are in its record.

It goes through the same exchange as the plug (``llm.exchange``): no proxy
taken from the environment, no redirect followed, the key sent in the
``Authorization`` header and hidden in every error. Nothing of what DeepSeek
answers is printed but the codes and the totals; a failure is said by its
kind or its status alone. ``--help`` reads no key. Nothing is written.

Exit status: 0 the balance was printed, or this text; 1 DeepSeek could not
be asked or answered in a way this script does not read; 2 the key is not
set, a setting is refused, or an argument was given that it does not take.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from typing import TextIO

import httpx

from ledger_hand.llm.exchange import Endpoint, exchange
from ledger_hand.llm.reply_json import json_object_or_none
from ledger_hand.ports import ModelError
from ledger_hand.settings import (
    DEEPSEEK_ADDRESS,
    SettingsError,
    Variable,
    load_model_settings,
)

BALANCE_PATH = "/user/balance"
# Long enough for a slow answer; the endpoint only reads one number.
_SECONDS = 30.0


def main(
    arguments: Sequence[str],
    *,
    out: TextIO = sys.stdout,
    environ: Mapping[str, str] | None = None,
    transport: httpx.BaseTransport | None = None,
) -> int:
    """Print the balance; ``environ`` and ``transport`` stand in for the machine in tests."""
    if list(arguments) in (["--help"], ["-h"]):
        print((__doc__ or "").strip(), file=out)
        return 0
    if arguments:
        print("usage: scripts/cloud_balance.py [--help]", file=out)
        return 2
    try:
        key = load_model_settings(environ).deepseek_key
    except SettingsError as error:
        print(f"setting refused: {error}", file=out)
        return 2
    if key is None:
        print(f"{Variable.DEEPSEEK_KEY.value} is not set", file=out)
        return 2
    endpoint = Endpoint(base_url=DEEPSEEK_ADDRESS, api_key=key, transport=transport)
    try:
        answer = exchange(endpoint, "GET", BALANCE_PATH, content=None, timeout_seconds=_SECONDS)
    except ModelError as error:
        print(f"the balance could not be asked for: {error.kind.value}", file=out)
        return 1
    if answer.status != 200:
        print(f"the balance could not be read: status {answer.status}", file=out)
        return 1
    lines = _balances(json_object_or_none(answer))
    if lines is None:
        print("the balance could not be read: an answer in another shape", file=out)
        return 1
    for line in lines:
        print(line, file=out)
    return 0


def _balances(data: Mapping[str, object] | None) -> list[str] | None:
    """One "code total" line for each money; ``None`` when the answer is not in that shape."""
    infos = None if data is None else data.get("balance_infos")
    if not isinstance(infos, list):
        return None
    lines: list[str] = []
    for info in infos:
        if not isinstance(info, dict):
            return None
        currency, total = info.get("currency"), info.get("total_balance")
        if not isinstance(currency, str) or not isinstance(total, str):
            return None
        if not (currency.isalnum() and _is_amount(total)):
            return None
        lines.append(f"{currency} {total}")
    return lines


def _is_amount(text: str) -> bool:
    whole, _, cents = text.partition(".")
    return whole.isdigit() and (cents == "" or cents.isdigit())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
