# fluid_provider_sdk/metadata.py
"""Provider metadata — exposed to CLI, marketplace, and registry UIs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .version import SDK_VERSION


@dataclass
class ProviderMetadata:
    """Metadata exposed to ``fluid providers``, the marketplace, and tooling.

    Provider authors override ``BaseProvider.get_provider_info()`` to supply
    rich metadata.  All fields have sensible defaults so providers can adopt
    incrementally.
    """

    name: str  # canonical name, e.g. "databricks"
    display_name: str = ""  # human-friendly, e.g. "Databricks"
    description: str = ""  # one-line summary
    version: str = "0.0.0"  # provider package version
    sdk_version: str = SDK_VERSION  # SDK version it was built against
    author: str = "Unknown"
    url: Optional[str] = None  # project homepage
    license: Optional[str] = None  # SPDX id, e.g. "Apache-2.0"
    supported_platforms: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.display_name:
            self.display_name = self.name.replace("_", " ").title()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "sdk_version": self.sdk_version,
            "author": self.author,
            "url": self.url,
            "license": self.license,
            "supported_platforms": self.supported_platforms,
            "tags": self.tags,
        }
