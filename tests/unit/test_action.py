"""Unit tests for ``fluid_sdk.action``."""

from __future__ import annotations

from fluid_sdk import PluginAction, validate_actions
from fluid_sdk.action import PHASE_DEFAULT, PHASE_SCAFFOLD


def test_minimal_action() -> None:
    a = PluginAction(op="create", resource_id="x")
    assert a.op == "create"
    assert a.resource_id == "x"
    assert a.phase == PHASE_DEFAULT
    assert a.idempotent is True
    assert a.params == {}
    assert a.depends_on == []


def test_to_dict_omits_defaults() -> None:
    """Default values should not appear in serialised dict."""
    a = PluginAction(op="create", resource_id="x")
    d = a.to_dict()
    assert d == {"op": "create", "resource_id": "x"}
    assert "phase" not in d
    assert "idempotent" not in d


def test_to_dict_preserves_non_defaults() -> None:
    a = PluginAction(
        op="write_file",
        resource_type="file",
        resource_id="ci",
        params={"path": ".gitlab-ci.yml"},
        depends_on=["preamble"],
        phase=PHASE_SCAFFOLD,
        idempotent=False,
        description="GitLab CI",
        tags={"layer": "ci"},
    )
    d = a.to_dict()
    assert d["phase"] == PHASE_SCAFFOLD
    assert d["idempotent"] is False
    assert d["params"] == {"path": ".gitlab-ci.yml"}
    assert d["depends_on"] == ["preamble"]
    assert d["description"] == "GitLab CI"
    assert d["tags"] == {"layer": "ci"}


def test_from_dict_round_trip() -> None:
    original = PluginAction(
        op="write_file",
        resource_id="ci",
        params={"path": ".gitlab-ci.yml"},
        phase=PHASE_SCAFFOLD,
    )
    d = original.to_dict()
    restored = PluginAction.from_dict(d)
    assert restored.to_dict() == d


def test_from_dict_unknown_keys_fold_into_params() -> None:
    """Legacy action dicts with extra top-level keys round-trip cleanly."""
    legacy = {"op": "create", "resource_id": "x", "weird_legacy_field": 42}
    a = PluginAction.from_dict(legacy)
    assert a.op == "create"
    assert a.params == {"weird_legacy_field": 42}


def test_dict_compatibility() -> None:
    """PluginAction supports dict-style access for callers expecting dicts."""
    a = PluginAction(op="create", resource_id="x")
    assert a["op"] == "create"
    assert "op" in a
    assert a.get("missing", "default") == "default"


def test_validate_actions_empty_list() -> None:
    assert validate_actions([]) == []


def test_validate_actions_missing_op() -> None:
    a = PluginAction(op="", resource_id="x")
    errors = validate_actions([a])
    assert any("missing 'op'" in e for e in errors)


def test_validate_actions_missing_resource_id() -> None:
    a = PluginAction(op="create")
    errors = validate_actions([a])
    assert any("missing 'resource_id'" in e for e in errors)


def test_validate_actions_duplicate_resource_id() -> None:
    actions = [
        PluginAction(op="create", resource_id="dup"),
        PluginAction(op="update", resource_id="dup"),
    ]
    errors = validate_actions(actions)
    assert any("Duplicate resource_id" in e for e in errors)


def test_validate_actions_unknown_dependency() -> None:
    actions = [
        PluginAction(op="create", resource_id="child", depends_on=["missing"]),
    ]
    errors = validate_actions(actions)
    assert any("depends on unknown" in e for e in errors)


def test_validate_actions_valid_dependency() -> None:
    actions = [
        PluginAction(op="create", resource_id="parent"),
        PluginAction(op="update", resource_id="child", depends_on=["parent"]),
    ]
    assert validate_actions(actions) == []
