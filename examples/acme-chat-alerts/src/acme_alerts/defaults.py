"""The routes this organisation adds to every product's DAGs."""

from __future__ import annotations

from typing import Any, Dict, List

from fluid_sdk import alert_route


def default_routes() -> List[Dict[str, Any]]:
    """Written as a contract writes them; ``alert_route`` checks each against forge-cli's shape."""
    return [
        alert_route(
            "org-oncall",
            "acme-chat",
            connection="acme_chat_oncall",
            events=["failure"],
            severity="critical",
            options={"channel": "ops-oncall"},
        )
    ]
