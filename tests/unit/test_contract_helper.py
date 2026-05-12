"""Unit tests for ``fluid_sdk.contract.ContractHelper``."""

from __future__ import annotations

from fluid_sdk import ContractHelper
from fluid_sdk.testing.fixtures import LOCAL_CONTRACT, MINIMAL_CONTRACT


def test_helper_on_minimal_contract() -> None:
    h = ContractHelper(MINIMAL_CONTRACT)
    assert h.id == "minimal-product"
    assert h.name == "Minimal Product"
    assert h.fluid_version == "0.7.4"
    assert h.exposes() == []
    assert h.consumes() == []
    assert h.builds() == []
    assert h.primary_build() is None


def test_helper_on_local_contract() -> None:
    h = ContractHelper(LOCAL_CONTRACT)
    assert h.id == "local-product"
    assert h.product_type == "SDP"
    assert h.layer == "bronze"

    exposes = h.exposes()
    assert len(exposes) == 1
    assert exposes[0].id == "events"
    assert exposes[0].platform == "local"
    assert exposes[0].format == "parquet"
    assert exposes[0].path == "./data/events"
    assert len(exposes[0].columns) == 2
    assert exposes[0].columns[0].name == "id"
    assert exposes[0].columns[0].required is True

    builds = h.builds()
    assert len(builds) == 1
    assert builds[0].engine == "sql"
    assert builds[0].pattern == "embedded-logic"

    envs = h.environment_names()
    assert envs == ["dev"]


def test_extensions_block_default_empty() -> None:
    h = ContractHelper(MINIMAL_CONTRACT)
    assert h.extensions == {}
    assert h.extension("customScaffold") == {}


def test_extensions_block_populated() -> None:
    contract = {
        **MINIMAL_CONTRACT,
        "extensions": {
            "customScaffold": {
                "libraries": [{"id": "ci", "source": {"kind": "path", "path": "./bundle"}}],
            },
            "someOtherPlugin": {"foo": "bar"},
        },
    }
    h = ContractHelper(contract)
    assert "customScaffold" in h.extensions
    scaffold_cfg = h.extension("customScaffold")
    assert scaffold_cfg["libraries"][0]["id"] == "ci"


def test_helper_repr() -> None:
    h = ContractHelper(LOCAL_CONTRACT)
    r = repr(h)
    assert "local-product" in r
    assert "DataProduct" in r


def test_helper_contains() -> None:
    h = ContractHelper(LOCAL_CONTRACT)
    assert "id" in h
    assert "exposes" in h
    assert "nonexistent" not in h


def test_helper_get_default() -> None:
    h = ContractHelper(LOCAL_CONTRACT)
    assert h.get("id") == "local-product"
    assert h.get("missing", "default-value") == "default-value"
