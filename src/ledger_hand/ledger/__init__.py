"""Ledger: plugs for the ledger port, the one that reaches the person's own ledger.

The one plug so far is ``fake_ledger.FakeLedger``: an invented book
(``invented_book``) kept in memory, with its own simple way of working out
cost and profit (``moving_average``, ``fake_sums``). It is what the
assistant is built and tested against, and what a demonstration uses when
it must not depend on the real ledger. A plug that reaches the real ledger
goes here beside it.

The real ledger is reached through its assistant link, a small Node.js
program in the ledger's own folder. ``link_client.LedgerLink`` starts it as
a child process and talks to it (``link_failures`` names how that fails and
keeps the token); ``link_tools`` writes down the eight tools this program
expects of it. They hand back what the ledger answers as it came; no plug
uses them yet.

This part imports only the core and the ports file. It reads no clock, no
settings and no file, and reaches no network: the link client is handed
everything it needs, and only starts the link on this machine and talks to
it over its standard input and output.
"""
