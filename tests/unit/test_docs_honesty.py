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


def _docs() -> list:
    files = []
    for pattern in _DOC_GLOBS:
        files.extend(_REPO_ROOT.glob(pattern))
    return sorted(f for f in files if f.is_file())


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
