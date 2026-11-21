"""``CustomScaffold.apply`` writes through an exclusively created temp file.

The default ``apply()`` used to stage each file at ``<target>.tmp~`` by path. A symlink
planted there (a checked-out repository can carry one) sent the write and the ``chmod``
to a file outside the output directory, and the final rename turned the output file into
a symlink to it. These tests pin the fix and the behaviour around it.
"""

from __future__ import annotations

import base64
import os
import stat
from pathlib import Path
from typing import Any, Iterable, Mapping

import pytest

from fluid_sdk import CustomScaffold, ExecutionResult, write_file_action
from fluid_sdk.testing import CustomScaffoldTestHarness


class _Scaffold(CustomScaffold):
    """Default ``apply()``; the plan is irrelevant to these tests."""

    name = "atomic-write-scaffold"

    def plan(self, contract):
        return [write_file_action(path="a.txt", content=b"PAYLOAD").to_dict()]


def _victim(root: Path) -> Path:
    victim = root / "victim.txt"
    victim.write_text("ORIGINAL")
    victim.chmod(0o600)
    return victim


def _symlink(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):  # e.g. Windows without the privilege
        pytest.skip("symlinks are not available here")


def _write(scaffold: CustomScaffold, path: str, content: bytes = b"PAYLOAD", **kwargs: Any):
    return scaffold.apply([write_file_action(path=path, content=content, **kwargs).to_dict()])


# ── the fix: a planted link is never opened ──────────────────────────────────


@pytest.mark.parametrize("suffix", [".tmp~", ".tmp", "~", ".part"])
@pytest.mark.parametrize("rel", ["a.txt", "sub/dir/a.txt"])
def test_a_symlink_at_a_temp_style_name_is_never_followed(
    tmp_path: Path, rel: str, suffix: str
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    victim = _victim(tmp_path)
    link = out / (rel + suffix)
    _symlink(link, victim)

    result = _write(_Scaffold(output_root=out), rel)

    assert (result.applied, result.failed) == (1, 0)
    # The file outside the output directory is untouched: content and mode.
    assert victim.read_text() == "ORIGINAL"
    assert stat.S_IMODE(victim.stat().st_mode) == stat.S_IMODE(0o600)
    # The output is correct: a regular file, not a link to the victim.
    target = out / rel
    assert target.is_file() and not target.is_symlink()
    assert target.read_bytes() == b"PAYLOAD"
    # The planted link is still there, still pointing at the victim: apply() never touched it.
    assert link.is_symlink() and os.readlink(link) == str(victim)


def test_a_successful_write_leaves_no_temp_file(tmp_path: Path) -> None:
    result = _write(_Scaffold(output_root=tmp_path), "sub/a.txt")

    assert (result.applied, result.failed) == (1, 0)
    assert sorted(p.name for p in (tmp_path / "sub").iterdir()) == ["a.txt"]


def test_a_failed_rename_removes_its_temp_file(tmp_path: Path) -> None:
    (tmp_path / "a.txt").mkdir()  # a directory where the file must go: the rename fails

    result = _write(_Scaffold(output_root=tmp_path), "a.txt")

    assert (result.applied, result.failed) == (0, 1)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.txt"]  # only the directory


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
@pytest.mark.parametrize("mode", [0o644, 0o755, 0o600])
def test_the_planned_mode_is_applied_exactly_whatever_the_umask(tmp_path: Path, mode: int) -> None:
    previous = os.umask(0o077)
    try:
        _write(_Scaffold(output_root=tmp_path), "run.sh", mode=mode)
    finally:
        os.umask(previous)

    assert stat.S_IMODE((tmp_path / "run.sh").stat().st_mode) == mode


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_without_fchmod_the_mode_is_set_by_name_on_the_fresh_temp_file(
    tmp_path: Path, monkeypatch
) -> None:
    # Windows before Python 3.13 has no os.fchmod: the fallback chmods the temp file by its
    # random, just-created name. Simulate the platform by removing fchmod.
    monkeypatch.delattr(os, "fchmod")

    result = _write(_Scaffold(output_root=tmp_path), "run.sh", mode=0o755)

    assert (result.applied, result.failed) == (1, 0)
    assert stat.S_IMODE((tmp_path / "run.sh").stat().st_mode) == 0o755
    assert sorted(p.name for p in tmp_path.iterdir()) == ["run.sh"]


def test_a_file_name_near_the_filesystem_limit_still_writes(tmp_path: Path) -> None:
    name = "n" * 240 + ".txt"  # the temp name is longer than the target's: it must still fit

    result = _write(_Scaffold(output_root=tmp_path), name)

    assert (result.applied, result.failed) == (1, 0)
    assert (tmp_path / name).read_bytes() == b"PAYLOAD"


# ── behaviour that must not change ───────────────────────────────────────────


def test_a_symlinked_target_inside_the_root_is_written_through_as_before(tmp_path: Path) -> None:
    (tmp_path / "real.txt").write_text("old")
    _symlink(tmp_path / "link.txt", tmp_path / "real.txt")

    result = _write(_Scaffold(output_root=tmp_path), "link.txt")

    assert (result.applied, result.failed) == (1, 0)
    assert (tmp_path / "real.txt").read_bytes() == b"PAYLOAD"
    assert (tmp_path / "link.txt").is_symlink()


def test_a_symlinked_target_that_leaves_the_root_is_still_rejected(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    victim = _victim(tmp_path)
    _symlink(out / "a.txt", victim)

    result = _write(_Scaffold(output_root=out), "a.txt")

    assert (result.applied, result.failed) == (0, 1)
    assert "escapes output root" in result.results[0]["error"]
    assert victim.read_text() == "ORIGINAL"


# ── the conformance harness catches the vulnerable pattern ───────────────────


class _NaiveScaffold(CustomScaffold):
    """A hand-rolled ``apply()`` that stages each file at a predictable temp name."""

    name = "naive-scaffold"

    def plan(self, contract):
        return [write_file_action(path="a.txt", content=b"x").to_dict()]

    def apply(self, actions: Iterable[Mapping[str, Any]]) -> ExecutionResult:
        applied = 0
        for action in actions:
            params = action["params"]
            target = self.output_root / params["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(target.name + ".tmp~")
            tmp.write_bytes(base64.b64decode(params["content_b64"]))
            os.replace(tmp, target)
            applied += 1
        return ExecutionResult(plugin=self.name, role=self.role, applied=applied)


class TestDefaultApplyConformance(CustomScaffoldTestHarness):
    """The inherited ``apply()`` passes the full harness, the symlink check included."""

    plugin_class = _Scaffold
    sample_contracts = [{"id": "demo"}]


def test_the_harness_flags_an_apply_that_writes_through_a_planted_temp_symlink() -> None:
    class _NaiveHarness(CustomScaffoldTestHarness):
        plugin_class = _NaiveScaffold
        sample_contracts = [{"id": "demo"}]

    with pytest.raises(AssertionError, match="planted symlink"):
        _NaiveHarness().test_apply_does_not_write_through_planted_symlinks()


def test_the_harness_check_is_vacuous_without_sample_contracts_or_an_output_root() -> None:
    class _NoContracts(CustomScaffoldTestHarness):
        plugin_class = _NaiveScaffold
        allow_no_sample_contracts = True

    class _NoOutputRoot(CustomScaffoldTestHarness):
        plugin_class = _NaiveScaffold
        sample_contracts = [{"id": "demo"}]
        requires_output_root = False

    _NoContracts().test_apply_does_not_write_through_planted_symlinks()
    _NoOutputRoot().test_apply_does_not_write_through_planted_symlinks()
