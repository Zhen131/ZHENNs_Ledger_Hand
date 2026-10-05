"""A small check of a JSON value against a small JSON schema, for the live check.

It understands only the keywords the live check's table uses: ``type``
(object, string, integer, number, boolean, array), ``properties``,
``required``, ``additionalProperties: false`` and ``enum``. A schema using
any other keyword is refused, so the check can never pass by quietly
skipping a rule it does not know.

It is not a general JSON Schema validator and is not part of the program.

Names defined here: ``problems_with``.
"""

from __future__ import annotations

from collections.abc import Mapping

_KNOWN_KEYWORDS = frozenset({"type", "properties", "required", "additionalProperties", "enum"})
_TYPES: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
}


def problems_with(value: object, schema: Mapping[str, object], where: str = "$") -> list[str]:
    """Every way ``value`` breaks ``schema``; an empty list when it follows it."""
    unknown = set(schema) - _KNOWN_KEYWORDS
    if unknown:
        raise ValueError(f"{where}: the schema uses keywords this check does not know: {unknown}")
    expected = schema.get("type")
    if expected is not None and not _is_type(value, expected):
        return [f"{where}: expected {expected}, got {type(value).__name__}"]
    found: list[str] = []
    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        found.append(f"{where}: {value!r} is not one of {enum}")
    if isinstance(value, dict):
        found.extend(_object_problems(value, schema, where))
    return found


def _is_type(value: object, expected: object) -> bool:
    if not isinstance(expected, str) or expected not in _TYPES:
        raise ValueError(f"this check does not know the type {expected!r}")
    if isinstance(value, bool) and expected != "boolean":
        return False
    return isinstance(value, _TYPES[expected])


def _object_problems(
    value: dict[str, object], schema: Mapping[str, object], where: str
) -> list[str]:
    found: list[str] = []
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    assert isinstance(properties, dict) and isinstance(required, list)
    found.extend(f"{where}: {name!r} is missing" for name in required if name not in value)
    if schema.get("additionalProperties") is False:
        found.extend(
            f"{where}: {name!r} is not in the table" for name in value if name not in properties
        )
    for name, rule in properties.items():
        if name in value:
            found.extend(problems_with(value[name], rule, f"{where}.{name}"))
    return found
