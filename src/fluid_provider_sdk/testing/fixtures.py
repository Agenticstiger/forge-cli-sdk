"""
Sample contract fixtures for provider testing.

Each fixture represents a realistic FLUID contract in a common format.
Providers can use these directly or as a starting point for custom
test data.

Usage::

    from fluid_provider_sdk.testing import LOCAL_CONTRACT, GCP_CONTRACT

    class TestMyProvider(ProviderTestHarness):
        sample_contracts = [LOCAL_CONTRACT]
"""

from __future__ import annotations

from typing import Any, Dict, List

# ── Local / DuckDB ─────────────────────────────────────────────────

LOCAL_CONTRACT: Dict[str, Any] = {
    "fluidVersion": "0.7.1",
    "kind": "DataProduct",
    "id": "test.local_customer_360",
    "name": "Customer 360 (Local Test)",
    "description": "Customer analytics - local execution for testing",
    "domain": "customer-analytics",
    "metadata": {
        "layer": "Gold",
        "owner": {"team": "data-platform", "email": "dp@example.com"},
    },
    "tags": ["analytics", "local"],
    "consumes": [
        {
            "id": "customers",
            "path": "sample_data/customers.csv",
            "format": "csv",
        },
        {
            "id": "transactions",
            "path": "sample_data/transactions.csv",
            "format": "csv",
        },
    ],
    "builds": [
        {
            "id": "customer_360_analysis",
            "pattern": "embedded-logic",
            "engine": "sql",
            "properties": {
                "sql": (
                    "SELECT c.customer_id, c.name, "
                    "COUNT(t.id) AS total_txns, "
                    "SUM(t.amount) AS total_spend "
                    "FROM customers c "
                    "LEFT JOIN transactions t ON c.customer_id = t.customer_id "
                    "GROUP BY c.customer_id, c.name"
                ),
                "parameters": {
                    "inputs": [
                        {"name": "customers"},
                        {"name": "transactions"},
                    ]
                },
            },
        }
    ],
    "exposes": [
        {
            "exposeId": "customer_profiles",
            "kind": "table",
            "binding": {
                "platform": "local",
                "format": "csv",
                "location": {"path": "runtime/out/customer_profiles.csv"},
            },
            "contract": {
                "schema": [
                    {"name": "customer_id", "type": "integer", "required": True},
                    {"name": "name", "type": "string"},
                    {"name": "total_txns", "type": "integer"},
                    {"name": "total_spend", "type": "numeric"},
                ]
            },
        }
    ],
}


# ── GCP / BigQuery ─────────────────────────────────────────────────

GCP_CONTRACT: Dict[str, Any] = {
    "fluidVersion": "0.7.1",
    "kind": "DataProduct",
    "id": "finance.bitcoin_prices_gcp",
    "name": "Bitcoin Prices (GCP)",
    "description": "Real-time Bitcoin price data on BigQuery",
    "domain": "finance",
    "metadata": {
        "layer": "Gold",
        "owner": {"team": "data-engineering", "email": "de@example.com"},
    },
    "tags": ["crypto", "real-time"],
    "labels": {"cost_center": "CC-123"},
    "builds": [
        {
            "id": "ingest_btc",
            "pattern": "hybrid-reference",
            "engine": "python",
            "repository": "./runtime",
            "properties": {"model": "ingest"},
        }
    ],
    "exposes": [
        {
            "exposeId": "bitcoin_prices_table",
            "kind": "table",
            "title": "Bitcoin Prices",
            "binding": {
                "platform": "gcp",
                "format": "bigquery_table",
                "location": {
                    "project": "my-project",
                    "dataset": "crypto_data",
                    "table": "bitcoin_prices",
                    "region": "EU",
                },
            },
            "policy": {"classification": "Internal", "authn": "iam"},
            "tags": ["financial-data"],
            "labels": {"sensitivity": "internal"},
            "contract": {
                "schema": [
                    {"name": "price_usd", "type": "numeric", "required": True},
                    {"name": "price_eur", "type": "numeric"},
                    {"name": "market_cap_usd", "type": "numeric"},
                    {
                        "name": "ingestion_timestamp",
                        "type": "timestamp",
                        "required": True,
                    },
                ]
            },
        }
    ],
}


# ── AWS / Athena ───────────────────────────────────────────────────

AWS_CONTRACT: Dict[str, Any] = {
    "fluidVersion": "0.7.1",
    "kind": "DataProduct",
    "id": "finance.bitcoin_prices_aws",
    "name": "Bitcoin Prices (AWS)",
    "description": "Real-time Bitcoin price data on Athena/Glue",
    "domain": "finance",
    "metadata": {
        "layer": "Gold",
        "owner": {"team": "data-engineering"},
        "policies": {
            "retention_days": 365,
        },
    },
    "builds": [
        {
            "id": "ingest_btc",
            "pattern": "hybrid-reference",
            "engine": "python",
            "repository": "./runtime",
            "properties": {"model": "ingest"},
        }
    ],
    "exposes": [
        {
            "exposeId": "bitcoin_prices_table",
            "kind": "table",
            "binding": {
                "platform": "aws",
                "format": "parquet",
                "location": {
                    "database": "crypto_db",
                    "table": "bitcoin_prices",
                    "bucket": "my-data-bucket",
                    "path": "crypto/bitcoin_prices/",
                },
            },
            "contract": {
                "schema": [
                    {"name": "price_usd", "type": "numeric", "required": True},
                    {"name": "price_eur", "type": "numeric"},
                    {
                        "name": "ingestion_timestamp",
                        "type": "timestamp",
                        "required": True,
                    },
                ]
            },
        }
    ],
}


# ── Snowflake ──────────────────────────────────────────────────────

SNOWFLAKE_CONTRACT: Dict[str, Any] = {
    "fluidVersion": "0.7.1",
    "kind": "DataProduct",
    "id": "finance.bitcoin_prices_sf",
    "name": "Bitcoin Prices (Snowflake)",
    "description": "Real-time Bitcoin price data on Snowflake",
    "domain": "finance",
    "metadata": {
        "layer": "Gold",
        "owner": {"team": "data-engineering"},
    },
    "binding": {
        "location": {"database": "PROD_DB", "schema": "FINANCE"},
    },
    "security": {
        "access_control": {
            "grants": [
                {"role": "ANALYST", "privilege": "SELECT", "object_type": "TABLE"},
            ]
        },
    },
    "builds": [
        {
            "id": "ingest_btc",
            "engine": "python",
            "properties": {"model": "ingest"},
        }
    ],
    "exposes": [
        {
            "exposeId": "bitcoin_prices",
            "kind": "table",
            "binding": {
                "format": "snowflake_table",
                "location": {
                    "database": "PROD_DB",
                    "schema": "FINANCE",
                    "table": "BITCOIN_PRICES",
                },
            },
            "contract": {
                "schema": [
                    {"name": "PRICE_USD", "type": "NUMERIC", "required": True},
                    {"name": "PRICE_EUR", "type": "NUMERIC"},
                    {"name": "INGESTION_TS", "type": "TIMESTAMP_NTZ", "required": True},
                ]
            },
        }
    ],
}


# ── Convenience list ───────────────────────────────────────────────

SAMPLE_CONTRACTS: List[Dict[str, Any]] = [
    LOCAL_CONTRACT,
    GCP_CONTRACT,
    AWS_CONTRACT,
    SNOWFLAKE_CONTRACT,
]
