"""The Settings page: every model setting, its value now, its default and why; changes for this tab.

Above the table, one line says which plug talks to the model now (local
or cloud), at which address, and whether there is a key. Then one row for
each model setting the settings module names (``Variable``), so a setting
added there appears here by itself: its value now, its default, what it
sets and why its default is what it is, all as the settings module holds
them (``settings.ABOUT``). The key shows only whether there is one.
Under the table, the settings but the key can be changed (``settings_form``)
for this browser tab only; reopening the page or restarting the program goes
back to the environment and the defaults. The data folder is shown and
cannot be changed here.

When the parts cannot be built (a setting in the environment refused, or a
machine zone without a name), the page still opens: it says why, and shows
every setting's default and why, without values and without the inputs,
since a setting in the environment is put right in the environment.

Names defined here: ``PLUG_KEY``, ``TABLE_KEY``, ``FOLDER_KEY``, ``SCOPE``,
``rows`` and ``main``.
"""

from __future__ import annotations

import streamlit as st

from ledger_hand.settings import (
    ABOUT,
    DATA_DIRECTORY_VARIABLE,
    DataPlaces,
    ModelSettings,
    Variable,
)
from ledger_hand.ui import sayings, session, settings_form
from ledger_hand.ui.setting_text import plug_in_use, shown
from ledger_hand.wiring import AssemblyError

PLUG_KEY = "settings_plug"
TABLE_KEY = "settings_table"
FOLDER_KEY = "settings_data_folder"
SCOPE = (
    "Changes made here last for this browser tab only. Opening the page again, or starting "
    "the program again, goes back to the environment variables and the defaults. Nothing is "
    "written to a file or to the environment."
)
_DEFAULTS = ModelSettings()


def rows(settings: ModelSettings | None) -> dict[str, list[str]]:
    """The table's columns: one row per setting; no value now when ``settings`` is ``None``."""
    table: dict[str, list[str]] = {"Setting": [variable.value for variable in Variable]}
    if settings is not None:
        table["Now"] = [shown(settings, variable) for variable in Variable]
    table["Default"] = [shown(_DEFAULTS, variable) for variable in Variable]
    table["What it sets"] = [ABOUT[variable].sets for variable in Variable]
    table["Why this default"] = [ABOUT[variable].reason for variable in Variable]
    return table


def main() -> None:
    """Draw the page."""
    st.header("Settings")
    st.caption(SCOPE)
    try:
        parts = session.parts()
    except AssemblyError as error:
        st.error(sayings.assembly_failed(error))
        st.caption("Until then nothing can be changed here. Every setting, its default and why:")
        _table(None)
        return
    with st.container(key=PLUG_KEY):
        st.text(plug_in_use(parts.settings))
    _table(parts.settings)
    settings_form.draw(parts.settings)
    _data_folder(parts.places)


def _table(settings: ModelSettings | None) -> None:
    with st.container(key=TABLE_KEY):
        st.table(rows(settings), hide_index=True)


def _data_folder(places: DataPlaces | None) -> None:
    with st.container(key=FOLDER_KEY):
        st.subheader("Data folder")
        if places is None:
            st.text(
                "None: these parts were handed in without a data folder, so nothing is exported."
            )
        else:
            st.text(
                f"Folder:  {places.directory}\nBook:    {places.book}\nExports: {places.exports}"
            )
        st.caption(
            f"Read only here: set {DATA_DIRECTORY_VARIABLE} before the program starts to keep "
            "the data somewhere else."
        )


main()
