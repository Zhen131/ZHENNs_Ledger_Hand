"""Try the ledger's assistant link by hand, with no model: read four things, propose one trade.

    LEDGER_HAND_LEDGER_DIR=path/to/LocalFirstTradingLedger \\
        .venv/bin/python scripts/try_ledger_link.py [--json FILE]

It starts the ledger's own assistant link with the program's link client,
as the settings say (the ledger's folder, ``LEDGER_HAND_LEDGER_LINK_PORT``,
47651 by default, and ``LEDGER_HAND_LEDGER_PAGE_PORT``, 3000), and prints
the port. The token the ledger page asks for is printed only when the
output is a terminal; otherwise only how many characters it has. Then:

1. It calls ``list_assets`` once before any page is connected, to show what
   the ledger says then.
2. It waits for the person to open the ledger page, click Connect assistant
   and paste the port and the token (``--wait-seconds``, five minutes).
3. It calls the four reading tools, ``list_assets``, ``list_trades``,
   ``get_period_summary`` (from ``--start`` to today) and ``get_positions``,
   and prints what each found in a few plain lines.
4. It proposes one invented trade: a buy of 0.001 BTC at 60000 USDT, fee
   0.1 USDT, dated today, with the asset and the money found by their
   codes in ``list_assets``. The ledger only puts it on the page's pending
   list; nothing is written until the person clicks Save there.
5. It asks ``get_proposal_status`` every few seconds (``--poll-seconds``)
   and prints each change, until the proposal is saved, rejected or void.

With ``--json FILE`` it also writes every call, its arguments and the
ledger's answer as it came, into FILE as one JSON list. The token is in
none of it. Every number it sends is invented.

Exit status: 0 the proposal was saved, rejected or became void; 1 the link
failed, no page connected in time, a call came back as an error, or the
proposal could not be sent; 2 the script could not start (no ledger folder
named, or a setting refused).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any, TextIO

from ledger_hand.ledger.link_client import AnswerKind, LedgerLink, PageState, ToolAnswer
from ledger_hand.ledger.link_failures import LedgerLinkError
from ledger_hand.settings import LEDGER_DIRECTORY_VARIABLE, SettingsError
from ledger_hand.wiring import ledger_link

INVENTED_TRADE = {"quantity": "0.001", "price": "60000", "totalValue": "60", "fee": "0.1"}
SOURCE_TEXT = "Ledger Hand try-out: an invented buy of 0.001 BTC at 60000 USDT, fee 0.1 USDT"
SETTLED = {"saved", "rejected", "void"}


class Session:
    """The link and every call made through it, kept for ``--json``."""

    def __init__(self, link: LedgerLink, out: TextIO) -> None:
        self.link = link
        self.out = out
        self.calls: list[dict[str, Any]] = []

    def call(self, tool: str, arguments: Mapping[str, Any]) -> ToolAnswer:
        answer = self.link.call(tool, arguments)
        self.calls.append(
            {
                "tool": tool,
                "arguments": dict(arguments),
                "kind": answer.kind.value,
                "content": answer.content,
            }
        )
        return answer

    def say(self, line: str = "") -> None:
        print(line, file=self.out, flush=True)


def show_start(link: LedgerLink, out: TextIO) -> None:
    """Say where to connect; the token only to a terminal."""
    print(f"The ledger's assistant link listens on 127.0.0.1:{link.port}.", file=out)
    if out.isatty():
        print(f"Token (paste it into the ledger page): {link.token_to_show()}", file=out)
    else:
        size = len(link.token_to_show())
        print(f"Token: {size} characters, shown only when the output is a terminal.", file=out)
    print(
        f"Open the ledger at http://127.0.0.1:{link.page_port}/, click Connect assistant, "
        "and enter the port and the token there.",
        file=out,
        flush=True,
    )


def wait_for_page(link: LedgerLink, seconds: float) -> bool:
    """Whether a ledger page connected within ``seconds``."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if link.page_state() is PageState.CONNECTED:
            return True
        time.sleep(0.5)
    return False


def error_line(answer: ToolAnswer) -> str:
    content = answer.content
    field = f" (field {content['field']})" if content.get("field") else ""
    return f"ERROR {content.get('code')}{field}: {content.get('message')}"


def show_assets(session: Session) -> list[Mapping[str, Any]]:
    answer = session.call("list_assets", {})
    if answer.kind is AnswerKind.ERROR:
        session.say(f"list_assets: {error_line(answer)}")
        return []
    assets = list(answer.content.get("assets", []))
    session.say(f"list_assets: {len(assets)} assets")
    for asset in assets:
        session.say(
            f"  {asset['assetCode']} ({asset['assetKind']}), id {asset['assetId']}, "
            f"priced in {asset['priceCurrencyCode']}, can pay a trade: "
            f"{asset['canBeTradeCurrency']}"
        )
    return assets


def show_trades(session: Session) -> None:
    answer = session.call("list_trades", {})
    if answer.kind is AnswerKind.ERROR:
        session.say(f"list_trades: {error_line(answer)}")
        return
    trades = list(answer.content.get("trades", []))
    more = "more pages" if answer.content.get("nextPageToken") else "no more pages"
    session.say(f"list_trades: {len(trades)} trades on the first page, {more}")
    for trade in trades[:10]:
        session.say(
            f"  {trade['occurredAt']} {trade['side']} {trade['quantity']} {trade['assetCode']}"
            f" at {trade['price']} {trade['tradeCurrencyCode']}, fee {trade['fee']}"
            f" {trade['feeAssetCode']}, id {trade['tradeId']}"
        )


