# fluid_provider_sdk — Zero-dependency SDK for FLUID data product providers.
#
# This package provides the BaseProvider ABC, result types, and metadata
# classes that third-party provider authors need.  It has NO external
# dependencies beyond the Python 3.9+ standard library.
"""
FLUID Provider SDK
==================

Public API::

    from fluid_provider_sdk import (
        BaseProvider,
        ApplyResult,
        PlanAction,
        ProviderError,
        ProviderInternalError,
        ProviderMetadata,
        ProviderCapabilities,
        ProviderAction,
        ProviderHookSpec,
        CostEstimate,
        ContractHelper,
        ExposeSpec,
        ConsumeSpec,
        BuildSpec,
        ColumnSpec,
        validate_actions,
        invoke_hook,
        has_hook,
        SDK_VERSION,
    )
"""

from __future__ import annotations

from .actions import ProviderAction, validate_actions
from .base import BaseProvider
from .capabilities import ProviderCapabilities
from .contract import (
    BuildSpec,
    ColumnSpec,
    ConsumeSpec,
    ContractHelper,
    ExposeSpec,
)
from .hooks import CostEstimate, ProviderHookSpec, has_hook, invoke_hook
from .metadata import ProviderMetadata
from .types import ApplyResult, PlanAction, ProviderError, ProviderInternalError
from .version import SDK_VERSION

__all__ = [
    "BaseProvider",
    "ApplyResult",
    "PlanAction",
    "ProviderError",
    "ProviderInternalError",
    "ProviderMetadata",
    "ProviderCapabilities",
    "ProviderAction",
    "ProviderHookSpec",
    "CostEstimate",
    "ContractHelper",
    "ExposeSpec",
    "ConsumeSpec",
    "BuildSpec",
    "ColumnSpec",
    "validate_actions",
    "invoke_hook",
    "has_hook",
    "SDK_VERSION",
]

__version__ = SDK_VERSION
