"""Tests of the settings: defaults, every variable, malformed values and the key.

Every test hands ``load_model_settings`` its own mapping instead of the real
environment, so the tests give the same answers whatever the shell running
them has set; one test checks that the real environment is read by default.
"""

from __future__ import annotations

import os

import pytest

from ledger_hand.settings import (
    DEFAULT_BASE_URL,
    DEFAULT_CONTEXT_TOKENS,
    DEFAULT_MAX_REPLY_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_RETRIES,
    DEFAULT_RETRY_WAIT_SECONDS,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_TOP_P,
    ENV_PREFIX,
    MAX_RETRIES,
    ModelSettings,
    Secret,
    SettingsError,
    Variable,
    load_model_settings,
)

KEY = "sk-invented-0123456789abcdef"

# For each variable: a value to set, the field it lands in, and what the field
# then holds. None of these values is a default.
EVERY_VARIABLE = {
    Variable.URL: ("http://192.0.2.7:8080/", "base_url", "http://192.0.2.7:8080"),
    Variable.NAME: ("qwen2.5:14b", "model", "qwen2.5:14b"),
    Variable.KEY: (KEY, "api_key", Secret(KEY)),
    Variable.TEMPERATURE: ("0.7", "temperature", 0.7),
    Variable.TOP_P: ("0.85", "top_p", 0.85),
    Variable.MAX_REPLY_TOKENS: ("333", "max_reply_tokens", 333),
    Variable.CONTEXT_TOKENS: ("4096", "context_tokens", 4096),
    Variable.TIMEOUT_SECONDS: ("45.5", "timeout_seconds", 45.5),
    Variable.RETRIES: ("5", "retries", 5),
    Variable.RETRY_WAIT_SECONDS: ("0.25", "retry_wait_seconds", 0.25),
}


def test_with_nothing_set_every_setting_is_its_named_default() -> None:
    loaded = load_model_settings({})

    assert loaded == ModelSettings(
        base_url=DEFAULT_BASE_URL,
        model=DEFAULT_MODEL,
        api_key=None,
        temperature=DEFAULT_TEMPERATURE,
        top_p=DEFAULT_TOP_P,
        max_reply_tokens=DEFAULT_MAX_REPLY_TOKENS,
        context_tokens=DEFAULT_CONTEXT_TOKENS,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        retries=DEFAULT_RETRIES,
        retry_wait_seconds=DEFAULT_RETRY_WAIT_SECONDS,
    )
    assert loaded == ModelSettings()


def test_the_defaults_point_at_the_local_model_server_and_extract_steadily() -> None:
    assert DEFAULT_BASE_URL.startswith(("http://127.0.0.1:", "http://localhost:"))
    assert DEFAULT_TEMPERATURE == 0


def test_every_variable_is_covered_here() -> None:
    assert set(EVERY_VARIABLE) == set(Variable)
    assert all(variable.value.startswith(ENV_PREFIX) for variable in Variable)


@pytest.mark.parametrize("variable", list(Variable))
def test_each_variable_changes_its_own_setting_and_no_other(variable: Variable) -> None:
    text, field, expected = EVERY_VARIABLE[variable]

    loaded = load_model_settings({variable.value: text})

    assert getattr(loaded, field) == expected
    defaults = ModelSettings()
    for other in EVERY_VARIABLE.values():
        if other[1] != field:
            assert getattr(loaded, other[1]) == getattr(defaults, other[1])


def test_all_variables_at_once() -> None:
    loaded = load_model_settings(
        {variable.value: case[0] for variable, case in EVERY_VARIABLE.items()}
    )

    for _, field, expected in EVERY_VARIABLE.values():
        assert getattr(loaded, field) == expected


@pytest.mark.parametrize("blank", ["", " ", "\t\n"])
@pytest.mark.parametrize("variable", list(Variable))
def test_a_blank_variable_takes_its_default(variable: Variable, blank: str) -> None:
    assert load_model_settings({variable.value: blank}) == ModelSettings()


