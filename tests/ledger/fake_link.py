"""A stand-in for the ledger's assistant link and for Node.js, run as a script by the tests.

Started as ``node --version`` it says a version (``FAKE_NODE_VERSION``, or
v25.9.0). Started as ``node --import tsx assistant-link/main.ts --port=N
--page-port=M`` it speaks JSON-RPC 2.0, one object per line, the way the
link does, and follows the script ``FAKE_LINK_SCENARIO`` names:

- ``normal``: says it listens, shakes hands, says a page connected, lists
  the eight tools and answers ``list_assets`` with a result,
  ``get_positions`` with the ledger's error, ``drop_page`` by saying the
  page disconnected, and any other name with JSON-RPC's "invalid params";
  a notification goes before every answer, as one the client must skip.
- ``port_in_use``: says the port is taken, with the token in the line, and
  leaves with status 2, as the link does.
- ``bad_option``: says something else is wrong and leaves with status 2.
- ``refuse_handshake``: refuses the handshake with "invalid params".
- ``silent``: never answers a tool call.
- ``die``: leaves in the middle of a tool call.
- ``garbage``: answers a tool call with a line that is not JSON.
- ``never_listens``: never says it listens.
- ``no_structured``: answers a tool call without ``structuredContent``.
- ``wrong_port``: says it listens on another port.

It leaves with status 0 when its standard input closes. It writes no file.
Invented data only.
"""

from __future__ import annotations

import json
import os
import sys

TOOLS = [
    {"name": "list_assets", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_trades", "inputSchema": {"type": "object", "properties": {}}},
    {
        "name": "get_period_summary",
        "inputSchema": {"type": "object", "required": ["startDate", "endDate"]},
    },
    {"name": "get_positions", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "propose_trade_add", "inputSchema": {"type": "object", "required": ["trades"]}},
    {
        "name": "propose_trade_update",
        "inputSchema": {"type": "object", "required": ["tradeId", "trade"]},
    },
    {"name": "propose_trade_delete", "inputSchema": {"type": "object", "required": ["tradeId"]}},
    {"name": "get_proposal_status", "inputSchema": {"type": "object", "required": ["proposalId"]}},
]

NOT_CONNECTED = {
    "code": "LEDGER_PAGE_NOT_CONNECTED",
    "category": "temporarily-unavailable",
    "message": "The ledger page is not connected.",
}


def say(message: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def note(line: str) -> None:
    sys.stderr.write(line + "\n")
    sys.stderr.flush()


def tool_answer(name: str) -> dict[str, object]:
    if name == "list_assets":
        body: dict[str, object] = {"kind": "asset-list", "assets": []}
        return {"content": [{"type": "text", "text": json.dumps(body)}], "structuredContent": body}
    if name == "drop_page":
        note("assistant-link: page disconnected")
        body = {"kind": "asset-list", "assets": []}
        return {"content": [], "structuredContent": body}
    return {"content": [], "structuredContent": NOT_CONNECTED, "isError": True}


def answer_call(scenario: str, asked: object, name: str) -> None:
    if scenario == "silent":
        return
    if scenario == "die":
        sys.exit(1)
    if scenario == "garbage":
        sys.stdout.write("this is not json\n")
        sys.stdout.flush()
        return
    say({"jsonrpc": "2.0", "method": "notifications/message", "params": {}})
    if scenario == "no_structured":
        say({"jsonrpc": "2.0", "id": asked, "result": {"content": []}})
    elif name in {"list_assets", "get_positions", "drop_page"}:
        say({"jsonrpc": "2.0", "id": asked, "result": tool_answer(name)})
    else:
        error = {"code": -32602, "message": f"Tool {name} not found"}
        say({"jsonrpc": "2.0", "id": asked, "error": error})


def answer(scenario: str, message: dict[str, object]) -> None:
    method, asked = message.get("method"), message.get("id")
    if method == "initialize":
        if scenario == "refuse_handshake":
            error = {"code": -32602, "message": "The assistant link refuses this client."}
            say({"jsonrpc": "2.0", "id": asked, "error": error})
            return
        say({"jsonrpc": "2.0", "id": asked, "result": {"protocolVersion": "2025-06-18"}})
        note("assistant-link: page connected")
    elif method == "tools/list":
        say({"jsonrpc": "2.0", "id": asked, "result": {"tools": TOOLS}})
    elif method == "tools/call":
        params = message.get("params")
        name = str(params.get("name")) if isinstance(params, dict) else ""
        answer_call(scenario, asked, name)


def main() -> None:
    if sys.argv[1:] == ["--version"]:
        print(os.environ.get("FAKE_NODE_VERSION", "v25.9.0"))
        return
    scenario = os.environ.get("FAKE_LINK_SCENARIO", "normal")
    token = os.environ.get("LEDGER_LINK_TOKEN", "")
    port = next(a.split("=", 1)[1] for a in sys.argv if a.startswith("--port="))
    if scenario == "port_in_use":
        note(f"assistant-link: ERROR: Port 127.0.0.1:{port} is already in use ({token}).")
        sys.exit(2)
    if scenario == "bad_option":
        note("assistant-link: ERROR: --page-port must be a whole number from 1 to 65535.")
        sys.exit(2)
    if scenario != "never_listens":
        shown = "1" if scenario == "wrong_port" else port
        note(f"ledger-link token={token} port={shown}")
    for line in sys.stdin:
        answer(scenario, json.loads(line))


if __name__ == "__main__":
    main()
