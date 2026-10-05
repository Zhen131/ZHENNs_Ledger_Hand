"""Extraction: a passage of text becomes drafts of trades, and a list of issues.

The language model does one thing only: it copies phrases out of the passage
into a table, one row per trade. Everything else is done here, by the
program: checking that every phrase it copied really is a piece of the
passage, turning phrases into exact numbers and times with the core's rules,
and building drafts. Nothing the model did not copy is ever filled in.

``extract`` (in ``extractor``) is the entry point. The parts: ``reply_table``
is the table the model fills, ``reply_parser`` reads its reply,
``passage`` finds a copied phrase in the passage, ``passage_numbers`` finds
the numbers written in a text, ``unit_currency`` tells which currency a unit
word names, ``row_draft`` turns one row into a draft, ``issues`` holds the
kinds of issue, ``prompting`` builds the messages and ``prompts`` holds the
prompt versions.

This package imports only ``core`` and the ports file. It reads no clock, no
time zone of the machine and no environment variable: the current moment and
the zone are handed in. The layering check enforces it.
"""
