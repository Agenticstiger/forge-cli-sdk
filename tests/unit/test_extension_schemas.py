"""Unit tests for ``fluid_sdk.iter_extension_schemas`` (extension-schema discovery)."""

from __future__ import annotations

import importlib.metadata as md

from fluid_sdk import EXTENSION_SCHEMAS_GROUP, iter_extension_schemas


class _FakeEP:
    """Minimal stand-in for importlib.metadata.EntryPoint."""

    def __init__(self, name, fn):
        self.name = name
        self._fn = fn

    def load(self):
        return self._fn


def _raise_with_secret(fluid_version=None):
    raise RuntimeError("connection failed: token=sk-live-DEADBEEF")


def test_group_name_constant() -> None:
    assert EXTENSION_SCHEMAS_GROUP == "fluid_build.extension_schemas"


def test_empty_when_no_providers(monkeypatch) -> None:
    monkeypatch.setattr(md, "entry_points", lambda *a, **k: [])
    assert iter_extension_schemas() == {}


def test_collects_provider_schemas(monkeypatch) -> None:
    good = _FakeEP(
        "customScaffold", lambda fluid_version=None: {"title": "extensions.customScaffold"}
    )
    zero_arg = _FakeEP("otherExt", lambda: {"title": "extensions.otherExt"})
    monkeypatch.setattr(md, "entry_points", lambda *a, **k: [good, zero_arg])
    out = iter_extension_schemas("0.7.4")
    assert set(out) == {"customScaffold", "otherExt"}
    assert out["customScaffold"]["title"] == "extensions.customScaffold"
    assert out["otherExt"]["title"] == "extensions.otherExt"  # zero-arg provider supported


def test_isolation_skips_broken_and_nondict(monkeypatch, caplog) -> None:
    good = _FakeEP("customScaffold", lambda fluid_version=None: {"ok": True})
    boom = _FakeEP("brokenExt", _raise_with_secret)
    nondict = _FakeEP("weirdExt", lambda fluid_version=None: "not-a-dict")
    monkeypatch.setattr(md, "entry_points", lambda *a, **k: [good, boom, nondict])

    out = iter_extension_schemas()
    # The broken + non-dict providers are skipped; the good one survives.
    assert set(out) == {"customScaffold"}
    # The secret in the raising provider's message must never reach the logs.
    assert "sk-live-DEADBEEF" not in caplog.text


def test_discovery_failure_fails_open(monkeypatch) -> None:
    def boom(*a, **k):
        raise RuntimeError("metadata backend exploded")

    monkeypatch.setattr(md, "entry_points", boom)
    assert iter_extension_schemas() == {}
