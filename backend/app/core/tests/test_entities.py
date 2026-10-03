from types import SimpleNamespace

import pytest

from app.core.entities import apply_changes


def test_apply_changes_sets_the_given_fields() -> None:
    entity = SimpleNamespace(name="a", rate=1)

    apply_changes(entity, {"name": "b"})

    assert (entity.name, entity.rate) == ("b", 1)


def test_apply_changes_rejects_a_field_the_entity_does_not_have() -> None:
    entity = SimpleNamespace(name="a")

    with pytest.raises(AttributeError, match="typo"):
        apply_changes(entity, {"typo": 1})
