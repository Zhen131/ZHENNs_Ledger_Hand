"""Export: saved trades written as a file in the ledger's backup format.

The file is the one the Local-First Trading Ledger itself writes as a backup,
holding only the trades handed in and the coins those trades use. Everything
here is pure: it turns values into text and never writes a file, reads the
clock or looks anything up outside the program.

This package imports only ``core``. The layering check enforces it.
"""
