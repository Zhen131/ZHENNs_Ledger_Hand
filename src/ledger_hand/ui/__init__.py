"""The interface: a chat beside a table of what will be recorded, drawn with Streamlit.

Started from the top of the repository with
``streamlit run src/ledger_hand/ui/app.py``. The person types a passage in
the chat; the program's questions come back in the chat and are answered
there; the table shows each trade as it stands, with the price and the
total side by side; Save keeps the final records in the book.

The interface makes no business decision. What to ask, whether a passage is
settled, whether it can be saved, which trade can be left out and which
cannot be recorded all come from the flow's ``Progress``; the interface
lays them out and hands the person's words and clicks to the flows. It gets
the model, the book, the clock and the zone from the wiring module.

This is the only part of the package that may use Streamlit, and the only
one that keeps anything between reruns (``session``). Nothing typed is
written to disk; only the trades saved are kept, in the book.
"""