def test_blanks_around_a_value_are_dropped() -> None:
    loaded = load_model_settings({Variable.TEMPERATURE.value: "  0.3 ", Variable.NAME.value: " m "})

    assert loaded.temperature == 0.3
    assert loaded.model == "m"


def test_the_real_environment_is_read_when_no_mapping_is_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Whatever the shell running the tests has set with the prefix is cleared first.
    for name in list(os.environ):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name)
    monkeypatch.setenv(Variable.RETRIES.value, "7")

    assert load_model_settings().retries == 7


def test_other_variables_are_left_alone() -> None:
    loaded = load_model_settings({"PATH": "/bin", "LEDGER_HAND_PYTHON": "x", "OLLAMA_HOST": "y"})

    assert loaded == ModelSettings()


@pytest.mark.parametrize("name", [ENV_PREFIX + "TEMPRATURE", ENV_PREFIX + "url", ENV_PREFIX])
def test_an_unknown_name_with_the_prefix_is_refused(name: str) -> None:
    with pytest.raises(SettingsError, match="unknown setting"):
        load_model_settings({name: "1"})


# --- malformed values -------------------------------------------------------

NOT_PLAIN_NUMBERS = ["abc", "-0.1", "+1", "1e3", "inf", "nan", "0x10", ".5", "5.", "1,5", "1_0"]
NOT_WHOLE_NUMBERS = ["1.0", "-1", "+3", "1e3", "ten", "1_000", "1234567890", "３"]
NUMBER_VARIABLES = [
    Variable.TEMPERATURE,
    Variable.TOP_P,
    Variable.TIMEOUT_SECONDS,
    Variable.RETRY_WAIT_SECONDS,
]
WHOLE_VARIABLES = [Variable.MAX_REPLY_TOKENS, Variable.CONTEXT_TOKENS, Variable.RETRIES]


@pytest.mark.parametrize("text", NOT_PLAIN_NUMBERS + ["１", "0.５", "9" * 5000])
@pytest.mark.parametrize("variable", NUMBER_VARIABLES)
def test_a_number_setting_takes_only_plain_digits(variable: Variable, text: str) -> None:
    with pytest.raises(SettingsError, match=variable.value):
        load_model_settings({variable.value: text})


@pytest.mark.parametrize("text", NOT_WHOLE_NUMBERS + ["9" * 5000])
@pytest.mark.parametrize("variable", WHOLE_VARIABLES)
def test_a_whole_number_setting_takes_only_digits(variable: Variable, text: str) -> None:
    with pytest.raises(SettingsError, match=variable.value):
        load_model_settings({variable.value: text})


@pytest.mark.parametrize(
    ("variable", "text"),
    [
        (Variable.TOP_P, "0"),
        (Variable.TOP_P, "1.01"),
        (Variable.MAX_REPLY_TOKENS, "0"),
        (Variable.CONTEXT_TOKENS, "0"),
        (Variable.TIMEOUT_SECONDS, "0"),
        (Variable.TIMEOUT_SECONDS, "0.0"),
        (Variable.RETRIES, str(MAX_RETRIES + 1)),
    ],
)
def test_a_value_out_of_range_is_refused(variable: Variable, text: str) -> None:
    with pytest.raises(SettingsError, match="out of range"):
        load_model_settings({variable.value: text})


@pytest.mark.parametrize(
    ("variable", "text", "field", "expected"),
    [
        (Variable.TEMPERATURE, "0", "temperature", 0.0),
        (Variable.TOP_P, "1", "top_p", 1.0),
        (Variable.TOP_P, "0.000000001", "top_p", 0.000000001),
        (Variable.MAX_REPLY_TOKENS, "1", "max_reply_tokens", 1),
        (Variable.RETRIES, "0", "retries", 0),
        (Variable.RETRIES, str(MAX_RETRIES), "retries", MAX_RETRIES),
        (Variable.RETRY_WAIT_SECONDS, "0", "retry_wait_seconds", 0.0),
        (Variable.TIMEOUT_SECONDS, "0.001", "timeout_seconds", 0.001),
    ],
)
def test_the_edges_of_each_range_are_taken(
    variable: Variable, text: str, field: str, expected: object
) -> None:
    assert getattr(load_model_settings({variable.value: text}), field) == expected


