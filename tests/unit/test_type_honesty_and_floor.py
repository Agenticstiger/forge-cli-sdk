"""Pins for the type-honesty + conformance-floor hardening:

* ``PluginAction.from_dict`` coerces ``phase`` into the closed ``Phase`` domain
  (it used to re-stringify a bare ``str``).
* The reference ``apply`` implementations consume ``ActionStatus`` (it was an
  exported-but-unused island).
* The universal harness now requires sample contracts (no silent pass on empty)
  and checks an EXACT apply-reflects-plan ledger.
"""

from __future__ import annotations

import pytest

from fluid_sdk import (
    ActionStatus,
    CustomScaffold,
    Phase,
    PluginAction,
    Validator,
    write_file_action,
)
from fluid_sdk.roles import Finding
from fluid_sdk.testing import LOCAL_CONTRACT, PluginTestHarness

# ── Phase coercion in from_dict ───────────────────────────────────────


def test_from_dict_coerces_phase_to_domain_member():
    a = PluginAction.from_dict({"op": "create", "resource_id": "x", "phase": "build"})
    assert a.phase is Phase.BUILD  # a real Phase member, not the bare str "build"


def test_from_dict_unknown_phase_falls_back_to_default():
    a = PluginAction.from_dict({"op": "create", "resource_id": "x", "phase": "not-a-phase"})
    assert a.phase is Phase.DEFAULT


def test_from_dict_missing_phase_is_default():
    a = PluginAction.from_dict({"op": "create", "resource_id": "x"})
    assert a.phase is Phase.DEFAULT


# ── ActionStatus consumed by the reference apply impls ────────────────


class _Scaffold(CustomScaffold):
    name = "status-scaffold"

    def plan(self, contract):
        return [write_file_action(path="a.txt", content=b"hi").to_dict()]


def test_scaffold_apply_status_uses_action_status_domain(tmp_path):
    plugin = _Scaffold(output_root=tmp_path)
    result = plugin.apply(plugin.plan(LOCAL_CONTRACT))
    statuses = {r["status"] for r in result.results}
    # The emitted status strings are exactly the ActionStatus vocabulary.
    assert statuses <= {s.value for s in ActionStatus}
    assert ActionStatus.OK.value in statuses


class _Val(Validator):
    name = "status-validator"

    def plan(self, contract):
        return [Finding(severity="warn", code="C", message="m").to_action().to_dict()]


def test_validator_apply_status_is_reported():
    v = _Val()
    result = v.apply(v.plan({}))
    assert result.results[0]["status"] == ActionStatus.REPORTED.value


# ── conformance floor: fail on empty sample_contracts ─────────────────


def test_harness_requires_sample_contracts_by_default():
    class _Bare(CustomScaffold):
        name = "bare"

        def plan(self, contract):
            return []

    class _Harness(PluginTestHarness):
        plugin_class = _Bare
        # no sample_contracts, allow_no_sample_contracts defaults False

    with pytest.raises(AssertionError, match="no sample_contracts"):
        _Harness().test_sample_contracts_present()


def test_harness_opt_out_allows_empty():
    class _Bare(CustomScaffold):
        name = "bare"

        def plan(self, contract):
            return []

    class _Harness(PluginTestHarness):
        plugin_class = _Bare
        allow_no_sample_contracts = True

    _Harness().test_sample_contracts_present()  # does not raise


# ── conformance floor: EXACT apply-reflects-plan ledger ───────────────


def test_apply_reflects_plan_is_exact_not_a_net():
    """A plugin whose apply under-counts must FAIL the ledger (it used to slip
    through the old `>=` net)."""
    from fluid_sdk import ExecutionResult

    class _UnderCount(Validator):
        name = "undercount"

        def plan(self, contract):
            return [
                Finding(severity="warn", code="A", message="a").to_action().to_dict(),
                Finding(severity="warn", code="B", message="b").to_action().to_dict(),
            ]

        def apply(self, actions):
            # Wrongly reports a single result record for two planned actions.
            return ExecutionResult(plugin=self.name, role=self.role, results=[{"status": "ok"}])

    class _Harness(PluginTestHarness):
        plugin_class = _UnderCount
        sample_contracts = [LOCAL_CONTRACT]
        skip_apply = False

    with pytest.raises(AssertionError, match="exactly one result per planned action"):
        _Harness().test_apply_reflects_plan()
