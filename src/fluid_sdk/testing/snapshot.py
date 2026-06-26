"""Zero-dependency golden-file snapshot helper for plugin plan output.

Mirrors syrupy's UX (https://github.com/syrupy-project/syrupy) without taking
the dependency, to keep the SDK stdlib-only:

* ``FLUID_SNAPSHOT_UPDATE=1`` (or ``update=True``) writes/refreshes the snapshot
  and passes.
* Otherwise the live plan is compared to the stored snapshot.
* A **missing** snapshot fails (syrupy's "sound" rule — a forgotten snapshot is
  a test gap, not a silent pass), telling you how to create it.

Snapshots are canonical JSON (``sort_keys=True``) of the normalised plan, so
field reordering never produces a spurious diff. dbt's adapter test suite pins
expected output the same way; this brings that output-pinning discipline to
every plugin role.

Usage in a plugin's test file::

    from pathlib import Path
    from fluid_sdk.testing import assert_plan_matches_snapshot, LOCAL_CONTRACT
    from my_pkg.scaffold import MyScaffold

    SNAP = Path(__file__).parent / "__snapshots__"

    def test_plan_snapshot():
        assert_plan_matches_snapshot(
            MyScaffold(), LOCAL_CONTRACT, snapshot_dir=SNAP, name="local_plan"
        )
"""

from __future__ import annotations

import difflib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Union

UPDATE_ENV = "FLUID_SNAPSHOT_UPDATE"


def _as_dict(action: Any) -> Any:
    if hasattr(action, "to_dict"):
        return action.to_dict()
    return action


def _canonical(actions: Iterable[Any]) -> str:
    normalised = [_as_dict(a) for a in actions]
    return json.dumps(normalised, indent=2, sort_keys=True) + "\n"


def assert_plan_matches_snapshot(
    plugin: Any,
    contract: Mapping[str, Any],
    *,
    snapshot_dir: Union[str, Path],
    name: str,
    update: Optional[bool] = None,
) -> None:
    """Assert ``plugin.plan(contract)`` matches a stored golden snapshot.

    Args:
        plugin: a plugin instance (anything with ``plan(contract)``).
        contract: the contract to plan against.
        snapshot_dir: directory holding ``<name>.json`` snapshots.
        name: snapshot file stem.
        update: force write (True) / compare (False). ``None`` reads
            ``FLUID_SNAPSHOT_UPDATE`` from the environment.
    """
    actual = _canonical(plugin.plan(contract))
    snap_path = Path(snapshot_dir) / f"{name}.json"
    updating = (os.environ.get(UPDATE_ENV) == "1") if update is None else update

    if updating:
        snap_path.parent.mkdir(parents=True, exist_ok=True)
        snap_path.write_text(actual, encoding="utf-8")
        return

    if not snap_path.exists():
        raise AssertionError(
            f"snapshot {snap_path} does not exist — run with {UPDATE_ENV}=1 "
            f"(or pass update=True) to create it"
        )

    expected = snap_path.read_text(encoding="utf-8")
    if expected != actual:
        diff = "".join(
            difflib.unified_diff(
                expected.splitlines(keepends=True),
                actual.splitlines(keepends=True),
                fromfile=str(snap_path),
                tofile="<live plan>",
            )
        )
        raise AssertionError(
            f"plan snapshot mismatch for {name!r}; set {UPDATE_ENV}=1 to update.\n{diff}"
        )


__all__ = ["assert_plan_matches_snapshot", "UPDATE_ENV"]
