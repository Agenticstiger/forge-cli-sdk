"""Docs-honesty CI gate.

Scans every Markdown doc for ``from fluid_sdk[.sub] import ...`` statements and
``fluid_build.<group>`` entry-point group names, and asserts each one actually
resolves against the installed package. This is the anti-drift guarantee: a doc
can never again advertise an export, harness, or entry-point group that doesn't
exist (the bug this gate was written to catch was ``PluginHookSpec``, documented
but never exported).

It deliberately scans real ``import`` statements rather than a hand-maintained
allowlist, so the gate tracks the docs automatically.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import Set, Tuple

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Markdown docs that make API promises.
_DOC_GLOBS = ["README.md", "CHANGELOG.md", "docs/**/*.md"]

# Entry-point groups the FLUID ecosystem defines (SDK roles + CLI-internal groups).
# A doc referencing a group outside this set is almost certainly a typo.
_KNOWN_GROUPS = {
    "fluid_build.providers",
    "fluid_build.validators",
    "fluid_build.catalog_adapters",
    "fluid_build.custom_scaffolds",
    "fluid_build.iac_providers",
    "fluid_build.extension_schemas",
    "fluid_build.extension_validators",
    "fluid_build.commands",
    "fluid_build.apply_hooks",
    "fluid_build.modeling_techniques",
    "fluid_build.source_adapters",
}

# `from fluid_sdk[.sub] import ( ... )`  OR  `from fluid_sdk[.sub] import a, b`
_IMPORT_RE = re.compile(
    r"from\s+(fluid_sdk(?:\.[\w.]+)?)\s+import\s+(\([^)]*\)|[^\n#]+)",
)
_GROUP_RE = re.compile(r"fluid_build\.[a-z_]+")

# Markdown fenced code blocks, and the FIRST token of a `fluid <command>` invocation
# inside one (the top-level subcommand; flags are skipped by the `[a-z]` start).
_FENCE_RE = re.compile(r"```[\w]*\n(.*?)```", re.DOTALL)
_FLUID_CMD_RE = re.compile(r"(?m)^\s*\$?\s*fluid\s+([a-z][a-z0-9-]*)\b")
# Columns the `fluid plugins` command provably cannot emit — it reads entry-point
# names + allow/block status only and never loads plugin code to read PluginMetadata.
_IMPOSSIBLE_PLUGINS_COLUMNS = ("VERSION", "AUTHOR", "DESCRIPTION")


def _docs() -> list:
    files = []
    for pattern in _DOC_GLOBS:
        files.extend(_REPO_ROOT.glob(pattern))
    return sorted(f for f in files if f.is_file())


def _fenced_blocks(text: str):
    return _FENCE_RE.findall(text)


def _documented_fluid_commands() -> Set[Tuple[str, str]]:
    """Return {(doc_relpath, command)} for every `fluid <command>` in a code fence."""
    out: Set[Tuple[str, str]] = set()
    for doc in _docs():
        rel = str(doc.relative_to(_REPO_ROOT))
        for block in _fenced_blocks(doc.read_text(encoding="utf-8")):
            for cmd in _FLUID_CMD_RE.findall(block):
                out.add((rel, cmd))
    return out


def _cli_top_level_commands():
    """The CLI's real top-level subcommands, or ``None`` if the CLI isn't installed.

    The SDK is zero-dependency and its CI does not install the ``data-product-forge``
    CLI, so this returns ``None`` there and the command-existence check skips.
    """
    import importlib.util

    if importlib.util.find_spec("fluid_build") is None:
        return None
    try:
        from fluid_build.cli import build_parser

        parser = build_parser()
        cmds: Set[str] = set()
        groups = getattr(parser, "_subparsers", None)
        for action in (groups._group_actions if groups else []):
            cmds |= set(getattr(action, "choices", {}) or {})
        return cmds
    except Exception:
        return None


def _clean_name(token: str) -> str:
    token = token.strip().strip("(),")
    # strip an `as alias`
    token = token.split(" as ")[0].strip()
    return token


def _collect_imports() -> Set[Tuple[str, str, str]]:
    """Return {(module, symbol, doc_relpath)} for every fluid_sdk import in the docs."""
    found: Set[Tuple[str, str, str]] = set()
    for doc in _docs():
        # Strip Python `# ...` inline comments first: a `)` inside a comment
        # (e.g. `# user-actionable (auth, env)`) would otherwise truncate a
        # parenthesised import block and hide later symbols from the gate.
        text = re.sub(r"#[^\n]*", "", doc.read_text(encoding="utf-8"))
        rel = str(doc.relative_to(_REPO_ROOT))
        for module, names_blob in _IMPORT_RE.findall(text):
            for raw in names_blob.replace("\n", ",").split(","):
                name = _clean_name(raw)
                if name and name.isidentifier():
                    found.add((module, name, rel))
    return found


def test_every_documented_fluid_sdk_import_resolves() -> None:
    """Every ``from fluid_sdk... import X`` in the docs must actually import."""
    broken = []
    for module, name, doc in sorted(_collect_imports()):
        try:
            mod = importlib.import_module(module)
        except Exception as e:  # noqa: BLE001
            broken.append(f"{doc}: `import {module}` failed ({type(e).__name__})")
            continue
        if not hasattr(mod, name):
            broken.append(f"{doc}: `from {module} import {name}` — {module} has no {name!r}")
    assert not broken, "Docs advertise symbols that don't exist:\n  " + "\n  ".join(broken)


def test_top_level_documented_symbols_are_public() -> None:
    """Symbols documented as ``from fluid_sdk import X`` must be in ``__all__``."""
    import fluid_sdk

    public = set(fluid_sdk.__all__)
    missing = sorted(
        f"{doc}: {name}"
        for module, name, doc in _collect_imports()
        if module == "fluid_sdk" and name not in public
    )
    assert (
        not missing
    ), "Documented top-level symbols missing from fluid_sdk.__all__:\n  " + "\n  ".join(missing)


def test_documented_entrypoint_groups_are_known() -> None:
    """Every ``fluid_build.<group>`` named in the docs is a real group (no typos)."""
    unknown = []
    for doc in _docs():
        text = doc.read_text(encoding="utf-8")
        rel = str(doc.relative_to(_REPO_ROOT))
        for group in _GROUP_RE.findall(text):
            if group not in _KNOWN_GROUPS:
                unknown.append(f"{rel}: {group}")
    assert not unknown, "Docs reference unknown entry-point groups:\n  " + "\n  ".join(
        sorted(set(unknown))
    )


@pytest.mark.parametrize(
    "harness",
    [
        "PluginTestHarness",
        "CustomScaffoldTestHarness",
        "ValidatorTestHarness",
        "InfraProviderTestHarness",
        "CatalogAdapterTestHarness",
    ],
)
def test_documented_role_harnesses_exist_and_subclass_base(harness: str) -> None:
    """Every role harness the docs promise exists and subclasses PluginTestHarness."""
    import fluid_sdk.testing as t

    cls = getattr(t, harness, None)
    assert cls is not None, f"fluid_sdk.testing.{harness} is documented but missing"
    assert issubclass(cls, t.PluginTestHarness)


# ── CLI command-example honesty ───────────────────────────────────────
# The import-only checks above are blind to CLI-command-example drift (a doc could
# show a `fluid <cmd>` that doesn't exist, or output a command can't produce). These
# two close that gap as far as is feasible for a CLI-less SDK CI.
#
# Borrowed: the argparse-introspection pattern (assert documented commands exist in
# the parser tree). We DIVERGE from clitest / cram / markdown-clitest (which run the
# binary) because this zero-dependency SDK does not — and should not — install the
# `data-product-forge` CLI in its test env.


def test_documented_cli_commands_exist() -> None:
    """Every `fluid <command>` shown in a doc code fence is a real CLI command.

    Runs only when the CLI happens to be importable (e.g. a dev env with both
    installed); skips with a clear reason in SDK-only CI — "validate where feasible".
    """
    cli_cmds = _cli_top_level_commands()
    if cli_cmds is None:
        pytest.skip("data-product-forge CLI not installed; CLI-command-existence check skipped")
    bad = sorted(
        f"{doc}: `fluid {cmd}`" for doc, cmd in _documented_fluid_commands() if cmd not in cli_cmds
    )
    assert not bad, "Docs reference `fluid` commands that do not exist:\n  " + "\n  ".join(bad)


def test_fluid_plugins_output_advertises_no_impossible_columns() -> None:
    """A documented `fluid plugins` output block must not claim columns the command
    cannot emit (VERSION / AUTHOR / DESCRIPTION).

    Feasible WITHOUT the CLI installed, so it runs in SDK-only CI too — it pins the
    exact output-drift class (a NAME/ROLE/VERSION/AUTHOR/DESCRIPTION table) that the
    import-only gate is structurally blind to. A real header row carries several of
    these together, so we require >= 2 in one block to avoid flagging incidental prose.
    """
    offenders = []
    for doc in _docs():
        text = doc.read_text(encoding="utf-8")
        if "fluid plugins" not in text:
            continue
        rel = str(doc.relative_to(_REPO_ROOT))
        for block in _fenced_blocks(text):
            present = [c for c in _IMPOSSIBLE_PLUGINS_COLUMNS if c in block]
            if len(present) >= 2:
                offenders.append(f"{rel}: a `fluid plugins` block advertises {present} columns")
    assert not offenders, (
        "`fluid plugins` reads entry-point names + allow/block status only — it cannot "
        "print plugin version/author/description:\n  " + "\n  ".join(sorted(set(offenders)))
    )