@pytest.mark.parametrize(
    "url",
    [
        "localhost:11434",
        "127.0.0.1",
        "ftp://127.0.0.1",
        "http://",
        "http:///path",
        "http://user:pw@127.0.0.1:11434",
        "http://user@127.0.0.1",
        "http://127.0.0.1:11434?x=1",
        "http://127.0.0.1:11434?",
        "http://127.0.0.1:11434#top",
        "http://127.0.0.1:0",
        "http://127.0.0.1:70000",
        "http://127.0.0.1:port",
        "http://[::1",
        "http://exa mple",
        "http://例子.测试",
        "http://127.0.0.1\x00",
        "///",
    ],
)
def test_an_address_that_is_not_a_plain_web_address_is_refused(url: str) -> None:
    with pytest.raises(SettingsError, match=Variable.URL.value):
        load_model_settings({Variable.URL.value: url})


@pytest.mark.parametrize(
    ("url", "kept"),
    [
        ("http://localhost:11434", "http://localhost:11434"),
        ("https://models.example:443/ollama/", "https://models.example:443/ollama"),
        ("http://[::1]:11434", "http://[::1]:11434"),
        ("http://127.0.0.1:11434///", "http://127.0.0.1:11434"),
    ],
)
def test_a_plain_web_address_is_taken_without_trailing_slashes(url: str, kept: str) -> None:
    assert load_model_settings({Variable.URL.value: url}).base_url == kept


@pytest.mark.parametrize("name", ["has space", "tab\tname", "名字", "x" * 2049])
def test_a_model_name_must_be_printable_ascii(name: str) -> None:
    with pytest.raises(SettingsError, match=Variable.NAME.value):
        load_model_settings({Variable.NAME.value: name})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("temperature", float("nan")),
        ("temperature", float("inf")),
        ("temperature", True),
        ("top_p", "0.5"),
        ("max_reply_tokens", 2.0),
        ("retries", -1),
        ("retry_wait_seconds", -0.5),
        ("api_key", KEY),
        ("model", None),
        ("base_url", 1),
    ],
)
def test_settings_built_in_code_are_checked_the_same_way(field: str, value: object) -> None:
    with pytest.raises(SettingsError):
        ModelSettings(**{field: value})  # type: ignore[arg-type]


# --- the key ----------------------------------------------------------------


def test_the_key_is_kept_out_of_every_printed_form() -> None:
    loaded = load_model_settings({Variable.KEY.value: KEY})
    assert loaded.api_key is not None

    for shown in (
        repr(loaded),
        str(loaded),
        f"{loaded}",
        repr(loaded.api_key),
        f"{loaded.api_key}",
    ):
        assert KEY not in shown
    assert "<hidden>" in repr(loaded)
    assert loaded.api_key.reveal() == KEY


@pytest.mark.parametrize("bad", [KEY + " tail", KEY[:5] + "\n" + KEY[5:], "\x01" + KEY, KEY + "é"])
def test_a_malformed_key_is_refused_without_repeating_it(bad: str) -> None:
    with pytest.raises(SettingsError) as caught:
        load_model_settings({Variable.KEY.value: bad})

    message = str(caught.value)
    assert Variable.KEY.value in message
    assert KEY not in message
    assert bad.strip() not in message


def test_an_unknown_variable_error_does_not_repeat_the_values() -> None:
    with pytest.raises(SettingsError) as caught:
        load_model_settings({Variable.KEY.value: KEY, ENV_PREFIX + "KYE": KEY})

    assert KEY not in str(caught.value)


def test_secrets_compare_by_value() -> None:
    assert Secret("a") == Secret("a")
    assert Secret("a") != Secret("b")
    assert Secret("a") != "a"
    assert len({Secret("a"), Secret("a")}) == 1
