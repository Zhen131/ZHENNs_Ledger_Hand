"""Core rules: what a trade is and what makes one valid.

Everything in here is pure computation over values handed in by the caller.

The core never touches the network, the file system, a database or a user
interface. It imports only a short list of standard-library modules and other
core modules: no third-party code, no other part of this package. It never
reads the clock or the machine's time zone; the caller passes the current
moment and the zone in as arguments.

The layering check enforces all of this every time the checks run.
"""
