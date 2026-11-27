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

For the assistant page, the parts hold the ledger the assistant reaches
(``ledger``: the demo ledger, a ``ledger.fake_ledger.FakeLedger`` holding
the demo book of ``ledger.demo_book``, the cash of ``ledger.demo_cash`` and
the euro of ``ledger.demo_euro``, a new one each time the parts are
built), which kind of ledger it is (``ledger_kind``,
``flows.standing.LedgerKind``), and how many times the assistant may ask
the model in one turn (``assistant_steps``, from
``settings.load_assistant_steps``), and how many times apart a price and
the ledger's market price are far (``price_gap``, from
``settings.load_price_gap_times``). Parts handed in without a ledger hold
``None`` for both, and the page then sends nothing.

The interface's settings page hands in the changes made on it (variable to
text). The model settings are read from the environment first, then the
changes are put in with ``settings.apply_changes``, which reads and checks
them exactly as the environment's values are read; so whatever the page
does not change, the key among it, stays as the environment set it. The
whole set of parts is built again from the result, so every part that
comes from a setting follows the change. Nothing is written back to the
environment or anywhere else.

The settings the parts hold are the effective ones
(``settings.effective_settings``): with a plug that names a service, such
as deepseek, its address and model are filled in once, here, so the model,
the sentences that name the address or the model, the record on this
machine and the model's name the ledger writes into its change history all
say the same. Since every build starts from the environment again,
switching the plug back to local on the settings page goes back to the
environment's address and model.

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

``ledger_link`` builds, and does not start, the client of the ledger's
assistant link (``ledger.link_client.LedgerLink``) from the settings
``settings.load_ledger_link_settings`` reads: the ledger's folder, both
ports, the variables the link is started with, and this program's version
for the handshake. The token the link and the ledger page share is made
here, fresh each time (``make_link_token``: 24 random bytes written as
base64url, 32 characters), and kept only in memory. ``link_ledger`` builds
the real ledger's plug (``ledger.link_ledger.LinkLedger``) over a started
link, with the model's name and the machine's date for "today".
``link_keeper`` builds the one ``ledger.link_keeper.LinkKeeper`` the
assistant page shares between its browser tabs: each start builds a fresh
link with ``ledger_link`` (so a fresh token), and each plug is a
``link_ledger``. It is stopped when this program leaves (``atexit``); the
link would leave by itself anyway once its input closes. Without the
ledger's folder, or with a port that is refused, it is a ``LinkNotSet``
that says which.

The parts also say which ledger a new tab of the assistant page reaches
first (``first_ledger``, from ``settings.load_assistant_ledger``); a value
that is refused leaves the demo ledger first and says why
(``first_ledger_refused``).

This is the only module of the package that may import ``tzlocal``, and only
the interface may import this one. It does not draw anything or keep
anything between uses.

