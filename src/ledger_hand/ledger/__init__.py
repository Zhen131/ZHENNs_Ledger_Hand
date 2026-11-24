"""Ledger: plugs for the ledger port, the one that reaches the person's own ledger.

The one plug so far is ``fake_ledger.FakeLedger``: an invented book
(``invented_book``) kept in memory, with its own simple way of working out
cost and profit (``moving_average``, ``fake_sums``). It is what the
assistant is built and tested against, and what a demonstration uses when
it must not depend on the real ledger. A plug that reaches the real ledger
goes here beside it.

This part imports only the core and the ports file. It reads no clock, no
settings and no file, and reaches no network.
"""
