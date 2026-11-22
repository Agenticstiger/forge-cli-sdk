"""The route kind forge-cli reads: what the DAG imports and the arguments it passes.

This module runs where forge-cli does (``fluid validate``, ``fluid generate schedule``). The
Airflow notifier it names lives in :mod:`acme_alerts.notifiers`, which only Airflow imports.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from fluid_sdk import Alert, AlertNotifier, AlertRoute

_CHANNEL = re.compile(r"[a-z0-9][a-z0-9_-]{0,79}\Z")


class ChatNotifier(AlertNotifier):
    """``kind: acme-chat`` — post the alert to a chat channel through an Airflow connection."""

    notifier = "acme_alerts.notifiers:ChatNotifier"
    requirements = ("acme-chat-alerts>=0.1",)
    # A route may leave the connection out: the notifier then uses its default.
    requires_connection = False
    default_connection = "acme_chat_default"

    def check(self, route: AlertRoute) -> Sequence[str]:
        channel = route.options.get("channel", "ops")
        if not isinstance(channel, str) or not _CHANNEL.match(channel):
            return ["options.channel must be a channel name (lower case letters, digits, '-', '_')"]
        unknown = sorted(set(route.options) - {"channel"})
        if unknown:
            return [f"options reads only 'channel', not {', '.join(unknown)}"]
        return []

    def kwargs(self, route: AlertRoute, alert: Alert) -> Mapping[str, Any]:
        return {
            "message": f"[{alert.severity}] {alert.title}\n{alert.text}",
            "channel": route.options.get("channel", "ops"),
            "chat_conn_id": route.connection or self.default_connection,
            "dedup_key": alert.dedup_key,
        }
