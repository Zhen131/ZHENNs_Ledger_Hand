"""Asking: the follow-up question written as one sentence for the person at the keyboard.

What to ask is decided by the program (``core.followup``); this package only
words it. ``question_text`` hands the facts the program settled to the
model, which plays a meticulous bookkeeper (``prompts/bookkeeper.py``) and
writes one English question, and checks what comes back. When the model
fails, or writes something that is not one plain question, or brings in a
number, a coin or a word that is not among the facts, the program's own
sentence for that question (``templates``) is used instead. The label that
says which trade and which field is asked about is always the program's.

This package imports only ``core`` and the ports file. It reads no clock, no
time zone of the machine and no environment variable. The layering check
enforces it.
"""
