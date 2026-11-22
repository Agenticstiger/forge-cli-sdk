"""Test harnesses for FLUID plugin conformance — one per role, plus snapshots.

* :class:`PluginTestHarness` — universal harness for any :class:`BasePlugin`.
* :class:`CustomScaffoldTestHarness` — determinism, idempotency, path-traversal.
* :class:`ValidatorTestHarness` — finding severities + apply summarisation.
* :class:`InfraProviderTestHarness` — role/subclass conformance (apply skipped).
* :class:`CatalogAdapterTestHarness` — role/subclass conformance (apply skipped).
* :class:`AlertNotifierTestHarness` — an alert route kind (``fluid_build.alert_notifiers``).
* :class:`MaintenanceActionTestHarness` — a maintenance action (``fluid_build.maintenance_actions``).
* :class:`CommandPluginTestHarness` — a CLI subcommand (``fluid_build.commands``).
* :func:`assert_plan_matches_snapshot` — zero-dep golden-file plan snapshots.

Subclass the harness matching your plugin's role in your test suite; pytest
auto-discovers every ``test_*`` method.
"""

from .fixtures import LOCAL_CONTRACT, MINIMAL_CONTRACT
from .group_harnesses import (
    AlertNotifierTestHarness,
    CommandPluginTestHarness,
    MaintenanceActionTestHarness,
)
from .harness import PluginTestHarness
from .role_harnesses import (
    CatalogAdapterTestHarness,
    CustomScaffoldTestHarness,
    InfraProviderTestHarness,
    ValidatorTestHarness,
)
from .snapshot import assert_plan_matches_snapshot

__all__ = [
    "PluginTestHarness",
    "CustomScaffoldTestHarness",
    "ValidatorTestHarness",
    "InfraProviderTestHarness",
    "CatalogAdapterTestHarness",
    "AlertNotifierTestHarness",
    "MaintenanceActionTestHarness",
    "CommandPluginTestHarness",
    "assert_plan_matches_snapshot",
    "LOCAL_CONTRACT",
    "MINIMAL_CONTRACT",
]
