"""Plugs for the model port: the local Ollama server, and a cloud service.

``connect_model`` (in ``connect``) builds the plug the settings choose,
after checking that the settings fit it, wrapped so that the failures that
may pass on their own are tried again; ``connect_local_model`` (in
``local``) builds the local plug alone. The parts: ``ollama`` is the local
plug, ``ollama_request`` writes what it sends and ``ollama_reply`` reads
what comes back; ``cloud`` is the cloud plug, for an OpenAI-style chat
endpoint, with ``cloud_request`` and ``cloud_reply``; ``request_body`` and
``reply_json`` hold what both plugs share in writing and reading;
``exchange`` carries out one HTTP exchange and sorts its failures into the
six kinds; ``error_text`` makes what a server sent safe to show;
``retry_after`` reads how long a server asks to wait; ``retry`` tries again;
``ollama_identity`` asks the local server for its version and the model's
fingerprint, for the records of an experiment.

This package is the only one that may import ``httpx``. It imports the ports
file, the settings and nothing else of the package. It writes nothing to
disk and keeps no record of what was said.
"""
