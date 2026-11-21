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
from typing import Any, Callable, Iterable, Mapping, Sequence

import pytest

from fluid_sdk import CustomScaffold, ExecutionResult, write_file_action
from fluid_sdk.testing import CustomScaffoldTestHarness

_PLAN = [write_file_action(path="a.txt", content=b"PAYLOAD").to_dict()]


class _Scaffold(CustomScaffold):
    """Default ``apply()``; the plan is irrelevant to these tests."""

    name = "atomic-write-scaffold"

    def plan(self, contract):
        return list(_PLAN)


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


@pytest.mark.parametrize("name", ["n" * 240 + ".txt", "字" * 82, "weird name (1) é.txt"])
def test_long_multibyte_and_odd_file_names_still_write(tmp_path: Path, name: str) -> None:
    # The temp name must not be longer than the target's, or a name near the 255-byte limit
    # (in bytes, not characters) would start to fail.
    result = _write(_Scaffold(output_root=tmp_path), name)

    assert (result.applied, result.failed) == (1, 0)
    assert (tmp_path / name).read_bytes() == b"PAYLOAD"
    assert len(list(tmp_path.iterdir())) == 1


def test_the_temp_file_is_hidden_and_marked_tmp(tmp_path: Path, monkeypatch) -> None:
    seen = []
    real_replace = os.replace

    def spy(src, dst):
        seen.append(Path(src).name)
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)

    _write(_Scaffold(output_root=tmp_path), "docs/README.md")

    assert len(seen) == 1
    assert seen[0].startswith(".README.md.") and seen[0].endswith(".tmp~")


def test_a_path_that_names_the_output_root_itself_is_rejected_before_any_write(
    tmp_path: Path,
) -> None:
    out = tmp_path / "out"
    out.mkdir()

    result = _write(_Scaffold(output_root=out), ".")

    assert (result.applied, result.failed) == (0, 1)
    assert "is the output root itself" in result.results[0]["error"]
    # Nothing was created beside the output root (a temp file would have been).
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out"]
    assert list(out.iterdir()) == []


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


_PREDICTABLE_STAGING = {
    "name + .tmp~": lambda t: t.with_name(t.name + ".tmp~"),
    "with_suffix .tmp": lambda t: t.with_suffix(".tmp"),
    "name + .new": lambda t: t.with_name(t.name + ".new"),
    "dot + name + .tmp": lambda t: t.with_name("." + t.name + ".tmp"),
}


def _naive_scaffold(stage: Callable[[Path], Path], paths: Sequence[str] = ("a.txt",)) -> type:
    """A hand-rolled ``apply()`` that stages each file at a predictable temp name."""

    class _Naive(CustomScaffold):
        name = "naive-scaffold"

        def plan(self, contract):
            return [write_file_action(path=p, content=b"x").to_dict() for p in paths]

        def apply(self, actions: Iterable[Mapping[str, Any]]) -> ExecutionResult:
            applied = 0
            for action in actions:
                params = action["params"]
                target = self.output_root / params["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = stage(target)
                tmp.write_bytes(base64.b64decode(params["content_b64"]))
                os.replace(tmp, target)
                applied += 1
            return ExecutionResult(plugin=self.name, role=self.role, applied=applied)

    return _Naive


class TestDefaultApplyConformance(CustomScaffoldTestHarness):
    """The inherited ``apply()`` passes the full harness, the symlink check included."""

    plugin_class = _Scaffold
    sample_contracts = [{"id": "demo"}]


@pytest.mark.parametrize("scheme", sorted(_PREDICTABLE_STAGING))
def test_the_harness_flags_an_apply_that_stages_under_a_predictable_name(scheme: str) -> None:
    class _NaiveHarness(CustomScaffoldTestHarness):
        plugin_class = _naive_scaffold(_PREDICTABLE_STAGING[scheme])
        sample_contracts = [{"id": "demo"}]

    with pytest.raises(AssertionError, match="planted symlink"):
        _NaiveHarness().test_apply_does_not_write_through_planted_symlinks()


def test_the_harness_does_not_plant_a_name_the_plugin_itself_needs() -> None:
    # `pkg.part` is a directory the plugin writes into, `a.tmp` would be planted twice
    # (from a.txt and a.md): neither may break a correct plugin.
    class _Collisions(CustomScaffoldTestHarness):
        plugin_class = _naive_scaffold(
            lambda t: t.with_name(f".{t.name}.{os.getpid()}.staging.invalid~"),
            paths=("pkg", "pkg.part/mod.py", "a.txt", "a.md"),
        )
        sample_contracts = [{"id": "demo"}]

    _Collisions().test_apply_does_not_write_through_planted_symlinks()


def test_planned_paths_are_normalised_before_the_harness_picks_names_to_plant() -> None:
    # `./x.tmp` is a planned file, and `x.txt` would make the harness plant `x.tmp` (the
    # `{stem}.tmp` shape): a plugin that writes its targets directly must not be failed
    # for writing a file it planned.
    class _DirectWriter(CustomScaffold):
        name = "direct-writer"

        def plan(self, contract):
            return [write_file_action(path=p, content=b"x").to_dict() for p in ("./x.tmp", "x.txt")]

        def apply(self, actions: Iterable[Mapping[str, Any]]) -> ExecutionResult:
            for action in actions:
                target = self.output_root / action["params"]["path"]
                target.write_bytes(base64.b64decode(action["params"]["content_b64"]))
            return ExecutionResult(plugin=self.name, role=self.role, applied=2)

    class _Harness(CustomScaffoldTestHarness):
        plugin_class = _DirectWriter
        sample_contracts = [{"id": "demo"}]

    _Harness().test_apply_does_not_write_through_planted_symlinks()


def test_the_harness_check_is_vacuous_without_sample_contracts_or_an_output_root() -> None:
    class _NoContracts(CustomScaffoldTestHarness):
        plugin_class = _naive_scaffold(_PREDICTABLE_STAGING["name + .tmp~"])
        allow_no_sample_contracts = True

    class _NoOutputRoot(CustomScaffoldTestHarness):
        plugin_class = _naive_scaffold(_PREDICTABLE_STAGING["name + .tmp~"])
        sample_contracts = [{"id": "demo"}]
        requires_output_root = False

    _NoContracts().test_apply_does_not_write_through_planted_symlinks()
    _NoOutputRoot().test_apply_does_not_write_through_planted_symlinks()
