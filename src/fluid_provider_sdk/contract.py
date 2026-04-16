"""
Universal contract parser for FLUID data product contracts.

Handles all known contract format variants (0.4.0, 0.5.7, 0.7.1) and
provides typed, version-agnostic access to contract sections.

Usage::

    helper = ContractHelper(contract_dict)
    for expose in helper.exposes():
        print(expose.id, expose.platform, expose.format)
    for build in helper.builds():
        print(build.pattern, build.engine, build.sql)

This module is part of the FLUID Provider SDK and has **zero external
dependencies**.  Providers that adopt it get a stable, tested parsing
layer; providers that prefer raw dicts can continue to use them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

# ── Column / field spec ────────────────────────────────────────────


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
    def from_dict(cls, d: Dict[str, Any]) -> "ColumnSpec":
        return cls(
            name=d.get("name", ""),
            type=d.get("type", "string"),
            required=d.get("required", False),
            nullable=d.get("nullable", True),
            description=d.get("description"),
            sensitivity=d.get("sensitivity"),
            semantic_type=d.get("semanticType"),
            labels=dict(d.get("labels", {})),
            tags=list(d.get("tags", [])),
            raw=dict(d),
        )


# ── Expose spec ────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExposeSpec:
    """Parsed representation of a contract ``exposes[]`` entry.

    Normalises the many binding / location structures across providers
    into a single flat interface.  The original dict is always available
    via ``raw``.
    """

    id: str
    kind: Optional[str] = None  # "table", "view", "topic", …
    title: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None

    # Routing keys (from binding)
    platform: Optional[str] = None  # "gcp", "aws", "snowflake", "local"
    format: Optional[str] = None  # "bigquery_table", "snowflake_table", …

    # Location fields (unified from binding.location or legacy location)
    database: Optional[str] = None
    schema_name: Optional[str] = None
    table: Optional[str] = None
    bucket: Optional[str] = None
    path: Optional[str] = None
    dataset: Optional[str] = None  # GCP BigQuery
    project: Optional[str] = None  # GCP project override
    region: Optional[str] = None
    topic: Optional[str] = None  # GCP Pub/Sub
    cluster: Optional[str] = None  # AWS Redshift
    view: Optional[str] = None
    query: Optional[str] = None

    # Full location dict for provider-specific fields
    location: Dict[str, Any] = field(default_factory=dict)

    # Schema
    columns: List[ColumnSpec] = field(default_factory=list)

    # Governance
    policy: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)

    # Original dict
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExposeSpec":
        """Build an ``ExposeSpec`` from a raw expose dict.

        Handles both 0.4.0 (``location``-based) and 0.5.7+ (``binding``-based)
        formats transparently.
        """
        # -- ID (0.5.7: exposeId, 0.4.0: id) --
        expose_id = d.get("exposeId") or d.get("id") or ""

        # -- kind / type --
        kind = d.get("kind") or d.get("type")

        # -- Binding resolution (0.5.7 vs 0.4.0) --
        binding: Dict[str, Any] = d.get("binding") or {}
        old_location = d.get("location")

        if binding:
            platform = (binding.get("platform") or "").lower() or None
            fmt = binding.get("format")
            loc = binding.get("location") or {}
            if isinstance(loc, str):
                loc = {"path": loc}
        elif old_location and isinstance(old_location, dict):
            # 0.4.0 format: location.format / location.properties
            platform = None
            fmt = old_location.get("format")
            loc = old_location.get("properties") or old_location
        elif old_location and isinstance(old_location, str):
            platform = None
            fmt = None
            loc = {"path": old_location}
        else:
            platform = None
            fmt = None
            loc = {}

        if not isinstance(loc, dict):
            loc = {}

        # -- Schema (0.5.7: expose.contract.schema, 0.4.0: expose.schema) --
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
            columns = [
                ColumnSpec.from_dict(c) for c in schema_raw if isinstance(c, dict)
            ]

        return cls(
            id=expose_id,
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
            region=loc.get("region")
            or loc.get("location"),  # GCP uses "location" for region
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


# ── Consume spec ───────────────────────────────────────────────────


@dataclass(frozen=True)
class ConsumeSpec:
    """Parsed representation of a contract ``consumes[]`` entry."""

    id: str
    ref: Optional[str] = None  # productId / ref
    path: Optional[str] = None
    format: Optional[str] = None
    schema_raw: Optional[Any] = None
    required: bool = True
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ConsumeSpec":
        cid = d.get("exposeId") or d.get("id") or d.get("name") or ""
        loc = d.get("location")
        if isinstance(loc, dict):
            path = d.get("path") or loc.get("path")
        elif isinstance(loc, str):
            path = d.get("path") or loc
        else:
            path = d.get("path")
        return cls(
            id=cid,
            ref=d.get("productId") or d.get("ref"),
            path=path,
            format=d.get("format"),
            schema_raw=d.get("schema"),
            required=d.get("required", True),
            raw=dict(d),
        )


# ── Build spec ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class BuildSpec:
    """Parsed representation of a contract ``builds[]`` entry."""

    id: str = ""
    description: Optional[str] = None
    pattern: Optional[str] = None  # "declarative", "embedded-logic", "hybrid-reference"
    engine: Optional[str] = None  # "sql", "dbt", "python", "dataform", "spark"
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
    def from_dict(cls, d: Dict[str, Any], index: int = 0) -> "BuildSpec":
        props = d.get("properties") or {}
        # SQL can be in properties.sql or transformation.properties.model (0.4.0)
        sql = props.get("sql")
        if not sql:
            transformation = d.get("transformation") or {}
            sql = (transformation.get("properties") or {}).get("model")
        sql_file = props.get("sql_file") or props.get("sqlFile")
        return cls(
            id=d.get("id") or f"build_{index}",
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


# ── Contract helper ────────────────────────────────────────────────


class ContractHelper:
    """Universal contract parser.

    Wraps a raw contract ``Mapping`` and provides **typed, version-agnostic**
    accessors for every major section.  All providers can benefit from this
    without changing their ``plan(contract)`` signature — just wrap the
    incoming dict::

        def plan(self, contract):
            c = ContractHelper(contract)
            for expose in c.exposes():
                ...
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
        return self._raw.get("id")

    @property
    def name(self) -> Optional[str]:
        return self._raw.get("name")

    @property
    def description(self) -> Optional[str]:
        return self._raw.get("description")

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

    # ── Top-level tags / labels ────────────────────────────────────

    @property
    def tags(self) -> List[str]:
        return list(self._raw.get("tags") or [])

    @property
    def labels(self) -> Dict[str, str]:
        return dict(self._raw.get("labels") or {})

    # ── Exposes ────────────────────────────────────────────────────

    def exposes(self) -> List[ExposeSpec]:
        """Return parsed ``ExposeSpec`` objects for every ``exposes[]`` entry."""
        raw_list = self._raw.get("exposes") or []
        return [ExposeSpec.from_dict(e) for e in raw_list if isinstance(e, dict)]

    # ── Consumes ───────────────────────────────────────────────────

    def consumes(self) -> List[ConsumeSpec]:
        raw_list = self._raw.get("consumes") or []
        return [ConsumeSpec.from_dict(c) for c in raw_list if isinstance(c, dict)]

    # ── Builds ─────────────────────────────────────────────────────

    def builds(self) -> List[BuildSpec]:
        """Normalises ``builds`` (array) and ``build`` (single object) formats."""
        builds_raw = self._raw.get("builds")
        if isinstance(builds_raw, list):
            return [
                BuildSpec.from_dict(b, i)
                for i, b in enumerate(builds_raw)
                if isinstance(b, dict)
            ]
        build_raw = self._raw.get("build")
        if isinstance(build_raw, dict):
            return [BuildSpec.from_dict(build_raw, 0)]
        return []

    def primary_build(self) -> Optional[BuildSpec]:
        """Return the first build, or ``None``."""
        bl = self.builds()
        return bl[0] if bl else None

    # ── Security / access control ──────────────────────────────────

    @property
    def security(self) -> Dict[str, Any]:
        """``contract.security`` (Snowflake-style grants, RLS)."""
        return dict(self._raw.get("security") or {})

    @property
    def access_policy(self) -> Dict[str, Any]:
        """``contract.accessPolicy`` (0.7.1 root-level IAM grants)."""
        return dict(self._raw.get("accessPolicy") or {})

    @property
    def sovereignty(self) -> Dict[str, Any]:
        """``contract.sovereignty`` (0.7.1 data residency controls)."""
        return dict(self._raw.get("sovereignty") or {})

    # ── Top-level binding (Snowflake uses this) ────────────────────

    @property
    def binding(self) -> Dict[str, Any]:
        """``contract.binding`` — top-level binding used by Snowflake for infra."""
        return dict(self._raw.get("binding") or {})

    @property
    def binding_location(self) -> Dict[str, Any]:
        """``contract.binding.location`` — shortcut."""
        bl = self._raw.get("binding") or {}
        loc = bl.get("location") or {}
        return dict(loc) if isinstance(loc, dict) else {}

    # ── Snowflake extensions ───────────────────────────────────────

    @property
    def views(self) -> List[Dict[str, Any]]:
        return list(self._raw.get("views") or [])

    @property
    def streams(self) -> List[Dict[str, Any]]:
        return list(self._raw.get("streams") or [])

    # ── Raw access ─────────────────────────────────────────────────

    @property
    def raw(self) -> Dict[str, Any]:
        """The original contract dict."""
        return self._raw

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-like access for provider-specific keys."""
        return self._raw.get(key, default)

    def __contains__(self, key: str) -> bool:
        return key in self._raw

    def __repr__(self) -> str:
        return f"ContractHelper(id={self.id!r}, kind={self.kind!r}, version={self.fluid_version!r})"
