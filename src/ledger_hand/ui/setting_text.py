"""How a setting's value is written on the page: as it would be typed into the environment.

A number is written with plain digits and at most one point, never with an
exponent, so that what the page shows can be typed back as it stands (the
settings refuse ``1e-09``). A whole number of a float, such as ``120.0``,
is written ``120``; the plug is written by its name, ``local`` or
``cloud``. The key is never written: only whether there is one.
``plug_in_use`` says in one line which plug talks to the model, where, and
whether there is a key.

Names defined here: ``written``, ``key_state``, ``shown`` and
``plug_in_use``.
"""

from __future__ import annotations

from decimal import Decimal

from ledger_hand.settings import ABOUT, ModelSettings, Plug, Secret, Variable

_PLUGS = {
    Plug.LOCAL: "local, Ollama's own chat endpoint at {address}",
    Plug.CLOUD: ("cloud, the OpenAI-style chat endpoint at {address}; what is typed is sent there"),
}


def written(value: object) -> str:
    """``value`` as the environment would hold it."""
    if isinstance(value, bool):
        raise TypeError("a setting is never true or false")
    if isinstance(value, Plug):
        return value.value
    if isinstance(value, float):
        return format(Decimal(repr(value)).normalize(), "f")
    if isinstance(value, int | str):
        return str(value)
    raise TypeError(f"not a setting this page writes: {type(value).__name__}")


def key_state(key: Secret | None) -> str:
    """Whether there is a key, never the key itself."""
    return "not set" if key is None else "set"


def shown(settings: ModelSettings, variable: Variable) -> str:
    """The value ``settings`` hold for ``variable`` as the page shows it; the key as set or not."""
    if variable is Variable.KEY:
        return key_state(settings.api_key)
    return written(getattr(settings, ABOUT[variable].field))


def plug_in_use(settings: ModelSettings) -> str:
    """Which plug talks to the model, where, and whether there is a key; never the key."""
    plug = _PLUGS[settings.plug].format(address=settings.base_url)
    return f"Model plug now: {plug}. Key: {key_state(settings.api_key)}."
