"""Sample contract fixtures used by the conformance test harnesses.

These are minimal — enough to exercise basic plugin behaviour without
making assumptions about platform / provider specifics. Plugin authors
are encouraged to provide their own ``sample_contracts`` covering domain-
specific shapes.
"""

from __future__ import annotations

from typing import Any, Dict, List

# Minimal contract — almost no fields. Used to validate that plugins
# don't crash on sparse input.
MINIMAL_CONTRACT: Dict[str, Any] = {
    "fluidVersion": "0.7.4",
    "kind": "DataProduct",
    "id": "minimal-product",
    "name": "Minimal Product",
    "description": "Sparse contract used in conformance tests.",
    "metadata": {
        "owner": {"team": "test", "email": "test@example.com"},
    },
    "exposes": [],
    "consumes": [],
    "builds": [],
}


# Slightly richer — exercises exposes / builds / environments shapes.
LOCAL_CONTRACT: Dict[str, Any] = {
    "fluidVersion": "0.7.4",
    "kind": "DataProduct",
    "id": "local-product",
    "name": "Local Product",
    "description": "A local-platform fixture for conformance tests.",
    "domain": "example",
    "metadata": {
        "owner": {"team": "platform", "email": "platform@example.com"},
        "productType": "SDP",
        "layer": "bronze",
        "classification": "internal",
        "labels": {
            "repository.project": "example/repo",
            "repository.name": "local-product",
        },
    },
    "tags": ["test", "local"],
    "labels": {"team": "platform"},
    "exposes": [
        {
            "exposeId": "events",
            "kind": "table",
            "binding": {
                "platform": "local",
                "format": "parquet",
                "location": {"path": "./data/events"},
            },
            "contract": {
                "schema": [
                    {"name": "id", "type": "string", "required": True},
                    {"name": "ts", "type": "timestamp", "required": True},
                ],
            },
            "tags": ["pii"],
            "labels": {"sensitive": "true"},
        }
    ],
    "consumes": [],
    "builds": [
        {
            "id": "build_events",
            "pattern": "embedded-logic",
            "engine": "sql",
            "properties": {"sql": "SELECT id, ts FROM source"},
            "outputs": ["events"],
        }
    ],
    "environments": {
        "dev": {
            "metadata": {
                "labels": {"cloud.accountId": "000000000000"},
            },
        },
    },
}


def all_sample_contracts() -> List[Dict[str, Any]]:
    """Return every built-in sample contract."""
    return [MINIMAL_CONTRACT, LOCAL_CONTRACT]
