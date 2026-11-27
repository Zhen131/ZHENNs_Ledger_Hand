"""Tests of the variables handed on to the ledger's assistant link, by the system named.

On Windows, Node.js stops at once without SYSTEMROOT, so it is handed on
there too; on any other system PATH and HOME alone are, as before. Each
test names its system, so all run on every system. No key, token, secret or
password is ever handed on.
"""

from __future__ import annotations

import pytest

from ledger_hand.settings import load_ledger_link_settings

# Every variable the link could need on Windows, as one machine has them, and
# others it must never get.
_EVERYTHING = {
    "PATH": "path-value",
    "HOME": "home-value",
    "SYSTEMROOT": r"C:\Windows",
    "WINDIR": r"C:\Windows",
    "SYSTEMDRIVE": "C:",
    "TEMP": "temp-value",
    "TMP": "tmp-value",
    "USERPROFILE": "profile-value",
    "APPDATA": "appdata-value",
    "LOCALAPPDATA": "localappdata-value",
    "PATHEXT": ".COM;.EXE",
    "COMSPEC": "cmd-value",
    "DEEPSEEK_API_KEY": "secret-1",
    "LEDGER_HAND_MODEL_KEY": "secret-2",
    "SOME_TOKEN": "secret-3",
    "A_SECRET": "secret-4",
    "DB_PASSWORD": "secret-5",
    "OTHER": "x",
}

_NEVER = ("KEY", "TOKEN", "SECRET", "PASSWORD")


@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_on_a_mac_or_linux_only_path_and_home_are_handed_on(platform: str) -> None:
    read = load_ledger_link_settings(_EVERYTHING, platform=platform)

    assert dict(read.environment) == {"PATH": "path-value", "HOME": "home-value"}


def test_on_windows_systemroot_is_handed_on_besides_path_and_home() -> None:
    read = load_ledger_link_settings(_EVERYTHING, platform="win32")

    assert dict(read.environment) == {
        "PATH": "path-value",
        "HOME": "home-value",
        "SYSTEMROOT": r"C:\Windows",
    }


@pytest.mark.parametrize("platform", ["darwin", "linux", "win32"])
def test_no_name_handed_on_holds_a_key_token_secret_or_password(platform: str) -> None:
    read = load_ledger_link_settings(_EVERYTHING, platform=platform)

    for name in read.environment:
        assert not any(word in name.upper() for word in _NEVER), name
    assert not any(value.startswith("secret") for value in read.environment.values())


@pytest.mark.parametrize("platform", ["darwin", "win32"])
def test_a_variable_not_set_is_not_handed_on(platform: str) -> None:
    read = load_ledger_link_settings({"PATH": "path-value"}, platform=platform)

    assert dict(read.environment) == {"PATH": "path-value"}
