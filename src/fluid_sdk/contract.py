"""Universal contract parser for FLUID data product contracts.

The FLUID contract schema has evolved through several versions
(0.4.0, 0.5.7, 0.7.x). :class:`ContractHelper` provides a typed,
version-agnostic view so plugins don't have to detect format variants
themselves.

Usage::

    from fluid_sdk import ContractHelper

    helper = ContractHelper(contract_dict)
    for expose in helper.exposes():
        print(expose.id, expose.platform, expose.format)

    for build in helper.builds():
        print(build.pattern, build.engine, build.sql)

This module has **zero external dependencies** beyond the Python
standard library. Plugin authors who adopt it get a stable parsing
layer; those who prefer raw dicts can continue to use them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

# ---------------------------------------------------------------------------
# ColumnSpec — single field / column definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ColumnSpec:
    """A single schema column / field definition."""

    name: str
    type: str = "string"
    required: bool = False
    nullable: bool = True
    description: Optional[str] = None
    sensitivity: Optional[str] = None
    semantic_type: Optional[str] = None
    labels: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "ColumnSpec":
        return cls(
            name=str(d.get("name", "")),
            type=str(d.get("type", "string")),
            required=bool(d.get("required", False)),
            nullable=bool(d.get("nullable", True)),
            description=d.get("description"),
            sensitivity=d.get("sensitivity"),
            semantic_type=d.get("semanticType"),
            labels=dict(d.get("labels", {})),
            tags=list(d.get("tags", [])),
            raw=dict(d),
        )


# ---------------------------------------------------------------------------
# ExposeSpec — parsed `exposes[]` entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExposeSpec:
    """A parsed representation of one ``exposes[]`` entry.

    Normalises the many binding / location shapes across contract versions
    into a single flat interface. The original dict is always available
    via :attr:`raw`.
    """

    id: str
    kind: Optional[str] = None
    title: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None

    # Routing keys (from binding)
    platform: Optional[str] = None
    format: Optional[str] = None

    # Location fields (unified from binding.location or legacy location)
    database: Optional[str] = None
    schema_name: Optional[str] = None
    table: Optional[str] = None
    bucket: Optional[str] = None
    path: Optional[str] = None
    dataset: Optional[str] = None
    project: Optional[str] = None
    region: Optional[str] = None
    topic: Optional[str] = None
    cluster: Optional[str] = None
    view: Optional[str] = None
    query: Optional[str] = None

    # Full location dict for plugin-specific fields
    location: Dict[str, Any] = field(default_factory=dict)

    # Schema
    columns: List[ColumnSpec] = field(default_factory=list)

    # Governance
    policy: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)

    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "ExposeSpec":
        expose_id = d.get("exposeId") or d.get("id") or ""
        kind = d.get("kind") or d.get("type")

        binding: Dict[str, Any] = d.get("binding") or {}
        old_location = d.get("location")

        if binding:
            platform = (binding.get("platform") or "").lower() or None
            fmt = binding.get("format")
            loc = binding.get("location") or {}
            if isinstance(loc, str):
                loc = {"path": loc}
        elif isinstance(old_location, dict):
            platform = None
            fmt = old_location.get("format")
            loc = old_location.get("properties") or old_location
        elif isinstance(old_location, str):
            platform = None
            fmt = None
            loc = {"path": old_location}
        else:
            platform = None
            fmt = None
            loc = {}

        if not isinstance(loc, dict):
            loc = {}

        # Schema extraction across versions
        schema_raw: Any = None
        contract_section = d.get("contract") or {}
        if isinstance(contract_section, dict):
            schema_raw = contract_section.get("schema")
        if not schema_raw:
            schema_raw = d.get("schema")
        if isinstance(schema_raw, dict) and "fields" in schema_raw:
            schema_raw = schema_raw["fields"]
        columns: List[ColumnSpec] = []
        if isinstance(schema_raw, list):
            columns = [ColumnSpec.from_dict(c) for c in schema_raw if isinstance(c, dict)]

        return cls(
            id=str(expose_id),
            kind=kind,
            title=d.get("title"),
            version=d.get("version"),
            description=d.get("description"),
            platform=platform,
            format=fmt,
            database=loc.get("database"),
            schema_name=loc.get("schema"),
            table=loc.get("table"),
            bucket=loc.get("bucket"),
            path=loc.get("path"),
            dataset=loc.get("dataset"),
            project=loc.get("project"),
            region=loc.get("region") or loc.get("location"),
            topic=loc.get("topic"),
            cluster=loc.get("cluster"),
            view=loc.get("view"),
            query=loc.get("query"),
            location=dict(loc),
            columns=columns,
            policy=dict(d.get("policy", {})),
            tags=list(d.get("tags", [])),
            labels=dict(d.get("labels", {})),
            raw=dict(d),
        )


# ---------------------------------------------------------------------------
# ConsumeSpec — parsed `consumes[]` entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConsumeSpec:
    """Parsed representation of a contract ``consumes[]`` entry."""

    id: str
    ref: Optional[str] = None
    path: Optional[str] = None
    format: Optional[str] = None
    schema_raw: Optional[Any] = None
    required: bool = True
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "ConsumeSpec":
        cid = d.get("exposeId") or d.get("id") or d.get("name") or ""
        loc = d.get("location")
        if isinstance(loc, dict):
            path = d.get("path") or loc.get("path")
        elif isinstance(loc, str):
            path = d.get("path") or loc
        else:
            path = d.get("path")
        return cls(
            id=str(cid),
            ref=d.get("productId") or d.get("ref"),
            path=path,
            format=d.get("format"),
            schema_raw=d.get("schema"),
            required=bool(d.get("required", True)),
            raw=dict(d),
        )


# ---------------------------------------------------------------------------
# BuildSpec — parsed `builds[]` entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BuildSpec:
    """Parsed representation of a contract ``builds[]`` entry."""

    id: str = ""
    description: Optional[str] = None
    pattern: Optional[str] = None
    engine: Optional[str] = None
    sql: Optional[str] = None
    sql_file: Optional[str] = None
    repository: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    execution: Dict[str, Any] = field(default_factory=dict)
    outputs: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any], index: int = 0) -> "BuildSpec":
        props = d.get("properties") or {}
        sql = props.get("sql")
        if not sql:
            transformation = d.get("transformation") or {}
            sql = (transformation.get("properties") or {}).get("model")
        sql_file = props.get("sql_file") or props.get("sqlFile")
        return cls(
            id=str(d.get("id") or f"build_{index}"),
            description=d.get("description"),
            pattern=d.get("pattern"),
            engine=d.get("engine") or d.get("type"),
            sql=sql,
            sql_file=sql_file,
            repository=d.get("repository"),
            properties=dict(props),
            execution=dict(d.get("execution") or {}),
            outputs=list(d.get("outputs") or []),
            tags=list(d.get("tags", [])),
            labels=dict(d.get("labels", {})),
            raw=dict(d),
        )


# ---------------------------------------------------------------------------
# ContractHelper — the version-agnostic facade
# ---------------------------------------------------------------------------


class ContractHelper:
    """Universal, read-only view over a fluid contract dict.

    All plugins can wrap their incoming contract dict in a
    :class:`ContractHelper` to get a stable, typed accessor surface that
    doesn't change as the fluid contract schema evolves.
    """

    __slots__ = ("_raw",)

    def __init__(self, contract: Mapping[str, Any]) -> None:
        self._raw: Dict[str, Any] = dict(contract)

    # ── Identity ───────────────────────────────────────────────────

    @property
    def fluid_version(self) -> Optional[str]:
        return self._raw.get("fluidVersion")

    @property
    def kind(self) -> Optional[str]:
        return self._raw.get("kind")

    @property
    def id(self) -> Optional[str]:
        # Prefer the canonical top-level ``id``; fall back to
        # ``metadata.id`` for contracts that nested it there.
        top = self._raw.get("id")
        if top:
            return top
        meta = self._raw.get("metadata") or {}
        if isinstance(meta, dict):
            return meta.get("id") or meta.get("productId")
        return None

    @property
    def name(self) -> Optional[str]:
        top = self._raw.get("name")
        if top:
            return top
        meta = self._raw.get("metadata") or {}
        if isinstance(meta, dict):
            return meta.get("name")
        return None

    @property
    def description(self) -> Optional[str]:
        top = self._raw.get("description")
        if top:
            return top
        meta = self._raw.get("metadata") or {}
        if isinstance(meta, dict):
            return meta.get("description")
        return None

    @property
    def domain(self) -> Optional[str]:
        return self._raw.get("domain")

    # ── Metadata ───────────────────────────────────────────────────

    @property
    def metadata(self) -> Dict[str, Any]:
        return dict(self._raw.get("metadata") or {})

    @property
    def owner(self) -> Dict[str, Any]:
        return dict(self.metadata.get("owner") or {})

    @property
    def layer(self) -> Optional[str]:
        return self.metadata.get("layer")

    @property
    def product_type(self) -> Optional[str]:
        """Returns 'SDP', 'ADP', or 'CDP' if set in metadata, else None."""
        return self.metadata.get("productType")

    # ── Top-level tags / labels ────────────────────────────────────

    @property
    def tags(self) -> List[str]:
        return list(self._raw.get("tags") or [])

    @property
    def labels(self) -> Dict[str, str]:
        return dict(self._raw.get("labels") or {})

    # ── Exposes / consumes / builds ────────────────────────────────

    def exposes(self) -> List[ExposeSpec]:
        raw_list = self._raw.get("exposes") or []
        return [ExposeSpec.from_dict(e) for e in raw_list if isinstance(e, dict)]

    def consumes(self) -> List[ConsumeSpec]:
        raw_list = self._raw.get("consumes") or []
        return [ConsumeSpec.from_dict(c) for c in raw_list if isinstance(c, dict)]

    def builds(self) -> List[BuildSpec]:
        """Normalises ``builds`` (array) and ``build`` (single object)."""
        builds_raw = self._raw.get("builds")
        if isinstance(builds_raw, list):
            return [
                BuildSpec.from_dict(b, i) for i, b in enumerate(builds_raw) if isinstance(b, dict)
            ]
        build_raw = self._raw.get("build")
        if isinstance(build_raw, dict):
            return [BuildSpec.from_dict(build_raw, 0)]
        return []

    def primary_build(self) -> Optional[BuildSpec]:
        bl = self.builds()
        return bl[0] if bl else None

    # ── Security / sovereignty / binding ───────────────────────────

    @property
    def security(self) -> Dict[str, Any]:
        return dict(self._raw.get("security") or {})

    @property
    def access_policy(self) -> Dict[str, Any]:
        return dict(self._raw.get("accessPolicy") or {})

    @property
    def sovereignty(self) -> Dict[str, Any]:
        return dict(self._raw.get("sovereignty") or {})

    @property
    def binding(self) -> Dict[str, Any]:
        return dict(self._raw.get("binding") or {})

    @property
    def binding_location(self) -> Dict[str, Any]:
        bl = self._raw.get("binding") or {}
        loc = bl.get("location") or {}
        return dict(loc) if isinstance(loc, dict) else {}

    # ── Environments ───────────────────────────────────────────────

    @property
    def environments(self) -> Dict[str, Any]:
        env = self._raw.get("environments") or {}
        return dict(env) if isinstance(env, dict) else {}

    def environment_names(self) -> List[str]:
        return sorted(self.environments.keys())

    # ── Extensions (vendor-namespace bag) ──────────────────────────

    @property
    def extensions(self) -> Dict[str, Any]:
        """The top-level ``extensions`` block (introduced for plugin config).

        Plugins look up their config sub-key here — e.g. a custom-scaffold
        engine reads ``contract.extensions.customScaffold``.
        """
        return dict(self._raw.get("extensions") or {})

    def extension(self, key: str) -> Dict[str, Any]:
        """Convenience: return ``extensions[key]`` or an empty dict."""
        ext = self.extensions.get(key)
        return dict(ext) if isinstance(ext, dict) else {}

    # ── Raw access ─────────────────────────────────────────────────

    @property
    def raw(self) -> Dict[str, Any]:
        return self._raw

    def get(self, key: str, default: Any = None) -> Any:
        return self._raw.get(key, default)

    def __contains__(self, key: str) -> bool:
        return key in self._raw

    def __repr__(self) -> str:
        return (
            f"ContractHelper(id={self.id!r}, kind={self.kind!r}, "
            f"version={self.fluid_version!r})"
        )


__all__ = [
    "ContractHelper",
    "ColumnSpec",
    "ExposeSpec",
    "ConsumeSpec",
    "BuildSpec",
]
