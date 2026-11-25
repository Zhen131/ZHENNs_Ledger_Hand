"""Wiring: the one place that builds the program's parts from the settings and the machine.

``assemble`` gives back ``Parts``: the model (the plug the model settings
choose, local or cloud, trying again as they say), the tuning they name, the book
(the SQLite plug where the data settings keep it), the asset table, a
function that reads the current moment from the machine's clock, the name
of the machine's time zone, read with ``tzlocal``, and the settings and the
data places the parts were built from, for the interface to show. The
interface takes these and hands them to the flows, which never read the
settings, the clock or the machine's zone themselves.

For a screenshot, the parts hold two more things, when the settings choose
the local plug: the vision model (``llm.connect.connect_vision_model``: the
local plug with the model ``vision_model`` names, the address, the thinking
setting, the time allowed and the retries as the settings say), and a way to
ask the model server whether it has that model (``vision_check``). Asking
uses ``llm.ollama_identity.ask_identity`` with the vision model's name in
place of the model's: a model that is not in the server's list is
``VisionModelPresence.MISSING``, and any other failure is raised as its
``ModelError``. The cloud plug sends no pictures, so with it both are
``None``; so are they for parts handed in without them.

The interface's settings page hands in the changes made on it (variable to
text). The model settings are read from the environment first, then the
changes are put in with ``settings.apply_changes``, which reads and checks
them exactly as the environment's values are read; so whatever the page
does not change, the key among it, stays as the environment set it. The
whole set of parts is built again from the result, so every part that
comes from a setting follows the change. Nothing is written back to the
environment or anywhere else.

Building sends nothing and opens nothing: the model is first contacted by
the first call to it, the server is asked about the vision model only when
a screenshot comes, and the book is opened, or made, by its first use.
A setting in the environment that is refused, a change that is refused,
or a machine zone without a name the program takes, is an ``AssemblyError``
that says which (``AssemblyProblem``). Settings that do not fit the plug
they choose (a cloud plug without an address of its own, or off this
machine without https or a key) are refused the same way: as a setting
when the environment's settings do not fit, as a change when the changes
make them not fit.

This is the only module of the package that may import ``tzlocal``, and only
the interface may import this one. It does not draw anything or keep
anything between uses.

Names defined here: ``Parts``, ``AssemblyProblem``, ``AssemblyError``,
``assemble``, ``read_clock`` and ``machine_zone``.
"""

from __future__ import annotations

import enum
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

import tzlocal

from ledger_hand.core.assets import BUILT_IN_ASSETS, AssetTable
from ledger_hand.core.zones import is_zone_name
from ledger_hand.flows.progress import Tuning
from ledger_hand.flows.recording import tuning_from
from ledger_hand.flows.uploading import VisionModelCheck, VisionModelPresence
from ledger_hand.llm.connect import check_plug, connect_model, connect_vision_model
from ledger_hand.llm.ollama_identity import ask_identity
from ledger_hand.ports import ModelError, ModelErrorKind, ModelPort, StoragePort
from ledger_hand.settings import (
    DataPlaces,
    ModelSettings,
    Plug,
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

    ``assets`` is the asset table every passage is recorded with, and its
    coins are those an export may write; today it is always the built-in
    one. ``clock`` gives the current moment with its offset; ``zone`` is the name
    of the time zone a passage is read in. ``settings`` are the model
    settings the model and the tuning were built from, and ``places`` where
    the data is kept, the folder exports go into among it; both are there
    to be shown and used by the interface. ``places`` is ``None`` only for
    parts handed in without a data folder, which then offer no export.
    ``vision_model`` reads a screenshot and ``vision_check`` asks the server
    whether it has the model that does; both are ``None`` for the cloud plug,
    and for parts handed in without them.
    """

    model: ModelPort
    tuning: Tuning
    book: StoragePort
    assets: AssetTable
    clock: Callable[[], datetime]
    zone: str
    settings: ModelSettings = field(default_factory=ModelSettings)
    places: DataPlaces | None = None
    vision_model: ModelPort | None = None
    vision_check: VisionModelCheck | None = None


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
        check_plug(read)
    except SettingsError as error:
        raise AssemblyError(AssemblyProblem.SETTING_REFUSED, str(error)) from error
    try:
        settings = apply_changes(read, changes or {})
        model = connect_model(settings)
    except SettingsError as error:
        raise AssemblyError(AssemblyProblem.CHANGE_REFUSED, str(error)) from error
    zone = machine_zone()
    if zone is None:
        raise AssemblyError(AssemblyProblem.NO_ZONE_NAME)
    local = settings.plug is Plug.LOCAL
    return Parts(
        model=model,
        tuning=tuning_from(settings),
        book=SqliteStore(places.book),
        assets=BUILT_IN_ASSETS,
        clock=read_clock,
        zone=zone,
        settings=settings,
        places=places,
        vision_model=connect_vision_model(settings) if local else None,
        vision_check=_vision_model_check(settings) if local else None,
    )


def _vision_model_check(settings: ModelSettings) -> VisionModelCheck:
    """A way to ask the server ``settings`` name whether it has their vision model."""
    vision = replace(settings, model=settings.vision_model)

    def check() -> VisionModelPresence:
        try:
            ask_identity(vision)
        except ModelError as error:
            if error.kind is ModelErrorKind.MODEL_NOT_FOUND:
                return VisionModelPresence.MISSING
            raise
        return VisionModelPresence.PRESENT

    return check


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
