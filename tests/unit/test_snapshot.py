"""Unit tests for the zero-dep golden-file snapshot helper."""

from __future__ import annotations

import pytest

from fluid_sdk import CustomScaffold, write_file_action
from fluid_sdk.testing import LOCAL_CONTRACT, assert_plan_matches_snapshot


class _Scaffold(CustomScaffold):
    name = "snap-scaffold"

    def __init__(self, *, body: str = "hello", **kw):
        super().__init__(**kw)
        self._body = body

    def plan(self, contract):
        return [write_file_action(path="README.md", content=self._body.encode()).to_dict()]


def test_missing_snapshot_fails_until_created(tmp_path) -> None:
    plugin = _Scaffold()
    # Sound rule (syrupy): a missing snapshot is a failure, not a silent pass.
    with pytest.raises(AssertionError, match="does not exist"):
        assert_plan_matches_snapshot(
            plugin, LOCAL_CONTRACT, snapshot_dir=tmp_path, name="plan", update=False
        )


def test_update_writes_then_compare_passes(tmp_path) -> None:
    plugin = _Scaffold()
    # Write it.
    assert_plan_matches_snapshot(
        plugin, LOCAL_CONTRACT, snapshot_dir=tmp_path, name="plan", update=True
    )
    assert (tmp_path / "plan.json").exists()
    # Compare against the just-written snapshot — passes.
    assert_plan_matches_snapshot(
        plugin, LOCAL_CONTRACT, snapshot_dir=tmp_path, name="plan", update=False
    )


def test_drift_is_detected(tmp_path) -> None:
    assert_plan_matches_snapshot(
        _Scaffold(body="v1"), LOCAL_CONTRACT, snapshot_dir=tmp_path, name="plan", update=True
    )
    # A changed plan must fail the comparison.
    with pytest.raises(AssertionError, match="snapshot mismatch"):
        assert_plan_matches_snapshot(
            _Scaffold(body="v2"), LOCAL_CONTRACT, snapshot_dir=tmp_path, name="plan", update=False
        )
