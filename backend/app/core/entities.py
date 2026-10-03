"""Helpers for entities (ORM rows) shared by the modules' services."""

from collections.abc import Mapping
from typing import Any


def apply_changes(entity: object, values: Mapping[str, Any]) -> None:
    """Set each field of `values` on `entity`.

    A name the entity does not have is a programming error (a schema field with
    no column) and raises `AttributeError` instead of silently adding an
    attribute that would never be stored.
    """
    for field, value in values.items():
        if not hasattr(entity, field):
            raise AttributeError(
                f"{type(entity).__name__} has no field {field!r} to change"
            )
        setattr(entity, field, value)
