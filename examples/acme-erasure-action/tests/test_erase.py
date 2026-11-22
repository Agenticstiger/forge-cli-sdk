from __future__ import annotations

from acme_maintenance import EraseRequested

from fluid_sdk.testing import MaintenanceActionTestHarness


class TestEraseRequested(MaintenanceActionTestHarness):
    action_class = EraseRequested
    entry_point_name = "acme-erase"
    table = "fluid.silver.orders"
    sample_options = [
        {"requests": "gdpr.requests"},
        {"requests": "gdpr.requests", "key": "user_id", "status": "done"},
    ]
    bad_options = [
        {"requests": "gdpr.requests; DROP TABLE x"},
        {"requests": "gdpr.requests", "status": "it's-a-secret-value"},
        {"requests": "gdpr.requests", "key": "id) OR (1=1"},
        {},
        {"requests": "gdpr.requests", "unknown": "xyzzy-value"},
    ]


def test_the_statement() -> None:
    (sql,) = EraseRequested().statements("fluid.silver.orders", {"requests": "gdpr.requests"})
    assert sql == (
        "DELETE FROM fluid.silver.orders WHERE customer_id IN "
        "(SELECT customer_id FROM fluid.gdpr.requests WHERE status = 'approved')"
    )
