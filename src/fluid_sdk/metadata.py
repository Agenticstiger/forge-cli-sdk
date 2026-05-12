"""Plugin metadata — surfaces to ``fluid plugins list``, marketplace UIs, and tooling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .version import SDK_VERSION


@dataclass
class PluginMetadata:
    """Descriptive metadata for a plugin.

    Plugin authors override ``BasePlugin.get_plugin_info()`` to supply rich
    metadata; the FLUID CLI surfaces it in ``fluid plugins list``,
    marketplace listings, generated docs, and audit trails.

    All fields have sensible defaults so plugins can adopt incrementally.
    """

    name: str  # canonical name, lowercase, identifier-shaped
    role: str = "plugin"  # see fluid_sdk.roles.* for canonical values
    display_name: str = ""
    description: str = ""
    version: str = "0.0.0"
    sdk_version: str = SDK_VERSION  # SDK version the plugin was built against
    author: str = "Unknown"
    url: Optional[str] = None
    license: Optional[str] = None
    supported_platforms: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.display_name:
            self.display_name = self.name.replace("_", " ").replace("-", " ").title()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
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


__all__ = ["PluginMetadata"]
