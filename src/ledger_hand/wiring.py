"""Wiring: the one place that builds the program's parts from the settings and the machine.

``assemble`` gives back ``Parts``: the model (the local plug the model
settings name, trying again as they say), the tuning they name, the book
(the SQLite plug where the data settings keep it), the coin table, a
function that reads the current moment from the machine's clock, the name
of the machine's time zone, read with ``tzlocal``, and the settings and the
data places the parts were built from, for the interface to show. The
interface takes these and hands them to the flows, which never read the
settings, the clock or the machine's zone themselves.

The interface's settings page hands in the changes made on it (variable to
text). The model settings are read from the environment first, then the
changes are put in with ``settings.apply_changes``, which reads and checks
them exactly as the environment's values are read; so whatever the page
does not change, the key among it, stays as the environment set it. The
whole set of parts is built again from the result, so every part that
comes from a setting follows the change. Nothing is written back to the
environment or anywhere else.

Building sends nothing and opens nothing: the model is first contacted by
the first call to it, and the book is opened, or made, by its first use.
A setting in the environment that is refused, a change that is refused,
or a machine zone without a name the program takes, is an ``AssemblyError``
that says which (``AssemblyProblem``).

This is the only module of the package that may import ``tzlocal``, and only
the interface may import this one. It does not draw anything or keep
anything between uses.

Names defined here: ``Parts``, ``AssemblyProblem``, ``AssemblyError``,
``assemble``, ``read_clock`` and ``machine_zone``.
"""

from __future__ import annotations

import enum
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone

import tzlocal

from ledger_hand.core.coins import BUILT_IN_TABLE, CoinTable
from ledger_hand.core.zones import is_zone_name
from ledger_hand.flows.progress import Tuning
from ledger_hand.flows.recording import tuning_from
from ledger_hand.llm.local import connect_local_model
from ledger_hand.ports import ModelPort, StoragePort
from ledger_hand.settings import (
    DataPlaces,
    ModelSettings,
    SettingsError,
    Variable,
    apply_changes,
    load_data_places,
    load_model_settings,
)
from ledger_hand.storage.sqlite_store import SqliteStore


@dataclass(frozen=True)
class Parts:
    """What the interface hands to the flows.

    ``clock`` gives the current moment with its offset; ``zone`` is the name
    of the time zone a passage is read in. ``settings`` are the model
    settings the model and the tuning were built from, and ``places`` where
    the data is kept, the folder exports go into among it; both are there
    to be shown and used by the interface. ``places`` is ``None`` only for
    parts handed in without a data folder, which then offer no export.
    """

    model: ModelPort
    tuning: Tuning
    book: StoragePort
    coins: CoinTable
    clock: Callable[[], datetime]
    zone: str
    settings: ModelSettings = field(default_factory=ModelSettings)
    places: DataPlaces | None = None


class AssemblyProblem(enum.Enum):
    """Why the parts could not be built."""

    SETTING_REFUSED = "a setting was refused"
    CHANGE_REFUSED = "a change made on the settings page was refused"
    NO_ZONE_NAME = "the machine's time zone has no name the program takes"


class AssemblyError(Exception):
    """The parts could not be built; ``problem`` says why and ``detail`` says more."""

    def __init__(self, problem: AssemblyProblem, detail: str = "") -> None:
        self.problem = problem
        self.detail = detail
        super().__init__(f"{problem.value}: {detail}" if detail else problem.value)


def assemble(changes: Mapping[Variable, str] | None = None) -> Parts:
    """The parts the settings, ``changes`` to them and the machine name.

    Raises ``AssemblyError`` when they cannot be built: a setting in the
    environment refused, a change refused, or no zone name.
    """
    try:
        read = load_model_settings()
        places = load_data_places()
    except SettingsError as error:
        raise AssemblyError(AssemblyProblem.SETTING_REFUSED, str(error)) from error
    try:
        settings = apply_changes(read, changes or {})
    except SettingsError as error:
        raise AssemblyError(AssemblyProblem.CHANGE_REFUSED, str(error)) from error
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
        settings=settings,
        places=places,
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
