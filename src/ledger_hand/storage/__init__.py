"""Storage: the plug for the storage port, a SQLite file with numbered upgrade scripts.

``sqlite_store.SqliteStore`` keeps saved trades in one SQLite file, the book,
and does everything the storage port promises. Opening a book
(``book_file``) reads its version before anything else, refuses a file that
is newer, not a database or not this program's, without writing to it, and
brings a new or older book up to the current version with the upgrade
scripts in ``upgrades/``. How a trade becomes a row and back is in ``rows``;
how a failure of SQLite becomes one of the port's kinds, in ``failures``.

This is the only part of the program that may use ``sqlite3``. It reads no
clock: every moment it keeps is handed in.
"""
