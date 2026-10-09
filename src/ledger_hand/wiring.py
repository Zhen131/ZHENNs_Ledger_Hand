"""Wiring: the one place that builds the program's parts from the settings and the machine.

``assemble`` gives back ``Parts``: the model (the local plug the model
settings name, trying again as they say), the tuning they name, the book
(the SQLite plug where the data settings keep it), the coin table, a
function that reads the current moment from the machine's clock, and the
name of the machine's time zone, read with ``tzlocal``. The interface takes
these and hands them to the flows, which never read the settings, the clock
or the machine's zone themselves.

Building sends nothing and opens nothing: the model is first contacted by
the first call to it, and the book is opened, or made, by its first use.
A setting that is refused, or a machine zone without a name the program
takes, is an ``AssemblyError`` that says which (``AssemblyProblem``).

This is the only module of the package that may import ``tzlocal``, and only
the interface may import this one. It does not draw anything or keep
anything between uses.

Names defined here: ``Parts``, ``AssemblyProblem``, ``AssemblyError``,
``assemble``, ``read_clock`` and ``machine_zone``.
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

import tzlocal

from ledger_hand.core.coins import BUILT_IN_TABLE, CoinTable
from ledger_hand.core.zones import is_zone_name
from ledger_hand.flows.progress import Tuning
from ledger_hand.flows.recording import tuning_from
from ledger_hand.llm.local import connect_local_model
from ledger_hand.ports import ModelPort, StoragePort
from ledger_hand.settings import SettingsError, load_data_places, load_model_settings
from ledger_hand.storage.sqlite_store import SqliteStore


@dataclass(frozen=True)
class Parts:
    """What the interface hands to the flows.

    ``clock`` gives the current moment with its offset; ``zone`` is the name
    of the time zone a passage is read in.
    """

    model: ModelPort
    tuning: Tuning
    book: StoragePort
    coins: CoinTable
    clock: Callable[[], datetime]
    zone: str


class AssemblyProblem(enum.Enum):
    """Why the parts could not be built."""

    SETTING_REFUSED = "a setting was refused"
    NO_ZONE_NAME = "the machine's time zone has no name the program takes"


class AssemblyError(Exception):
    """The parts could not be built; ``problem`` says why and ``detail`` says more."""

    def __init__(self, problem: AssemblyProblem, detail: str = "") -> None:
        self.problem = problem
        self.detail = detail
        super().__init__(f"{problem.value}: {detail}" if detail else problem.value)


def assemble() -> Parts:
    """The parts the settings and the machine name; raises ``AssemblyError`` when they cannot be."""
    try:
        settings = load_model_settings()
        places = load_data_places()
    except SettingsError as error:
        raise AssemblyError(AssemblyProblem.SETTING_REFUSED, str(error)) from error
    zone = machine_zone()
    if zone is None:
        raise AssemblyError(AssemblyProblem.NO_ZONE_NAME)
    return Parts(
        model=connect_local_model(settings),
        tuning=tuning_from(settings),
        book=SqliteStore(places.book),
        coins=BUILT_IN_TABLE,
        clock=read_clock,
        zone=zone,
    )


def read_clock() -> datetime:
    """The current moment from the machine's clock, in UTC."""
    return datetime.now(timezone.utc)


def machine_zone() -> str | None:
    """The machine's zone name as tzlocal reads it, if the program takes it as it stands."""
    try:
        name = tzlocal.get_localzone_name()
    except (LookupError, OSError, ValueError):
        return None
    return name if is_zone_name(name) else None