def show_summary(session: Session, start: str, end: str) -> None:
    answer = session.call("get_period_summary", {"startDate": start, "endDate": end})
    if answer.kind is AnswerKind.ERROR:
        session.say(f"get_period_summary: {error_line(answer)}")
        return
    groups = list(answer.content.get("currencyGroups", []))
    session.say(f"get_period_summary {start} to {end}: {len(groups)} money groups")
    for group in groups:
        session.say(
            f"  {group['currencyCode']}: {group['buyCount']} buys, spent "
            f"{group['buyTotalSpent']}; {group['sellCount']} sells, received "
            f"{group['sellTotalReceived']}; realized {group['realizedProfitAndLoss']}"
        )


def show_positions(session: Session) -> None:
    answer = session.call("get_positions", {})
    if answer.kind is AnswerKind.ERROR:
        session.say(f"get_positions: {error_line(answer)}")
        return
    rows = list(answer.content.get("positions", []))
    session.say(f"get_positions: {len(rows)} rows")
    for row in rows:
        session.say(
            f"  {row['assetCode']}: quantity {row['quantity']}, remaining cost "
            f"{row['remainingCost']} {row['valueCurrencyCode']}"
        )


def asset_id(assets: Sequence[Mapping[str, Any]], code: str, kind: str) -> str | None:
    found = [a for a in assets if a["assetCode"] == code and a["assetKind"] == kind]
    return str(found[0]["assetId"]) if len(found) == 1 else None


def propose(session: Session, assets: Sequence[Mapping[str, Any]], today: str) -> str | None:
    """Propose the invented trade; its proposal id, or ``None`` when it was not taken."""
    btc, usdt = asset_id(assets, "BTC", "crypto"), asset_id(assets, "USDT", "currency")
    if btc is None or usdt is None:
        session.say("No single BTC coin and USDT money in list_assets; nothing proposed.")
        return None
    trade = {"occurredDate": today, "type": "buy", "assetId": btc, **INVENTED_TRADE}
    trade |= {"quoteAssetId": usdt, "feeAssetId": usdt}
    arguments = {"trades": [trade], "sourceText": SOURCE_TEXT, "modelName": "none (try-out)"}
    answer = session.call("propose_trade_add", arguments)
    if answer.kind is AnswerKind.ERROR:
        session.say(f"propose_trade_add: {error_line(answer)}")
        return None
    (result,) = answer.content["results"]
    if not result["ok"]:
        error = result["error"]
        session.say(f"propose_trade_add: not taken, {error['code']}: {error['message']}")
        return None
    session.say(
        f"propose_trade_add: proposal {result['proposalId']} is waiting on the ledger page's "
        "pending list. Nothing is written until Save is clicked there."
    )
    return str(result["proposalId"])


def follow(session: Session, proposal: str, poll_seconds: float) -> bool:
    """Ask about ``proposal`` until it settles; whether it did."""
    last = None
    while True:
        answer = session.call("get_proposal_status", {"proposalId": proposal})
        if answer.kind is AnswerKind.ERROR:
            session.say(f"get_proposal_status: {error_line(answer)}")
            return False
        status = answer.content["status"]
        if status != last:
            extra = answer.content.get("tradeId") or answer.content.get("message") or ""
            session.say(f"get_proposal_status: {status}{', ' + str(extra) if extra else ''}")
            last = status
        if status in SETTLED:
            return True
        time.sleep(poll_seconds)


def run(session: Session, arguments: argparse.Namespace) -> bool:
    before = session.call("list_assets", {})
    shown = error_line(before) if before.kind is AnswerKind.ERROR else "an answer"
    session.say(f"Before any page connects, list_assets answers: {shown}")
    if not wait_for_page(session.link, arguments.wait_seconds):
        session.say(f"No ledger page connected within {arguments.wait_seconds:g} seconds.")
        return False
    session.say("A ledger page is connected.")
    assets = show_assets(session)
    show_trades(session)
    today = date.today().isoformat()
    show_summary(session, arguments.start, today)
    show_positions(session)
    proposal = propose(session, assets, today)
    return proposal is not None and follow(session, proposal, arguments.poll_seconds)


def options(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Try the ledger's assistant link, no model.")
    parser.add_argument("--json", type=Path, help="also write every call and answer here")
    parser.add_argument("--wait-seconds", type=float, default=300.0)
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    parser.add_argument("--start", default="2000-01-01", help="first day of the summary")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None, out: TextIO = sys.stdout) -> int:
    arguments = options(argv)
    try:
        link = ledger_link()
    except SettingsError as error:
        print(f"A setting was refused: {error}", file=out)
        return 2
    if link is None:
        print(f"Name the ledger's folder in {LEDGER_DIRECTORY_VARIABLE} first.", file=out)
        return 2
    session = Session(link, out)
    try:
        with link:
            show_start(link, out)
            done = run(session, arguments)
    except LedgerLinkError as error:
        print(f"The link failed: {error}", file=out)
        done = False
    if arguments.json is not None:
        text = json.dumps(session.calls, ensure_ascii=False, indent=2)
        arguments.json.write_text(text + "\n", encoding="utf-8")
        print(f"Every call and answer written to {arguments.json}", file=out)
    return 0 if done else 1


if __name__ == "__main__":
    raise SystemExit(main())
