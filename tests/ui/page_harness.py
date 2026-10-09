"""Shared pieces of the interface tests of Export, the settings page, failures and reminders.

Two ways to open the real page headless, both with a fixed clock and zone:

- ``open_with`` puts in parts the test makes itself, with the settings and
  the data folder it names (so Export has a folder to write into);
- ``open_built`` puts in a ``Builds``, a way of building the parts that runs
  the real wiring module (the environment is the test's) and then puts in a
  ``PlugLikeModel``: a scripted model that, like a plug built from those
  settings, uses the settings' parameters for a call that hands in none,
  and records the parameters of every call. So a change on the settings
  page can be seen to reach the model.

And ways to look at what the page shows: the settings page's table, a note
(what was said after Export or on the settings page), the warning beside
Export, and every piece of text the page drew, to look for a key in.

Controls are found by their keys only, never by their place on the page.

Names defined here: ``PlugLikeModel``, ``Builds``, ``open_with``,
``open_built``, ``to_settings``, ``to_record``, ``set_setting``, ``apply``,
``reset``, ``settings_rows``, ``note``, ``warning``, ``every_text`` and
``unescaped``.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path

from streamlit.testing.v1 import AppTest

from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.flows.recording import tuning_from
from ledger_hand.llm.ollama import parameters_from
from ledger_hand.ports import JsonSchema, Message, ModelParameters, ModelReply, StoragePort
from ledger_hand.settings import DataPlaces, ModelSettings, Variable
from ledger_hand.ui.export_panel import RESULT_KEY, WARNING_KEY
from ledger_hand.ui.session import BUILDER_KEY, PARTS_KEY
from ledger_hand.ui.settings_form import APPLY_KEY, RESET_KEY, input_key
from ledger_hand.ui.settings_page import TABLE_KEY
from ledger_hand.wiring import Parts, assemble
from tests.fakes.routed_model import RoutedModel
from tests.ui.app_harness import APP_FILE, NOW, ZONE


class PlugLikeModel:
    """A routed scripted model behind the defaults a plug built from ``settings`` would use."""

    def __init__(self, settings: ModelSettings, routed: RoutedModel) -> None:
        self.settings = settings
        self.routed = routed
        self.used: list[ModelParameters] = []

    def chat(
        self,
        messages: Sequence[Message],
        *,
        reply_schema: JsonSchema | None = None,
        parameters: ModelParameters | None = None,
    ) -> ModelReply:
        chosen = parameters_from(self.settings) if parameters is None else parameters
        self.used.append(chosen)
        return self.routed.chat(messages, reply_schema=reply_schema, parameters=parameters)


class Builds:
    """Builds the parts as the page asks: the real wiring module, then a plug-like model.

    Every set of parts built is kept (``built``), with its model; all of them
    play from the one script, ``routed``. ``book``, when given, replaces the
    book the wiring module names.
    """

    def __init__(self, routed: RoutedModel, *, book: StoragePort | None = None) -> None:
        self.routed = routed
        self.book = book
        self.built: list[Parts] = []

    def __call__(self, changes: Mapping[Variable, str]) -> Parts:
        parts = assemble(changes)
        model = PlugLikeModel(parts.settings, self.routed)
        built = dataclasses.replace(
            parts,
            model=model,
            clock=lambda: NOW,
            zone=ZONE,
            book=parts.book if self.book is None else self.book,
        )
        self.built.append(built)
        return built

    @property
    def models(self) -> list[PlugLikeModel]:
        return [parts.model for parts in self.built if isinstance(parts.model, PlugLikeModel)]


def open_with(
    model: object,
    book: StoragePort,
    data: Path,
    *,
    settings: ModelSettings | None = None,
    clock: Callable[[], datetime] = lambda: NOW,
) -> AppTest:
    """The page, run once, with parts the test makes: the data folder ``data``, never made here."""
    chosen = ModelSettings() if settings is None else settings
    page = AppTest.from_file(str(APP_FILE), default_timeout=30)
    page.session_state[PARTS_KEY] = Parts(
        model=model,  # type: ignore[arg-type]
        tuning=tuning_from(chosen),
        book=book,
        coins=BUILT_IN_TABLE,
        clock=clock,
        zone=ZONE,
        settings=chosen,
        places=DataPlaces(data),
    )
    return page.run()


def open_built(builds: Builds) -> AppTest:
    """The page, run once, building its parts with ``builds``."""
    page = AppTest.from_file(str(APP_FILE), default_timeout=30)
    page.session_state[BUILDER_KEY] = builds
    return page.run()


def to_settings(page: AppTest) -> AppTest:
    return page.switch_page("settings_page.py").run()


def to_record(page: AppTest) -> AppTest:
    return page.switch_page("record_page.py").run()


def set_setting(page: AppTest, variable: Variable, text: str) -> AppTest:
    """Type ``text`` into the input for ``variable`` on the settings page."""
    return page.text_input(key=input_key(variable)).input(text).run()


def apply(page: AppTest) -> AppTest:
    return page.button(key=APPLY_KEY).click().run()


def reset(page: AppTest) -> AppTest:
    return page.button(key=RESET_KEY).click().run()


def settings_rows(page: AppTest) -> list[dict[str, str]]:
    """The rows of the settings page's table, as shown."""
    frame = page.container(key=TABLE_KEY).table[0].value
    return [
        {str(name): str(value) for name, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def note(page: AppTest, key: str = RESULT_KEY) -> tuple[str, str] | None:
    """The note shown under ``key``: its tone (success, info, error) and its words as written."""
    try:
        holder = page.container(key=key)
    except KeyError:
        return None
    found = [
        (tone, str(element.value))
        for tone in ("success", "info", "error")
        for element in getattr(holder, tone)
    ]
    ((tone, value),) = found
    return tone, unescaped(value)


def _elements(node: object) -> list[object]:
    found = [node]
    for child in getattr(node, "children", {}).values():
        found += _elements(child)
    return found


def unescaped(markdown: str) -> str:
    """The words a note's Markdown shows: escapes dropped, hard line breaks back to lines."""
    return re.sub(r"\\(.)", r"\1", markdown).replace("  \n", "\n")


def warning(page: AppTest) -> str:
    """The words always shown beside Export."""
    (shown,) = page.container(key=WARNING_KEY).markdown
    return str(shown.value)


def every_text(page: AppTest) -> str:
    """Every piece of text the page drew, in the main area and the sidebar, with tables' cells."""
    pieces: list[str] = []
    for node in [*_elements(page.main), *_elements(page.sidebar)]:
        proto = getattr(node, "proto", None)
        if proto is not None:
            pieces.append(str(proto))
        if type(node).__name__ in ("Dataframe", "Table"):
            pieces.append(node.value.to_csv())  # type: ignore[attr-defined]
    return "\n".join(pieces)