Names defined here: ``Parts``, ``AssemblyProblem``, ``AssemblyError``,
``assemble``, ``read_clock``, ``machine_zone``, ``make_link_token``,
``ledger_link``, ``link_ledger``, ``LinkNotSet``, ``NoLink`` and ``link_keeper``.
"""

from __future__ import annotations

import atexit
import enum
import secrets
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal

import tzlocal

from ledger_hand import __version__
from ledger_hand.core.assets import BUILT_IN_ASSETS, AssetTable
from ledger_hand.core.zones import is_zone_name
from ledger_hand.flows.progress import Tuning
from ledger_hand.flows.recording import tuning_from
from ledger_hand.flows.standing import LedgerKind
from ledger_hand.flows.uploading import VisionModelCheck, VisionModelPresence
from ledger_hand.ledger.demo_euro import demo_ledger_with_euro_rates
from ledger_hand.ledger.link_client import LedgerLink, LinkSetup
from ledger_hand.ledger.link_failures import LinkToken
from ledger_hand.ledger.link_keeper import LinkKeeper
from ledger_hand.ledger.link_ledger import LinkLedger, ToolCaller
from ledger_hand.llm.connect import check_plug, connect_model, connect_vision_model
from ledger_hand.llm.ollama_identity import ask_identity
from ledger_hand.ports import LedgerPort, ModelError, ModelErrorKind, ModelPort, StoragePort
from ledger_hand.settings import (
    DEFAULT_ASSISTANT_STEPS,
    DEFAULT_NAME_TABLE,
    DEFAULT_PRICE_GAP_TIMES,
    DEFAULT_RATE_GAP_PERCENT,
    DEFAULT_REMEMBER_NAMES,
    LEDGER_DIRECTORY_VARIABLE,
    AssistantLedger,
    DataPlaces,
    LedgerLinkSettings,
    ModelSettings,
    Plug,
    SettingsError,
    Switch,
    Variable,
    apply_changes,
    effective_settings,
    load_assistant_ledger,
    load_assistant_steps,
    load_data_places,
    load_ledger_link_settings,
    load_model_settings,
    load_name_table,
    load_price_gap_times,
    load_rate_gap_percent,
    load_remember_names,
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
    and for parts handed in without them. ``ledger`` is the ledger the
    assistant reaches and ``ledger_kind`` which kind it is, both ``None``
    for parts handed in without one; ``assistant_steps`` is how many times
    the assistant may ask the model in one turn, and ``steps_refused`` why
    that setting was refused, when it was (the assistant page then sends
    nothing and says why; the other pages do not use it). ``price_gap`` is
    how many times apart a price and the market price are far, and
    ``price_gap_refused`` why that setting was refused, when it was (the
    assistant page then sends nothing and says why). ``rate_gap`` and
    ``rate_gap_refused`` are the same for how far apart, in a hundred, the
    rate of a trade paid in another money and the last such rate are.
    ``name_table`` and ``remember_names`` say whether the assistant matches
    a name the ledger's list does not know by the program's table of company
    names, and by the user's earlier answers (kept in
    ``places.asset_names``); ``names_refused`` why either setting was
    refused, when one was (the assistant page then sends nothing and says
    why).
    ``first_ledger``
    is which ledger a new tab of the assistant page reaches first, and
    ``first_ledger_refused`` why the setting was refused, when it was.
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
    ledger: LedgerPort | None = None
    ledger_kind: LedgerKind | None = None
    assistant_steps: int = DEFAULT_ASSISTANT_STEPS
    steps_refused: str | None = None
    price_gap: Decimal = DEFAULT_PRICE_GAP_TIMES
    price_gap_refused: str | None = None
    rate_gap: Decimal = DEFAULT_RATE_GAP_PERCENT
    rate_gap_refused: str | None = None
    name_table: bool = DEFAULT_NAME_TABLE is Switch.ON
    remember_names: bool = DEFAULT_REMEMBER_NAMES is Switch.ON
    names_refused: str | None = None
    first_ledger: AssistantLedger = AssistantLedger.DEMO
    first_ledger_refused: str | None = None


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
        check_plug(effective_settings(read))
    except SettingsError as error:
        raise AssemblyError(AssemblyProblem.SETTING_REFUSED, str(error)) from error
    try:
        settings = effective_settings(apply_changes(read, changes or {}))
        model = connect_model(settings)
    except SettingsError as error:
        raise AssemblyError(AssemblyProblem.CHANGE_REFUSED, str(error)) from error
    zone = machine_zone()
    if zone is None:
        raise AssemblyError(AssemblyProblem.NO_ZONE_NAME)
    local = settings.plug is Plug.LOCAL
    steps, steps_refused = _steps()
    gap, gap_refused = _price_gap()
    rate_gap, rate_gap_refused = _rate_gap()
    table, remembering, names_refused = _names()
    first, first_refused = _first_ledger()
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
        # The demo ledger takes cards with cells left empty, as the real one does now,
        # has the ledger's tool for cash balances (``demo_cash``), and a euro, with the
        # money each of its own assets is priced in, and the ledger's tool for exchange
        # rates with two made-up rates (``demo_euro``).
        ledger=demo_ledger_with_euro_rates(),
        ledger_kind=LedgerKind.DEMO,
        assistant_steps=steps,
        steps_refused=steps_refused,
        price_gap=gap,
        price_gap_refused=gap_refused,
        rate_gap=rate_gap,
        rate_gap_refused=rate_gap_refused,
        name_table=table,
        remember_names=remembering,
        names_refused=names_refused,
        first_ledger=first,
        first_ledger_refused=first_refused,
    )


def _first_ledger() -> tuple[AssistantLedger, str | None]:
    """Which ledger a new tab reaches first, or the demo ledger and why the setting was refused."""
    try:
        return load_assistant_ledger(), None
    except SettingsError as error:
        return AssistantLedger.DEMO, str(error)


def _steps() -> tuple[int, str | None]:
    """How many steps the assistant may take, or why the setting was refused.

    A refused step limit stops only the assistant page, which says why; the
    Record and Settings pages are built as before.
    """
    try:
        return load_assistant_steps(), None
    except SettingsError as error:
        return DEFAULT_ASSISTANT_STEPS, str(error)


def _price_gap() -> tuple[Decimal, str | None]:
    """How many times apart a price is far, or the default and why the setting was refused.

    Like a refused step limit, it stops only the assistant page, which says why.
    """
    try:
        return load_price_gap_times(), None
    except SettingsError as error:
        return DEFAULT_PRICE_GAP_TIMES, str(error)


def _rate_gap() -> tuple[Decimal, str | None]:
    """How far apart, in a hundred, a rate is far, or the default and why it was refused.

    Like a refused price gap, it stops only the assistant page, which says why.
    """
    try:
        return load_rate_gap_percent(), None
    except SettingsError as error:
        return DEFAULT_RATE_GAP_PERCENT, str(error)


def _names() -> tuple[bool, bool, str | None]:
    """Whether names are matched by the table and by the user's answers, or the defaults and
    why a setting was refused. Like a refused price gap, it stops only the assistant page."""
    try:
        return load_name_table(), load_remember_names(), None
    except SettingsError as error:
        return DEFAULT_NAME_TABLE is Switch.ON, DEFAULT_REMEMBER_NAMES is Switch.ON, str(error)


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


def make_link_token() -> LinkToken:
    """A fresh token for the assistant link: 24 random bytes as base64url, 32 characters."""
    return LinkToken(secrets.token_urlsafe(24))


def link_ledger(link: LedgerLink, model_name: str) -> LinkLedger:
    """The real ledger's plug over a started ``link``; today is the machine's date.

    ``model_name`` is what the ledger writes into its change history as the
    model behind the assistant.
    """
    return LinkLedger(
        link, model_name=model_name, today=lambda: datetime.now().date(), timer=time.monotonic
    )


def ledger_link(settings: LedgerLinkSettings | None = None) -> LedgerLink | None:
    """The client of the ledger's assistant link, built and not started; ``None`` without a folder.

    ``settings`` are read from the environment when not handed in. A port
    that is refused is the ``SettingsError`` the settings module raises.
    """
    read = load_ledger_link_settings() if settings is None else settings
    if read.directory is None:
        return None
    return LedgerLink(
        LinkSetup(
            ledger_directory=read.directory,
            token=make_link_token(),
            hand_version=__version__,
            port=read.link_port,
            page_port=read.page_port,
            environment=read.environment,
        )
    )


class LinkNotSet(enum.Enum):
    """Why there is no assistant link to start."""

    NO_FOLDER = f"{LEDGER_DIRECTORY_VARIABLE} is not set"
    SETTING_REFUSED = "a setting of the assistant link was refused"


@dataclass(frozen=True)
class NoLink:
    """Why there is no assistant link to start, and the settings' own words when one was refused."""

    reason: LinkNotSet
    detail: str = ""


def link_keeper() -> LinkKeeper | NoLink:
    """The keeper of this program's one assistant link, or why there can be none.

    Build it once for the whole program: its port is fixed.
    """
    try:
        settings = load_ledger_link_settings()
    except SettingsError as error:
        return NoLink(LinkNotSet.SETTING_REFUSED, str(error))
    if settings.directory is None:
        return NoLink(LinkNotSet.NO_FOLDER)

    def make_link() -> LedgerLink:
        built = ledger_link(settings)
        assert built is not None  # the folder was checked just above
        return built

    def make_plug(caller: ToolCaller, model_name: str) -> LedgerPort:
        return LinkLedger(
            caller, model_name=model_name, today=lambda: datetime.now().date(), timer=time.monotonic
        )

    keeper = LinkKeeper(make_link, make_plug)
    atexit.register(keeper.stop)
    return keeper
