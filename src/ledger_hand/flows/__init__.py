"""Flows: the parts strung together into one task the person at the keyboard does.

``recording`` takes a passage the whole way: judge it, extract its trades,
check each one, ask about what is missing one trade and one field at a time,
read the answers back in and check again, until every trade is a record,
skipped or impossible to record. Each step hands back the whole state as one
value that never changes (``progress``); a command line or an interface only
shows it. Nothing here writes anything anywhere: saving is a later step.

This package may use every part of the program except the interface. It
reads no clock and no time zone of the machine: the current moment and the
zone are handed in.
"""
