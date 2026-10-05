"""Plugs for the model port: today the local Ollama server.

``connect_local_model`` (in ``local``) builds the plug from the settings,
wrapped so that the failures that may pass on their own are tried again. The
parts: ``ollama`` is the plug itself; ``ollama_request`` writes what is sent
and ``ollama_reply`` reads what comes back; ``exchange`` carries out one
HTTP exchange and sorts its failures into the six kinds; ``error_text``
makes what a server sent safe to show; ``retry`` tries again;
``ollama_identity`` asks the server for its version and the model's
fingerprint, for the records of an experiment.

This package is the only one that may import ``httpx``. It imports the ports
file, the settings and nothing else of the package. It writes nothing to
disk and keeps no record of what was said.
"""
