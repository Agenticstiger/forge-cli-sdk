"""Unit tests for ``fluid_sdk.roles.custom_scaffold``."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from fluid_sdk import (
    CustomScaffold,
    ExecutionResult,
    ScaffoldFile,
    write_file_action,
)
from fluid_sdk.action import PHASE_SCAFFOLD


def test_scaffold_file_sha256() -> None:
    f = ScaffoldFile(path="x.txt", content=b"hello")
    assert f.sha256 == hashlib.sha256(b"hello").hexdigest()


def test_write_file_action_canonical() -> None:
    action = write_file_action(path="ci/.gitlab-ci.yml", content=b"foo: bar\n")
    assert action.op == "write_file"
    assert action.resource_type == "file"
    assert action.resource_id == "ci/.gitlab-ci.yml"
    assert action.phase == PHASE_SCAFFOLD
    params = action.params
    assert params["path"] == "ci/.gitlab-ci.yml"
    assert base64.b64decode(params["content_b64"]) == b"foo: bar\n"
    assert params["sha256"] == hashlib.sha256(b"foo: bar\n").hexdigest()
    assert params["size_bytes"] == len(b"foo: bar\n")
    assert params["mode"] == 0o644


def test_write_file_action_explicit_resource_id() -> None:
    action = write_file_action(
        path="ci/.gitlab-ci.yml",
        content=b"foo",
        resource_id="ci-main",
        description="main pipeline",
        depends_on=["ci-prelude"],
        tags={"layer": "ci"},
    )
    assert action.resource_id == "ci-main"
    assert action.description == "main pipeline"
    assert action.depends_on == ["ci-prelude"]
    assert action.tags == {"layer": "ci"}


# ---------------------------------------------------------------------------
# Toy CustomScaffold subclass for default-apply tests
# ---------------------------------------------------------------------------


class _ToyScaffold(CustomScaffold):
    name = "toy-scaffold"

    def plan(self, contract):
        product_id = contract.get("id", "unknown")
        return [
            write_file_action(
                path="README.md",
                content=f"# {product_id}\n".encode("utf-8"),
            ).to_dict(),
            write_file_action(
                path=f"products/{product_id}.yaml",
                content=f"id: {product_id}\n".encode("utf-8"),
            ).to_dict(),
        ]


def test_default_apply_writes_files(tmp_path: Path) -> None:
    scaffold = _ToyScaffold(output_root=tmp_path)
    actions = scaffold.plan({"id": "demo"})
    result = scaffold.apply(actions)

    assert isinstance(result, ExecutionResult)
    assert result.applied == 2
    assert result.failed == 0
    assert result.plugin == "toy-scaffold"
    assert result.role == "custom_scaffold"
    assert (tmp_path / "README.md").read_text() == "# demo\n"
    assert (tmp_path / "products" / "demo.yaml").read_text() == "id: demo\n"


def test_apply_is_idempotent(tmp_path: Path) -> None:
    """Re-applying the same actions must be byte-identical."""
    scaffold = _ToyScaffold(output_root=tmp_path)
    actions = scaffold.plan({"id": "demo"})

    scaffold.apply(actions)
    first_bytes = {
        p.relative_to(tmp_path).as_posix(): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }

    scaffold.apply(actions)
    second_bytes = {
        p.relative_to(tmp_path).as_posix(): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }

    assert first_bytes == second_bytes


def test_path_traversal_rejected(tmp_path: Path) -> None:
    """Writing outside output_root must fail."""
    scaffold = _ToyScaffold(output_root=tmp_path)
    evil_action = write_file_action(
        path="../escape.txt",
        content=b"haha",
    ).to_dict()
    result = scaffold.apply([evil_action])
    assert result.applied == 0
    assert result.failed == 1
    assert "escapes output root" in result.results[0]["error"]


def test_sha256_mismatch_rejected(tmp_path: Path) -> None:
    """A tampered action (wrong sha256) is rejected at apply."""
    scaffold = _ToyScaffold(output_root=tmp_path)
    action = write_file_action(path="x.txt", content=b"original").to_dict()
    # Tamper: change content_b64 without updating sha256.
    action["params"]["content_b64"] = base64.b64encode(b"tampered").decode("ascii")
    result = scaffold.apply([action])
    assert result.failed == 1
    assert "sha256 mismatch" in result.results[0]["error"]


def test_unsupported_op_skipped(tmp_path: Path) -> None:
    """Default apply skips unknown ops with a warning rather than failing."""
    scaffold = _ToyScaffold(output_root=tmp_path)
    action = {"op": "create_dataset", "resource_id": "ds1", "params": {}}
    result = scaffold.apply([action])
    assert result.applied == 0
    assert result.failed == 0
    assert any("unsupported op" in w for w in result.warnings)
    assert result.results[0]["status"] == "skipped"


def test_role_is_set() -> None:
    assert _ToyScaffold.role == "custom_scaffold"


def test_plan_determinism() -> None:
    """Same contract twice must produce identical plans."""
    scaffold = _ToyScaffold(output_root=Path("/tmp"))
    plan1 = scaffold.plan({"id": "demo"})
    plan2 = scaffold.plan({"id": "demo"})
    assert plan1 == plan2
