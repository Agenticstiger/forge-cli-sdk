"""Regression: ``ContractHelper.id`` / ``.name`` / ``.description`` fall
back to ``metadata.*`` when the top-level key is absent.

Many contracts in the wild put product identity under ``metadata`` rather
than at the top level. The old behaviour silently returned ``None`` and
downstream renderers produced output paths like ``config/.json`` — quiet,
confusing, hard to diagnose. The new behaviour: prefer top-level, fall
back to ``metadata.{id, name, description}``.
"""

from __future__ import annotations

from fluid_sdk import ContractHelper


def test_id_top_level_wins() -> None:
    h = ContractHelper({"id": "top-level-id", "metadata": {"id": "nested-id"}})
    assert h.id == "top-level-id"


def test_id_falls_back_to_metadata_id() -> None:
    h = ContractHelper({"metadata": {"id": "nested-id"}})
    assert h.id == "nested-id"


def test_id_falls_back_to_metadata_product_id() -> None:
    """``metadata.productId`` is a common variant."""
    h = ContractHelper({"metadata": {"productId": "via-product-id"}})
    assert h.id == "via-product-id"


def test_id_returns_none_when_truly_absent() -> None:
    h = ContractHelper({"metadata": {}})
    assert h.id is None


def test_name_top_level_wins() -> None:
    h = ContractHelper({"name": "Top Name", "metadata": {"name": "Nested Name"}})
    assert h.name == "Top Name"


def test_name_falls_back_to_metadata_name() -> None:
    h = ContractHelper({"metadata": {"name": "Nested Name"}})
    assert h.name == "Nested Name"


def test_description_falls_back_to_metadata_description() -> None:
    h = ContractHelper({"metadata": {"description": "Nested description"}})
    assert h.description == "Nested description"


def test_metadata_not_a_dict_does_not_crash() -> None:
    """Defensive: contracts with metadata as a string / list shouldn't crash
    the helper. Fall back to None gracefully."""
    h = ContractHelper({"metadata": "weird-value"})
    assert h.id is None
    assert h.name is None
    assert h.description is None
