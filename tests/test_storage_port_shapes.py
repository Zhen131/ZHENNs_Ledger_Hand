"""Tests of the storage port's own shapes: its error and the eight kinds of failure."""

from __future__ import annotations

from ledger_hand.ports import StorageError, StorageErrorKind, StoragePort
from tests.fakes.memory_store import MemoryStore


def test_the_eight_kinds_of_failure_are_exactly_these() -> None:
    assert {kind.value for kind in StorageErrorKind} == {
        "newer_version",
        "not_a_database",
        "not_this_programs",
        "damaged",
        "locked",
        "inaccessible",
        "conflict",
        "unexpected",
    }


def test_an_error_says_its_kind_and_message() -> None:
    error = StorageError(StorageErrorKind.LOCKED, "the book is busy")

    assert error.kind is StorageErrorKind.LOCKED
    assert error.message == "the book is busy"
    assert str(error) == "locked: the book is busy"
    assert repr(error) == "StorageError(LOCKED, 'the book is busy')"


def test_the_stand_in_is_a_storage_port() -> None:
    store: StoragePort = MemoryStore()

    assert store.confirmed_coins() == ()
