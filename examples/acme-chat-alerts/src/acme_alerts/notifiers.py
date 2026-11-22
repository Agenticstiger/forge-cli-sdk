"""The Airflow notifier the generated DAGs import. Only Airflow imports this module.

It reads the chat webhook URL from the Airflow connection named by ``chat_conn_id`` (the
connection's host), so the URL is never in a contract or a DAG, and posts the message with the
standard library.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

try:  # Airflow 3
    from airflow.sdk.bases.notifier import BaseNotifier
except ImportError:  # pragma: no cover - depends on the Airflow major
    try:  # Airflow 2
        from airflow.notifications.basenotifier import BaseNotifier
    except ImportError:  # no Airflow here: importable, but not usable as a notifier
        BaseNotifier = object  # type: ignore[assignment,misc]


class ChatNotifier(BaseNotifier):  # type: ignore[misc,valid-type]
    template_fields = ("message", "channel")

    def __init__(
        self, message: str, channel: str, chat_conn_id: str, dedup_key: str = "", **kwargs: Any
    ) -> None:
        if BaseNotifier is not object:
            super().__init__(**kwargs)
        self.message = message
        self.channel = channel
        self.chat_conn_id = chat_conn_id
        self.dedup_key = dedup_key

    def notify(self, context: Any) -> None:  # pragma: no cover - needs Airflow and a webhook
        from airflow.hooks.base import BaseHook

        url = BaseHook.get_connection(self.chat_conn_id).host
        body = json.dumps(
            {"channel": self.channel, "text": self.message, "key": self.dedup_key}
        ).encode()
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(request, timeout=10).close()  # noqa: S310 - the connection's URL
