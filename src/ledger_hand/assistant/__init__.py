"""Assistant: what the assistant's model is handed and how its calls are judged.

The model is handed eight tools (``tools``) and a system prompt
(``prompting``, with its versions in ``prompts/``). Each tool call it makes
is judged (``judging``) before anything is asked of the ledger: the tool
must be on the list, its arguments must follow its schema, and every
copied argument must be a piece of what the user said. What the program
hands back for a call is written as JSON text (``results``), and how one
turn of the chat went is kept as plain values (``outcome``).

The loop that strings these together, asking the model and the ledger in
turn, is in ``flows/assisting.py``. This part imports only the core, the
ports file and extraction (for judging a copied phrase). It reads no clock
and no settings: the current moment and the zone are handed in.
"""
