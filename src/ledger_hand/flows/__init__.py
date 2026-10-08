"""Flows: the parts strung together into the tasks the person at the keyboard does.

``recording`` takes a passage the whole way: judge it, extract its trades,
check each one, ask about what is missing one trade and one field at a time,
read the answers back in and check again, until every trade is a record,
skipped or impossible to record. Each step hands back the whole state as one
value that never changes (``progress``); a command line or an interface only
shows it. Recording writes nothing; with a book handed in, it reads the book
for an earlier save of the same passage and for the coins confirmed before.

``saving`` keeps the final records of a passage in the book, only when the
person asked for it. ``exporting`` writes the saved trades not exported yet
as one new file the ledger can import, and marks them only once the file is
there.

This package may use every part of the program except the interface. It
reads no clock and no time zone of the machine: the current moment and the
zone are handed in. The book is handed in too, as a storage port.
"""
