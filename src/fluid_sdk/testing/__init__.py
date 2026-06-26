"""Test harnesses for FLUID plugin conformance — one per role, plus snapshots.

* :class:`PluginTestHarness` — universal harness for any :class:`BasePlugin`.
* :class:`CustomScaffoldTestHarness` — determinism, idempotency, path-traversal.
* :class:`ValidatorTestHarness` — finding severities + apply summarisation.
* :class:`InfraProviderTestHarness` — role/subclass conformance (apply skipped).
* :class:`CatalogAdapterTestHarness` — role/subclass conformance (apply skipped).
* :func:`assert_plan_matches_snapshot` — zero-dep golden-file plan snapshots.

Subclass the harness matching your plugin's role in your test suite; pytest
auto-discovers every ``test_*`` method.
"""

from .fixtures import LOCAL_CONTRACT, MINIMAL_CONTRACT
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
    "assert_plan_matches_snapshot",
    "LOCAL_CONTRACT",
    "MINIMAL_CONTRACT",
]
