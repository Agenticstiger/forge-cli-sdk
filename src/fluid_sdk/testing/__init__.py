"""Test harnesses for FLUID plugin conformance.

* :class:`PluginTestHarness` — universal harness for any :class:`BasePlugin`.
* :class:`CustomScaffoldTestHarness` — adds determinism, idempotency,
  path-traversal safety checks specific to file-emitting plugins.

Subclass the right harness in your plugin's test suite; pytest auto-discovers
every ``test_*`` method.
"""

from .fixtures import LOCAL_CONTRACT, MINIMAL_CONTRACT
from .harness import PluginTestHarness
from .role_harnesses import CustomScaffoldTestHarness

__all__ = [
    "PluginTestHarness",
    "CustomScaffoldTestHarness",
    "LOCAL_CONTRACT",
    "MINIMAL_CONTRACT",
]
